#!/usr/bin/env python3
# main.py
import sys
import os
import asyncio
from datetime import datetime, timedelta
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QGridLayout, QLineEdit,
    QHBoxLayout, QLabel, QDialog, QMessageBox, QListWidget,
    QListWidgetItem, QSystemTrayIcon, QMenu, QVBoxLayout, QScrollArea, QFrame
)
from qasync import QEventLoop
from chat_client import ChatClient
from Interface_Controls import (
    MessageInput, FriendItemWidget, ChatAreaWidget, ChatBubbleWidget,
    style_button, style_line_edit, style_list_widget, style_scrollbar,
    OnLine, style_rounded_button, style_text_edit, theme_manager, style_label,
    login_style_line_edit
)


# ---------------- 公共辅助函数 ----------------
def resource_path(relative_path: str) -> str:
    """
    获取资源文件的绝对路径，支持 PyInstaller 打包。
    """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath('.'))
    return os.path.join(base_path, relative_path)


def format_time(timestamp: str) -> str:
    """
    格式化时间戳：
      - 一天内显示“小时:分钟”
      - 超过一天显示“月.日 小时:分钟”
    """
    try:
        t = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        return t.strftime("%H:%M") if datetime.now() - t < timedelta(days=1) else t.strftime("%m.%d %H:%M")
    except Exception:
        return datetime.now().strftime("%H:%M")


def create_themed_message_box(parent: QWidget, title: str, text: str) -> QMessageBox:
    """
    创建主题化的消息弹窗，修正“添加好友”弹窗点击确认后文字为黑色的问题，
    通过遍历所有 QLabel 并设置当前主题中的文本颜色。
    """
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(QMessageBox.Information)
    # 根据当前主题设置文本颜色（暗黑模式下文字为白色）
    current_theme = theme_manager.current_theme
    text_color = current_theme.get('TEXT_COLOR', '#ffffff')
    msg_box.setStyleSheet(f"QLabel {{ color: {text_color}; }}")
    ok_button = msg_box.addButton(QMessageBox.Ok)
    style_rounded_button(ok_button)
    for label in msg_box.findChildren(QLabel):
        style_label(label)
    return msg_box


