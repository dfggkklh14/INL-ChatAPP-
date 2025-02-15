#!/usr/bin/env python3
# main.py
import sys
import os
import asyncio
from datetime import datetime, timedelta
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QGridLayout, QLineEdit,
                             QHBoxLayout, QLabel, QDialog, QMessageBox, QListWidget,
                             QListWidgetItem, QSystemTrayIcon, QMenu, QVBoxLayout, QScrollArea, QFrame)
from qasync import QEventLoop
from chat_client import ChatClient
from Interface_Controls import (MessageInput, FriendItemWidget, ChatAreaWidget, ChatBubbleWidget,
                                  style_button, style_line_edit, style_list_widget, style_scrollbar,
                                  OnLine, style_rounded_button, style_text_edit)

# ---------------- 实用函数 ----------------
def resource_path(rp):
    """获取资源文件的绝对路径"""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath('.'))
    return os.path.join(base_path, rp)

def format_time(ts):
    """
    格式化时间戳：
      - 如果时间在一天内，显示“小时:分钟”
      - 超过一天，显示“月.日 小时:分钟”
    """
    try:
        t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return t.strftime("%H:%M") if datetime.now() - t < timedelta(days=1) else t.strftime("%m.%d %H:%M")
    except Exception:
        return datetime.now().strftime("%H:%M")

