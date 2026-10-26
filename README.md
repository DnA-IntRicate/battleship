# Battleship

Group project for EEE3095S-2026 at the University of Cape Town (UCT): a serial game
server for two-player Battleship.

The **STM32F051 board is the referee**. It holds both fleets, checks every request and
replies over UART; it never sends a player the opponent's ships. The **PC client** is a
PySide6 GUI that two players share (hotseat). It only shows what the board confirms.

- `src/battleship/server/`: STM32 firmware (C). `server.c` is the game logic,
  `main.c` the UART, LED and LCD handling.
- `src/battleship/client/`: Python client: protocol, serial session and GUI.
- `tests/`: unit tests and the automated test harness that drives the board.
- `docs/protocol.md`: the message protocol between client and board.

## What you need

**Hardware:** the UCT STM32F051 development board (new version) and one USB cable. On this
board the on-board ST-Link is both the programmer and the game's serial port, so no UART
adapter is needed.

**Software:**

| Tool | Needed for | Install (Windows) | Install (Ubuntu/Debian) |
|---|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Everything (installs Python 3.14 and all packages) | `scripts\setup.bat` | `scripts/setup.sh` |
| GNU Make | Building the firmware | `winget install ezwinports.make` | `sudo apt install make` |
| Arm GNU Toolchain | Building the firmware | `winget install Arm.GnuArmEmbeddedToolchain` | `sudo apt install gcc-arm-none-eabi` |
| OpenOCD | Flashing the board | `winget install xpack-dev-tools.openocd-xpack` | `sudo apt install openocd` |

The Python client and the tests only need uv. The other three are only for building and
flashing the firmware. Restart your terminal after installing, so the tools are on `PATH`.

## Setup

1. Clone the repository and open a terminal in it:
   ```bash
   git clone https://github.com/DnA-IntRicate/battleship.git
   cd battleship
   ```
2. Install uv (skip if `uv --version` already works):
   ```bash
   scripts\setup.bat     # Windows
   scripts/setup.sh      # Linux / macOS
   ```
3. Install Python 3.14 and the project's packages into `.venv`:
   ```bash
   uv sync
   ```
4. **Firmware only:** tell the build where the Arm compiler and OpenOCD are. Create a file
   called `.stm32env` in the repository root (it is git-ignored, one per machine):
   ```make
   # Windows example; adjust the versions to match your installation
   ARM_GCC_PATH = C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin
   OPENOCD = C:/Users/<you>/AppData/Local/Microsoft/WinGet/Packages/xpack-dev-tools.openocd-xpack_Microsoft.Winget.Source_8wekyb3d8bbwe/xpack-openocd-0.12.0-7/bin/openocd.exe
   ```
   ```make
   # Ubuntu / Debian
   ARM_GCC_PATH = /usr/bin
   OPENOCD = openocd
   ```
   Use forward slashes; spaces in paths are fine. Without this file the build fails with
   `CreateProcess(NULL, cc ...) failed` or `cc: command not found`.

## Build and flash the firmware

Plug in the board, then:

```bash
uv run poe build
uv run poe flash
```

The flash ends with `** Verified OK **` and `** Resetting Target **`. The board shows
"Welcome to BATTLESHIP!" on its LCD, plays a short LED animation, and its status LED turns
green. The firmware stays on the board, so you only need to flash again after the firmware
changes.

## Run the game

1. Find the board's serial port. It is listed as **STLink Virtual COM Port**:
   ```bash
   uv run poe ports
   ```
2. Start the GUI:
   ```bash
   uv run battleship-client
   ```
3. The port list preselects the ST-Link port. Press **Connect**, then **New Game**.

Or build, flash and start the GUI in one go:

```bash
uv run battleship -p COM10
```

### How to play

1. **Placing:** P1 chooses a ship and Horizontal or Vertical, then clicks the cell on
   *Your fleet* where the ship's bow should go. When P1 has placed all five ships, the
   screen covers the boards. Pass the computer to P2, who presses "I'm P2, show my boards"
   and places their fleet.
2. **Firing:** players take turns clicking a cell on *Your shots*. After each shot the
   boards are covered again until the next player takes over, so neither sees the other's
   fleet.
3. The first player to sink all five of the opponent's ships wins. **Resign** ends the game
   early. **New Game** starts again; **Disconnect** closes the connection.

If the board rejects a request, the reason appears in red at the bottom of the window
(for example "You have already fired at that cell."). If the board is reset during a
game, the GUI reconnects on your next click and reports that the game was lost.

## Run the tests

```bash
uv run pytest                  # PC tests only; board tests are skipped
uv run pytest --port COM10     # everything, including the tests on the board
```

The board tests drive the real STM32 over its serial port and need the current firmware
flashed. They cover every test case the brief requires; see `tests/test_required.py`.
The run prints which target it used, e.g. `battleship target: board on COM10`.

Lint and type checks, as run in CI:

```bash
uv run ruff check .
uv run ty check
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Build fails with `cc` not found | Create `.stm32env` (Setup, step 4) |
| No ST-Link port in the list | Replug the USB cable or try another socket, then press **Refresh** in the GUI. The port number can change between sockets |
| `could not open port` / `Access is denied` | Another program has the port open (a serial terminal, a second GUI, a test run). Close it |
| "No valid reply from the board" just after a reset | The board ignores requests during its ~1 s startup animation. Wait for the green LED and try again |
| Nothing works after flashing | Press the board's reset button and reconnect |

## Authors

Muddathir Firfirey and Adam Foflonker.

## Demo Video

<video src="./docs/DemoVideo.mp4" controls width="100%"></video>

---
