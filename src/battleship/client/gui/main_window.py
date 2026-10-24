"""
Main window of the Battleship client.

The window never touches the serial port: it emits requests to a SerialWorker
on a background thread and redraws only from the replies that come back.
"""

import os

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from serial.tools import list_ports

from battleship.client.gui.board_view import BoardView
from battleship.client.gui.worker import Request, SerialWorker
from battleship.client.protocol import NUM_CELLS, Board, Nack, Ok, Player, Reply

EMPTY = "." * NUM_CELLS

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

        self.own_view = BoardView("Your fleet")
        self.target_view = BoardView("Your shots")

        boards = QHBoxLayout()
        boards.addWidget(self.own_view)
        boards.addWidget(self.target_view)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.show_status("Not connected. Choose the board's port and press Connect.")

        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addLayout(boards)
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
            # Not an error: there is simply no game yet.
            self.show_board(None)
            self.show_status("Connected. No game in progress.")
        elif isinstance(reply, Nack):
            self.show_status(reply.message, error=True)
        elif tag == "connect":
            self.connected = True
            self.show_status(f"Connected to {self.port_box.currentData()}.")
            self.request_state()
        elif tag == "disconnect":
            self.connected = False
            self.close_requested.emit()
            self.show_board(None)
            self.show_status("Disconnected.")
        elif tag == "state" and isinstance(reply, Board):
            self.show_board(reply)
        elif tag == "new":
            self.show_status(f"New game. {Player.P1}, place your ships.")
            self.request_state()
        elif tag == "resign":
            resigned = self.board.turn if self.board else "The player"
            self.show_status(f"{resigned} resigned. Game over.")
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
        self.board = board
        self.own_view.show_board(board.own if board else EMPTY)
        self.target_view.show_board(board.target if board else EMPTY)

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
        self.resign_button.setEnabled(idle and self.connected and self.in_game)
        self.disconnect_button.setToolTip("Resign the game first." if self.in_game else "")
        self.own_view.set_clickable(False)
        self.target_view.set_clickable(False)

    def closeEvent(self, event: QCloseEvent):
        # Close the port on the worker's thread, then stop that thread.
        self.close_requested.emit()
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()

        super().closeEvent(event)
