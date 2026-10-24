import os

import pytest

# Draw widgets in memory, so the tests also run on machines without a screen (CI).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from test_worker import FakePort  # noqa: E402

from battleship.client.gui.main_window import MainWindow  # noqa: E402
from battleship.client.gui.worker import SerialWorker  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

EMPTY = "." * 100
FLEET = "CCCCC" + "." * 95


def make_window(port: FakePort) -> MainWindow:
    """A window whose worker uses `port` and runs on the same thread (replies are instant)."""
    window = MainWindow(SerialWorker(open_port=lambda _name: port), threaded=False)
    window.port_box.clear()
    window.port_box.addItem("COM10 – test port", "COM10")

    return window


def test_connect_with_no_game():
    window = make_window(FakePort("OK", "NACK:NOGAME"))

    window.connect_button.click()

    assert window.connected
    assert window.status.text() == "Connected. No game in progress."
    assert not window.connect_button.isEnabled()
    assert window.disconnect_button.isEnabled()


def test_connect_draws_board_from_state():
    window = make_window(FakePort("OK", f"BOARD:P1:{FLEET}:{EMPTY}"))

    window.connect_button.click()

    assert window.board is not None
    assert window.own_view._cells[0].text() == "C"


def test_connect_failure_is_shown_as_error():
    window = make_window(FakePort())  # never replies

    window.connect_button.click()

    assert not window.connected
    assert window.status.text().startswith("Could not connect")
    assert window.status.property("error")
    assert window.connect_button.isEnabled()


def test_connect_without_port():
    window = make_window(FakePort())
    window.port_box.clear()

    window.connect_button.click()

    assert window.status.text() == "Choose a serial port first."


def test_disconnect_disabled_mid_game():
    window = make_window(FakePort("OK", f"BOARD:P1:{FLEET}:{EMPTY}", "NACK:BADSTATE"))
    window.connect_button.click()

    assert not window.disconnect_button.isEnabled()
    assert window.disconnect_button.toolTip() == "Resign the game first."

    # The server still decides: if the request were sent anyway, its reason is shown.
    window.disconnect_from_board()
    assert window.connected
    assert window.status.text() == "That is not allowed at this point in the game."
    assert window.status.property("error")


def test_new_game():
    port = FakePort("OK", "NACK:NOGAME", "OK:PLACE", f"BOARD:P1:{EMPTY}:{EMPTY}")
    window = make_window(port)
    window.connect_button.click()
    assert window.new_button.isEnabled()
    assert not window.resign_button.isEnabled()

    window.new_button.click()

    assert port.written[-2:] == [b"NEW\n", b"STATE:P1\n"]
    assert window.status.text() == "New game. P1, place your ships."
    assert window.in_game
    assert not window.new_button.isEnabled()
    assert window.resign_button.isEnabled()


def test_resign_asks_first(monkeypatch: pytest.MonkeyPatch):
    port = FakePort("OK", f"BOARD:P1:{FLEET}:{EMPTY}")
    window = make_window(port)
    window.connect_button.click()
    questions: list[str] = []
    monkeypatch.setattr(window, "confirm", lambda question: questions.append(question) or False)

    window.resign_button.click()

    assert questions == ["Resign the game as P1?"]
    assert port.written[-1] == b"STATE:P1\n"  # nothing sent after the refusal


def test_resign(monkeypatch: pytest.MonkeyPatch):
    port = FakePort("OK", f"BOARD:P1:{FLEET}:{EMPTY}", "OK:GAMEOVER", f"BOARD:--:{FLEET}:{EMPTY}")
    window = make_window(port)
    window.connect_button.click()
    monkeypatch.setattr(window, "confirm", lambda _question: True)

    window.resign_button.click()

    assert b"RESIGN:P1\n" in port.written
    assert window.status.text() == "P1 resigned. Game over."
    assert not window.in_game
    assert window.new_button.isEnabled()
    assert window.disconnect_button.isEnabled()


def test_handoff_hides_boards_until_next_player_takes_over():
    p2_fleet = "." * 95 + "DD..."
    port = FakePort("OK", f"BOARD:P2:{FLEET}:{EMPTY}", f"BOARD:P2:{p2_fleet}:{EMPTY}")
    window = make_window(port)

    # P1's view arrives, but it is P2's turn: P1's fleet must not be shown.
    window.connect_button.click()
    assert window.handing_off
    assert window.own_view._cells[0].text() == ""
    assert "Pass the computer to P2" in window.handoff_label.text()
    assert not window.resign_button.isEnabled()

    window.handoff_button.click()

    assert port.written[-1] == b"STATE:P2\n"
    assert window.viewer.value == "P2"
    assert not window.handing_off
    assert window.viewer_label.text() == "<b>P2's boards</b>"
    assert window.own_view._cells[95].text() == "D"


def test_game_over_shows_boards_without_handoff():
    window = make_window(FakePort("OK", f"BOARD:--:{FLEET}:{EMPTY}"))

    window.connect_button.click()

    assert not window.handing_off
    assert window.own_view._cells[0].text() == "C"


def test_disconnect():
    port = FakePort("OK", "NACK:NOGAME", "OK")
    window = make_window(port)
    window.connect_button.click()

    window.disconnect_button.click()

    assert not window.connected
    assert port.closed
    assert window.status.text() == "Disconnected."
    assert window.connect_button.isEnabled()
