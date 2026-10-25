"""
Framing robustness: malformed, oversized, partial and garbage input, run on the board.

These tests write raw bytes to the serial connection instead of going through
GameSession, which only ever sends well-formed requests.
"""

import time

import pytest
from harness import snapshot, start_game

from battleship.client import protocol
from battleship.client.protocol import Nack, Ok, Reply
from battleship.client.session import REPLY_TIMEOUT_S, GameSession

PARTIAL_TIMEOUT_S = 0.5  # protocol §2.3


def drain(session: GameSession):
    """Discard anything the server has already sent."""
    if session.conn.in_waiting:
        session.conn.read(session.conn.in_waiting)


def raw_exchange(session: GameSession, data: bytes) -> Reply:
    """Write raw bytes and return the server's next reply."""
    drain(session)
    session.conn.write(data)

    line = session.conn.readline(timeout=REPLY_TIMEOUT_S)
    assert line is not None, f"no reply to {data!r}"

    return protocol.parse_reply(line)


@pytest.mark.parametrize(
    "data",
    [
        b"FOO\n",  # unknown command
        b"move:P1:A0\n",  # commands are case-sensitive
        b"MOVE:P1\n",  # missing field
        b"MOVE:P1:A0:X\n",  # extra field
        b"MOVE:P1:A0:\n",  # trailing separator
        b"MOVE:P3:A0\n",  # no such player
        b"\x01\x7fMOVE\x00:P1:A0\n",  # non-printable bytes
    ],
)
def test_bad_frame_rejected(session: GameSession, data: bytes):
    start_game(session)
    before = snapshot(session)

    assert raw_exchange(session, data) == Nack("BADCMD")
    assert snapshot(session) == before


@pytest.mark.parametrize(("length", "reason"), [(64, "BADCMD"), (65, "TOOLONG")])
def test_frame_length_limit(session: GameSession, length: int, reason: str):
    # 64 bytes is the longest frame the server accepts (protocol §2.3).
    start_game(session)
    before = snapshot(session)

    assert raw_exchange(session, b"A" * length + b"\n") == Nack(reason)
    assert snapshot(session) == before


def test_bad_checksum_rejected(session: GameSession):
    start_game(session)
    before = snapshot(session)

    assert raw_exchange(session, b"MOVE:P1:A0*00\n") == Nack("CHECKSUM")
    assert snapshot(session) == before


def test_checksummed_request_gets_checksummed_reply(session: GameSession):
    drain(session)
    session.conn.write(b"CONNECT*5E\n")

    assert session.conn.readline(timeout=REPLY_TIMEOUT_S) == "OK*04"


def test_crlf_terminator_accepted(session: GameSession):
    assert raw_exchange(session, b"CONNECT\r\n") == Ok()


def test_empty_lines_ignored(session: GameSession):
    drain(session)
    session.conn.write(b"\n\r\n")

    assert session.conn.readline(timeout=0.3) is None


def test_partial_frame_completed_within_timeout(session: GameSession):
    start_game(session)
    session.conn.write(b"MOVE:P1:")
    time.sleep(0.1)

    assert raw_exchange(session, b"A0\n") == Ok(("HIT",))


def test_partial_frame_discarded_after_timeout(session: GameSession):
    start_game(session)
    before = snapshot(session)

    session.conn.write(b"MOVE:P1:A")
    time.sleep(PARTIAL_TIMEOUT_S + 0.2)

    # Had the partial frame survived, this would read "MOVE:P1:ASTATE:P1".
    assert raw_exchange(session, b"STATE:P1\n") == before[0]


def test_server_survives_garbage_burst(session: GameSession):
    start_game(session)
    before = snapshot(session)

    # Every byte value four times over, including embedded newlines.
    session.conn.write(bytes(range(256)) * 4)
    session.conn.write(b"\n")
    time.sleep(1.0)
    drain(session)

    assert snapshot(session) == before


def test_back_to_back_requests(session: GameSession):
    # One reply per request (protocol §2.2), even when sent in one write.
    start_game(session)
    expected = list(snapshot(session))

    drain(session)
    session.conn.write(b"STATE:P1\nSTATE:P2\n")
    replies = [session.conn.readline(timeout=REPLY_TIMEOUT_S) for _ in range(2)]

    assert [protocol.parse_reply(line) if line else None for line in replies] == expected
