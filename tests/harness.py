"""
Helpers shared by the board tests: a known fleet layout and scripted games.
"""

from battleship.client.protocol import NUM_CELLS, Board, Ok, Player, Reply
from battleship.client.session import GameSession

EMPTY = "." * NUM_CELLS

# Both players use this layout: one ship per row, A to E, starting at column 0.
# Knowing where every ship is lets tests script hits, misses and a full win.
LAYOUT = [("C", "A0"), ("B", "B0"), ("R", "C0"), ("S", "D0"), ("D", "E0")]

# Every ship cell of LAYOUT, in firing order (17 cells).
SHIP_CELLS = [
    f"{row}{col}"
    for row, length in zip("ABCDE", (5, 4, 3, 3, 2), strict=True)
    for col in range(length)
]

# Cells LAYOUT leaves empty: rows F to J (50 cells).
WATER_CELLS = [f"{row}{col}" for row in "FGHIJ" for col in range(10)]


def start_game(session: GameSession):
    """Start a new game and place both fleets (P1 first, then P2).
    Afterwards the game is in the firing phase and it is P1's turn."""
    assert session.new_game() == Ok(("PLACE",))

    replies = [session.place(player, ship, cell, "H") for player in Player for ship, cell in LAYOUT]
    assert replies == [Ok(("PLACED",))] * 9 + [Ok(("READY",))]


def snapshot(session: GameSession) -> tuple[Board, Board]:
    """Both players' views of the game, to compare before and after a request."""
    return session.board(Player.P1), session.board(Player.P2)


def play_to_win(session: GameSession) -> list[Reply]:
    """
    From the start of firing, P1 sinks P2's whole fleet while P2 only hits water.
    Returns P1's replies, one per shot.
    """
    replies = []
    for shot, cell in enumerate(SHIP_CELLS):
        replies.append(session.fire(Player.P1, cell))

        if shot < len(SHIP_CELLS) - 1:
            assert session.fire(Player.P2, WATER_CELLS[shot]) == Ok(("MISS",))

    return replies
