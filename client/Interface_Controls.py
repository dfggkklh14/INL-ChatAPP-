from PyQt5.QtGui import QTextOption
from PyQt5.QtWidgets import (
    QPushButton, QLineEdit, QTextEdit,
    QListWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QMessageBox
)

def style_button(button: QPushButton):
    button.setStyleSheet("""
        QPushButton {
            background-color: #2E8B57;
            color: #ffffff;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 14px;
        }
        QPushButton:hover {
            background-color: #3CB371;
        }
        QPushButton:pressed {
            background-color: #2E8B57;
        }
    """)

def style_text_edit(text_edit: QTextEdit):
    text_edit.setWordWrapMode(QTextOption.WrapAnywhere)
    text_edit.setStyleSheet("""
        QTextEdit {
            border: 1px solid #cccccc;
            border-radius: 4px;
            padding: 6px;
            background: #ffffff;
            font-size: 14px;
            color: #333333;
        }
        QTextEdit:focus {
            border: 1px solid #2E8B57;
        }
    """)

def style_line_edit(line_edit: QLineEdit):
    line_edit.setStyleSheet("""
        QLineEdit {
            border: 1px solid #cccccc;
            border-radius: 4px;
            padding: 6px;
            background: #ffffff;
            font-size: 14px;
            color: #333333;
        }
        QLineEdit:focus {
            border: 1px solid #2E8B57;
        }
    """)

def style_list_widget(list_widget: QListWidget):
    list_widget.setStyleSheet("""
        QListWidget {
            border: 1px solid #cccccc;
            border-radius: 4px;
            background: #ffffff;
            font-size: 14px;
            color: #333333;
        }
        QListWidget::item {
            padding: 6px;
            border-bottom: 1px solid #eeeeee;
            outline: none;
        }
        QListWidget::item:hover {
            background: #f5f5f5;
            outline: none;
        }
        QListWidget::item:selected {
            background: #2E8B57;
            color: #ffffff;
            border: none;
            outline: none;
        }
        QListWidget::item:focus {
            outline: none;
        }
    """)

def style_dialog(dialog: QDialog):
    dialog.setStyleSheet("""
        QDialog {
            background: #ffffff;
            border: none;
        }
    """)

def style_vbox_layout(vbox_layout: QVBoxLayout):
    vbox_layout.setSpacing(0)

def style_hbox_layout(hbox_layout: QHBoxLayout):
    hbox_layout.setSpacing(0)

def style_grid_layout(grid_layout: QGridLayout):
    grid_layout.setSpacing(0)

def style_message_box(message_box: QMessageBox):
    message_box.setStyleSheet("""
        QMessageBox {
            background: #ffffff;
            border: none;
            font-size: 14px;
        }
    """)
