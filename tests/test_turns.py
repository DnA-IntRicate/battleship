"""
Turn order, out-of-state commands and hidden information run on the board.

Every rejected request must leave both players' boards unchanged.
"""

import pytest
from harness import EMPTY, SHIP_CELLS, snapshot, start_game

from battleship.client.protocol import Nack, Ok, Player, cell_index
from battleship.client.session import GameSession

# Turn order


def test_move_during_placement(session: GameSession):
    session.new_game()
    before = snapshot(session)

    assert session.fire(Player.P1, "A0") == Nack("NOTREADY")
    assert snapshot(session) == before


def test_move_out_of_turn(session: GameSession):
    start_game(session)
    before = snapshot(session)

    # P1 fires first, so P2 may not.
    assert session.fire(Player.P2, "A0") == Nack("NOTURN")
    assert snapshot(session) == before

    # After P1's shot it is P2's turn, so P1 may not fire again.
    assert session.fire(Player.P1, "J9") == Ok(("MISS",))
    before = snapshot(session)

    assert session.fire(Player.P1, "J8") == Nack("NOTURN")
    assert snapshot(session) == before


def test_move_without_game(session: GameSession):
    # The session fixture leaves the server in IDLE or GAME_OVER.
    assert session.fire(Player.P1, "A0") == Nack("NOGAME")


@pytest.mark.parametrize("cell", ["B-1", "7B", "a1"])
def test_malformed_cell_rejected(session: GameSession, cell: str):
    start_game(session)
    before = snapshot(session)

    assert session.fire(Player.P1, cell) == Nack("BADCMD")
    assert snapshot(session) == before


# Starting and ending games


def test_new_rejected_mid_game(session: GameSession):
    start_game(session)
    before = snapshot(session)

    assert session.new_game() == Nack("BADSTATE")
    assert snapshot(session) == before


def test_resign_ends_game(session: GameSession):
    start_game(session)

    assert session.resign(Player.P2) == Ok(("GAMEOVER",))
    assert session.board(Player.P1).turn is None
    assert session.fire(Player.P1, "A0") == Nack("NOGAME")
    assert session.new_game() == Ok(("PLACE",))


def test_resign_without_game(session: GameSession):
    assert session.resign(Player.P1) == Nack("NOGAME")


def test_disconnect_mid_game_rejected(session: GameSession):
    start_game(session)
    before = snapshot(session)

    assert session.disconnect() == Nack("BADSTATE")
    assert snapshot(session) == before


def test_disconnect_ends_session(session: GameSession):
    assert session.disconnect() == Ok()
    assert session.new_game() == Nack("NOSESSION")


def test_connect_mid_game_keeps_game(session: GameSession):
    # A restarted GUI reconnects without losing the game (protocol §4).
    start_game(session)
    session.fire(Player.P1, "A0")
    before = snapshot(session)

    assert session.connect() == Ok()
    assert snapshot(session) == before


# Hidden information


def test_state_hides_opponent_ships(session: GameSession):
    start_game(session)
    p1, p2 = snapshot(session)

    # Each player sees their own 17 ship cells but nothing of the opponent's.
    for board in (p1, p2):
        assert sum(board.own.count(ship) for ship in "CBRSD") == len(SHIP_CELLS)
        assert board.target == EMPTY

    # After a hit, the shooter learns only that one cell.
    session.fire(Player.P1, "A0")
    p1, _ = snapshot(session)
    a0 = cell_index("A0")
    assert p1.target == EMPTY[:a0] + "X" + EMPTY[a0 + 1 :]
