"""
Ship placement rules run on the board.

Every rejected placement must leave both players' boards unchanged.
"""

import pytest
from harness import LAYOUT, snapshot, start_game

from battleship.client.protocol import Nack, Ok, Player
from battleship.client.session import GameSession


@pytest.mark.parametrize(
    ("ship", "cell", "orientation", "reason"),
    [
        ("C", "A6", "H", "RANGE"),  # runs off the right edge
        ("C", "G0", "V", "RANGE"),  # runs off the bottom edge
        ("C", "K0", "H", "RANGE"),  # bow is off the board
        ("Z", "A0", "H", "BADSHIP"),
        ("CX", "A0", "H", "BADSHIP"),
        ("C", "A0", "X", "BADCMD"),  # orientation must be H or V
        ("C", "A-1", "H", "BADCMD"),  # malformed cell
    ],
)
def test_bad_placement_rejected(
    session: GameSession, ship: str, cell: str, orientation: str, reason: str
):
    session.new_game()
    before = snapshot(session)

    assert session.place(Player.P1, ship, cell, orientation) == Nack(reason)
    assert snapshot(session) == before


def test_overlapping_ship_rejected(session: GameSession):
    session.new_game()
    assert session.place(Player.P1, "C", "A0", "H") == Ok(("PLACED",))
    before = snapshot(session)

    # A vertical Battleship from A2 would cross the Carrier at A2.
    assert session.place(Player.P1, "B", "A2", "V") == Nack("OVERLAP")
    assert snapshot(session) == before


def test_duplicate_ship_rejected(session: GameSession):
    session.new_game()
    assert session.place(Player.P1, "C", "A0", "H") == Ok(("PLACED",))
    before = snapshot(session)

    assert session.place(Player.P1, "C", "J0", "H") == Nack("DUPSHIP")
    assert snapshot(session) == before


@pytest.mark.xfail(
    strict=True,
    reason="firmware checks RANGE before BADSHIP and DUPSHIP, against protocol 7.1",
)
@pytest.mark.parametrize(("ship", "reason"), [("Z", "BADSHIP"), ("C", "DUPSHIP")])
def test_placement_check_order(session: GameSession, ship: str, reason: str):
    # Each request has two faults; §7.1 says which one is reported.
    session.new_game()
    assert session.place(Player.P1, "C", "A0", "H") == Ok(("PLACED",))

    assert session.place(Player.P1, ship, "K0", "H") == Nack(reason)


def test_placement_out_of_turn(session: GameSession):
    session.new_game()
    assert session.place(Player.P2, "C", "A0", "H") == Nack("NOTURN")

    # Once P1's fleet is complete it is P2's turn to place.
    for ship, cell in LAYOUT:
        session.place(Player.P1, ship, cell, "H")

    assert session.board(Player.P1).turn == Player.P2
    assert session.place(Player.P1, "C", "J0", "H") == Nack("NOTURN")


def test_place_while_firing_rejected(session: GameSession):
    start_game(session)

    assert session.place(Player.P1, "C", "J0", "H") == Nack("BADSTATE")


def test_place_without_game(session: GameSession):
    # The session fixture leaves the server in IDLE or GAME_OVER.
    assert session.place(Player.P1, "C", "A0", "H") == Nack("NOGAME")
