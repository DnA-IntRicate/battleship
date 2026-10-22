"""
The brief's required harness tests (EEE3095S project brief, p. 4), run on the board.

Battleship has no draw, so the brief's scripted
draw case does not apply. There is no AI opponent, so that case does not apply
either.
"""

import pytest
from harness import EMPTY, SHIP_CELLS, play_to_win, snapshot, start_game

from battleship.client.protocol import Board, Nack, Ok, Player, Win, cell_index
from battleship.client.session import GameSession


def with_cell(board: str, cell: str, char: str) -> str:
    """board with one cell replaced, to build an expected board."""
    i = cell_index(cell)
    return board[:i] + char + board[i + 1 :]


def test_connect_returns_ok(session: GameSession):
    assert session.connect() == Ok()


def test_new_returns_empty_board(session: GameSession):
    assert session.new_game() == Ok(("PLACE",))

    assert session.board(Player.P1) == Board(Player.P1, EMPTY, EMPTY)
    assert session.board(Player.P2) == Board(Player.P1, EMPTY, EMPTY)


@pytest.mark.parametrize(("cell", "reply", "mark"), [("A0", "HIT", "X"), ("J9", "MISS", "o")])
def test_legal_move_changes_one_cell(session: GameSession, cell: str, reply: str, mark: str):
    start_game(session)
    p1_before, p2_before = snapshot(session)

    assert session.fire(Player.P1, cell) == Ok((reply,))

    # Exactly one cell changes, in both players' views, and the turn passes to P2.
    p1_after, p2_after = snapshot(session)
    assert p1_after == Board(Player.P2, p1_before.own, with_cell(p1_before.target, cell, mark))
    assert p2_after == Board(Player.P2, with_cell(p2_before.own, cell, mark), p2_before.target)


def test_occupied_cell_rejected(session: GameSession):
    start_game(session)
    session.fire(Player.P1, "A0")
    session.fire(Player.P2, "J9")
    before = snapshot(session)

    assert session.fire(Player.P1, "A0") == Nack("OCCUPIED")
    assert snapshot(session) == before


@pytest.mark.parametrize("cell", ["K3", "A10"])
def test_out_of_range_move_rejected(session: GameSession, cell: str):
    start_game(session)
    before = snapshot(session)

    assert session.fire(Player.P1, cell) == Nack("RANGE")
    assert snapshot(session) == before


def test_move_after_game_over_rejected(session: GameSession):
    start_game(session)
    play_to_win(session)
    before = snapshot(session)

    assert session.fire(Player.P2, "J9") == Nack("NOGAME")
    assert session.fire(Player.P1, "J9") == Nack("NOGAME")
    assert snapshot(session) == before


def test_scripted_win(session: GameSession):
    start_game(session)

    # A ship sinks on its last cell: C on shot 5, B on 9, R on 12, S on 15.
    # The 17th shot sinks the last ship (D) and wins the game.
    hit, sunk = Ok(("HIT",)), lambda ship: Ok(("SUNK", ship))
    expected = (
        [hit] * 4 + [sunk("C")]
        + [hit] * 3 + [sunk("B")]
        + [hit] * 2 + [sunk("R")]
        + [hit] * 2 + [sunk("S")]
        + [hit, Win(Player.P1)]
    )  # fmt: skip
    assert play_to_win(session) == expected

    p1, _ = snapshot(session)
    assert p1.turn is None  # Game over
    assert p1.target.count("X") == len(SHIP_CELLS)
