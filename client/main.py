#!/usr/bin/env python3
import sys
import os
import asyncio
import ctypes
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Callable

from PyQt5.QtCore import Qt, QSize, QTimer, QRegularExpression, QEvent
from PyQt5.QtGui import QIcon, QRegularExpressionValidator
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QGridLayout, QLineEdit,
    QHBoxLayout, QLabel, QDialog, QMessageBox, QListWidget,
    QListWidgetItem, QSystemTrayIcon, QMenu, QVBoxLayout, QScrollArea, QFrame
)
from qasync import QEventLoop

from chat_client import ChatClient
from Interface_Controls import (
    MessageInput, FriendItemWidget, ChatAreaWidget, ChatBubbleWidget,
    OnLine, theme_manager, StyleGenerator, generate_thumbnail)
from client.Viewer import ImageViewer


# 用于闪烁任务栏图标
class FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("hwnd", ctypes.c_void_p),
        ("dwFlags", ctypes.c_uint),
        ("uCount", ctypes.c_uint),
        ("dwTimeout", ctypes.c_uint),
    ]

def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, '_MEIPASS', os.path.abspath('.'))
    return os.path.join(base_path, relative_path)

def format_time(timestamp: str) -> str:
    try:
        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%H:%M") if datetime.now() - dt < timedelta(days=1) else dt.strftime("%m.%d %H:%M")
    except ValueError:
        return datetime.now().strftime("%H:%M")

def create_themed_message_box(parent: QWidget, title: str, text: str) -> QMessageBox:
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(QMessageBox.Information)
    theme = theme_manager.current_theme
    msg_box.setStyleSheet(f"QLabel {{ color: {theme.get('TEXT_COLOR', '#ffffff')}; }}")
    ok_button = msg_box.addButton("确认", QMessageBox.AcceptRole)
    ok_button.setFixedSize(50, 25)
    StyleGenerator.apply_style(ok_button, "button", extra="border-radius: 4px;")
    for label in msg_box.findChildren(QLabel):
        StyleGenerator.apply_style(label, "label")
    return msg_box

def create_line_edit(parent: QWidget, placeholder: str, echo: QLineEdit.EchoMode) -> QLineEdit:
    le = QLineEdit(parent)
    le.setPlaceholderText(placeholder)
    le.setMinimumHeight(30)
    le.setEchoMode(echo)
    StyleGenerator.apply_style(le, "line_edit")
    regex = QRegularExpression(r'^[a-zA-Z0-9!@#$%^&*()_+={}\[\]:;"\'<>,.?/\\|`~\-]*$')
    le.setValidator(QRegularExpressionValidator(regex, le))
    return le

def run_async(coro) -> None:
    asyncio.create_task(coro)

# 登录窗口
class LoginWindow(QDialog):
    def __init__(self, main_app: "ChatApp") -> None:
        super().__init__()
        self.main_app = main_app
        self.chat_client = ChatClient()
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("ChatINL 登录")
        self.setFixedSize(250, 110)
        self.setWindowIcon(QIcon(resource_path("icon.ico")))

        layout = QGridLayout(self)
        self.username_input = create_line_edit(self, "请输入账号", QLineEdit.Normal)
        self.password_input = create_line_edit(self, "请输入密码", QLineEdit.Password)
        self.login_button = QPushButton("登录", self)
        self.login_button.setMinimumHeight(30)
        StyleGenerator.apply_style(self.login_button, "button", extra="border-radius: 4px;")
        self.login_button.clicked.connect(self.on_login)

        layout.addWidget(self.username_input, 0, 1)
        layout.addWidget(self.password_input, 1, 1)
        layout.addWidget(self.login_button, 2, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(2, 1)

    def on_login(self) -> None:
        username, password = self.username_input.text().strip(), self.password_input.text().strip()
        if not username or not password:
            QMessageBox.critical(self, "错误", "账号或密码不能为空")
        elif not self.chat_client or not self.chat_client.client_socket:
            QMessageBox.critical(self, "错误", "未连接到服务器，请检查网络或重试")
        else:
            run_async(self.async_login(username, password))

    async def async_login(self, username: str, password: str) -> None:
        res = await self.chat_client.authenticate(username, password)
        if res == "认证成功":
            self.accept()
            run_async(self.chat_client.start_reader())
            if not self.main_app.chat_window:
                self.main_app.chat_window = ChatWindow(self.chat_client, self.main_app)
            self.chat_client.on_new_message_callback = self.main_app.chat_window.handle_new_message
            self.chat_client.on_new_media_callback = self.main_app.chat_window.handle_new_message
            self.chat_client.on_friend_list_update_callback = self.main_app.chat_window.update_friend_list
            self.main_app.chat_window.show()
        else:
            QMessageBox.critical(self, "错误", res)

    def closeEvent(self, event) -> None:
        self.main_app.quit_app()
        event.accept()

# 添加好友对话框
class AddFriendDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("添加好友")
        self.setFixedSize(300, 100)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.label = QLabel("请输入好友用户名：", self)
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("好友用户名")
        self.input.setFixedHeight(30)
        StyleGenerator.apply_style(self.input, "line_edit")

        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("取消", self)
        self.cancel_btn.setFixedHeight(30)
        StyleGenerator.apply_style(self.cancel_btn, "button", extra="border-radius: 4px;")
        self.cancel_btn.clicked.connect(self.reject)
        self.confirm_btn = QPushButton("确认", self)
        self.confirm_btn.setFixedHeight(30)
        StyleGenerator.apply_style(self.confirm_btn, "button", extra="border-radius: 4px;")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.accept)

        layout.addWidget(self.label)
        layout.addWidget(self.input)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.confirm_btn)
        layout.addLayout(btn_layout)

        self.input.textChanged.connect(lambda text: self.confirm_btn.setEnabled(bool(text.strip())))
        self.update_theme(theme_manager.current_theme)

    def update_theme(self, theme: dict) -> None:
        StyleGenerator.apply_style(self.label, "label")
        StyleGenerator.apply_style(self.input, "text_edit")

