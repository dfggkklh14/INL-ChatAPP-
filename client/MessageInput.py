import asyncio
import json
from typing import Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtWidgets import QMessageBox, QDialog, QWidget, QScrollArea, QGridLayout, QPushButton, QVBoxLayout, \
    QTextEdit, QHBoxLayout, QLabel, QMenu, QFileDialog

from Interface_Controls import get_scrollbar_style, FONTS, StyleGenerator, style_text_edit, theme_manager


class EmoticonPopup(QDialog):
    """
    表情选择弹窗（非模态），点击表情后发出信号，失去焦点时自动关闭。
    """
    emoticonClicked = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup)
        self.setWindowTitle("选择表情")
        self.setFocusPolicy(Qt.StrongFocus)
        self._init_ui()

    def _init_ui(self) -> None:
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.verticalScrollBar().setStyleSheet(get_scrollbar_style())
        scroll_area.setFixedSize(370, 250)

        content_widget = QWidget()
        grid_layout = QGridLayout(content_widget)
        grid_layout.setContentsMargins(5, 5, 5, 5)
        grid_layout.setSpacing(5)

        emoticons = [
            "😀", "😁", "😂", "🤣", "😃", "😄", "😅", "😆",
            "😉", "😊", "😋", "😎", "😍", "😘", "🥰", "😗",
            "😙", "😚", "🙂", "🤗", "🤩", "🤔", "🤨", "😐",
            "😑", "😶", "🙄", "😏", "😣", "😥", "😮", "🤐",
            "😯", "😪", "😫", "🥱", "😴", "😌", "😛", "😜",
            "😝", "🤤", "😒", "😓", "😔", "😕", "🙃", "🤑",
            "😲", "☹️", "🙁", "😖", "😞", "😟", "😤", "😢",
            "😭", "😦", "😧", "😨", "😩", "🤯", "😬", "😰",
            "😱", "🥵", "🥶", "😳", "🤪", "😵", "😡", "😠",
            "🤬", "😷", "🤒", "🤕", "🤢", "🤮", "🤧", "😇",
            "💖", "💙", "💚", "💛", "💜", "🧡", "❤️", "🤍",
            "🤎", "🖤", "💔", "❣️", "💌", "💋", "👑", "🎉",
            "🎂", "🎁", "🌹", "🌸", "🌺", "🌻", "🌼", "🌷",
            "🌴", "🌵", "🍀", "🍎", "🍊", "🍓", "🍒", "🍑",
            "🍍", "🍉", "🍇", "🍓", "🍍", "🍔", "🍕", "🍣",
            "🍿", "🍩", "🍪", "🍦", "🥧", "🍫", "🍬", "🍭",
            "🥚", "🍳", "🍞", "🍩", "🥯", "🥨", "🥒", "🥬",
            "🍅", "🥕", "🥔", "🍠", "🍗", "🍖", "🍤", "🍖",
            "🍛", "🍜", "🍣", "🍲", "🥗", "🍙", "🍚", "🍘"
        ]
        btn_size = 40
        max_cols = scroll_area.width() // (btn_size + 5)
        row = col = 0
        font = QFont(FONTS['MESSAGE'])
        font.setHintingPreference(QFont.PreferNoHinting)
        font.setStyleStrategy(QFont.PreferAntialias)
        for emo in emoticons:
            btn = QPushButton(emo, content_widget)
            btn.setFixedSize(btn_size, btn_size)
            btn.setFont(font)
            btn.setStyleSheet("font-size: 25px; border: none; background: transparent;")
            btn.clicked.connect(lambda checked, e=emo: self.emoticonClicked.emit(e))
            grid_layout.addWidget(btn, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        content_widget.setLayout(grid_layout)
        scroll_area.setWidget(content_widget)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)
        self.setFixedSize(scroll_area.size())

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.close()

class CustomTextEdit(QTextEdit):
    """
    自定义 QTextEdit，回车（不带 Shift）发送消息信号。
    """
    sendMessage = pyqtSignal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            event.accept()
            self.sendMessage.emit()
        else:
            super().keyPressEvent(event)

    def update_theme(self, theme: dict) -> None:
        """更新主题时重新应用样式"""
        StyleGenerator.apply_style(self, "text_edit")
        self.verticalScrollBar().setStyleSheet(get_scrollbar_style())

