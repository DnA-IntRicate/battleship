import threading
import time

import pytest
import serial

from battleship.client.uart import SerialConnection


class FakeSerial:
    """Stand-in for serial.Serial. Tests push device output in with feed()."""

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get("timeout") or 0.1
        self.written = bytearray()
        self.flushed = False
        self.closed = False
        self._rx = bytearray()
        self._cv = threading.Condition()
        self._fail: Exception | None = None

    # Test controls
    def feed(self, data: bytes):
        with self._cv:
            self._rx.extend(data)
            self._cv.notify_all()

    def fail(self, exc: Exception):
        with self._cv:
            self._fail = exc
            self._cv.notify_all()

    # serial.Serial surface used by SerialConnection
    @property
    def in_waiting(self) -> int:
        with self._cv:
            return len(self._rx)

    def read(self, size: int = 1) -> bytes:
        with self._cv:
            self._cv.wait_for(lambda: self._rx or self._fail, self.timeout)
            if self._fail:
                raise self._fail

            data = bytes(self._rx[:size])
            del self._rx[:size]

            return data

    def write(self, data: bytes):
        self.written.extend(data)

    def flush(self):
        self.flushed = True

    def reset_input_buffer(self):
        with self._cv:
            self._rx.clear()

    def close(self):
        self.closed = True


def wait_until(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True

        time.sleep(0.005)

    return False


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setattr(serial, "Serial", FakeSerial)
    c = SerialConnection()
    yield c

    c.close()


@pytest.fixture
def fake(conn) -> FakeSerial:
    return conn._conn


# ---- Non-blocking behavour ------------------------------------------------

def test_read_methods_return_none_when_empty(conn: SerialConnection):
    assert conn.read(10) is None
    assert conn.readline() is None
    assert conn.read_until(b"\n") is None


def test_readline_returns_complete_line_stripped(conn: SerialConnection, fake: FakeSerial):
    fake.feed(b"hello\r\n")
    assert conn.readline(timeout=1.0) == "hello"


def test_partial_line_stays_buffered_until_terminator(conn: SerialConnection, fake: FakeSerial):
    fake.feed(b"Battleship bro")
    assert wait_until(lambda: conn.in_waiting == 14)
    assert conn.readline() is None

    fake.feed(b"adcast!\n")
    assert conn.readline(timeout=1.0) == "Battleship broadcast!"


def test_multiple_lines_returned_in_order(conn: SerialConnection, fake: FakeSerial):
    fake.feed(b"one\ntwo\nthree\n")
    assert conn.readline(timeout=1.0) == "one"
    assert conn.readline(timeout=1.0) == "two"
    assert conn.readline(timeout=1.0) == "three"
    assert conn.readline() is None


def test_timeout_waits_for_late_data(conn: SerialConnection, fake: FakeSerial):
    threading.Timer(0.05, fake.feed, args=(b"late\n",)).start()
    assert conn.readline(timeout=1.0) == "late"


def test_timeout_expires_returns_none(conn: SerialConnection):
    start = time.monotonic()
    assert conn.readline(timeout=0.1) is None
    assert time.monotonic() - start >= 0.09


# ---- read / read_until -----------------------------------------------------

def test_read_returns_at_most_size_bytes(conn: SerialConnection, fake: FakeSerial):
    fake.feed(b"abcdef")
    assert wait_until(lambda: conn.in_waiting == 6)
    assert conn.read(4) == "abcd"
    assert conn.in_waiting == 2
    assert conn.read(10) == "ef"


def test_read_until_custom_terminator(conn: SerialConnection, fake: FakeSerial):
    fake.feed(b"abc;def;")
    assert conn.read_until(b";", timeout=1.0) == "abc;"
    assert conn.read_until(b";", timeout=1.0) == "def;"


def test_read_until_size_cap_without_terminator(conn: SerialConnection, fake: FakeSerial):
    fake.feed(b"abcdefgh")
    assert conn.read_until(b"\n", size=5, timeout=1.0) == "abcde"
    assert conn.in_waiting == 3


def test_invalid_utf8_is_replaced(conn: SerialConnection, fake: FakeSerial):
    fake.feed(b"ok\xff\xfe\n")
    line = conn.readline(timeout=1.0)
    assert line is not None
    assert line.startswith("ok")
    assert "\ufffd" in line


# ---- write / lifecycle -----------------------------------------------------

def test_write_sends_and_flushes(conn: SerialConnection, fake: FakeSerial):
    conn.write(b"CMD\n")
    assert bytes(fake.written) == b"CMD\n"
    assert fake.flushed


def test_close_stops_thread_and_closes_port(conn: SerialConnection, fake: FakeSerial):
    conn.close()
    assert not conn._thread.is_alive()
    assert fake.closed


def test_context_manager_closes(monkeypatch):
    monkeypatch.setattr(serial, "Serial", FakeSerial)
    with SerialConnection() as c:
        fake = c._conn
        thread = c._thread
    assert fake.closed
    assert not thread.is_alive()


def test_stale_input_is_discarded_on_connect(monkeypatch):
    # reset_input_buffer is called in __init__, so nothing should be pending
    monkeypatch.setattr(serial, "Serial", FakeSerial)
    with SerialConnection() as c:
        assert c.in_waiting == 0


# ---- Error handling --------------------------------------------------------

def test_reader_error_raises_on_next_read(conn: SerialConnection, fake: FakeSerial):
    fake.fail(serial.SerialException("device unplugged"))
    with pytest.raises(serial.SerialException):
        conn.readline(timeout=1.0)


def test_buffered_data_is_drained_before_error_raised(conn: SerialConnection, fake: FakeSerial):
    fake.feed(b"last words\n")
    assert wait_until(lambda: conn.in_waiting > 0)
    fake.fail(serial.SerialException("device unplugged"))

    assert conn.readline(timeout=1.0) == "last words"
    with pytest.raises(serial.SerialException):
        conn.readline(timeout=1.0)
