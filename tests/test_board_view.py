import os

import pytest

# Draw widgets in memory, so the tests also run on machines without a screen (CI).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import Qt  # noqa: E402

from battleship.client.gui.board_view import BoardView  # noqa: E402
from battleship.client.protocol import cell_index  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def button_at(view: BoardView, cell: str):
    return view._cells[cell_index(cell)]


def test_show_board_draws_each_character():
    view = BoardView("Your fleet")
    view.show_board("C" + "X" + "o" + "." * 97)

    assert button_at(view, "A0").text() == "C"
    assert button_at(view, "A1").text() == "✕"
    assert button_at(view, "A2").text() == "•"
    assert button_at(view, "A3").text() == ""


def test_show_board_rejects_wrong_length():
    view = BoardView("Your fleet")

    with pytest.raises(ValueError):
        view.show_board("." * 99)


def test_click_emits_cell_name():
    view = BoardView("Target")
    clicked: list[str] = []
    view.cell_clicked.connect(clicked.append)

    button_at(view, "B7").click()
    button_at(view, "J9").click()

    assert clicked == ["B7", "J9"]


def test_set_clickable():
    view = BoardView("Target")
    clicked: list[str] = []
    view.cell_clicked.connect(clicked.append)

    view.set_clickable(False)
    button_at(view, "A0").click()

    assert clicked == []
    assert not button_at(view, "A0").isEnabled()
    assert button_at(view, "A0").cursor().shape() == Qt.CursorShape.ArrowCursor

    view.set_clickable(True)
    assert button_at(view, "A0").cursor().shape() == Qt.CursorShape.PointingHandCursor
