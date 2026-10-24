"""
Background worker that owns the serial connection.

Every request blocks until the board replies (up to 1 s), so the GUI never
calls GameSession itself. It moves a SerialWorker to a QThread and talks to it
with signals: Qt queues each cross-thread signal, so the worker's slots run on
the worker thread and the GUI's slots on the GUI thread, without locks.
"""

from collections.abc import Callable
from typing import Protocol

import serial
from PySide6.QtCore import QObject, Signal, Slot

from battleship.client.protocol import ProtocolError, Reply
from battleship.client.session import GameSession, LineConnection
from battleship.client.uart import SerialConnection

# A request is any GameSession call, e.g. `lambda s: s.fire(Player.P1, "B7")`.
type Request = Callable[[GameSession], Reply]

# Everything a request can fail with: no reply, a garbled reply, or a port
# that could not be opened or was unplugged.
_REQUEST_ERRORS = (TimeoutError, ProtocolError, serial.SerialException, OSError)


class Port(LineConnection, Protocol):
    """A connection the worker can also close, like SerialConnection."""

    def close(self): ...


class SerialWorker(QObject):
    # (tag, reply): tag says which request the reply belongs to.
    finished = Signal(str, object)
    # (tag, message): the request failed without a reply from the server.
    failed = Signal(str, str)

    def __init__(self, open_port: Callable[[str], Port] = SerialConnection):
        super().__init__()
        self._open_port = open_port
        self._conn: Port | None = None
        self._session: GameSession | None = None

    @Slot(str)
    def open(self, port: str):
        """Open port and send CONNECT, replies with tag "connect"."""
        self.close()

        try:
            self._conn = self._open_port(port)
            self._session = GameSession(self._conn)
            self.finished.emit("connect", self._session.connect())
        except _REQUEST_ERRORS as e:
            self.close()
            self.failed.emit("connect", str(e))

    @Slot(str, object)
    def run(self, tag: str, request: Request):
        if self._session is None:
            self.failed.emit(tag, "Not connected to the board.")
            return

        try:
            self.finished.emit(tag, request(self._session))
        except _REQUEST_ERRORS as e:
            self.failed.emit(tag, str(e))

    @Slot()
    def close(self):
        if self._conn is not None:
            self._conn.close()

        self._conn = None
        self._session = None
