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
    assert window.status.text() == "P1, place your ships: 5 left."
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
    assert window.status.text() == "P1 resigned. Game over. Press New Game to play again."
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


def ships_in(window: MainWindow) -> list[str]:
    box = window.ship_box
    return [box.itemData(i) for i in range(box.count())]


def test_placement_controls_shown_while_placing():
    window = make_window(FakePort("OK", f"BOARD:P1:{EMPTY}:{EMPTY}"))

    window.connect_button.click()

    assert window.placing
    assert not window.placement_bar.isHidden()
    assert ships_in(window) == ["C", "B", "R", "S", "D"]
    assert window.own_view._cells[0].isEnabled()
    assert not window.target_view._cells[0].isEnabled()


def test_click_places_selected_ship():
    port = FakePort("OK", f"BOARD:P1:{EMPTY}:{EMPTY}", "OK:PLACED", f"BOARD:P1:{FLEET}:{EMPTY}")
    window = make_window(port)
    window.connect_button.click()

    window.own_view._cells[0].click()  # A0, Carrier, horizontal by default

    assert b"PLACE:P1:C:A0:H\n" in port.written
    assert ships_in(window) == ["B", "R", "S", "D"]
    assert window.status.text() == "P1, place your ships: 4 left."


def test_place_vertical_with_chosen_ship():
    port = FakePort("OK", f"BOARD:P1:{EMPTY}:{EMPTY}", "NACK:OVERLAP")
    window = make_window(port)
    window.connect_button.click()
    window.ship_box.setCurrentIndex(4)  # Destroyer
    window.vertical.setChecked(True)

    window.own_view._cells[12].click()  # B2

    assert port.written[-1] == b"PLACE:P1:D:B2:V\n"


def test_rejected_placement_shows_reason():
    window = make_window(FakePort("OK", f"BOARD:P1:{EMPTY}:{EMPTY}", "NACK:OVERLAP"))
    window.connect_button.click()

    window.own_view._cells[0].click()

    assert window.status.text() == "That ship would overlap another ship."
    assert window.status.property("error")
    assert ships_in(window) == ["C", "B", "R", "S", "D"]


def test_complete_fleet_hands_over_to_p2():
    almost = "CCCCC" + "BBBB." + "RRR.." + "SSS.." + "." * 80  # Destroyer missing
    port = FakePort(
        "OK",
        f"BOARD:P1:{almost}:{EMPTY}",
        "OK:PLACED",
        f"BOARD:P2:{almost[:80]}DD{'.' * 18}:{EMPTY}",
    )
    window = make_window(port)
    window.connect_button.click()
    assert ships_in(window) == ["D"]

    window.own_view._cells[90].click()  # J0

    assert b"PLACE:P1:D:J0:H\n" in port.written
    assert window.handing_off
    assert window.status.text() == "P1's turn is over. Pass the computer to P2."


# A complete fleet (17 ship cells), so the window is in the firing phase.
FULL = "CCCCC....." + "BBBB......" + "RRR......." + "SSS......." + "DD........" + "." * 50
HIT_A0 = "X" + EMPTY[1:]


def firing_window(*replies: str) -> tuple[MainWindow, FakePort]:
    """A connected window where it is P1's turn to fire, then `replies`."""
    port = FakePort("OK", f"BOARD:P1:{FULL}:{EMPTY}", *replies)
    window = make_window(port)
    window.connect_button.click()

    return window, port


def test_firing_enables_only_the_shots_grid():
    window, _ = firing_window()

    assert window.firing
    assert window.placement_bar.isHidden()
    assert window.target_view._cells[0].isEnabled()
    assert not window.own_view._cells[0].isEnabled()
    assert window.status.text() == "P1, your turn: click a cell on Your shots to fire."


def test_fire_shows_result_and_hands_over():
    window, port = firing_window("OK:HIT", f"BOARD:P2:{FULL}:{HIT_A0}")

    window.target_view._cells[0].click()  # A0

    assert b"MOVE:P1:A0\n" in port.written
    assert window.handing_off
    assert "P1 fired at A0: hit." in window.handoff_label.text()
    assert window.status.text() == (
        "P1 fired at A0: hit. P1's turn is over. Pass the computer to P2."
    )


def test_next_player_is_told_the_last_shot():
    p2_own = "X" + FULL[1:]
    window, _ = firing_window("OK:HIT", f"BOARD:P2:{FULL}:{HIT_A0}", f"BOARD:P2:{p2_own}:{EMPTY}")
    window.target_view._cells[0].click()

    window.handoff_button.click()

    assert window.own_view._cells[0].text() == "✕"
    assert window.status.text() == (
        "P1 fired at A0: hit. P2, your turn: click a cell on Your shots to fire."
    )


def test_sunk_names_the_ship():
    window, _ = firing_window("OK:SUNK:D", f"BOARD:P2:{FULL}:{EMPTY}")

    window.target_view._cells[41].click()  # E1

    assert window.last_shot == "P1 fired at E1 and sank the Destroyer!"


def test_win_ends_game_and_disables_moves():
    window, _ = firing_window("WIN:P1", f"BOARD:--:{FULL}:{HIT_A0}")

    window.target_view._cells[0].click()

    assert not window.in_game
    assert not window.handing_off
    assert window.status.text() == "P1 wins! Game over. Press New Game to play again."
    assert not window.target_view._cells[1].isEnabled()
    assert not window.own_view._cells[0].isEnabled()
    assert window.new_button.isEnabled()


def test_rejected_shot_shows_reason_and_keeps_turn():
    window, _ = firing_window("NACK:OCCUPIED")

    window.target_view._cells[0].click()

    assert window.status.text() == "You have already fired at that cell."
    assert window.status.property("error")
    assert window.firing
    assert window.target_view._cells[0].isEnabled()


RESET_MESSAGE = "The board was reset, so the game was lost. Press New Game to start again."


def test_board_reboot_reconnects_and_resyncs():
    # After the reset button the board has no session: the shot gets NOSESSION.
    window, port = firing_window("NACK:NOSESSION", "OK", "NACK:NOGAME")

    window.target_view._cells[0].click()

    assert port.written[-3:] == [b"\n", b"CONNECT\n", b"STATE:P1\n"]
    assert window.connected
    assert window.status.text() == RESET_MESSAGE
    assert not window.in_game
    assert window.own_view._cells[0].text() == ""
    assert window.new_button.isEnabled()
    assert window.disconnect_button.isEnabled()


def test_game_reset_with_session_kept():
    # A game reset that keeps the session gives NOGAME instead.
    window, port = firing_window("NACK:NOGAME", "NACK:NOGAME")

    window.target_view._cells[0].click()

    assert port.written[-1] == b"STATE:P1\n"
    assert window.status.text() == RESET_MESSAGE
    assert window.new_button.isEnabled()


def test_reconnect_after_reset_can_fail():
    window, _ = firing_window("NACK:NOSESSION")  # then the board stops answering

    window.target_view._cells[0].click()

    assert not window.connected
    assert window.status.text().startswith("Could not connect")
    assert window.connect_button.isEnabled()


def test_disconnect():
    port = FakePort("OK", "NACK:NOGAME", "OK")
    window = make_window(port)
    window.connect_button.click()

    window.disconnect_button.click()

    assert not window.connected
    assert port.closed
    assert window.status.text() == "Disconnected."
    assert window.connect_button.isEnabled()
