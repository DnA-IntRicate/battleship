import pytest
import serial

from battleship.client.gui.worker import SerialWorker
from battleship.client.protocol import Nack, Ok, Player


class FakePort:
    """Stand-in for SerialConnection. Replies are queued in advance."""

    def __init__(self, *replies: str):
        self.written: list[bytes] = []
        self.closed = False
        self._replies = list(replies)

    @property
    def in_waiting(self) -> int:
        return 0

    def read(self, size: int, timeout: float = 0.0) -> str | None:
        return None

    def readline(self, timeout: float = 0.0) -> str | None:
        return self._replies.pop(0) if self._replies else None

    def write(self, data: bytes):
        self.written.append(data)

    def close(self):
        self.closed = True


def make_worker(port: FakePort) -> tuple[SerialWorker, list[tuple]]:
    """A worker using port, and a list that records every signal it emits."""
    worker = SerialWorker(open_port=lambda _name: port)
    signals: list[tuple] = []
    worker.finished.connect(lambda tag, reply: signals.append(("finished", tag, reply)))
    worker.failed.connect(lambda tag, message: signals.append(("failed", tag, message)))

    return worker, signals


def test_open_connects():
    port = FakePort("OK")
    worker, signals = make_worker(port)

    worker.open("COM10")

    assert signals == [("finished", "connect", Ok())]
    assert port.written == [b"\n", b"CONNECT\n"]


def test_open_reports_unreachable_board():
    port = FakePort()  # never replies
    worker, signals = make_worker(port)

    worker.open("COM10")

    assert signals[0][:2] == ("failed", "connect")
    assert port.closed


def test_open_reports_missing_port():
    def no_such_port(name: str) -> FakePort:
        raise serial.SerialException(f"could not open port {name}")

    worker = SerialWorker(open_port=no_such_port)
    signals: list[tuple] = []
    worker.failed.connect(lambda tag, message: signals.append((tag, message)))

    worker.open("COM99")

    assert signals == [("connect", "could not open port COM99")]


def test_run_reports_reply_with_its_tag():
    worker, signals = make_worker(FakePort("OK", "NACK:NOTURN"))
    worker.open("COM10")

    worker.run("fire", lambda s: s.fire(Player.P2, "A0"))

    assert signals[-1] == ("finished", "fire", Nack("NOTURN"))


@pytest.mark.parametrize("reply", [None, "GARBAGE"])
def test_run_reports_timeout_and_bad_reply(reply: str | None):
    replies = ["OK"] + ([reply] if reply else [])
    worker, signals = make_worker(FakePort(*replies))
    worker.open("COM10")

    worker.run("state", lambda s: s.state(Player.P1))

    assert signals[-1][:2] == ("failed", "state")


def test_run_before_open_fails():
    worker, signals = make_worker(FakePort())

    worker.run("new", lambda s: s.new_game())

    assert signals == [("failed", "new", "Not connected to the board.")]


def test_close_closes_port():
    port = FakePort("OK")
    worker, signals = make_worker(port)
    worker.open("COM10")

    worker.close()
    worker.run("new", lambda s: s.new_game())

    assert port.closed
    assert signals[-1] == ("failed", "new", "Not connected to the board.")
