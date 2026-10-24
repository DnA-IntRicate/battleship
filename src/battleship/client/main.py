import sys

from PySide6.QtWidgets import QApplication

from battleship.client.gui.main_window import MainWindow


def main():
    """Open the Battleship window. It preselects $BATTLESHIP_PORT if it is set."""
    app = QApplication(sys.argv)
    app.setApplicationName("Battleship")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
