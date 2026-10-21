"""
Request/reply session with the Battleship server.

Used by both the GUI (from a worker thread) and the test harness. Each call
sends one request and blocks until the matching reply arrives or times out.
"""

from typing import Protocol

from battleship.client import protocol
from battleship.client.protocol import Board, Player, Reply

# How long to wait for a reply before giving up (protocol §2.2).
REPLY_TIMEOUT_S = 1.0


class LineConnection(Protocol):
    """The parts of `SerialConnection` the session needs."""

    @property
    def in_waiting(self) -> int: ...

    def read(self, size: int, timeout: float = 0.0) -> str | None: ...

    def readline(self, timeout: float = 0.0) -> str | None: ...

    def write(self, data: bytes): ...


class GameSession:
    def __init__(
        self,
        conn: LineConnection,
        timeout: float = REPLY_TIMEOUT_S,
        use_checksum: bool = False,
    ):
        self.conn = conn
        self.timeout = timeout
        self.use_checksum = use_checksum

    def request(self, payload: str) -> Reply:
        """
        Send one request and return its parsed reply.

        Raises TimeoutError if no reply arrives in time, and
        protocol.ProtocolError if the reply is malformed.
        """
        # Anything already buffered is a stale reply to an earlier, timed-out
        # request; drop it so it cannot be mistaken for this request's reply.
        if self.conn.in_waiting:
            self.conn.read(self.conn.in_waiting)

        self.conn.write(protocol.encode(payload, self.use_checksum))

        line = self.conn.readline(timeout=self.timeout)
        if line is None:
            raise TimeoutError(f"no reply to {payload!r} within {self.timeout} s")

        return protocol.parse_reply(line)

    def connect(self) -> Reply:
        # A bare newline first clears any partial frame left on the server (§2.2).
        self.conn.write(b"\n")
        return self.request(protocol.cmd_connect())

    def new_game(self) -> Reply:
        return self.request(protocol.cmd_new())

    def place(self, player: Player, ship: str, cell: str, orientation: str) -> Reply:
        return self.request(protocol.cmd_place(player, ship, cell, orientation))

    def fire(self, player: Player, cell: str) -> Reply:
        return self.request(protocol.cmd_move(player, cell))

    def state(self, player: Player) -> Reply:
        return self.request(protocol.cmd_state(player))

    def board(self, player: Player) -> Board:
        """Like `state`, but raises ProtocolError unless the reply is a board."""
        reply = self.state(player)
        if not isinstance(reply, Board):
            raise protocol.ProtocolError(f"expected BOARD, got {reply!r}")

        return reply

    def resign(self, player: Player) -> Reply:
        return self.request(protocol.cmd_resign(player))

    def disconnect(self) -> Reply:
        return self.request(protocol.cmd_disconnect())