# 聊天窗口
class ChatWindow(QWidget):
    def __init__(self, client: ChatClient, main_app: "ChatApp") -> None:
        super().__init__()
        self.client = client
        self.main_app = main_app
        self.auto_scrolling = False
        self.last_message_times: Dict[str, str] = {}
        self.unread_messages: Dict[str, int] = {}
        self.current_page = 1
        self.page_size = 20
        self.loading_history = False
        self.has_more_history = True
        self.chat_components: Dict[str, Optional[QWidget]] = {k: None for k in
            ['area_widget', 'scroll', 'input', 'send_button', 'online', 'chat']}
        self.scroll_to_bottom_btn: Optional[QPushButton] = None
        self.add_friend_dialog: Optional[AddFriendDialog] = None
        self._setup_window()
        self._setup_ui()
        theme_manager.register(self)
        self.active_bubbles = {}
        self.image_viewer = None
        self.image_list = []

    def _setup_window(self) -> None:
        self.setWindowTitle(f"ChatINL 用户: {self.client.username}")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.setMinimumSize(450, 500)
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry((screen.width() - 700) // 2, (screen.height() - 500) // 2, 700, 500)

    def _setup_ui(self) -> None:
        main_layout = QGridLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.theme_panel = self._create_panel(self._create_theme_buttons, 0)
        self.left_panel = self._create_friend_list_panel()
        self.content_widget = self._create_content_widget()

        main_layout.addWidget(self.theme_panel, 0, 0)
        main_layout.addWidget(self.left_panel, 0, 1)
        main_layout.addWidget(self.content_widget, 0, 2)
        main_layout.setColumnStretch(2, 1)
        self._update_friend_list_width()

    def _create_panel(self, button_setup: Callable[[QVBoxLayout], None], width: int) -> QWidget:
        panel = QWidget(self)
        panel.setFixedWidth(width)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        button_setup(layout)
        layout.addStretch()
        return panel

    def _create_theme_buttons(self, layout: QVBoxLayout) -> None:
        for icon, mode in (("Day_Icon.ico", "light"), ("Night_Icon.ico", "dark")):
            btn = QPushButton(self)
            btn.setFixedHeight(30)
            StyleGenerator.apply_style(btn, "button", extra="border-radius: 4px;")
            btn.setIcon(QIcon(resource_path(icon)))
            btn.setIconSize(QSize(15, 15))
            btn.clicked.connect(lambda _, m=mode: self.set_mode(m))
            layout.addWidget(btn)

    def _create_friend_list_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        top_layout = QHBoxLayout()
        self.mode_switch_button = QPushButton("<", panel)
        self.mode_switch_button.setFixedSize(20, 40)
        StyleGenerator.apply_style(self.mode_switch_button, "button")
        self.mode_switch_button.clicked.connect(self.toggle_theme_panel)
        self.add_button = QPushButton(panel)
        self.add_button.setFixedHeight(40)
        StyleGenerator.apply_style(self.add_button, "button")
        self.add_button.setIcon(QIcon(resource_path("Add_Icon.ico")))
        self.add_button.setIconSize(QSize(25, 25))
        self.add_button.clicked.connect(lambda: run_async(self.async_show_add_friend()))

        top_layout.addWidget(self.mode_switch_button)
        top_layout.addWidget(self.add_button)
        top_layout.addStretch()

        self.friend_list = QListWidget(panel)
        self.friend_list.setSelectionMode(QListWidget.SingleSelection)
        self.friend_list.setFocusPolicy(Qt.StrongFocus)
        StyleGenerator.apply_style(self.friend_list, "list_widget")
        self.friend_list.verticalScrollBar().setStyleSheet(StyleGenerator._BASE_STYLES["scrollbar"].format(**theme_manager.current_theme))
        self.friend_list.itemClicked.connect(lambda item: run_async(self.select_friend(item)))

        layout.addLayout(top_layout)
        layout.addWidget(self.friend_list)
        return panel

    def _create_content_widget(self) -> QWidget:
        content = QWidget(self)
        self.content_layout = QGridLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.default_label = QLabel(self)
        self.default_label.setPixmap(QIcon(resource_path("icon.ico")).pixmap(128, 128))
        self.default_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.default_label, 0, 0, Qt.AlignCenter)
        return content

    def toggle_theme_panel(self) -> None:
        new_width = 50 if self.theme_panel.width() == 0 else 0
        delta = new_width - self.theme_panel.width()
        self.theme_panel.setFixedWidth(new_width)
        if not self.isMaximized():
            self.resize(self.width() + delta, self.height())

    def set_mode(self, mode: str) -> None:
        theme_manager.set_mode(mode)
        self.update_theme(theme_manager.current_theme)

    def update_theme(self, theme: dict) -> None:
        self.setStyleSheet(f"background-color: {theme['MAIN_INTERFACE']};")
        if hasattr(self, "friend_list"):
            StyleGenerator.apply_style(self.friend_list, "list_widget")
        self.friend_list.verticalScrollBar().setStyleSheet(StyleGenerator._BASE_STYLES["scrollbar"].format(**theme_manager.current_theme))
        if (scroll := self.chat_components.get('scroll')):
            scroll.viewport().setStyleSheet(f"background-color: {theme['chat_bg']};")
            StyleGenerator.apply_style(scroll, "scrollbar")
        if (chat := self.chat_components.get('chat')):
            chat.setStyleSheet(f"background-color: {theme['chat_bg']};")
        if (input_widget := self.chat_components.get('input')):
            StyleGenerator.apply_style(input_widget.text_edit, "text_edit")
        if (send_btn := self.chat_components.get('send_button')):
            StyleGenerator.apply_style(send_btn, "button")
        if (online := self.chat_components.get('online')):
            online.update_theme(theme)
        if self.add_friend_dialog and self.add_friend_dialog.isVisible():
            self.add_friend_dialog.update_theme(theme)
        if self.scroll_to_bottom_btn:
            StyleGenerator.apply_style(self.scroll_to_bottom_btn, "button", extra="border-radius: 15px;")
        if self.image_viewer:
            self.image_viewer.setStyleSheet(f"background-color: rgba(0, 0, 0, 220);")
            StyleGenerator.apply_style(self.image_viewer.prev_button, "button", extra="border-radius: 25px;")
            StyleGenerator.apply_style(self.image_viewer.next_button, "button", extra="border-radius: 25px;")
            StyleGenerator.apply_style(self.image_viewer.close_button, "button", extra="border-radius: 15px;")

    def resizeEvent(self, event) -> None:
        self._update_friend_list_width()
        if self.scroll_to_bottom_btn:
            self._position_scroll_button()
        if self.image_viewer and self.image_viewer.isVisible() and self.chat_components.get('scroll'):
            viewport = self.chat_components['scroll'].viewport()
            self.image_viewer.setGeometry(viewport.geometry())  # 确保调整时更新大小
        super().resizeEvent(event)
        print(f"ChatWindow resized to {self.size()}")

    def _update_friend_list_width(self) -> None:
        width = 75 if self.width() <= 500 else 180
        self.friend_list.setFixedWidth(width)
        self.add_button.setFixedWidth(width - self.mode_switch_button.width() - 2)

    def clear_chat_area(self) -> None:
        for comp in self.chat_components.values():
            if comp:
                comp.deleteLater()
        self.chat_components = {k: None for k in ['area_widget', 'scroll', 'input', 'send_button', 'online', 'chat']}
        if self.scroll_to_bottom_btn:
            self.scroll_to_bottom_btn.deleteLater()
            self.scroll_to_bottom_btn = None
        self.default_label.show()

    def setup_chat_area(self) -> None:
        self.default_label.hide()
        if self.chat_components.get('chat'):  # 如果已存在聊天区域，先清理
            self.clear_chat_area()
        self.chat_components['area_widget'] = QWidget(self)
        area_layout = QVBoxLayout(self.chat_components['area_widget'])
        area_layout.setContentsMargins(0, 0, 0, 0)
        area_layout.setSpacing(0)
        self.chat_components['online'] = OnLine(self)
        self.chat_components['online'].setStyleSheet("border: none; background-color: #ffffff;")
        self.chat_components['online'].setFixedHeight(50)
        self.chat_components['chat'] = ChatAreaWidget(self)
        self.chat_components['chat'].setStyleSheet(f"background-color: #e9e9e9;")
        self.chat_components['scroll'] = QScrollArea(self)
        self.chat_components['scroll'].setWidgetResizable(True)
        self.chat_components['scroll'].setFrameShape(QFrame.NoFrame)
        self.chat_components['scroll'].setWidget(self.chat_components['chat'])
        self.chat_components['scroll'].viewport().setStyleSheet("background-color: #e9e9e9; border: none;")
        StyleGenerator.apply_style(self.chat_components['scroll'],"scrollbar")
        sb = self.chat_components['scroll'].verticalScrollBar()
        sb.valueChanged.connect(self.on_scroll_changed)
        self._create_scroll_button(theme_manager.current_theme)
        area_layout.addWidget(self.chat_components['online'])
        area_layout.addWidget(self.chat_components['scroll'])
        self.chat_components['input'] = MessageInput(self)
        self.chat_components['input'].setFixedHeight(70)
        self.chat_components['send_button'] = QPushButton("发送", self)
        self.chat_components['send_button'].setFixedSize(110, 70)
        StyleGenerator.apply_style(self.chat_components['send_button'],"button")
        self.chat_components['send_button'].clicked.connect(lambda: asyncio.create_task(self.send_message()))
        self.content_layout.addWidget(self.chat_components['area_widget'], 0, 0, 1, 2)
        self.content_layout.addWidget(self.chat_components['input'], 1, 0)
        self.content_layout.addWidget(self.chat_components['send_button'], 1, 1)
        self.image_viewer = ImageViewer(self.chat_components['scroll'].viewport())
        self.image_viewer.hide()  # 默认隐藏
        theme_manager.register(self.image_viewer)
        self.update_theme(theme_manager.current_theme)

    def _create_scroll_button(self, theme: dict) -> None:
        if not self.scroll_to_bottom_btn and self.chat_components.get('scroll'):
            self.scroll_to_bottom_btn = QPushButton(self.chat_components['scroll'].viewport())
            self.scroll_to_bottom_btn.setFixedSize(30, 30)
            self.scroll_to_bottom_btn.clicked.connect(self.on_scroll_button_clicked)
            StyleGenerator.apply_style(self.scroll_to_bottom_btn, "button", extra="border-radius: 15px;")
            self.scroll_to_bottom_btn.setIcon(QIcon(resource_path("arrow_down.ico")))
            self.scroll_to_bottom_btn.setIconSize(QSize(15, 15))
            self.scroll_to_bottom_btn.hide()

    async def show_image_viewer(self, file_id: str, original_file_name: str) -> None:
        """显示图片查看器并加载指定图片"""
        if not self.image_viewer or not self.chat_components.get('scroll'):
            return
        print(f"Viewport size: {self.chat_components['scroll'].viewport().size()}")

        current_index = next((i for i, (fid, _) in enumerate(self.image_list) if fid == file_id), 0)
        self.image_viewer.set_image_list(self.image_list, current_index)

        scroll = self.chat_components['scroll']
        viewport = scroll.viewport()
        # 调整 ImageViewer 大小以覆盖 viewport 区域，不改变父控件
        self.image_viewer.setGeometry(viewport.geometry())
        # 记录当前滚动条的位置和滚动区域引用
        self.image_viewer._previous_scroll_value = scroll.verticalScrollBar().value()
        self.image_viewer.scroll_area = scroll
        # 禁用滚动条，避免用户操作底下内容
        scroll.verticalScrollBar().setEnabled(False)
        scroll.horizontalScrollBar().setEnabled(False)

        self.image_viewer.show()
        self.image_viewer.raise_()
        print(f"ImageViewer shown with size: {self.image_viewer.size()}")

    def _reset_chat_area(self) -> None:
        self.clear_chat_area()
        self.setup_chat_area()
        self.current_page = 1
        self.has_more_history = True
        if self.image_viewer:
            self.image_viewer.hide()
        self.image_list.clear()

    def on_scroll_button_clicked(self) -> None:
        self.adjust_scroll()
        if self.client.current_friend:
            self.unread_messages[self.client.current_friend] = 0
            run_async(self.update_friend_list())
        self.scroll_to_bottom_btn.hide()

    def on_scroll_changed(self, value: int) -> None:
        sb = self.chat_components['scroll'].verticalScrollBar()
        if value == 0 and self.has_more_history and not self.loading_history:
            run_async(self.load_chat_history(reset=False))
        self._check_scroll_position()
        if (self.client.current_friend and
            self.unread_messages.get(self.client.current_friend, 0) > 0 and
            not self.auto_scrolling and sb.maximum() - value <= 5):
            self.unread_messages[self.client.current_friend] = 0
            run_async(self.update_friend_list())

    def _scroll_to_bottom(self) -> None:
        """确保界面更新完成后，将滚动条滚动到最底部"""
        QApplication.processEvents()
        scroll = self.chat_components.get('scroll')
        if scroll:
            sb = scroll.verticalScrollBar()
            sb.setValue(sb.maximum())
            self._check_scroll_position()
        self.auto_scrolling = False

    def adjust_scroll(self) -> None:
        """先触发更新，再将滚动条滚到底部"""
        self.auto_scrolling = True
        if self.chat_components.get('chat'):
            self.chat_components['chat'].update()
        QApplication.processEvents()
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _check_scroll_position(self) -> None:
        sb = self.chat_components['scroll'].verticalScrollBar()
        should_show = (self.client.current_friend and
                       self.unread_messages.get(self.client.current_friend, 0) > 0 and
                       sb.maximum() - sb.value() > 50)
        self._create_scroll_button(theme_manager.current_theme)
        if should_show:
            self._position_scroll_button()
            self.scroll_to_bottom_btn.show()
        else:
            self.scroll_to_bottom_btn.hide()

    def _position_scroll_button(self) -> None:
        if self.scroll_to_bottom_btn and (scroll := self.chat_components.get('scroll')):
            viewport = scroll.viewport()
            x = max(10, viewport.width() - self.scroll_to_bottom_btn.width() - 10)
            y = max(10, viewport.height() - self.scroll_to_bottom_btn.height() - 10)
            self.scroll_to_bottom_btn.move(x, y)

    def should_scroll_to_bottom(self) -> bool:
        sb = self.chat_components['scroll'].verticalScrollBar()
        return (sb.maximum() - sb.value()) < self.chat_components['scroll'].viewport().height()

    async def add_message(self, message: str, is_current: bool, tstr: str, message_type: str = 'text',
                          file_id: str = None, original_file_name: str = None, thumbnail_path: str = None,
                          file_size: str = None, duration: str = None) -> None:
        bubble = ChatBubbleWidget(
            message, tstr, "right" if is_current else "left", is_current,
            message_type, file_id, original_file_name, thumbnail_path, file_size, duration
        )
        self.chat_components['chat'].addBubble(bubble)
        if message_type == 'image' and file_id:
            self.image_list.append((file_id, original_file_name or f"image_{file_id}"))
            print(f"Added to image_list: {file_id}, {original_file_name}")  # 调试输出
        if is_current or self.should_scroll_to_bottom():
            self.adjust_scroll()

    async def _handle_message(self, sender: str, msg: str, is_current: bool, wt: str, received: bool,
                              message_type: str = 'text', file_id: str = None, original_file_name: str = None,
                              thumbnail_path: str = None, file_size: str = None, duration: str = None) -> None:
        self.last_message_times[sender] = wt
        if sender == self.client.current_friend:
            if received and file_size and message_type != 'image' and isinstance(file_size, str) and 'KB' in file_size:
                file_size = f"{float(file_size.replace('KB', '').strip()) / 1024:.2f} MB"
            await self.add_message(msg, is_current, format_time(wt), message_type, file_id, original_file_name,
                                   thumbnail_path, file_size, duration)
            if received:
                if self.should_scroll_to_bottom():
                    self.adjust_scroll()
                    self.unread_messages[sender] = 0
                else:
                    self.unread_messages[sender] = self.unread_messages.get(sender, 0) + 1
                    self._check_scroll_position()
        else:
            self.unread_messages[sender] = self.unread_messages.get(sender, 0) + 1
        if not self.isVisible() or self.isMinimized():
            self.show_notification(f"用户 {sender}:", msg)
        await self.update_friend_list()

    async def send_message(self) -> None:
        text = self.chat_components['input'].text_edit.toPlainText().strip()
        if not text or not self.client.current_friend:
            return
        await self.client.send_message(self.client.current_friend, text)
        wt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bubble = ChatBubbleWidget(
            text, format_time(wt), "right", True, "text"
        )
        self.chat_components['chat'].addBubble(bubble)  # 单独添加
        self.adjust_scroll()
        self.chat_components['input'].text_edit.clear()

    async def send_media(self, file_path: str, file_type: str) -> None:
        """保留原有单文件上传逻辑，仅为兼容性保留"""
        await self.send_multiple_media([file_path])

    async def send_multiple_media(self, file_paths: List[str]) -> None:
        if not self.client.current_friend:
            return

        # 为每个文件创建气泡
        bubbles = {}
        for file_path in file_paths:
            file_type = self.client._detect_file_type(file_path)
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            file_size_str = f"{file_size_mb:.2f} MB"
            thumbnail_path = generate_thumbnail(file_path, file_type) if file_type in ('image', 'video') else None

            wt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            bubble = ChatBubbleWidget(
                "", format_time(wt), "right", True, file_type, None,
                os.path.basename(file_path), thumbnail_path, file_size_str, None
            )
            self.chat_components['chat'].addBubble(bubble)
            bubbles[file_path] = bubble
        self.adjust_scroll()

        # 进度回调
        async def progress_callback(type_, progress, filename):
            file_path = next((fp for fp in bubbles if os.path.basename(fp) == filename), None)
            if file_path and type_ == "upload":
                bubbles[file_path].update_progress(progress)
                QApplication.processEvents()

        # 并发上传
        results = await self.client.send_multiple_media(self.client.current_friend, file_paths, progress_callback)
        for file_path, res in zip(file_paths, results):
            bubble = bubbles[file_path]
            if res.get("status") == "success":
                bubble.file_id = res.get("file_id")
                bubble.duration = res.get("duration")
                bubble.complete_progress()
                # 如果是图片，添加到 image_list
                if self.client._detect_file_type(file_path) == "image" and bubble.file_id:
                    self.image_list.insert(0,(bubble.file_id, os.path.basename(file_path) or f"image_{bubble.file_id}"))
                    print(f"Added sent image to image_list: {bubble.file_id}, {os.path.basename(file_path)}")  # 调试输出
            else:
                bubble.complete_progress()
                QMessageBox.critical(self, "错误", f"发送失败: {res.get('message')}")

    async def handle_new_message(self, res: dict) -> None:
        sender = res["from"]
        wt = res["write_time"]
        msg_type = res.get("type", "new_message")

        msg = res.get("message", "") if msg_type == "new_message" else ""
        file_id = res.get("file_id")
        file_type = res.get("file_type")
        original_file_name = res.get("original_file_name")
        thumbnail_path = res.get("thumbnail_path")
        file_size = res.get("file_size")
        duration = res.get("duration")
        file_size_str = None
        if file_size and isinstance(file_size, (int, float)):
            file_size_mb = file_size / (1024 * 1024)
            file_size_str = f"{file_size_mb:.2f} MB"
        elif file_size:
            file_size_str = file_size

        self.last_message_times[sender] = wt
        self.unread_messages[sender] = self.unread_messages.get(sender, 0) + 1

        # 如果是图片消息，添加到 image_list
        if msg_type == "new_media" and file_type == "image" and file_id:
            self.image_list.insert(0, (file_id, original_file_name or f"image_{file_id}"))
            print(f"Added received image to image_list: {file_id}, {original_file_name}")  # 调试输出

        if sender == self.client.current_friend:
            if not self.chat_components.get('chat'):
                self.setup_chat_area()
            bubble_type = file_type if msg_type == "new_media" else "text"
            bubble = ChatBubbleWidget(
                msg, format_time(wt), "left", False, bubble_type,
                file_id, original_file_name, thumbnail_path, file_size_str, duration
            )
            self.chat_components['chat'].addBubble(bubble)  # 单独添加
            if self.should_scroll_to_bottom():
                self.adjust_scroll()
                self.unread_messages[sender] = 0
            else:
                self._check_scroll_position()

        notification_msg = msg if msg_type == "new_message" else f"收到新的{file_type}: {original_file_name or '未知文件'}"
        self.show_notification(f"用户 {sender}:", notification_msg)
        await self.update_friend_list()

    def _sort_friends(self, friends: List[dict]) -> List[dict]:
        online = sorted(
            [f for f in friends if f.get("online")],
            key=lambda x: self.last_message_times.get(x["username"], "1970-01-01 00:00:00"), reverse=True
        )
        offline = sorted(
            [f for f in friends if not f.get("online")],
            key=lambda x: self.last_message_times.get(x["username"], "1970-01-01 00:00:00"), reverse=True
        )
        return online + offline

    async def update_friend_list(self, friends: Optional[List[dict]] = None) -> None:
        friends = friends or self.client.friends
        current_friend = self.client.current_friend
        self.friend_list.clear()
        for friend in self._sort_friends(friends):
            uname = friend["username"]
            unread_count = self.unread_messages.get(uname, 0)
            item = QListWidgetItem(self.friend_list)
            item.setSizeHint(QSize(0, 40))
            widget = FriendItemWidget(uname, friend.get("online", False), unread_count)
            self.friend_list.setItemWidget(item, widget)
            theme_manager.register(widget)
            if uname == current_friend:
                item.setSelected(True)
                if (online := self.chat_components.get('online')):
                    online.update_status(uname, friend.get("online", False))
        for i in range(self.friend_list.count()):
            if widget := self.friend_list.itemWidget(self.friend_list.item(i)):
                widget.update_theme(theme_manager.current_theme)

    async def load_chat_history(self, reset: bool = False) -> None:
        if reset:
            self._reset_chat_area()
        if not self.client.current_friend or not self.has_more_history:
            return

        self.loading_history = True
        sb = self.chat_components.get('scroll', {}).verticalScrollBar()
        old_val = sb.value() if sb else 0

        res = await self.client.get_chat_history_paginated(
            self.client.current_friend, self.current_page, self.page_size
        )
        if res and res.get("type") == "chat_history" and (messages := res.get("data", [])):
            bubbles = []
            for msg in messages:
                file_size = msg.get("file_size", 0)
                if isinstance(file_size, (int, float)):
                    file_size_str = f"{file_size / (1024 * 1024):.2f} MB"
                else:
                    file_size_str = file_size
                bubble = ChatBubbleWidget(
                    msg.get("message", ""), format_time(msg.get("write_time", "")),
                    "right" if msg.get("is_current_user") else "left", msg.get("is_current_user", False),
                    msg.get("attachment_type", "text"), msg.get("file_id"), msg.get("original_file_name"),
                    msg.get("thumbnail_path"), file_size_str, msg.get("duration")
                )
                bubbles.append(bubble)
                # 如果是图片消息，添加到图片列表
                if msg.get("attachment_type") == "image" and msg.get("file_id"):
                    self.image_list.append(
                        (msg.get("file_id"), msg.get("original_file_name") or f"image_{msg.get('file_id')}"))
            self.chat_components['chat'].addBubbles(bubbles)

            def update_and_scroll():
                for bubble in bubbles:
                    bubble.updateBubbleSize()
                QApplication.processEvents()
                if reset and sb:
                    sb.setValue(sb.maximum())
                    if sb.value() != sb.maximum():
                        sb.setValue(sb.maximum())
                elif sb:
                    self.auto_scrolling = True
                    inserted = sum(b.sizeHint().height() for b in bubbles)
                    sb.setValue(old_val + inserted)
                    self.auto_scrolling = False
                self._check_scroll_position()

            QTimer.singleShot(0, update_and_scroll)
            self.has_more_history = len(messages) >= self.page_size
            if self.has_more_history:
                self.current_page += 1
        self.loading_history = False

    async def select_friend(self, item: Optional[QListWidgetItem]) -> None:
        if not item:
            self.clear_chat_area()
            self.client.current_friend = None
            return
        friend = self.friend_list.itemWidget(item).username
        if friend == self.client.current_friend:
            return
        self.client.current_friend = friend
        self._reset_chat_area()
        await self.load_chat_history(reset=True)
        online_status = any(f["username"] == friend and f.get("online", False) for f in self.client.friends)
        self.chat_components['online'].update_status(friend, online_status)
        sb = self.chat_components['scroll'].verticalScrollBar()
        if sb.maximum() - sb.value() <= 5:
            self.unread_messages[friend] = 0
        await self.update_friend_list()

    def show_notification(self, sender: str, msg: str) -> None:
        self.notification_sender = sender.replace("用户 ", "").rstrip(":")
        self.main_app.tray_icon.showMessage(sender, msg, QIcon(resource_path("icon.ico")), 2000)
        self.flash_taskbar_icon()

    def on_notification_clicked(self) -> None:
        if not hasattr(self, 'notification_sender'):
            return
        if self.isMinimized() or not self.isVisible():
            self.showNormal()
        self.activateWindow()
        for i in range(self.friend_list.count()):
            item = self.friend_list.item(i)
            if (widget := self.friend_list.itemWidget(item)) and widget.username == self.notification_sender:
                self.friend_list.setCurrentItem(item)
                run_async(self.select_friend(item))
                break
        delattr(self, 'notification_sender')

    async def async_show_add_friend(self) -> None:
        if self.add_friend_dialog and self.add_friend_dialog.isVisible():
            self.add_friend_dialog.raise_()
            self.add_friend_dialog.activateWindow()
            return
        dialog = AddFriendDialog(self)
        self.add_friend_dialog = dialog
        fut = asyncio.get_running_loop().create_future()

        def set_future_result(_):
            if not fut.done():  # 仅在未完成时设置结果
                fut.set_result(None)

        dialog.finished.connect(set_future_result)
        dialog.confirm_btn.clicked.connect(lambda: run_async(self.proc_add_friend(dialog)))
        dialog.show()
        await fut
        self.add_friend_dialog = None

    async def proc_add_friend(self, dialog: AddFriendDialog) -> None:
        if friend_name := dialog.input.text().strip():
            res = await self.client.add_friend(friend_name)
            create_themed_message_box(self, "提示", res).exec_()
            dialog.accept()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.friend_list.clearSelection()
        self.clear_chat_area()
        self.client.current_friend = None
        self.hide()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.friend_list.clearSelection()
            self.clear_chat_area()
            self.client.current_friend = None
        super().keyPressEvent(event)

    def flash_taskbar_icon(self) -> None:
        hwnd = int(self.winId())
        flash_info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 3, 10, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(flash_info))

    def stop_flash_taskbar_icon(self) -> None:
        hwnd = int(self.winId())
        flash_info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0, 0, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(flash_info))

    def event(self, event) -> bool:
        if event.type() == QEvent.WindowActivate:
            self.stop_flash_taskbar_icon()
        return super().event(event)

