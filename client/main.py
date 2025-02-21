#!/usr/bin/env python3
# main.py
import sys, os, asyncio, ctypes
from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, QSize, QTimer, QRegularExpression, QEvent
from PyQt5.QtGui import QIcon, QRegularExpressionValidator
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QGridLayout, QLineEdit,
    QHBoxLayout, QLabel, QDialog, QMessageBox, QListWidget,
    QListWidgetItem, QSystemTrayIcon, QMenu, QVBoxLayout, QScrollArea, QFrame)
from qasync import QEventLoop

# 项目内部模块
from chat_client import ChatClient
from Interface_Controls import (
    MessageInput, FriendItemWidget, ChatAreaWidget, ChatBubbleWidget,
    style_button, style_line_edit, style_list_widget, style_scrollbar,
    OnLine, style_rounded_button, style_text_edit, theme_manager, style_label, circle_button_style, get_scrollbar_style)

# ------------------ 新增 ------------------
# 定义 FlashWindowEx 使用的结构体，用于任务栏图标闪烁（仅 Windows 有效）
class FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("hwnd", ctypes.c_void_p),
        ("dwFlags", ctypes.c_uint),
        ("uCount", ctypes.c_uint),
        ("dwTimeout", ctypes.c_uint),
    ]
# ------------------ 公共辅助函数 ------------------
def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, '_MEIPASS', os.path.abspath('.'))
    return os.path.join(base_path, relative_path)

def format_time(timestamp: str) -> str:
    try:
        t = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        return t.strftime("%H:%M") if datetime.now() - t < timedelta(days=1) else t.strftime("%m.%d %H:%M")
    except Exception:
        return datetime.now().strftime("%H:%M")

def create_themed_message_box(parent: QWidget, title: str, text: str) -> QMessageBox:
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(QMessageBox.Information)
    current_theme = theme_manager.current_theme
    msg_box.setStyleSheet(f"QLabel {{ color: {current_theme.get('TEXT_COLOR', '#ffffff')}; }}")
    ok_button = msg_box.addButton("确认", QMessageBox.AcceptRole)
    style_rounded_button(ok_button)
    for label in msg_box.findChildren(QLabel):
        style_label(label)
    return msg_box

def create_line_edit(parent: QWidget, placeholder: str, echo: QLineEdit.EchoMode) -> QLineEdit:
    """创建带有通用样式、回显模式及输入验证的 QLineEdit"""
    le = QLineEdit(parent)
    le.setPlaceholderText(placeholder)
    le.setMinimumHeight(30)
    style_line_edit(le)
    le.setEchoMode(echo)
    # 限制仅允许字母、数字及常见符号
    regex = QRegularExpression(r'^[a-zA-Z0-9!@#$%^&*()_+={}\[\]:;"\'<>,.?/\\|`~\-]*$')
    le.setValidator(QRegularExpressionValidator(regex, le))
    return le