# ---------------- 登录窗口 ----------------
class LoginWindow(QDialog):
    """登录窗口"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ChatINL 登录")
        self.setFixedSize(250, 110)
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.chat_client = ChatClient()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QGridLayout(self)
        # 账号输入框
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("请输入账号")
        self.username_input.setMinimumHeight(30)
        login_style_line_edit(self.username_input)
        layout.addWidget(self.username_input, 0, 1)
        # 密码输入框
        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setMinimumHeight(30)
        self.password_input.setEchoMode(QLineEdit.Password)
        login_style_line_edit(self.password_input)
        layout.addWidget(self.password_input, 1, 1)
        # 登录按钮
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
            global chat_window_global
            if chat_window_global is None:
                chat_window_global = ChatWindow(self.chat_client, tray_icon)
            # 设置回调，新消息与好友列表更新由服务端主动推送
            self.chat_client.on_new_message_callback = chat_window_global.handle_new_message
            self.chat_client.on_friend_list_update_callback = chat_window_global.update_friend_list
            chat_window_global.show()
        else:
            self.show_error_message(res)

    def closeEvent(self, event) -> None:
        quit_app()
        event.accept()

# ---------------- 添加好友对话框 ----------------
class AddFriendDialog(QDialog):
    """添加好友对话框，支持主题切换"""

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
        button_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("取消", self)
        self.cancel_btn.setFixedHeight(30)
        style_rounded_button(self.cancel_btn)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        self.confirm_btn = QPushButton("确认", self)
        self.confirm_btn.setFixedHeight(30)
        style_rounded_button(self.confirm_btn)
        self.confirm_btn.setEnabled(False)
        button_layout.addWidget(self.confirm_btn)
        layout.addLayout(button_layout)
        self.input.textChanged.connect(lambda: self.confirm_btn.setEnabled(bool(self.input.text().strip())))
        self.update_theme(theme_manager.current_theme)

    def update_theme(self, theme: dict) -> None:
        style_label(self.label)
        style_line_edit(self.input)
        # 如有需要，可根据主题调整 placeholder 颜色

# ---------------- 聊天窗口 ----------------
class ChatWindow(QWidget):
    def __init__(self, client: ChatClient, tray_icon: QSystemTrayIcon) -> None:
        super().__init__()
        self.client = client
        self.tray_icon = tray_icon
        self.setWindowTitle(f"ChatINL 用户: {self.client.username}")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.screen = QApplication.primaryScreen().geometry()
        x = (self.screen.width() - 700) // 2
        y = (self.screen.height() - 500) // 2
        self.setGeometry(x, y, 700, 500)
        self.setMinimumSize(450, 500)
        self.friend_list_width = 180
        self.mode_switch_button_width = 20
        self.last_message_times = {}
        self.unread_messages = {}
        self.current_page = 1
        self.page_size = 20
        self.loading_history = False
        self.has_more_history = True
        self.chat_components = {
            'area_widget': None,
            'scroll': None,
            'input': None,
            'send_button': None,
            'online': None,
            'chat': None
        }
        self.add_friend_dialog = None  # 当前添加好友对话框
        self.notification_sender = None
        self._init_ui()
        theme_manager.register(self)

    def _init_ui(self) -> None:
        main_layout = QGridLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 左侧主题面板 ---
        self.theme_panel = QWidget(self)
        self.theme_panel.setFixedWidth(0)
        theme_layout = QVBoxLayout(self.theme_panel)
        theme_layout.setContentsMargins(5, 5, 5, 5)
        theme_layout.setSpacing(5)
        # 日间模式按钮
        day_mode_button = QPushButton(self.theme_panel)
        day_mode_button.setFixedHeight(30)
        style_rounded_button(day_mode_button)
        day_mode_button.setIcon(QIcon(resource_path("Day_Icon.ico")))
        day_mode_button.setIconSize(QSize(15, 15))
        day_mode_button.clicked.connect(self.set_day_mode)
        theme_layout.addWidget(day_mode_button)
        # 夜间模式按钮
        night_mode_button = QPushButton(self.theme_panel)
        night_mode_button.setFixedHeight(30)
        style_rounded_button(night_mode_button)
        night_mode_button.setIcon(QIcon(resource_path("Night_Icon.ico")))
        night_mode_button.setIconSize(QSize(15, 15))
        night_mode_button.clicked.connect(self.set_night_mode)
        theme_layout.addWidget(night_mode_button)
        theme_layout.addStretch()

        # --- 好友列表面板 ---
        self.left_panel = QWidget(self)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)
        top_buttons_layout = QHBoxLayout()
        self.mode_switch_button = QPushButton("<", self.left_panel)
        self.mode_switch_button.setFixedSize(self.mode_switch_button_width, 40)
        style_button(self.mode_switch_button)
        self.mode_switch_button.clicked.connect(self.toggle_theme_panel)
        top_buttons_layout.addWidget(self.mode_switch_button)
        self.add_button = QPushButton(self.left_panel)
        self.add_button.setFixedHeight(40)
        style_button(self.add_button)
        self.add_button.setIcon(QIcon(resource_path("Add_Icon.ico")))
        self.add_button.setIconSize(QSize(20, 20))
        self.add_button.clicked.connect(lambda: asyncio.create_task(self.async_show_add_friend()))
        top_buttons_layout.addWidget(self.add_button)
        top_buttons_layout.addStretch()
        left_layout.addLayout(top_buttons_layout)
        self.friend_list = QListWidget(self.left_panel)
        self.friend_list.setFixedWidth(self.friend_list_width)
        self.friend_list.setSelectionMode(QListWidget.SingleSelection)
        self.friend_list.setFocusPolicy(Qt.StrongFocus)
        style_list_widget(self.friend_list)
        self.friend_list.itemClicked.connect(lambda item: asyncio.create_task(self.select_friend(item)))
        left_layout.addWidget(self.friend_list)

        # --- 聊天区域 ---
        self.content_widget = QWidget(self)
        self.content_layout = QGridLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.default_label = QLabel(self)
        self.default_label.setPixmap(QIcon(resource_path("icon.ico")).pixmap(128, 128))
        self.default_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.default_label, 0, 0, Qt.AlignCenter)
        main_layout.addWidget(self.theme_panel, 0, 0)
        main_layout.addWidget(self.left_panel, 0, 1)
        main_layout.addWidget(self.content_widget, 0, 2)
        main_layout.setColumnStretch(2, 1)
        self._update_friend_list_width()

    def toggle_theme_panel(self) -> None:
        if self.theme_panel.width() == 0:
            self.theme_panel.setFixedWidth(50)
            if not self.isMaximized():
                self.resize(self.width() + 50, self.height())
        else:
            if not self.isMaximized():
                self.resize(self.width() - 50, self.height())
            self.theme_panel.setFixedWidth(0)

    def set_day_mode(self) -> None:
        theme_manager.set_mode("light")
        self.update_theme(theme_manager.current_theme)

    def set_night_mode(self) -> None:
        theme_manager.set_mode("dark")
        self.update_theme(theme_manager.current_theme)

    def update_theme(self, theme: dict) -> None:
        self.setStyleSheet(f"background-color: {theme['MAIN_INTERFACE']};")
        if self.chat_components.get('scroll'):
            self.chat_components['scroll'].viewport().setStyleSheet(
                f"background-color: {theme['chat_bg']};")
            style_scrollbar(self.chat_components['scroll'])
        if self.chat_components.get('chat'):
            self.chat_components['chat'].setStyleSheet(
                f"background-color: {theme['chat_bg']};")
        if self.chat_components.get('input'):
            style_text_edit(self.chat_components['input'])
        if self.chat_components.get('send_button'):
            style_button(self.chat_components['send_button'])
        style_list_widget(self.friend_list)
        if self.chat_components.get('online'):
            self.chat_components['online'].update_theme(theme)
        if self.add_friend_dialog and self.add_friend_dialog.isVisible():
            self.add_friend_dialog.update_theme(theme)

    def resizeEvent(self, event) -> None:
        self._update_friend_list_width()
        super().resizeEvent(event)

    def _update_friend_list_width(self) -> None:
        self.friend_list_width = 75 if self.width() <= 500 else 180
        self.friend_list.setFixedWidth(self.friend_list_width)
        self.add_button.setFixedWidth(self.friend_list_width - self.mode_switch_button_width - 2)

    def handle_friend_list_key_press(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.friend_list.clearSelection()
            self.clear_chat_area()
            self.client.current_friend = None
        else:
            QListWidget.keyPressEvent(self.friend_list, event)

    def clear_chat_area(self) -> None:
        for comp in self.chat_components.values():
            if comp:
                comp.deleteLater()
        self.chat_components = {key: None for key in self.chat_components}
        self.default_label.show()

    def setup_chat_area(self) -> None:
        self.default_label.hide()
        bg = "#e9e9e9"
        self.chat_components['area_widget'] = QWidget(self)
        area_layout = QVBoxLayout(self.chat_components['area_widget'])
        area_layout.setContentsMargins(0, 0, 0, 0)
        area_layout.setSpacing(0)
        self.friend_status_widget = OnLine(self)
        self.friend_status_widget.setStyleSheet("border: none; background-color: #ffffff;")
        self.friend_status_widget.setFixedHeight(50)
        self.chat_components['online'] = self.friend_status_widget
        self.chat_components['chat'] = ChatAreaWidget(self)
        self.chat_components['chat'].setStyleSheet(f"border: 1px; background-color: {bg};")
        self.chat_components['scroll'] = QScrollArea(self)
        self.chat_components['scroll'].viewport().setStyleSheet(f"border: none; background-color: {bg};")
        self.chat_components['scroll'].setFrameShape(QFrame.NoFrame)
        self.chat_components['scroll'].setWidgetResizable(True)
        self.chat_components['scroll'].setWidget(self.chat_components['chat'])
        style_scrollbar(self.chat_components['scroll'])
        self.chat_components['scroll'].verticalScrollBar().valueChanged.connect(self.on_scroll)
        area_layout.addWidget(self.friend_status_widget)
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

    def _reset_chat_area(self) -> None:
        self.clear_chat_area()
        self.setup_chat_area()
        self.current_page = 1
        self.has_more_history = True

    def on_scroll(self, value: int) -> None:
        if value == 0 and self.has_more_history and not self.loading_history:
            asyncio.create_task(self.load_more_chat_history())

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(0, lambda: self.chat_components['scroll'].verticalScrollBar().setValue(
            self.chat_components['scroll'].verticalScrollBar().maximum()))

    def should_scroll_to_bottom(self) -> bool:
        sb = self.chat_components['scroll'].verticalScrollBar()
        return (self.chat_components['chat'].height() <= self.chat_components['scroll'].viewport().height() or
                sb.value() >= sb.maximum() - 10)

    def add_message(self, msg: str, is_current: bool, tstr: str) -> None:
        bubble = ChatBubbleWidget(msg, tstr, "right" if is_current else "left", is_current)
        self.chat_components['chat'].addBubble(bubble)
        if is_current or self.should_scroll_to_bottom():
            QTimer.singleShot(10, self._scroll_to_bottom)

    async def process_message(self, sender: str, msg: str, is_current: bool, wt: str = None) -> None:
        wt = wt or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_message_times[sender] = wt
        if sender == self.client.current_friend:
            self.add_message(msg, is_current, format_time(wt))
        else:
            self.unread_messages[sender] = self.unread_messages.get(sender, 0) + 1
            self.show_notification(f"用户 {sender}:", msg)
        await self.update_friend_list()

    async def handle_new_message(self, res: dict) -> None:
        sender = res.get("from")
        msg = res.get("message")
        wt = res.get("write_time")
        if sender == self.client.current_friend:
            self.add_message(msg, False, format_time(wt))
        else:
            await self.process_message(sender, msg, False, wt)

    async def send_message(self) -> None:
        text = self.chat_components['input'].toPlainText().strip()
        if not self.client.current_friend or not text:
            return
        await self.client.send_message(self.client.username, self.client.current_friend, text)
        await self.process_message(self.client.current_friend, text, True)
        self.chat_components['input'].clear()

    async def load_more_chat_history(self) -> None:
        if not self.client.current_friend or not self.has_more_history:
            return
        self.loading_history = True
        scroll_bar = self.chat_components['scroll'].verticalScrollBar()
        old_value = scroll_bar.value()
        res = await self.client.get_chat_history_paginated(
            self.client.current_friend, self.current_page, self.page_size
        )
        if res and res.get("type") == "chat_history":
            messages = res.get("data", [])
            if messages:
                inserted_height = 0
                for msg in messages:
                    bubble = ChatBubbleWidget(
                        msg.get("message", ""),
                        format_time(msg.get("write_time", "")),
                        "right" if msg.get("is_current_user") else "left",
                        msg.get("is_current_user", False)
                    )
                    self.chat_components['chat'].addBubble(bubble, 0)
                    inserted_height += bubble.sizeHint().height()
                QTimer.singleShot(0, lambda: scroll_bar.setValue(old_value + inserted_height))
            if len(messages) < self.page_size:
                self.has_more_history = False
            else:
                self.current_page += 1
        self.loading_history = False

    async def update_friend_list(self, friends: list = None) -> None:
        friends = friends if friends is not None else self.client.friends
        current_friend = self.client.current_friend
        self.friend_list.clear()
        online_friends = sorted(
            [f for f in friends if f.get("online")],
            key=lambda x: self.last_message_times.get(x["username"], "1970-01-01 00:00:00"),
            reverse=True
        )
        offline_friends = sorted(
            [f for f in friends if not f.get("online")],
            key=lambda x: self.last_message_times.get(x["username"], "1970-01-01 00:00:00"),
            reverse=True
        )
        sorted_friends = online_friends + offline_friends
        current_online = False
        for f in sorted_friends:
            uname = f["username"]
            item = QListWidgetItem(self.friend_list)
            item.setSizeHint(QSize(0, 40))
            widget = FriendItemWidget(uname, f.get("online", False), self.unread_messages.get(uname, 0))
            self.friend_list.setItemWidget(item, widget)
            theme_manager.register(widget)
            if uname == current_friend:
                item.setSelected(True)
                current_online = f.get("online", False)
        if current_friend:
            self.friend_status_widget.update_status(current_friend, current_online)
        for i in range(self.friend_list.count()):
            item = self.friend_list.item(i)
            widget = self.friend_list.itemWidget(item)
            if widget:
                widget.update_theme(theme_manager.current_theme)

    async def select_friend(self, item: QListWidgetItem) -> None:
        if not item:
            self.clear_chat_area()
            self.client.current_friend = None
            return
        widget = self.friend_list.itemWidget(item)
        friend = widget.username if widget else item.data(Qt.UserRole)
        self.client.current_friend = friend
        self._reset_chat_area()
        res = await self.client.get_chat_history_paginated(friend, self.current_page, self.page_size)
        if res and res.get("type") == "chat_history":
            messages = res.get("data", [])
            messages.reverse()
            for msg in messages:
                bubble = ChatBubbleWidget(
                    msg.get("message", ""),
                    format_time(msg.get("write_time", "")),
                    "right" if msg.get("is_current_user") else "left",
                    msg.get("is_current_user", False)
                )
                self.chat_components['chat'].addBubble(bubble)
            if messages:
                QTimer.singleShot(0, self._scroll_to_bottom)
                if len(messages) < self.page_size:
                    self.has_more_history = False
                else:
                    self.current_page += 1
        current_online = any(f.get("username") == friend and f.get("online", False) for f in self.client.friends)
        self.friend_status_widget.update_status(friend, current_online)
        if friend in self.unread_messages:
            self.unread_messages[friend] = 0
            await self.update_friend_list()

    def show_notification(self, sender: str, msg: str) -> None:
        self.notification_sender = sender.replace("用户 ", "").rstrip(":")
        self.tray_icon.showMessage(sender, msg, QIcon(resource_path("icon.ico")), 2000)

    def on_notification_clicked(self) -> None:
        if not self.notification_sender:
            return
        self.show()
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
        if self.add_friend_dialog is not None and self.add_friend_dialog.isVisible():
            self.add_friend_dialog.raise_()
            self.add_friend_dialog.activateWindow()
            return
        self.add_friend_dialog = AddFriendDialog(self)
        self.add_friend_dialog.confirm_btn.clicked.connect(lambda: asyncio.create_task(self.proc_add_friend()))
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
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

# ---------------- 应用退出与系统托盘 ----------------
def quit_app() -> None:
    async def shutdown() -> None:
        try:
            if login_window.chat_client and login_window.chat_client.client_socket:
                await login_window.chat_client.close_connection()
        except Exception as ex:
            QMessageBox.critical(login_window, '错误', f"退出时关闭连接异常: {ex}", QMessageBox.Ok)
        cur = asyncio.current_task()
        tasks = [t for t in asyncio.all_tasks() if t is not cur]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await loop.shutdown_asyncgens()
        tray_icon.hide()
        loop.stop()
        app.quit()
    asyncio.create_task(shutdown())


def on_tray_activated(reason) -> None:
    global chat_window_global
    if reason == QSystemTrayIcon.Trigger:
        if chat_window_global:
            chat_window_global.show()
            chat_window_global.activateWindow()
        else:
            login_window.show()
            login_window.activateWindow()

# ---------------- 主函数 ----------------
def main() -> None:
    global app, tray_icon, loop, login_window, chat_window_global
    app = QApplication(sys.argv)
    tray_icon = QSystemTrayIcon(app)
    tray_icon.setIcon(QIcon(resource_path("icon.ico")))
    tray_icon.setToolTip("ChatINL")
    tray_icon.show()
    menu = QMenu()
    menu.addAction("打开主界面", lambda: on_tray_activated(QSystemTrayIcon.Trigger))
    menu.addAction("退出", quit_app)
    tray_icon.setContextMenu(menu)
    tray_icon.activated.connect(on_tray_activated)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    login_window = LoginWindow()
    login_window.show()
    chat_window_global = None
    with loop:
        sys.exit(loop.run_forever())

if __name__ == '__main__':
    main()
