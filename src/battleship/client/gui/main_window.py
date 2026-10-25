"""
Main window of the Battleship client.

The window never touches the serial port: it emits requests to a SerialWorker
on a background thread and redraws only from the replies that come back.
"""

import os

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from serial.tools import list_ports

from battleship.client.gui.board_view import BoardView
from battleship.client.gui.worker import Request, SerialWorker
from battleship.client.protocol import FLEET, NUM_CELLS, Board, Nack, Ok, Player, Reply, Win

EMPTY = "." * NUM_CELLS

# Cells a complete fleet occupies (17). A player whose own board shows fewer
# ship cells is still placing ships.
FLEET_CELLS = sum(length for _name, length in FLEET.values())

# Status line styles; both have a contrast ratio above 9:1 in light and dark themes.
_INFO_CSS = "background: #e8f1fb; color: #0f2a44; padding: 6px; border-radius: 4px;"
_ERROR_CSS = "background: #fdecea; color: #7a1712; padding: 6px; border-radius: 4px;"


class MainWindow(QMainWindow):
    # Requests to the worker. Qt queues them onto the worker's thread.
    open_requested = Signal(str)
    run_requested = Signal(str, object)
    close_requested = Signal()

    def __init__(self, worker: SerialWorker | None = None, threaded: bool = True):
        super().__init__()
        self.setWindowTitle("Battleship")

        self.connected = False
        self.busy = False  # a request is waiting for its reply
        self.board: Board | None = None  # last board the server sent
        self.viewer = Player.P1  # whose boards are shown
        self.last_shot = ""  # e.g. "P1 fired at B7: hit.", shown to both players
        self.result = ""  # e.g. "P1 wins!", shown once the game is over

        self._build_ui()

        # The worker owns the serial port and runs on its own thread, so the
        # window keeps responding while a request waits for the board.
        self.worker = worker or SerialWorker()
        self.worker_thread: QThread | None = None
        if threaded:
            self.worker_thread = QThread(self)
            self.worker.moveToThread(self.worker_thread)
            self.worker_thread.start()

        self.open_requested.connect(self.worker.open)
        self.run_requested.connect(self.worker.run)
        self.close_requested.connect(self.worker.close)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)

        self.refresh_ports()
        self.update_controls()

    def _build_ui(self):
        self.port_box = QComboBox()
        self.port_box.setMinimumWidth(280)
        port_label = QLabel("&Port:")  # Alt+P focuses the port list
        port_label.setBuddy(self.port_box)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setAccessibleName("Refresh serial ports")
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        self.new_button = QPushButton("New Game")
        self.resign_button = QPushButton("Resign")

        for button in (
            self.refresh_button,
            self.connect_button,
            self.disconnect_button,
            self.new_button,
            self.resign_button,
        ):
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.new_button.clicked.connect(self.new_game)
        self.resign_button.clicked.connect(self.resign)

        self.refresh_button.clicked.connect(self.refresh_ports)
        self.connect_button.clicked.connect(self.connect_to_board)
        self.disconnect_button.clicked.connect(self.disconnect_from_board)

        controls = QHBoxLayout()
        controls.addWidget(port_label)
        controls.addWidget(self.port_box)
        controls.addWidget(self.refresh_button)
        controls.addStretch()
        controls.addWidget(self.connect_button)
        controls.addWidget(self.disconnect_button)
        controls.addSpacing(16)
        controls.addWidget(self.new_button)
        controls.addWidget(self.resign_button)

        # Page 1: the current player's boards.
        self.viewer_label = QLabel()
        self.own_view = BoardView("Your fleet")
        self.target_view = BoardView("Your shots")
        self.own_view.cell_clicked.connect(self.on_own_cell)
        self.target_view.cell_clicked.connect(self.on_target_cell)

        # Placement controls, shown only while the viewer is placing ships.
        self.ship_box = QComboBox()
        ship_label = QLabel("&Ship:")
        ship_label.setBuddy(self.ship_box)
        self.horizontal = QRadioButton("&Horizontal")
        self.vertical = QRadioButton("&Vertical")
        self.horizontal.setChecked(True)
        orientation = QButtonGroup(self)
        orientation.addButton(self.horizontal)
        orientation.addButton(self.vertical)

        placement_row = QHBoxLayout()
        placement_row.addWidget(ship_label)
        placement_row.addWidget(self.ship_box)
        placement_row.addSpacing(16)
        placement_row.addWidget(self.horizontal)
        placement_row.addWidget(self.vertical)
        placement_row.addStretch()

        self.placement_bar = QWidget()
        placement_layout = QVBoxLayout(self.placement_bar)
        placement_layout.setContentsMargins(0, 0, 0, 0)
        placement_layout.addLayout(placement_row)
        placement_layout.addWidget(
            QLabel(
                "Click the cell where the ship's bow should go: "
                "horizontal ships extend right, vertical ships extend down."
            )
        )
        self.placement_bar.setHidden(True)

        boards = QHBoxLayout()
        boards.addWidget(self.own_view)
        boards.addWidget(self.target_view)

        boards_page = QWidget()
        boards_layout = QVBoxLayout(boards_page)
        boards_layout.addWidget(self.viewer_label)
        boards_layout.addWidget(self.placement_bar)
        boards_layout.addLayout(boards)

        # Page 2: covers the boards while the computer is passed to the other player.
        self.handoff_label = QLabel()
        self.handoff_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.handoff_button = QPushButton()
        self.handoff_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.handoff_button.clicked.connect(self.take_over)

        handoff_page = QWidget()
        handoff_layout = QVBoxLayout(handoff_page)
        handoff_layout.addStretch()
        handoff_layout.addWidget(self.handoff_label)
        handoff_layout.addWidget(self.handoff_button, alignment=Qt.AlignmentFlag.AlignCenter)
        handoff_layout.addStretch()

        self.pages = QStackedWidget()
        self.pages.addWidget(boards_page)
        self.pages.addWidget(handoff_page)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.show_status("Not connected. Choose the board's port and press Connect.")

        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addWidget(self.pages)
        layout.addWidget(self.status)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    # Requests

    def send(self, tag: str, request: Request):
        """Hand one request to the worker; the reply arrives in on_finished or on_failed."""
        self.busy = True
        self.update_controls()
        self.run_requested.emit(tag, request)

    def request_state(self):
        viewer = self.viewer
        self.send("state", lambda s: s.state(viewer))

    @Slot()
    def refresh_ports(self):
        self.port_box.clear()
        for port in sorted(list_ports.comports(), key=lambda p: p.device):
            self.port_box.addItem(f"{port.device} – {port.description}", port.device)

        # Prefer the port the CLI passed in, else the ST-Link virtual COM port.
        wanted = os.environ.get("BATTLESHIP_PORT")
        for i in range(self.port_box.count()):
            if self.port_box.itemData(i) == wanted or (
                not wanted and "STLink" in self.port_box.itemText(i)
            ):
                self.port_box.setCurrentIndex(i)
                break

    @Slot()
    def connect_to_board(self):
        port = self.port_box.currentData()
        if not port:
            self.show_status("Choose a serial port first.", error=True)
            return

        self.busy = True
        self.update_controls()
        self.show_status(f"Connecting to {port}…")
        self.open_requested.emit(port)

    @Slot()
    def disconnect_from_board(self):
        self.send("disconnect", lambda s: s.disconnect())

    @Slot()
    def new_game(self):
        self.send("new", lambda s: s.new_game())

    @Slot()
    def resign(self):
        # In hotseat play the player whose turn it is is at the keyboard.
        player = self.board.turn if self.board else None
        if player is None:
            return

        if self.confirm(f"Resign the game as {player}?"):
            self.send("resign", lambda s: s.resign(player))

    def confirm(self, question: str) -> bool:
        """Ask before an irreversible action. Tests replace this method."""
        answer = QMessageBox.question(self, "Battleship", question)
        return answer == QMessageBox.StandardButton.Yes

    # Replies (always handled on the GUI thread)

    @Slot(str, object)
    def on_finished(self, tag: str, reply: Reply):
        self.busy = False

        if tag == "state" and reply == Nack("NOGAME"):
            if self.in_game:
                # We were mid-game, but the server has no game: it was reset.
                self.forget_game()
                self.show_status(
                    "The board was reset, so the game was lost. Press New Game to start again."
                )
            else:
                # Not an error: there is simply no game yet.
                self.show_board(None)
                self.show_status("Connected. No game in progress.")
        elif reply == Nack("NOSESSION") and tag != "connect":
            # The board rebooted (reset button) and forgot our CONNECT.
            # Reconnect; the STATE that follows tells us what survived.
            self.show_status("The board was reset. Reconnecting…")
            self.send("connect", lambda s: s.connect())
        elif reply == Nack("NOGAME") and self.in_game:
            # The game was wiped while we thought it was running; confirm with STATE.
            self.request_state()
        elif isinstance(reply, Nack):
            self.show_status(reply.message, error=True)
        elif tag == "connect":
            self.connected = True
            self.show_status(f"Connected to {self.port_box.currentData()}.")
            self.request_state()
        elif tag == "disconnect":
            self.connected = False
            self.close_requested.emit()
            self.viewer = Player.P1
            self.show_board(None)
            self.show_status("Disconnected.")
        elif tag == "state" and isinstance(reply, Board):
            self.show_board(reply)
        elif tag == "new":
            self.viewer = Player.P1  # P1 always places first
            self.last_shot = self.result = ""
            self.show_status(f"New game. {Player.P1}, place your ships.")
            self.request_state()
        elif tag == "resign":
            resigned = self.board.turn if self.board else "The player"
            self.result = f"{resigned} resigned."
            self.request_state()
        elif tag.startswith("fire:"):
            self.record_shot(tag.removeprefix("fire:"), reply)
            self.request_state()
        elif isinstance(reply, Ok):
            self.request_state()

        self.update_controls()

    @Slot(str, str)
    def on_failed(self, tag: str, message: str):
        self.busy = False
        if tag == "connect":
            self.connected = False
            self.show_status(f"Could not connect: {message}", error=True)
        else:
            self.show_status(f"No valid reply from the board: {message}", error=True)

        self.update_controls()

    # Display

    def show_board(self, board: Board | None):
        """Draw the viewer's boards, or cover them if the turn has passed to the other player."""
        self.board = board

        if board is not None and board.turn is not None and board.turn != self.viewer:
            # Hotseat: never leave one player's fleet on screen for the other.
            self.own_view.show_board(EMPTY)
            self.target_view.show_board(EMPTY)
            self.handoff_label.setText(
                f"<p>{self.last_shot}</p>"
                f"<h2>Pass the computer to {board.turn}</h2>"
                f"<p>{self.viewer}, look away from the screen.</p>"
            )
            self.handoff_button.setText(f"I'm {board.turn}, show my boards")
            self.pages.setCurrentIndex(1)
            self.show_status(
                f"{self.last_shot} {self.viewer}'s turn is over. "
                f"Pass the computer to {board.turn}.".lstrip()
            )
            return

        self.pages.setCurrentIndex(0)
        self.viewer_label.setText(f"<b>{self.viewer}'s boards</b>" if board else "")
        self.own_view.show_board(board.own if board else EMPTY)
        self.target_view.show_board(board.target if board else EMPTY)
        self.update_placement()

        if self.firing:
            self.show_status(
                f"{self.last_shot} {self.viewer}, your turn: "
                "click a cell on Your shots to fire.".lstrip()
            )
        elif board is not None and board.turn is None:
            self.show_status(f"{self.result} Game over. Press New Game to play again.".lstrip())

    @property
    def firing(self) -> bool:
        """True while it is the viewer's turn and both fleets are placed."""
        board = self.board
        return board is not None and board.turn == self.viewer and not self.placing

    @Slot(str)
    def on_target_cell(self, cell: str):
        """A click on the viewer's shots grid fires at that cell."""
        if not self.firing:
            return

        player = self.viewer
        self.send(f"fire:{cell}", lambda s: s.fire(player, cell))

    def record_shot(self, cell: str, reply: Reply):
        """Describe a shot the server accepted, for both players to read."""
        shooter = self.viewer
        match reply:
            case Ok(("MISS",)):
                self.last_shot = f"{shooter} fired at {cell}: miss."
            case Ok(("HIT",)):
                self.last_shot = f"{shooter} fired at {cell}: hit."
            case Ok(("SUNK", ship)):
                name = FLEET[ship][0] if ship in FLEET else ship
                self.last_shot = f"{shooter} fired at {cell} and sank the {name}!"
            case Win(winner):
                self.last_shot = f"{shooter} fired at {cell} and sank the last ship."
                self.result = f"{winner} wins!"

    @property
    def placing(self) -> bool:
        """True while it is the viewer's turn and their fleet is incomplete."""
        board = self.board
        if board is None or board.turn != self.viewer:
            return False

        return sum(char in "CBRSDX" for char in board.own) < FLEET_CELLS

    def update_placement(self):
        """Show the placement controls with the ships the viewer has not placed yet."""
        self.placement_bar.setHidden(not self.placing)
        if self.board is None or not self.placing:
            return

        selected = self.ship_box.currentData()
        remaining = [ship for ship in FLEET if ship not in self.board.own]

        self.ship_box.clear()
        for ship in remaining:
            name, length = FLEET[ship]
            self.ship_box.addItem(f"{name} ({length})", ship)
        if selected in remaining:
            self.ship_box.setCurrentIndex(remaining.index(selected))

        self.show_status(f"{self.viewer}, place your ships: {len(remaining)} left.")

    @Slot(str)
    def on_own_cell(self, cell: str):
        """A click on the viewer's fleet grid places the selected ship there."""
        ship = self.ship_box.currentData()
        if not self.placing or not ship:
            return

        player = self.viewer
        orientation = "H" if self.horizontal.isChecked() else "V"
        self.send("place", lambda s: s.place(player, ship, cell, orientation))

    def forget_game(self):
        """Clear everything the GUI showed about a game the server no longer has."""
        self.viewer = Player.P1
        self.last_shot = self.result = ""
        self.show_board(None)

    @property
    def handing_off(self) -> bool:
        return self.pages.currentIndex() == 1

    @Slot()
    def take_over(self):
        """The next player is at the screen: show their boards."""
        if self.board is not None and self.board.turn is not None:
            self.viewer = self.board.turn
            self.request_state()

    def show_status(self, text: str, error: bool = False):
        self.status.setText(text)
        self.status.setStyleSheet(_ERROR_CSS if error else _INFO_CSS)
        self.status.setProperty("error", error)

    @property
    def in_game(self) -> bool:
        """True while the server's last board shows a game in progress."""
        return self.board is not None and self.board.turn is not None

    def update_controls(self):
        # The server checks every request anyway; disabling buttons it would
        # reject just saves the user from errors.
        idle = not self.busy
        self.port_box.setEnabled(idle and not self.connected)
        self.refresh_button.setEnabled(idle and not self.connected)
        self.connect_button.setEnabled(idle and not self.connected)
        self.disconnect_button.setEnabled(idle and self.connected and not self.in_game)
        self.new_button.setEnabled(idle and self.connected and not self.in_game)
        self.resign_button.setEnabled(
            idle and self.connected and self.in_game and not self.handing_off
        )
        self.handoff_button.setEnabled(idle)
        self.disconnect_button.setToolTip("Resign the game first." if self.in_game else "")
        self.placement_bar.setEnabled(idle)
        self.own_view.set_clickable(idle and self.placing and not self.handing_off)
        self.target_view.set_clickable(idle and self.firing and not self.handing_off)

    def closeEvent(self, event: QCloseEvent):
        # Close the port on the worker's thread, then stop that thread.
        self.close_requested.emit()
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()

        super().closeEvent(event)