# 主应用类
class ChatApp:
    def __init__(self) -> None:
        self.app = QApplication(sys.argv)
        self.tray_icon = QSystemTrayIcon(self.app)
        self._setup_tray()
        self.loop = QEventLoop(self.app)
        asyncio.set_event_loop(self.loop)
        self.login_window = LoginWindow(self)
        self.chat_window: Optional[ChatWindow] = None

    def _setup_tray(self) -> None:
        self.tray_icon.setIcon(QIcon(resource_path("icon.ico")))
        self.tray_icon.setToolTip("ChatINL")
        menu = QMenu()
        menu.addAction("打开主界面", lambda: self.on_tray_activated(QSystemTrayIcon.Trigger))
        menu.addAction("退出", self.quit_app)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.messageClicked.connect(self.on_notification_clicked)
        self.tray_icon.show()

    def on_tray_activated(self, reason: int) -> None:
        if reason == QSystemTrayIcon.Trigger:
            window = self.chat_window or self.login_window
            window.show()
            window.activateWindow()

    def on_notification_clicked(self) -> None:
        if self.chat_window:
            self.chat_window.on_notification_clicked()

    def quit_app(self) -> None:
        async def shutdown():
            try:
                if self.login_window.chat_client and self.login_window.chat_client.client_socket:
                    await self.login_window.chat_client.close_connection()
            except Exception as ex:
                QMessageBox.critical(self.login_window, '错误', f"退出时关闭连接异常: {ex}", QMessageBox.Ok)
            for task in [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]:
                task.cancel()
            await asyncio.gather(*asyncio.all_tasks(), return_exceptions=True)
            await self.loop.shutdown_asyncgens()
            self.tray_icon.hide()
            self.loop.stop()
            self.app.quit()
        run_async(shutdown())

    def run(self) -> None:
        self.login_window.show()
        with self.loop:
            sys.exit(self.loop.run_forever())

def main() -> None:
    ChatApp().run()

if __name__ == '__main__':
    main()