class ReplyPreviewWidget(QWidget):
    """
    回复预览控件，显示回复内容及关闭按钮。
    """
    DOWNLOAD_LABELS = {
        "image": "图片",
        "video": "视频",
        "file": "文件"
    }

    def __init__(self, reply_to_id: int, reply_preview: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.reply_to_id = reply_to_id
        self.reply_preview = reply_preview
        self.setFixedHeight(45)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.filling_wid = QWidget(self)
        self.filling_wid.setStyleSheet(f"background-color: {theme_manager.current_theme['list_background']};border-radius: 0px;")
        filling_layout = QVBoxLayout(self.filling_wid)
        filling_layout.setContentsMargins(5, 5, 5, 5)
        filling_layout.setAlignment(Qt.AlignCenter)

        self.background_container = QWidget(self.filling_wid)
        self.background_container.setStyleSheet("background-color: rgba(200, 200, 200, 50); border-radius: 5px;")
        container_layout = QHBoxLayout(self.background_container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        container_layout.setSpacing(5)

        # 创建文本标签
        self.reply_label = QLabel(self.background_container)
        self.reply_label.setFont(FONTS['FILE_SIZE'])
        StyleGenerator.apply_style(self.reply_label, "label")
        full_text = self._format_reply_text()

        fm = QFontMetrics(self.reply_label.font())
        available_width = self.width() - 30 if self.width() > 30 else 100
        truncated_text = fm.elidedText(full_text, Qt.ElideRight, available_width)
        self.reply_label.setText(truncated_text)
        self.reply_label.setWordWrap(False)

        # 关闭按钮
        self.close_button = QPushButton("×", self.background_container)
        self.close_button.setFixedSize(20, 20)
        StyleGenerator.apply_style(self.close_button, "button", extra="border-radius: 10px;")
        self.close_button.clicked.connect(self.cancel_reply)

        # 布局：让背景容器自动填充
        container_layout.addWidget(self.reply_label)
        container_layout.addStretch()
        container_layout.addWidget(self.close_button)

        # 把 background_container 添加到 filling_wid
        filling_layout.addWidget(self.background_container)

        # 把 filling_wid 添加到 main_layout
        main_layout.addWidget(self.filling_wid)
        self.setLayout(main_layout)

    def _format_reply_text(self) -> str:
        """
        格式化回复文本，与 ChatBubbleWidget 保持一致。
        """
        if not self.reply_preview:
            return f"回复消息 #{self.reply_to_id} (预览为空)"
        try:
            preview_data = json.loads(self.reply_preview)
            sender = preview_data.get('sender', '未知用户')
            raw_content = preview_data.get('content', '消息内容不可用')
            if raw_content.startswith('[image]:'):
                filename = raw_content[len('[image]:'):].strip()
                display_content = f"{self.DOWNLOAD_LABELS.get('image', '图片')}: {filename}"
            elif raw_content.startswith('[video]:'):
                filename = raw_content[len('[video]:'):].strip()
                display_content = f"{self.DOWNLOAD_LABELS.get('video', '视频')}: {filename}"
            elif raw_content.startswith('[file]:'):
                filename = raw_content[len('[file]:'):].strip()
                display_content = f"{self.DOWNLOAD_LABELS.get('file', '文件')}: {filename}"
            else:
                display_content = raw_content
            return f"回复 {sender}: {display_content}"
        except Exception as e:
            return f"回复消息 #{self.reply_to_id} (解析错误: {str(e)})"

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        available_width = self.width() - 20
        fm = QFontMetrics(self.reply_label.font())
        full_text = self._format_reply_text()
        truncated_text = fm.elidedText(full_text, Qt.ElideRight, available_width - 30)
        self.reply_label.setText(truncated_text)

    def cancel_reply(self) -> None:
        chat_window = self.window()
        if hasattr(chat_window, 'client'):
            chat_window.client.reply_to_id = None
        if hasattr(chat_window, 'chat_components') and chat_window.chat_components.get('input'):
            chat_window.chat_components['input'].remove_reply_preview()
        self.deleteLater()

    def update_theme(self, theme: dict) -> None:
        # 更新外部容器的背景颜色为按钮背景色
        self.filling_wid.setStyleSheet(f"background-color: {theme['list_background']};border-radius: 0px;")
        # 更新字体颜色适配主题
        StyleGenerator.apply_style(self.reply_label, "label")
        # 更新关闭按钮样式
        StyleGenerator.apply_style(self.close_button, "button", extra="border-radius: 10px;")
        # 内部容器保持现有颜色
        self.background_container.setStyleSheet("background-color: rgba(200, 200, 200, 50); border-radius: 5px;")

class MessageInput(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(70)
        self.setAcceptDrops(True)
        self.reply_widget = None
        self._init_ui()
        self._DOWNLOAD_LABELS = ReplyPreviewWidget.DOWNLOAD_LABELS
        self.file = None

    def _init_ui(self) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.input_container = QWidget(self)
        input_layout = QGridLayout(self.input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(0)

        self.text_edit = CustomTextEdit(self.input_container)
        self.text_edit.setFont(FONTS['MESSAGE'])
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlaceholderText("请输入消息")
        style_text_edit(self.text_edit)
        self.text_edit.sendMessage.connect(self.on_send_message)

        self.emoticon_button = QPushButton("😊", self.input_container)
        self.emoticon_button.setFixedSize(30, 35)
        self.emoticon_button.clicked.connect(self.show_emoticon_popup)
        StyleGenerator.apply_style(self.emoticon_button, "button")

        self.plus_button = QPushButton("+", self.input_container)
        self.plus_button.setFixedSize(30, 35)
        StyleGenerator.apply_style(self.plus_button, "button")
        self.plus_button.clicked.connect(self.show_plus_menu)

        self.send_button = QPushButton("发送", self.input_container)
        self.send_button.setFixedSize(110, 70)
        StyleGenerator.apply_style(self.send_button, "button")
        self.send_button.clicked.connect(self.on_send_message)

        input_layout.addWidget(self.emoticon_button, 0, 0, Qt.AlignHCenter)
        input_layout.addWidget(self.plus_button, 1, 0, Qt.AlignHCenter)
        input_layout.addWidget(self.text_edit, 0, 1, 2, 1)
        input_layout.addWidget(self.send_button, 0, 2, 2, 1)
        input_layout.setRowMinimumHeight(0, 35)
        input_layout.setRowMinimumHeight(1, 35)
        input_layout.setColumnStretch(0, 0)
        input_layout.setColumnStretch(1, 1)
        input_layout.setColumnStretch(2, 1)

        self.main_layout.addWidget(self.input_container)
        self.setLayout(self.main_layout)
        self.popup: Optional[EmoticonPopup] = None

    def show_reply_preview(self, reply_to_id: int, reply_preview: str) -> None:
        if self.reply_widget:
            self.reply_widget.deleteLater()
        self.reply_widget = ReplyPreviewWidget(reply_to_id, reply_preview, self)
        self.main_layout.insertWidget(0, self.reply_widget)
        self.setFixedHeight(115)
        theme_manager.register(self.reply_widget)
        self.reply_widget.update_theme(theme_manager.current_theme)

    def remove_reply_preview(self) -> None:
        if self.reply_widget:
            self.reply_widget.deleteLater()  # 删除回复预览控件
            self.reply_widget = None
            self.setFixedHeight(70)  # 恢复输入框高度
            # 通知聊天窗口更新 reply_to_id
            chat_window = self.window()
            if hasattr(chat_window, 'client'):
                chat_window.client.reply_to_id = None

    def on_send_message(self) -> None:
        parent_obj = self.window()
        if parent_obj and hasattr(parent_obj, "send_message"):
            asyncio.create_task(parent_obj.send_message())

    def show_emoticon_popup(self) -> None:
        self.popup = EmoticonPopup(self)
        self.popup.emoticonClicked.connect(self.insert_emoticon)
        self.popup.adjustSize()
        btn_pos = self.emoticon_button.mapToGlobal(self.emoticon_button.rect().topLeft())
        self.popup.move(btn_pos.x(), btn_pos.y() - self.popup.height())
        self.popup.show()

    def insert_emoticon(self, emo: str) -> None:
        cursor = self.text_edit.textCursor()
        cursor.insertText(emo)
        self.text_edit.setTextCursor(cursor)

    def show_plus_menu(self) -> None:
        menu = QMenu(self)
        file_filters = {
            'file': ("文件", "所有文件 (*.*)"),
            'image': ("图片", "图片文件 (*.jpg *.jpeg *.png *.gif *.bmp)"),
            'video': ("视频", "视频文件 (*.mp4 *.avi *.mkv *.mov *.wmv)")
        }
        for f_type, (label, filt) in file_filters.items():
            menu.addAction(label, lambda ft=f_type: self.send_file(ft))
        StyleGenerator.apply_style(self, "menu")
        menu.exec_(self.plus_button.mapToGlobal(self.plus_button.rect().bottomLeft()))

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def send_file(self, file_type: str) -> None:
        filters = {
            'file': "所有文件 (*.*)",
            'image': "图片文件 (*.jpg *.jpeg *.png *.gif *.bmp)",
            'video': "视频文件 (*.mp4 *.avi *.mkv *.mov *.wmv)"
        }
        file_paths, _ = QFileDialog.getOpenFileNames(self, f"选择{self._DOWNLOAD_LABELS.get(file_type, '文件')}", "", filters.get(file_type, ""))
        if not file_paths:
            return
        chat_window = self.window()
        if hasattr(chat_window, 'send_multiple_media'):
            asyncio.create_task(chat_window.send_multiple_media(file_paths))
        else:
            QMessageBox.critical(self, "错误", "无法发送文件：未找到聊天窗口方法")

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if file_paths:
            chat_window = self.window()
            if hasattr(chat_window, 'send_multiple_media'):
                asyncio.create_task(chat_window.send_multiple_media(file_paths))
            else:
                QMessageBox.critical(self, "错误", "无法发送文件：未找到聊天窗口方法")
            event.acceptProposedAction()