# ------------------ 登录窗口 ------------------
class LoginWindow(QDialog):
    def __init__(self, main_app: "ChatApp") -> None:
        super().__init__()
        self.main_app = main_app
        self.setWindowTitle("ChatINL 登录")
        self.setFixedSize(250, 110)
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.chat_client = ChatClient()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QGridLayout(self)
        self.username_input = create_line_edit(self, "请输入账号", QLineEdit.Normal)
        self.password_input = create_line_edit(self, "请输入密码", QLineEdit.Password)
        layout.addWidget(self.username_input, 0, 1)
        layout.addWidget(self.password_input, 1, 1)
        self.login_button = QPushButton("登录", self)
        self.login_button.setMinimumHeight(30)
        style_rounded_button(self.login_button)
        layout.addWidget(self.login_button, 2, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(2, 1)
        self.login_button.clicked.connect(self.on_login)

    def show_error_message(self, msg: str) -> None:
        QMessageBox.critical(self, "错误", msg)

    def on_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        if not username or not password:
            return self.show_error_message("账号或密码不能为空")
        if not self.chat_client or not self.chat_client.client_socket:
            return self.show_error_message("未连接到服务器，请检查网络或重试")
        asyncio.create_task(self.async_login(username, password))

    async def async_login(self, username: str, password: str) -> None:
        res = await self.chat_client.authenticate(username, password)
        if res == "认证成功":
            self.accept()
            asyncio.create_task(self.chat_client.start_reader())
            if not self.main_app.chat_window:
                self.main_app.chat_window = ChatWindow(self.chat_client, self.main_app)
            # 注册新消息及好友列表更新回调
            self.chat_client.on_new_message_callback = self.main_app.chat_window.handle_new_message
            self.chat_client.on_friend_list_update_callback = self.main_app.chat_window.update_friend_list
            self.main_app.chat_window.show()
        else:
            self.show_error_message(res)

    def closeEvent(self, event) -> None:
        self.main_app.quit_app()
        event.accept()

# ------------------ 添加好友对话框 ------------------
class AddFriendDialog(QDialog):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("添加好友")
        self.setFixedSize(300, 100)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.label = QLabel("请输入好友用户名：", self)
        layout.addWidget(self.label)
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("好友用户名")
        self.input.setFixedHeight(30)
        style_line_edit(self.input)
        layout.addWidget(self.input)
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("取消", self)
        self.cancel_btn.setFixedHeight(30)
        style_rounded_button(self.cancel_btn)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        self.confirm_btn = QPushButton("确认", self)
        self.confirm_btn.setFixedHeight(30)
        style_rounded_button(self.confirm_btn)
        self.confirm_btn.setEnabled(False)
        btn_layout.addWidget(self.confirm_btn)
        layout.addLayout(btn_layout)
        self.input.textChanged.connect(lambda text: self.confirm_btn.setEnabled(bool(text.strip())))
        self.update_theme(theme_manager.current_theme)

    def update_theme(self, theme: dict) -> None:
        style_label(self.label)
        style_line_edit(self.input)

# ------------------ 聊天窗口 ------------------
class ChatWindow(QWidget):
    def __init__(self, client: ChatClient, main_app: "ChatApp") -> None:
        super().__init__()
        self.auto_scrolling = False
        self.client = client
        self.main_app = main_app
        self.setWindowTitle(f"ChatINL 用户: {self.client.username}")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self._center_window(700, 500)
        self.setMinimumSize(450, 500)
        self.last_message_times = {}
        self.unread_messages = {}
        self.current_page = 1
        self.page_size = 20
        self.loading_history = False
        self.has_more_history = True
        self.add_friend_dialog = None
        # 用字典管理聊天区域的各个组件，便于复用与更新
        self.chat_components = {name: None for name in ('area_widget', 'scroll', 'input', 'send_button', 'online', 'chat')}
        self.scroll_to_bottom_btn = None
        self._init_ui()
        theme_manager.register(self)

    def _center_window(self, w: int, h: int) -> None:
        geo = QApplication.primaryScreen().geometry()
        self.setGeometry((geo.width()-w)//2, (geo.height()-h)//2, w, h)

    def _init_ui(self) -> None:
        main_layout = QGridLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.theme_panel = self._init_theme_panel()
        self.left_panel = self._init_friend_list_panel()
        self.content_widget = self._init_content_area()
        main_layout.addWidget(self.theme_panel, 0, 0)
        main_layout.addWidget(self.left_panel, 0, 1)
        main_layout.addWidget(self.content_widget, 0, 2)
        main_layout.setColumnStretch(2, 1)
        self._update_friend_list_width()

    def _init_theme_panel(self) -> QWidget:
        panel = QWidget(self)
        panel.setFixedWidth(0)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        for icon, mode in ((resource_path("Day_Icon.ico"), "light"),
                           (resource_path("Night_Icon.ico"), "dark")):
            btn = QPushButton(panel)
            btn.setFixedHeight(30)
            style_rounded_button(btn)
            btn.setIcon(QIcon(resource_path(icon)))
            btn.setIconSize(QSize(15, 15))
            btn.clicked.connect(lambda _, m=mode: self.set_mode(m))
            layout.addWidget(btn)
        layout.addStretch()
        return panel

    def _init_friend_list_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        top_layout = QHBoxLayout()
        self.mode_switch_button = QPushButton("<", panel)
        self.mode_switch_button.setFixedSize(20, 40)
        style_button(self.mode_switch_button)
        self.mode_switch_button.clicked.connect(self.toggle_theme_panel)
        top_layout.addWidget(self.mode_switch_button)
        self.add_button = QPushButton(panel)
        self.add_button.setFixedHeight(40)
        style_button(self.add_button)
        self.add_button.setIcon(QIcon(resource_path("Add_Icon.ico")))
        self.add_button.setIconSize(QSize(25, 25))
        self.add_button.clicked.connect(lambda: asyncio.create_task(self.async_show_add_friend()))
        top_layout.addWidget(self.add_button)
        top_layout.addStretch()
        layout.addLayout(top_layout)
        self.friend_list = QListWidget(panel)
        self.friend_list.setSelectionMode(QListWidget.SingleSelection)
        self.friend_list.setFocusPolicy(Qt.StrongFocus)
        style_list_widget(self.friend_list)
        self.friend_list.verticalScrollBar().setStyleSheet(get_scrollbar_style())
        self.friend_list.itemClicked.connect(lambda item: asyncio.create_task(self.select_friend(item)))
        layout.addWidget(self.friend_list)
        return panel

    def _init_content_area(self) -> QWidget:
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
        style_list_widget(self.friend_list)
        self.friend_list.verticalScrollBar().setStyleSheet(get_scrollbar_style())
        self.setStyleSheet(f"background-color: {theme['MAIN_INTERFACE']};")
        if self.chat_components['scroll']:
            self.chat_components['scroll'].viewport().setStyleSheet(f"background-color: {theme['chat_bg']};")
            style_scrollbar(self.chat_components['scroll'])
        if self.chat_components['chat']:
            self.chat_components['chat'].setStyleSheet(f"background-color: {theme['chat_bg']};")
        if self.chat_components.get('input'):
            style_text_edit(self.chat_components['input'])
        if self.chat_components.get('send_button'):
            style_button(self.chat_components['send_button'])
        style_list_widget(self.friend_list)
        if self.chat_components.get('online'):
            self.chat_components['online'].update_theme(theme)
        if self.add_friend_dialog and self.add_friend_dialog.isVisible():
            self.add_friend_dialog.update_theme(theme)
        if self.scroll_to_bottom_btn:
            circle_button_style(self.scroll_to_bottom_btn)

    def resizeEvent(self, event) -> None:
        self._update_friend_list_width()
        if self.scroll_to_bottom_btn:
            self._position_scroll_button()
        super().resizeEvent(event)

    def _update_friend_list_width(self) -> None:
        width = 75 if self.width() <= 500 else 180
        self.friend_list.setFixedWidth(width)
        self.add_button.setFixedWidth(width - self.mode_switch_button.width() - 2)

    def clear_chat_area(self) -> None:
        for comp in self.chat_components.values():
            if comp:
                comp.deleteLater()
        self.chat_components = {k: None for k in self.chat_components}
        if self.scroll_to_bottom_btn:
            self.scroll_to_bottom_btn.deleteLater()
            self.scroll_to_bottom_btn = None
        self.default_label.show()

    def setup_chat_area(self) -> None:
        self.default_label.hide()
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
        style_scrollbar(self.chat_components['scroll'])
        sb = self.chat_components['scroll'].verticalScrollBar()
        sb.valueChanged.connect(self.on_scroll_changed)
        self._create_scroll_button(theme_manager.current_theme)
        area_layout.addWidget(self.chat_components['online'])
        area_layout.addWidget(self.chat_components['scroll'])
        self.chat_components['input'] = MessageInput(self)
        self.chat_components['input'].setPlaceholderText("输入消息")
        self.chat_components['input'].setFixedHeight(70)
        self.chat_components['send_button'] = QPushButton("发送", self)
        self.chat_components['send_button'].setFixedSize(110, 70)
        style_button(self.chat_components['send_button'])
        self.chat_components['send_button'].clicked.connect(lambda: asyncio.create_task(self.send_message()))
        self.content_layout.addWidget(self.chat_components['area_widget'], 0, 0, 1, 2)
        self.content_layout.addWidget(self.chat_components['input'], 1, 0)
        self.content_layout.addWidget(self.chat_components['send_button'], 1, 1)
        self.update_theme(theme_manager.current_theme)

    def _create_scroll_button(self, theme: dict) -> None:
        if not self.scroll_to_bottom_btn:
            self.scroll_to_bottom_btn = QPushButton(self.chat_components['scroll'].viewport())
            self.scroll_to_bottom_btn.setFixedSize(30, 30)
            self.scroll_to_bottom_btn.clicked.connect(self.on_scroll_button_clicked)
        circle_button_style(self.scroll_to_bottom_btn)
        self.scroll_to_bottom_btn.setIcon(QIcon(resource_path("arrow_down.ico")))
        self.scroll_to_bottom_btn.setIconSize(QSize(15, 15))
        self.scroll_to_bottom_btn.hide()

    def _reset_chat_area(self) -> None:
        self.clear_chat_area()
        self.setup_chat_area()
        self.current_page = 1
        self.has_more_history = True

    def on_scroll_button_clicked(self):
        self.adjust_scroll()
        if self.client.current_friend:
            self.unread_messages[self.client.current_friend] = 0
            asyncio.create_task(self.update_friend_list())
        self.scroll_to_bottom_btn.hide()

    def on_scroll_changed(self, value: int):
        sb = self.chat_components['scroll'].verticalScrollBar()
        if value == 0 and self.has_more_history and not self.loading_history:
            asyncio.create_task(self.load_chat_history(reset=False))
        self._check_scroll_position()
        if (self.client.current_friend and
            self.unread_messages.get(self.client.current_friend, 0) > 0 and
            not self.auto_scrolling and
            (sb.maximum() - value) <= 5):
            self.unread_messages[self.client.current_friend] = 0
            asyncio.create_task(self.update_friend_list())

    def adjust_scroll(self):
        def _adjust():
            sb = self.chat_components['scroll'].verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
                self._check_scroll_position()
            self.auto_scrolling = False

        self.auto_scrolling = True
        QTimer.singleShot(0, _adjust)  # 在下一个事件循环迭代执行

    def _check_scroll_position(self):
        sb = self.chat_components['scroll'].verticalScrollBar()
        if not self.scroll_to_bottom_btn:
            self._create_scroll_button(theme_manager.current_theme)
        should_show = (self.client.current_friend and
                       self.unread_messages.get(self.client.current_friend, 0) > 0 and
                       (sb.maximum() - sb.value()) > 50)
        if should_show:
            self._position_scroll_button()
            self.scroll_to_bottom_btn.show()
        else:
            self.scroll_to_bottom_btn.hide()

    def _position_scroll_button(self):
        if not self.scroll_to_bottom_btn or not self.chat_components.get('scroll'):
            return
        viewport = self.chat_components['scroll'].viewport()
        btn = self.scroll_to_bottom_btn
        x = max(10, viewport.width() - btn.width() - 10)
        y = max(10, viewport.height() - btn.height() - 10)
        btn.move(x, y)

    def should_scroll_to_bottom(self) -> bool:
        sb = self.chat_components['scroll'].verticalScrollBar()
        return (sb.maximum() - sb.value()) < self.chat_components['scroll'].viewport().height()

    def add_message(self, msg: str, is_current: bool, tstr: str) -> None:
        bubble = ChatBubbleWidget(msg, tstr, "right" if is_current else "left", is_current)
        self.chat_components['chat'].addBubble(bubble)
        if is_current or self.should_scroll_to_bottom():
            self.adjust_scroll()

    # 修改 _handle_message 中的通知触发判断
    async def _handle_message(self, sender: str, msg: str, is_current: bool, wt: str, received: bool) -> None:
        self.last_message_times[sender] = wt
        if sender == self.client.current_friend:
            if received:
                if self.should_scroll_to_bottom():
                    self.adjust_scroll()
                    self.unread_messages[sender] = 0
                else:
                    self.unread_messages[sender] = self.unread_messages.get(sender, 0) + 1
                    self._check_scroll_position()
            self.add_message(msg, is_current, format_time(wt))
        else:
            self.unread_messages[sender] = self.unread_messages.get(sender, 0) + 1
        # 修改判断条件：只要窗口不可见（例如被隐藏到托盘），都触发通知
        if not self.isVisible() or self.isMinimized():
            self.show_notification(f"用户 {sender}:", msg)
        await self.update_friend_list()

    async def send_message(self) -> None:
        text = self.chat_components['input'].toPlainText().strip()
        if not self.client.current_friend or not text:
            return
        await self.client.send_message(self.client.username, self.client.current_friend, text)
        wt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await self._handle_message(self.client.current_friend, text, True, wt, received=False)
        self.chat_components['input'].clear()
        self.adjust_scroll()

    async def handle_new_message(self, res: dict):
        sender, msg, wt = res.get("from"), res.get("message"), res.get("write_time")
        await self._handle_message(sender, msg, False, wt, received=True)

    def _sort_friends(self, friends: list) -> list:
        online = [f for f in friends if f.get("online")]
        offline = [f for f in friends if not f.get("online")]
        online.sort(key=lambda x: self.last_message_times.get(x["username"], "1970-01-01 00:00:00"), reverse=True)
        offline.sort(key=lambda x: self.last_message_times.get(x["username"], "1970-01-01 00:00:00"), reverse=True)
        return online + offline

    async def update_friend_list(self, friends: list = None) -> None:
        friends = friends if friends is not None else self.client.friends
        current_friend = self.client.current_friend
        self.friend_list.clear()
        for f in self._sort_friends(friends):
            uname = f["username"]
            item = QListWidgetItem(self.friend_list)
            item.setSizeHint(QSize(0, 40))
            widget = FriendItemWidget(uname, f.get("online", False), self.unread_messages.get(uname, 0))
            self.friend_list.setItemWidget(item, widget)
            theme_manager.register(widget)
            if uname == current_friend:
                item.setSelected(True)
                self.chat_components['online'].update_status(current_friend, f.get("online", False))
        for i in range(self.friend_list.count()):
            w = self.friend_list.itemWidget(self.friend_list.item(i))
            if w:
                w.update_theme(theme_manager.current_theme)

    async def load_chat_history(self, reset: bool = False) -> None:
        if reset:
            self._reset_chat_area()
            self.current_page = 1
            self.has_more_history = True

        if not self.client.current_friend or not self.has_more_history:
            return

        self.loading_history = True
        sb = self.chat_components.get('scroll').verticalScrollBar() if self.chat_components.get('scroll') else None
        old_val = sb.value() if sb else 0

        res = await self.client.get_chat_history_paginated(
            self.client.current_friend, self.current_page, self.page_size
        )
        if res and res.get("type") == "chat_history":
            messages = res.get("data", [])
            if messages:
                bubbles = []
                for msg in messages:
                    bubble = ChatBubbleWidget(
                        msg.get("message", ""),
                        format_time(msg.get("write_time", "")),
                        "right" if msg.get("is_current_user") else "left",
                        msg.get("is_current_user", False)
                    )
                    bubbles.append(bubble)
                self.chat_components['chat'].addBubbles(bubbles)
                if reset:
                    QTimer.singleShot(50, self.adjust_scroll)  # 延迟滚动，确保尺寸生效
                elif sb:
                    self.auto_scrolling = True
                    inserted = sum(b.sizeHint().height() for b in bubbles)
                    QTimer.singleShot(50, lambda: sb.setValue(old_val + inserted))
                    QTimer.singleShot(100, lambda: setattr(self, 'auto_scrolling', False))
            if len(messages) < self.page_size:
                self.has_more_history = False
            else:
                self.current_page += 1
        self.loading_history = False

    async def select_friend(self, item: QListWidgetItem) -> None:
        if not item:
            self.clear_chat_area()
            self.client.current_friend = None
            return
        widget = self.friend_list.itemWidget(item)
        friend = widget.username if widget else item.data(Qt.UserRole)
        self.client.current_friend = friend
        self._reset_chat_area()
        await self.load_chat_history(reset=True)
        online = any(f.get("username") == friend and f.get("online", False)
                     for f in self.client.friends)
        self.chat_components['online'].update_status(friend, online)
        sb = self.chat_components['scroll'].verticalScrollBar()
        if sb.maximum() - sb.value() <= 5:
            self.unread_messages[friend] = 0
        await self.update_friend_list()

    def show_notification(self, sender: str, msg: str) -> None:
        """收到新消息时，弹出系统通知并闪烁任务栏图标"""
        self.notification_sender = sender.replace("用户 ", "").rstrip(":")
        self.main_app.tray_icon.showMessage(sender, msg, QIcon(resource_path("icon.ico")), 2000)
        self.flash_taskbar_icon()

    def on_notification_clicked(self) -> None:
        if not getattr(self, 'notification_sender', None):
            return
        if self.isMinimized() or not self.isVisible():
            self.showNormal()  # 恢复窗口
        self.activateWindow()
        for i in range(self.friend_list.count()):
            item = self.friend_list.item(i)
            widget = self.friend_list.itemWidget(item)
            if widget and widget.username == self.notification_sender:
                self.friend_list.setCurrentItem(item)
                asyncio.create_task(self.select_friend(item))
                break
        self.notification_sender = None

    async def async_show_add_friend(self) -> None:
        if self.add_friend_dialog and self.add_friend_dialog.isVisible():
            self.add_friend_dialog.raise_()
            self.add_friend_dialog.activateWindow()
            return
        self.add_friend_dialog = AddFriendDialog(self)
        self.add_friend_dialog.confirm_btn.clicked.connect(lambda: asyncio.create_task(self.proc_add_friend()))
        fut = asyncio.get_running_loop().create_future()
        self.add_friend_dialog.finished.connect(lambda _: fut.set_result(None))
        self.add_friend_dialog.show()
        await fut
        self.add_friend_dialog = None

    async def proc_add_friend(self) -> None:
        friend_name = self.add_friend_dialog.input.text().strip()
        if friend_name:
            res = await self.client.add_friend(friend_name)
            msg_box = create_themed_message_box(self, "提示", res)
            msg_box.exec_()
            self.add_friend_dialog.accept()

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
        else:
            super().keyPressEvent(event)

    # ------------------ 新增：任务栏图标闪烁控制 ------------------
    def flash_taskbar_icon(self):
        """当收到新消息且窗口未激活或最小化时，闪烁任务栏图标（仅 Windows 有效）"""
        hwnd = int(self.winId())
        FLASHW_ALL = 3  # 同时闪烁任务栏和标题栏
        flash_info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_ALL, 10, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(flash_info))

    def stop_flash_taskbar_icon(self):
        """停止任务栏图标闪烁"""
        hwnd = int(self.winId())
        FLASHW_STOP = 0
        flash_info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_STOP, 0, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(flash_info))

    def event(self, event):
        """重写 event 方法，窗口激活时停止闪烁"""
        if event.type() == QEvent.WindowActivate:
            self.stop_flash_taskbar_icon()
        return super().event(event)