# ---------------- 登录窗口 ----------------
class LoginWindow(QDialog):
    """ChatINL 登录窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChatINL 登录")
        self.setFixedSize(250, 110)
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.chat_client = ChatClient()
        self._init_ui()

    def _init_ui(self):
        layout = QGridLayout(self)
        # 账号输入框
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("请输入账号")
        self.username_input.setMinimumHeight(30)
        style_line_edit(self.username_input)
        layout.addWidget(self.username_input, 0, 1)
        # 密码输入框
        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setMinimumHeight(30)
        self.password_input.setEchoMode(QLineEdit.Password)
        style_line_edit(self.password_input)
        layout.addWidget(self.password_input, 1, 1)
        # 登录按钮
        self.login_button = QPushButton("登录", self)
        self.login_button.setMinimumHeight(30)
        style_rounded_button(self.login_button)
        layout.addWidget(self.login_button, 2, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(2, 1)
        self.login_button.clicked.connect(self.on_login)

    def show_error_message(self, msg):
        QMessageBox.critical(self, "错误", msg)

    def on_login(self):
        u = self.username_input.text().strip()
        p = self.password_input.text().strip()
        if not u or not p:
            return self.show_error_message("账号或密码不能为空")
        if not self.chat_client or not self.chat_client.client_socket:
            return self.show_error_message("未连接到服务器，请检查网络或重试")
        asyncio.create_task(self.async_login(u, p))

    async def async_login(self, u, p):
        res = await self.chat_client.authenticate(u, p)
        if res == "认证成功":
            self.accept()
            asyncio.create_task(self.chat_client.start_reader())
            global chat_window_global
            if chat_window_global is None:
                chat_window_global = ChatWindow(self.chat_client, tray_icon)
            # 设置回调：新消息和好友列表更新由服务端主动推送
            self.chat_client.on_new_message_callback = chat_window_global.handle_new_message
            self.chat_client.on_friend_list_update_callback = chat_window_global.update_friend_list
            chat_window_global.show()
        else:
            self.show_error_message(res)

# ---------------- 聊天窗口 ----------------
class ChatWindow(QWidget):
    """ChatINL 聊天主窗口"""
    def __init__(self, client, tray_icon):
        super().__init__()
        self.client = client
        self.tray_icon = tray_icon
        self.setWindowTitle(f"ChatINL 用户: {self.client.username}")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.screen = QApplication.primaryScreen().geometry()  # 获取屏幕尺寸
        x = (self.screen.width() - 650) // 2  # 计算水平居中位置
        y = (self.screen.height() - 500) // 2  # 计算垂直居中位置
        self.setGeometry(x, y, 650, 500)  # 设置窗口位置和大小
        self.setMinimumSize(450, 500)
        # 初始化好友列表宽度变量
        self.friend_list_width = 180
        # 好友消息及未读信息记录
        self.last_message_times = {}
        self.unread_messages = {}
        # 分页加载参数
        self.current_page = 1
        self.page_size = 20
        self.loading_history = False
        self.has_more_history = True
        # 聊天区域组件字典
        self.chat_components = {
            'area_widget': None,
            'scroll': None,
            'input': None,
            'send_button': None,
            'online': None,
            'chat': None
        }
        self._init_ui()
        self._init_notifications()

    # ----------- UI 初始化 -----------
    def _init_ui(self):
        main_layout = QGridLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        # 左侧：好友列表及添加好友按钮
        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)
        self.add_button = QPushButton("添加好友", self)
        self.add_button.setFixedHeight(40)
        style_button(self.add_button)
        self.add_button.clicked.connect(lambda: asyncio.create_task(self.async_show_add_friend()))
        left_layout.addWidget(self.add_button)
        self.friend_list = QListWidget(self)
        self.friend_list.setFixedWidth(self.friend_list_width)
        self.friend_list.setSelectionMode(QListWidget.SingleSelection)
        self.friend_list.setFocusPolicy(Qt.StrongFocus)
        self.friend_list.setFrameShape(QListWidget.NoFrame)
        style_list_widget(self.friend_list)
        self.friend_list.itemClicked.connect(lambda item: asyncio.create_task(self.select_friend(item)))
        # Esc 键处理
        self.friend_list.keyPressEvent = self.handle_friend_list_key_press
        left_layout.addWidget(self.friend_list)
        # 右侧：聊天区域
        self.content_widget = QWidget(self)
        self.content_layout = QGridLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.default_label = QLabel(self)
        self.default_label.setPixmap(QIcon(resource_path("icon.ico")).pixmap(128, 128))
        self.default_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.default_label, 0, 0, Qt.AlignCenter)
        main_layout.addWidget(left_panel, 0, 0, -1, 1)
        main_layout.addWidget(self.content_widget, 0, 1, -1, 1)
        main_layout.setColumnStretch(1, 1)
        self._update_friend_list_width()

    def resizeEvent(self, event):
        """窗口大小变化时，调整好友列表宽度"""
        self._update_friend_list_width()
        super().resizeEvent(event)

    def _update_friend_list_width(self):
        """根据窗口宽度更新好友列表的宽度"""
        if hasattr(self, 'friend_list'):
            window_width = self.width()
            if window_width <= 500:
                self.friend_list_width = 75
            else:
                self.friend_list_width = 180
            self.friend_list.setFixedWidth(self.friend_list_width)
    def FriendSetSize(self):
        """根据窗口大小动态调整 FriendSetSize 的值"""
        if self.width() >= 500:
            self.FriendSetSize = 50
        else:
            self.FriendSetSize = 180

    def _init_notifications(self):
        self.notification_sender = None
        self.tray_icon.messageClicked.connect(self.on_notification_clicked)
        self.setFocusPolicy(Qt.StrongFocus)

    # ----------- 好友列表与聊天区域管理 -----------
    def handle_friend_list_key_press(self, event):
        if event.key() == Qt.Key_Escape:
            self.friend_list.clearSelection()
            self.clear_chat_area()
            self.client.current_friend = None
        else:
            QListWidget.keyPressEvent(self.friend_list, event)

    def clear_chat_area(self):
        """清空聊天区域并显示默认图片"""
        for key in self.chat_components:
            if self.chat_components[key]:
                self.chat_components[key].deleteLater()
                self.chat_components[key] = None
        self.default_label.show()

    def setup_chat_area(self):
        """初始化聊天区域组件"""
        self.default_label.hide()
        bg = "#e9e9e9"
        # 聊天区域容器
        self.chat_components['area_widget'] = QWidget(self)
        area_layout = QVBoxLayout(self.chat_components['area_widget'])
        area_layout.setContentsMargins(0, 0, 0, 0)
        area_layout.setSpacing(0)
        # 在线状态
        self.friend_status_widget = OnLine(self)
        self.friend_status_widget.setStyleSheet("border: none; background-color: #ffffff;")
        self.friend_status_widget.setFixedHeight(50)
        self.chat_components['online'] = self.friend_status_widget
        # 聊天记录显示区
        self.chat_components['chat'] = ChatAreaWidget(self)
        self.chat_components['chat'].setStyleSheet(f"border: 1px; background-color: {bg};")
        # 滚动区域
        self.chat_components['scroll'] = QScrollArea(self)
        self.chat_components['scroll'].viewport().setStyleSheet(f"border: none; background-color: {bg};")
        self.chat_components['scroll'].setFrameShape(QFrame.NoFrame)
        self.chat_components['scroll'].setWidgetResizable(True)
        self.chat_components['scroll'].setWidget(self.chat_components['chat'])
        style_scrollbar(self.chat_components['scroll'])
        self.chat_components['scroll'].verticalScrollBar().valueChanged.connect(self.on_scroll)
        area_layout.addWidget(self.friend_status_widget)
        area_layout.addWidget(self.chat_components['scroll'])
        # 消息输入与发送
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

    def _reset_chat_area(self):
        """重置聊天区域和分页参数"""
        self.clear_chat_area()
        self.setup_chat_area()
        self.current_page = 1
        self.has_more_history = True

    def on_scroll(self, value):
        """滚动到顶部时加载更多历史记录"""
        if value == 0 and self.has_more_history and not self.loading_history:
            asyncio.create_task(self.load_more_chat_history())

    def _scroll_to_bottom(self):
        QTimer.singleShot(0, lambda: self.chat_components['scroll'].verticalScrollBar().setValue(
            self.chat_components['scroll'].verticalScrollBar().maximum()))

    def should_scroll_to_bottom(self):
        sb = self.chat_components['scroll'].verticalScrollBar()
        return (self.chat_components['chat'].height() <= self.chat_components['scroll'].viewport().height() or
                sb.value() >= sb.maximum() - 10)

    # ----------- 消息处理 -----------
    def add_message(self, msg, is_current, tstr):
        """在聊天区域添加消息气泡"""
        bubble = ChatBubbleWidget(msg, tstr, "right" if is_current else "left", is_current)
        self.chat_components['chat'].addBubble(bubble)
        if is_current or self.should_scroll_to_bottom():
            QTimer.singleShot(10, self._scroll_to_bottom)

    async def process_message(self, sender, msg, is_current, wt=None):
        wt = wt or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_message_times[sender] = wt
        if sender == self.client.current_friend:
            self.add_message(msg, is_current, format_time(wt))
        else:
            self.unread_messages[sender] = self.unread_messages.get(sender, 0) + 1
            self.show_notification(f"用户 {sender}:", msg)
        await self.update_friend_list()

    async def handle_new_message(self, res):
        sender = res.get("from")
        msg = res.get("message")
        wt = res.get("write_time")
        if sender == self.client.current_friend:
            self.add_message(msg, False, format_time(wt))
        else:
            await self.process_message(sender, msg, False, wt)

    async def send_message(self):
        text = self.chat_components['input'].toPlainText().strip()
        if not self.client.current_friend or not text:
            return
        await self.client.send_message(self.client.username, self.client.current_friend, text)
        await self.process_message(self.client.current_friend, text, True)
        self.chat_components['input'].clear()

    async def load_more_chat_history(self):
        if not self.client.current_friend or not self.has_more_history:
            return
        self.loading_history = True
        scroll_bar = self.chat_components['scroll'].verticalScrollBar()
        old_value = scroll_bar.value()
        res = await self.client.get_chat_history_paginated(self.client.current_friend, self.current_page, self.page_size)
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

    # ----------- 好友列表更新与选择 -----------
    async def update_friend_list(self, friends=None):
        friends = friends if friends is not None else self.client.friends
        current_friend = self.client.current_friend
        self.friend_list.clear()
        online_friends = sorted(
            [f for f in friends if f.get("online")],
            key=lambda x: self.last_message_times.get(x["username"], "1970-01-01 00:00:00"),
            reverse=True)
        offline_friends = sorted(
            [f for f in friends if not f.get("online")],
            key=lambda x: self.last_message_times.get(x["username"], "1970-01-01 00:00:00"),
            reverse=True)
        sorted_friends = online_friends + offline_friends
        current_online = False
        for f in sorted_friends:
            uname = f["username"]
            item = QListWidgetItem(self.friend_list)
            item.setSizeHint(QSize(0, 40))
            self.friend_list.setItemWidget(item, FriendItemWidget(uname, f.get("online", False), self.unread_messages.get(uname, 0)))
            if uname == current_friend:
                item.setSelected(True)
                current_online = f.get("online", False)
        if current_friend:
            self.friend_status_widget.update_status(current_friend, current_online)

    async def select_friend(self, item):
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

    # ----------- 系统托盘通知 -----------
    def show_notification(self, sender, msg):
        self.notification_sender = sender.replace("用户 ", "").rstrip(":")
        self.tray_icon.showMessage(sender, msg, QIcon(resource_path("icon.ico")), 2000)

    def on_notification_clicked(self):
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

    # ----------- 添加好友对话框 -----------
    async def async_show_add_friend(self):
        d = QDialog(self)
        d.setWindowTitle("添加好友")
        d.setFixedSize(300, 100)
        v = QVBoxLayout(d)
        v.addWidget(QLabel("请输入好友用户名：", d))
        inp = QLineEdit(d)
        style_line_edit(inp)
        inp.setPlaceholderText("好友用户名")
        inp.setFixedHeight(30)
        v.addWidget(inp)
        h = QHBoxLayout()
        b_cancel = QPushButton("取消", d)
        style_rounded_button(b_cancel)
        b_cancel.setFixedHeight(30)
        b_cancel.clicked.connect(d.reject)
        h.addWidget(b_cancel)
        b_confirm = QPushButton("确认", d)
        style_rounded_button(b_confirm)
        b_confirm.setFixedHeight(30)
        b_confirm.setEnabled(False)
        h.addWidget(b_confirm)
        v.addLayout(h)
        inp.textChanged.connect(lambda: b_confirm.setEnabled(bool(inp.text().strip())))
        async def proc_add():
            res = await self.client.add_friend(inp.text().strip())
            if hasattr(self, 'show_return_message'):
                self.show_return_message(res)
            d.accept()
        def key_h(e):
            if e.key() == Qt.Key_Return and b_confirm.isEnabled():
                asyncio.create_task(proc_add())
            elif e.key() == Qt.Key_Escape:
                d.reject()
            else:
                QDialog.keyPressEvent(d, e)
        d.keyPressEvent = key_h
        b_confirm.clicked.connect(lambda: asyncio.create_task(proc_add()))
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        d.finished.connect(lambda _: fut.set_result(None))
        d.show()
        await fut

    # ----------- 事件处理 -----------
    def closeEvent(self, e):
        e.ignore()
        self.friend_list.clearSelection()
        self.clear_chat_area()
        self.client.current_friend = None
        self.hide()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.friend_list.clearSelection()
            self.clear_chat_area()
            self.client.current_friend = None
        else:
            super().keyPressEvent(e)

# ---------------- 应用退出与系统托盘 ----------------
def quit_app():
    async def shutdown():
        try:
            if login_window.chat_client and login_window.chat_client.client_socket:
                await login_window.chat_client.close_connection()
        except Exception as ex:
            print("退出时关闭连接异常:", ex)
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

def on_tray_activated(reason):
    global chat_window_global
    if reason == QSystemTrayIcon.Trigger:
        if chat_window_global:
            chat_window_global.show()
            chat_window_global.activateWindow()
        else:
            login_window.show()
            login_window.activateWindow()

# ---------------- 主函数 ----------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    tray_icon = QSystemTrayIcon(app)
    tray_icon.setIcon(QIcon(resource_path("icon.ico")))
    tray_icon.setToolTip("ChatINL")
    tray_icon.show()
    m = QMenu()
    m.addAction("退出", quit_app)
    tray_icon.setContextMenu(m)
    tray_icon.activated.connect(on_tray_activated)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    login_window = LoginWindow()
    login_window.show()
    global chat_window_global
    chat_window_global = None
    with loop:
        sys.exit(loop.run_forever())
