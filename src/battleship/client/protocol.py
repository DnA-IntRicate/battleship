"""
Client side of the Battleship serial protocol (see docs/protocol.md).

Builds request lines and parses reply lines. Nothing here touches the serial
port or decides whether a move is legal; the server is the referee.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

BOARD_SIZE = 10
NUM_CELLS = BOARD_SIZE * BOARD_SIZE
ROWS = "ABCDEFGHIJ"

# Ship letter -> (name, length), in the order the protocol lists them (§3.2).
FLEET: dict[str, tuple[str, int]] = {
    "C": ("Carrier", 5),
    "B": ("Battleship", 4),
    "R": ("Cruiser", 3),
    "S": ("Submarine", 3),
    "D": ("Destroyer", 2),
}

# Human-readable text for every NACK reason (§7), for display in the GUI.
NACK_MESSAGES: dict[str, str] = {
    "BADCMD": "The server did not understand that request.",
    "TOOLONG": "The request was too long.",
    "CHECKSUM": "The request was corrupted in transit (checksum mismatch).",
    "NOSESSION": "Not connected: send CONNECT first.",
    "NOGAME": "There is no game in progress.",
    "BADSTATE": "That is not allowed at this point in the game.",
    "NOTREADY": "Both fleets must be placed before firing.",
    "NOTURN": "It is not your turn.",
    "RANGE": "That is off the board.",
    "OCCUPIED": "You have already fired at that cell.",
    "OVERLAP": "That ship would overlap another ship.",
    "DUPSHIP": "That ship has already been placed.",
    "BADSHIP": "Unknown ship.",
}

_CELL_RE = re.compile(r"^([A-Z])(\d{1,2})$")
_OWN_CHARS = frozenset(".XoCBRSD")
_TARGET_CHARS = frozenset(".Xo")


class ProtocolError(ValueError):
    """A reply line does not follow the protocol."""


class ChecksumError(ProtocolError):
    """A reply carried a checksum that does not match its payload."""


class Player(StrEnum):
    P1 = "P1"
    P2 = "P2"

    @property
    def other(self) -> Player:
        return Player.P2 if self is Player.P1 else Player.P1


# --- Framing (§2) -------------------------------------------------------------


def checksum(payload: str) -> str:
    """Two-digit uppercase hex XOR of every byte in `payload` (§2.4)."""
    value = 0
    for byte in payload.encode("ascii"):
        value ^= byte

    return f"{value:02X}"


def encode(payload: str, with_checksum: bool = False) -> bytes:
    """Frame a request: optional `*HH` suffix, then the `\\n` terminator."""
    if with_checksum:
        payload = f"{payload}*{checksum(payload)}"

    return (payload + "\n").encode("ascii")


def strip_checksum(line: str) -> str:
    """Remove and verify a trailing `*HH`, if present. Raises ChecksumError."""
    if len(line) >= 3 and line[-3] == "*":
        payload, given = line[:-3], line[-2:]
        if given != checksum(payload):
            raise ChecksumError(f"bad checksum in reply {line!r}")

        return payload

    return line


# --- Cells (§3.1) -------------------------------------------------------------


def cell_name(index: int) -> str:
    """Row-major index to cell name, e.g. 17 -> "B7"."""
    if not 0 <= index < NUM_CELLS:
        raise ValueError(f"cell index {index} is off the board")

    row, col = divmod(index, BOARD_SIZE)
    return f"{ROWS[row]}{col}"


def cell_index(name: str) -> int:
    """Cell name to row-major index, e.g. "B7" -> 17. Raises ValueError."""
    match = _CELL_RE.match(name)
    if match is None:
        raise ValueError(f"malformed cell {name!r}")

    row = ord(match.group(1)) - ord("A")
    col = int(match.group(2))
    if row >= BOARD_SIZE or col >= BOARD_SIZE:
        raise ValueError(f"cell {name!r} is off the board")

    return row * BOARD_SIZE + col


# --- Requests (§6) ------------------------------------------------------------


def cmd_connect() -> str:
    return "CONNECT"


def cmd_new() -> str:
    return "NEW"


def cmd_place(player: Player, ship: str, cell: str, orientation: str) -> str:
    return f"PLACE:{player}:{ship}:{cell}:{orientation}"


def cmd_move(player: Player, cell: str) -> str:
    return f"MOVE:{player}:{cell}"


def cmd_state(player: Player) -> str:
    return f"STATE:{player}"


def cmd_resign(player: Player) -> str:
    return f"RESIGN:{player}"


def cmd_disconnect() -> str:
    return "DISCONNECT"


# --- Replies (§5, §6, §7) -----------------------------------------------------


@dataclass(frozen=True)
class Ok:
    """Success. `detail` holds the fields after "OK", e.g. ("SUNK", "D")."""

    detail: tuple[str, ...] = ()


@dataclass(frozen=True)
class Nack:
    reason: str

    @property
    def message(self) -> str:
        return NACK_MESSAGES.get(self.reason, f"Rejected by the server ({self.reason}).")


@dataclass(frozen=True)
class Win:
    player: Player


@dataclass(frozen=True)
class Board:
    """A `STATE` reply. `turn` is None once the game is over."""

    turn: Player | None
    own: str
    target: str


type Reply = Ok | Nack | Win | Board


def parse_reply(line: str) -> Reply:
    """Parse one reply line (terminator already removed). Raises ProtocolError."""
    kind, *fields = strip_checksum(line.rstrip("\r\n")).split(":")

    match kind:
        case "OK" if all(fields):
            return Ok(tuple(fields))

        case "NACK" if len(fields) == 1 and fields[0]:
            return Nack(fields[0])

        case "WIN" if len(fields) == 1 and fields[0] in Player:
            return Win(Player(fields[0]))

        case "BOARD" if len(fields) == 3:
            turn, own, target = fields
            if (
                (turn == "--" or turn in Player)
                and len(own) == NUM_CELLS
                and len(target) == NUM_CELLS
                and set(own) <= _OWN_CHARS
                and set(target) <= _TARGET_CHARS
            ):
                return Board(None if turn == "--" else Player(turn), own, target)

    raise ProtocolError(f"malformed reply {line!r}")