# ------------------ 主应用类 ------------------
class ChatApp:
    def __init__(self) -> None:
        self.app = QApplication(sys.argv)
        self.tray_icon = QSystemTrayIcon(self.app)
        self._setup_tray()
        self.loop = QEventLoop(self.app)
        asyncio.set_event_loop(self.loop)
        self.login_window = LoginWindow(self)
        self.chat_window = None

    def _setup_tray(self) -> None:
        self.tray_icon.setIcon(QIcon(resource_path("icon.ico")))
        self.tray_icon.setToolTip("ChatINL")
        self.tray_icon.show()
        menu = QMenu()
        menu.addAction("打开主界面", lambda: self.on_tray_activated(QSystemTrayIcon.Trigger))
        menu.addAction("退出", self.quit_app)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        # 连接点击通知消息的信号
        self.tray_icon.messageClicked.connect(self.on_notification_clicked)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.chat_window:
                self.chat_window.show()
                self.chat_window.activateWindow()
            else:
                self.login_window.show()
                self.login_window.activateWindow()

    def on_notification_clicked(self):
        if self.chat_window:
            self.chat_window.on_notification_clicked()

    def quit_app(self) -> None:
        async def shutdown() -> None:
            try:
                if self.login_window.chat_client and self.login_window.chat_client.client_socket:
                    await self.login_window.chat_client.close_connection()
            except Exception as ex:
                QMessageBox.critical(self.login_window, '错误', f"退出时关闭连接异常: {ex}", QMessageBox.Ok)
            cur = asyncio.current_task()
            tasks = [t for t in asyncio.all_tasks() if t is not cur]
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.loop.shutdown_asyncgens()
            self.tray_icon.hide()
            self.loop.stop()
            self.app.quit()
        asyncio.create_task(shutdown())

    def run(self) -> None:
        self.login_window.show()
        with self.loop:
            sys.exit(self.loop.run_forever())

def main() -> None:
    chat_app = ChatApp()
    chat_app.run()

if __name__ == '__main__':
    main()
