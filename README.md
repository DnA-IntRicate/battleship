# Battleship

Group project for EEE3095S-2026 at the University of Cape Town (UCT): a serial game server for two-player Battleship.

The **STM32F051 board is the referee**. It holds both fleets, checks every request and replies over UART; it never sends a player the opponent's ships. The **PC client** is a PySide6 GUI that two players share (hotseat). It only shows what the board confirms.

---

## Repo Layout

- `src/battleship/server/`: STM32 firmware (C).
  - `server.c`: Contains the game logic.
  - `main.c`: Contains the primary entry-point and all hardware-level programming.
- `src/battleship/client/`: Python client: protocol, serial session and GUI.
- `tests/`: Unit tests and the automated test harness that drives the board.
- `docs/protocol.md`: The message protocol between client and board.
- `docs/DemoVideo.mp4`: The demo video.

---

## Software Prerequisites

- GNU Make
- ARM GNU Toolchain
- OpenOCD
- Python `3.14`

> **NOTE**: This entire project is managed by **uv**.

## Setup

``` bash
git clone https://github.com/DnA-IntRicate/battleship.git
cd battleship

# Run the setup script (installs uv)

# Windows
scripts\setup.bat

# Linux / macOS
scripts/setup.sh

# Initialize the project's environment
uv sync
```

### .stm32env Configuration

You may be required to manually create a `.stm32env` file to tell the build system where the ARM toolchain and OpenOCD are. Create a file called `.stm32env` in the repository root (this file is git-ignored):

``` make
# Windows example; adjust the versions to match your installation
ARM_GCC_PATH = C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin
OPENOCD = C:/Users/<you>/AppData/Local/Microsoft/WinGet/Packages/xpack-dev-tools.openocd-xpack_Microsoft.Winget.Source_8wekyb3d8bbwe/xpack-openocd-0.12.0-7/bin/openocd.exe
```

```make
# Ubuntu / Debian
ARM_GCC_PATH = /usr/bin
OPENOCD = openocd
```

---

## Running the project

The project has multiple different targets that may be run, which are outlined as follows:

- `uv run battleship`: Builds the server, flashes the server, pauses `250 ms` to wait for the server to settle, then runs the client app.
- `uv run battleship build`: Builds the server via the **Makefile**.
- `uv run battleship clean`: Cleans the server via the **Makefile**.
- `uv run battleship flash`: Flashes the server via the **Makefile**.
- `uv run battleship client`: Runs the client app/game.
- `uv run battleship settle`: Does nothing for `250 ms`.
- `uv run battleship ports`: Lists all available **COM** ports on the system:

### The fastest way to run the project

Run:

``` bash
uv run battleship
```

The flash ends with `** Verified OK **` and `** Resetting Target **`. The board shows `"Welcome to BATTLESHIP!"` on its LCD, plays a short LED animation, and its status LED turns green.

---

## How to play

1. **Placing:** P1 chooses a ship and Horizontal or Vertical, then clicks the cell on *Your fleet* where the ship's bow should go. When P1 has placed all five ships, the screen covers the boards. Pass the computer to P2, who presses "I'm P2, show my boards" and places their fleet.
2. **Firing:** players take turns clicking a cell on *Your shots*. After each shot the boards are covered again until the next player takes over, so neither sees the other's fleet.
3. The first player to sink all five of the opponent's ships wins. **Resign** ends the game early. **New Game** starts again; **Disconnect** closes the connection.

If the board rejects a request, the reason appears in red at the bottom of the window (for example "You have already fired at that cell."). If the board is reset during a game, the GUI reconnects on your next click and reports that the game was lost.

---

## Run the unit tests

``` bash
uv run pytest                  # PC tests only; board tests are skipped
uv run pytest --port COM10     # everything, including the tests on the board
```

The board tests drive the real STM32 over its serial port and need the current firmware flashed. They cover every test case the brief requires; see `tests/test_required.py`. The run prints which target it used, e.g. `battleship target: board on COM10`.

### Lint and type checks, as run in CI

``` bash
uv run ruff check
uv run ruff format
uv run ty check
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Build fails with `cc` not found | Create `.stm32env` (Setup, step 4) |
| No ST-Link port in the list | Replug the USB cable or try another socket, then press **Refresh** in the GUI. The port number can change between sockets |
| `could not open port` / `Access is denied` | Another program has the port open (a serial terminal, a second GUI, a test run). Close it |
| "No valid reply from the board" just after a reset | The board ignores requests during its ~1 s startup animation. Wait for the green LED and try again |
| Nothing works after flashing | Press the board's reset button and reconnect |

---
