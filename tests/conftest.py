"""
Shared fixtures for the test harness.

Tests that use the `session` fixture drive the real STM32 server over UART.
They only run when a serial port is given, and are skipped otherwise:

    uv run pytest --port COM10
"""

from collections.abc import Iterator

import pytest

from battleship.client.protocol import Board, Player
from battleship.client.session import GameSession
from battleship.client.uart import SerialConnection


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--port",
        default=None,
        help="serial port of the STM32 server, e.g. COM10. "
        "Without it, tests that need the board are skipped.",
    )


def pytest_report_header(config: pytest.Config) -> str:
    port = config.getoption("--port")
    if port:
        return f"battleship target: board on {port}"

    return "battleship target: none (board tests skipped, pass --port to run them)"


@pytest.fixture(scope="session")
def connection(request: pytest.FixtureRequest) -> Iterator[SerialConnection]:
    """One serial connection to the board, shared by the whole test run."""
    port = request.config.getoption("--port")
    if not port:
        pytest.skip("needs the board: run with --port <port>")

    with SerialConnection(port=port) as conn:
        yield conn


@pytest.fixture
def session(connection: SerialConnection) -> GameSession:
    """A connected session with no game in progress (IDLE or GAME_OVER)."""
    session = GameSession(connection)
    session.connect()

    # A game may still be running from an earlier test or an earlier run.
    state = session.state(Player.P1)
    if isinstance(state, Board) and state.turn is not None:
        session.resign(Player.P1)

    return session
