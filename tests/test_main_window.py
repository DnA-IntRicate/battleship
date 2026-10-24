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


def test_disconnect_mid_game_shows_reason():
    window = make_window(FakePort("OK", f"BOARD:P1:{FLEET}:{EMPTY}", "NACK:BADSTATE"))
    window.connect_button.click()

    window.disconnect_button.click()

    assert window.connected
    assert window.status.text() == "That is not allowed at this point in the game."
    assert window.status.property("error")


def test_disconnect():
    port = FakePort("OK", "NACK:NOGAME", "OK")
    window = make_window(port)
    window.connect_button.click()

    window.disconnect_button.click()

    assert not window.connected
    assert port.closed
    assert window.status.text() == "Disconnected."
    assert window.connect_button.isEnabled()
