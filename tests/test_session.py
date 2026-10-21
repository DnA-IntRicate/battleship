import pytest

from battleship.client.protocol import Board, Nack, Ok, Player, ProtocolError, Win
from battleship.client.session import GameSession

EMPTY = "." * 100


class FakeConnection:
    """Stand-in for SerialConnection. Replies are queued in advance with reply()."""

    def __init__(self):
        self.written: list[bytes] = []
        self.stale = ""
        self._replies: list[str] = []

    def reply(self, *lines: str):
        self._replies.extend(lines)

    @property
    def in_waiting(self) -> int:
        return len(self.stale)

    def read(self, size: int, timeout: float = 0.0) -> str | None:
        data, self.stale = self.stale[:size], self.stale[size:]
        return data or None

    def readline(self, timeout: float = 0.0) -> str | None:
        return self._replies.pop(0) if self._replies else None

    def write(self, data: bytes):
        self.written.append(data)


@pytest.fixture
def conn() -> FakeConnection:
    return FakeConnection()


def test_request_sends_framed_line_and_parses_reply(conn: FakeConnection):
    conn.reply("OK:HIT")

    assert GameSession(conn).fire(Player.P1, "B7") == Ok(("HIT",))
    assert conn.written == [b"MOVE:P1:B7\n"]


def test_request_with_checksum(conn: FakeConnection):
    conn.reply("OK*04")

    assert GameSession(conn, use_checksum=True).request("CONNECT") == Ok()
    assert conn.written == [b"CONNECT*5E\n"]


def test_request_times_out(conn: FakeConnection):
    with pytest.raises(TimeoutError):
        GameSession(conn).new_game()


def test_request_rejects_malformed_reply(conn: FakeConnection):
    conn.reply("GARBAGE")

    with pytest.raises(ProtocolError):
        GameSession(conn).new_game()


def test_stale_input_is_discarded_before_sending(conn: FakeConnection):
    conn.stale = "OK:MISS\r\n"
    conn.reply("OK:PLACE")

    assert GameSession(conn).new_game() == Ok(("PLACE",))
    assert conn.stale == ""


def test_connect_flushes_partial_frame_first(conn: FakeConnection):
    conn.reply("OK")

    assert GameSession(conn).connect() == Ok()
    assert conn.written == [b"\n", b"CONNECT\n"]


def test_every_command(conn: FakeConnection):
    session = GameSession(conn)
    conn.reply("OK:PLACE", "OK:PLACED", "WIN:P1", "OK:GAMEOVER", "OK")

    assert session.new_game() == Ok(("PLACE",))
    assert session.place(Player.P1, "C", "A0", "H") == Ok(("PLACED",))
    assert session.fire(Player.P1, "E1") == Win(Player.P1)
    assert session.resign(Player.P2) == Ok(("GAMEOVER",))
    assert session.disconnect() == Ok()
    assert conn.written == [
        b"NEW\n",
        b"PLACE:P1:C:A0:H\n",
        b"MOVE:P1:E1\n",
        b"RESIGN:P2\n",
        b"DISCONNECT\n",
    ]


def test_board(conn: FakeConnection):
    conn.reply(f"BOARD:P2:{EMPTY}:{EMPTY}")

    assert GameSession(conn).board(Player.P2) == Board(Player.P2, EMPTY, EMPTY)
    assert conn.written == [b"STATE:P2\n"]


def test_board_raises_when_reply_is_not_a_board(conn: FakeConnection):
    conn.reply("NACK:NOGAME")
    session = GameSession(conn)

    with pytest.raises(ProtocolError):
        session.board(Player.P1)

    conn.reply("NACK:NOGAME")
    assert session.state(Player.P1) == Nack("NOGAME")
