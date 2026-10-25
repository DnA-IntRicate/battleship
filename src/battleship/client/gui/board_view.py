"""
A 10x10 board drawn from one of the server's 100-character board strings.

The widget holds no game state: show_board() is the only way to change what it
shows, and the window only calls it with a board from a STATE reply.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from battleship.client.protocol import BOARD_SIZE, NUM_CELLS, ROWS, cell_name

CELL_PX = 36

# Board character -> (text, background colour, text colour). Every pair has a
# contrast ratio of at least 4.5:1, and each state also has its own symbol, so
# the board does not rely on colour alone.
_WATER = ("", "#9cc9e6", "black")  # 11.9:1
_STYLES: dict[str, tuple[str, str, str]] = {
    ".": _WATER,
    "X": ("✕", "#b52b27", "white"),  # hit
    "o": ("•", "#f4f8fb", "#4a6b82"),  # miss
    **{ship: (ship, "#56616b", "white") for ship in "CBRSD"},  # unhit ship
}

# Hover and keyboard focus need their own borders: "border: none" would hide
# Qt's default focus ring.
_CELL_CSS = """
QPushButton {{ background: {background}; color: {colour}; font-weight: bold;
               border: 2px solid transparent; }}
QPushButton:enabled:hover {{ border-color: #f4f8fb; }}
QPushButton:focus {{ border-color: #1a73e8; }}
"""


class BoardView(QWidget):
    # Emits the cell name, e.g. "B7", when a cell is clicked.
    cell_clicked = Signal(str)

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)

        grid = QGridLayout()
        grid.setSpacing(2)

        for col in range(BOARD_SIZE):
            grid.addWidget(QLabel(str(col)), 0, col + 1)
        for row, letter in enumerate(ROWS):
            grid.addWidget(QLabel(letter), row + 1, 0)

        self._cells: list[QPushButton] = []
        for index in range(NUM_CELLS):
            button = QPushButton()
            button.setFixedSize(CELL_PX, CELL_PX)

            # name=name binds this cell's name now, a plain closure would see
            # the loop's last value, so every button would report "J9".
            name = cell_name(index)
            button.clicked.connect(lambda _=False, name=name: self.cell_clicked.emit(name))

            row, col = divmod(index, BOARD_SIZE)
            grid.addWidget(button, row + 1, col + 1)
            self._cells.append(button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{title}</b>"))
        layout.addLayout(grid)

        self.show_board("." * NUM_CELLS)

    def show_board(self, cells: str):
        """Draw a board string from a BOARD reply (own or target)."""
        for button, char in zip(self._cells, cells, strict=True):
            text, background, colour = _STYLES.get(char, _WATER)
            button.setText(text)
            button.setStyleSheet(_CELL_CSS.format(background=background, colour=colour))

    def set_clickable(self, clickable: bool):
        cursor = Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor
        for button in self._cells:
            button.setEnabled(clickable)
            button.setCursor(cursor)


if __name__ == "__main__":
    # Demo: uv run python -m battleship.client.gui.board_view
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    view = BoardView("Your fleet")
    view.show_board("CCCCC....." + "BBBB.X...." + "RRo......." + "SSS.o....." + "DX" + "." * 58)
    view.cell_clicked.connect(print)
    view.show()
    app.exec()
