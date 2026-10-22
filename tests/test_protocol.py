import pytest

from battleship.client import protocol
from battleship.client.protocol import (
    Board,
    ChecksumError,
    Nack,
    Ok,
    Player,
    ProtocolError,
    Win,
)

EMPTY = "." * 100


# Framing


def test_checksum_matches_spec_examples():
    # Worked examples from docs/protocol.md §2.4.
    assert protocol.checksum("CONNECT") == "5E"
    assert protocol.checksum("MOVE:P1:B7") == "05"
    assert protocol.checksum("OK") == "04"
    assert protocol.checksum("NACK:CHECKSUM") == "30"


def test_encode():
    assert protocol.encode("CONNECT") == b"CONNECT\n"
    assert protocol.encode("CONNECT", with_checksum=True) == b"CONNECT*5E\n"


def test_strip_checksum():
    assert protocol.strip_checksum("OK*04") == "OK"
    assert protocol.strip_checksum("OK") == "OK"

    with pytest.raises(ChecksumError):
        protocol.strip_checksum("OK*05")


# Cells


@pytest.mark.parametrize(
    ("name", "index"), [("A0", 0), ("A9", 9), ("B0", 10), ("B7", 17), ("J9", 99)]
)
def test_cell_round_trip(name: str, index: int):
    assert protocol.cell_index(name) == index
    assert protocol.cell_name(index) == name


@pytest.mark.parametrize("name", ["K3", "A10", "", "a1", "7B", "B-1", "A123"])
def test_cell_index_rejects_bad_cells(name: str):
    with pytest.raises(ValueError):
        protocol.cell_index(name)


@pytest.mark.parametrize("index", [-1, 100])
def test_cell_name_rejects_off_board_index(index: int):
    with pytest.raises(ValueError):
        protocol.cell_name(index)


# Requests


def test_commands():
    assert protocol.cmd_connect() == "CONNECT"
    assert protocol.cmd_new() == "NEW"
    assert protocol.cmd_place(Player.P1, "C", "A0", "H") == "PLACE:P1:C:A0:H"
    assert protocol.cmd_move(Player.P2, "B7") == "MOVE:P2:B7"
    assert protocol.cmd_state(Player.P1) == "STATE:P1"
    assert protocol.cmd_resign(Player.P2) == "RESIGN:P2"
    assert protocol.cmd_disconnect() == "DISCONNECT"


def test_player_other():
    assert Player.P1.other is Player.P2
    assert Player.P2.other is Player.P1


# Replies


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("OK", Ok()),
        ("OK:PLACE", Ok(("PLACE",))),
        ("OK:SUNK:D", Ok(("SUNK", "D"))),
        ("OK*04", Ok()),
        ("OK\r\n", Ok()),
        ("NACK:OCCUPIED", Nack("OCCUPIED")),
        ("WIN:P2", Win(Player.P2)),
        (f"BOARD:P1:{EMPTY}:{EMPTY}", Board(Player.P1, EMPTY, EMPTY)),
        (
            f"BOARD:--:{'C' * 5 + 'X' + 'o' * 94}:{EMPTY}",
            Board(None, "C" * 5 + "X" + "o" * 94, EMPTY),
        ),
    ],
)
def test_parse_reply(line: str, expected: protocol.Reply):
    assert protocol.parse_reply(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "",
        "HELLO",
        "OK::",
        "NACK",
        "NACK:",
        "WIN:1",
        "WIN:P3",
        f"BOARD:1:{EMPTY}:{EMPTY}",  # turn must be P1, P2 or --
        f"BOARD:P1:{EMPTY[:99]}:{EMPTY}",  # short board
        f"BOARD:P1:{EMPTY}:{'C' * 100}",  # ship letters never appear in the target board
        f"BOARD:P1:{EMPTY}",
    ],
)
def test_parse_reply_rejects_malformed(line: str):
    with pytest.raises(ProtocolError):
        protocol.parse_reply(line)


def test_parse_reply_rejects_bad_checksum():
    with pytest.raises(ChecksumError):
        protocol.parse_reply("NACK:CHECKSUM*31")


def test_every_nack_reason_has_a_message():
    for reason in ["BADCMD", "TOOLONG", "CHECKSUM", "NOSESSION", "NOGAME", "BADSTATE", "NOTREADY",
                   "NOTURN", "RANGE", "OCCUPIED", "OVERLAP", "DUPSHIP", "BADSHIP"]:  # fmt: skip
        assert Nack(reason).message == protocol.NACK_MESSAGES[reason]

    assert "WEIRD" in Nack("WEIRD").message
