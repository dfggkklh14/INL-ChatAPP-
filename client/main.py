#!/usr/bin/env python3
import sys, os, asyncio
from datetime import datetime, timedelta
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QGridLayout, QLineEdit,
                             QHBoxLayout, QLabel, QDialog, QMessageBox, QListWidget,
                             QListWidgetItem, QSystemTrayIcon, QMenu, QVBoxLayout, QScrollArea)
from qasync import QEventLoop
from chat_client import ChatClient
from Interface_Controls import (MessageInput, FriendItemWidget, ChatAreaWidget, ChatBubbleWidget,
                                style_button, style_line_edit, style_text_edit, style_list_widget, style_scrollbar)


def resource_path(relative_path: str) -> str:
    """获取资源路径"""
    # PyInstaller打包后的路径
    if getattr(sys, 'frozen', False):
        # 如果是打包后的应用，返回打包后临时目录中的资源路径
        base = sys._MEIPASS
    else:
        # 如果是开发环境，使用当前脚本所在的路径
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)

def format_time(timestamp: str) -> str:
    """格式化时间"""
    try:
        ts = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        return ts.strftime("%H:%M") if (datetime.now() - ts) < timedelta(days=1) else ts.strftime("%m.%d %H:%M")
    except Exception:
        return datetime.now().strftime("%H:%M")

# ---------------- 登录窗口 ----------------
class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChatINL 登录")
        self.setFixedSize(250, 110)
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.chat_client = ChatClient()
        self._init_ui()

    def _init_ui(self):
        """初始化 UI"""
        layout = QGridLayout(self)
        for i, (placeholder, echo) in enumerate([("请输入账号", QLineEdit.Normal), ("请输入密码", QLineEdit.Password)]):
            le = QLineEdit(self)
            le.setPlaceholderText(placeholder)
            le.setMinimumHeight(30)
            if echo == QLineEdit.Password: le.setEchoMode(QLineEdit.Password)
            style_line_edit(le)
            setattr(self, f"{'username' if i==0 else 'password'}_input", le)
            layout.addWidget(le, i, 1)
        self.login_button = QPushButton("登录", self)
        self.login_button.setMinimumHeight(30)
        style_button(self.login_button)
        layout.addWidget(self.login_button, 2, 1)
        layout.setColumnStretch(0, 1); layout.setColumnStretch(2, 1)
        self.login_button.clicked.connect(self.on_login)

    def show_error_message(self, message: str):
        """显示错误消息"""
        QMessageBox.critical(self, "错误", message)

    def on_login(self):
        """登录时"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        if not username or not password:
            return self.show_error_message("账号或密码不能为空")
        if not self.chat_client or not self.chat_client.client_socket:
            return self.show_error_message("未连接到服务器，请检查网络或重试")
        asyncio.create_task(self.async_login(username, password))

    async def async_login(self, username: str, password: str):
        """异步登录"""
        result = await self.chat_client.authenticate(username, password)
        if result == "认证成功":
            self.accept()
            asyncio.create_task(self.chat_client.start_reader())
            global chat_window_global
            if chat_window_global is None:
                chat_window_global = ChatWindow(self.chat_client, tray_icon)
            self.chat_client.on_new_message_callback = chat_window_global.handle_new_message
            chat_window_global.show()
            await chat_window_global.update_friend_list_from_server()
        else:
            self.show_error_message(result)

# ---------------- 聊天主窗口 ----------------
class ChatWindow(QWidget):
    def __init__(self, chat_client: ChatClient, tray_icon: QSystemTrayIcon):
        super().__init__()
        self.client, self.tray_icon = chat_client, tray_icon
        self.setWindowTitle(f"ChatINL 用户: {self.client.username}")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.setGeometry(100, 100, 650, 500)
        self.setMinimumSize(650, 500)
        self.last_message_times, self.unread_messages = {}, {}
        self.chat_components = {'area_widget': None, 'scroll': None, 'input': None, 'send_button': None}
        self._init_ui(); self._init_timers(); self._init_notifications()

    def _init_ui(self):
        """初始化 UI"""
        main_layout = QGridLayout(self); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0)
        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel); left_layout.setContentsMargins(0,0,0,0); left_layout.setSpacing(2)
        self.add_button = QPushButton("添加好友", self)
        self.add_button.setFixedHeight(40)
        style_button(self.add_button)
        self.add_button.clicked.connect(lambda: asyncio.create_task(self.async_show_add_friend()))
        left_layout.addWidget(self.add_button)
        self.friend_list = QListWidget(self)
        self.friend_list.setFixedWidth(180)
        self.friend_list.setSelectionMode(QListWidget.SingleSelection)
        self.friend_list.setFocusPolicy(Qt.StrongFocus)
        self.friend_list.setFrameShape(QListWidget.NoFrame)
        style_list_widget(self.friend_list)
        self.friend_list.itemClicked.connect(lambda item: asyncio.create_task(self.select_friend(item)))
        self.friend_list.keyPressEvent = self.handle_friend_list_key_press
        left_layout.addWidget(self.friend_list)
        self.content_widget = QWidget(self)
        self.content_layout = QGridLayout(self.content_widget)
        self.content_layout.setContentsMargins(10,10,10,10)
        self.default_label = QLabel(self)
        self.default_label.setPixmap(QIcon(resource_path("icon.ico")).pixmap(128, 128))
        self.default_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.default_label, 0, 0, Qt.AlignCenter)
        main_layout.addWidget(left_panel, 0, 0, -1, 1)
        main_layout.addWidget(self.content_widget, 0, 1, -1, 1)
        main_layout.setColumnStretch(1, 1)

    def _init_timers(self):
        """初始化定时器"""
        self.new_message_timer = QTimer(self); self.new_message_timer.timeout.connect(lambda: asyncio.create_task(self.check_new_messages())); self.new_message_timer.start(10000)
        self.friend_list_timer = QTimer(self); self.friend_list_timer.timeout.connect(lambda: asyncio.create_task(self.update_friend_list_from_server())); self.friend_list_timer.start(5000)

    def _init_notifications(self):
        """初始化通知"""
        self.notification_sender = None
        self.tray_icon.messageClicked.connect(self.on_notification_clicked)
        self.setFocusPolicy(Qt.StrongFocus)

    def handle_friend_list_key_press(self, event):
        """处理好友列表按键"""
        if event.key() == Qt.Key_Escape:
            self.friend_list.clearSelection(); self.clear_chat_area(); self.client.current_friend = None
        else:
            QListWidget.keyPressEvent(self.friend_list, event)

    def clear_chat_area(self):
        """清除聊天区域"""
        for key in self.chat_components:
            if self.chat_components[key]:
                self.chat_components[key].deleteLater(); self.chat_components[key] = None
        self.default_label.show()

    def setup_chat_area(self):
        """设置聊天区域"""
        self.default_label.hide()
        self.chat_components['area_widget'] = ChatAreaWidget(self)
        self.chat_components['scroll'] = QScrollArea(self)
        self.chat_components['scroll'].setWidgetResizable(True)
        self.chat_components['scroll'].setWidget(self.chat_components['area_widget'])
        style_scrollbar(self.chat_components['scroll'])
        self.chat_components['input'] = MessageInput(self)
        self.chat_components['input'].setPlaceholderText("输入消息")
        self.chat_components['input'].setFixedHeight(60)
        style_text_edit(self.chat_components['input'])
        self.chat_components['send_button'] = QPushButton("发送", self)
        self.chat_components['send_button'].setFixedSize(110, 60)
        style_button(self.chat_components['send_button'])
        self.chat_components['send_button'].clicked.connect(lambda: asyncio.create_task(self.send_message()))
        self.content_layout.addWidget(self.chat_components['scroll'], 0, 0, 1, 2)
        self.content_layout.addWidget(self.chat_components['input'], 1, 0)
        self.content_layout.addWidget(self.chat_components['send_button'], 1, 1)

    def _scroll_to_bottom(self):
        """将滚动条滚动到底部"""
        QTimer.singleShot(0, lambda: self.chat_components['scroll'].verticalScrollBar().setValue(self.chat_components['scroll'].verticalScrollBar().maximum()))

    def should_scroll_to_bottom(self) -> bool:
        """判断是否需要滚动到底部"""
        if not self.chat_components['scroll']: return False
        sb = self.chat_components['scroll'].verticalScrollBar()
        return (self.chat_components['area_widget'].height() <= self.chat_components['scroll'].viewport().height() or
                sb.value() >= sb.maximum() - 10)

    def add_message(self, message: str, is_current_user: bool, time_str: str):
        """添加消息"""
        should_scroll = is_current_user or self.should_scroll_to_bottom()
        bubble = ChatBubbleWidget(message, time_str, "right" if is_current_user else "left", is_current_user)
        self.chat_components['area_widget'].addBubble(bubble)
        if should_scroll:
            QTimer.singleShot(10, self._scroll_to_bottom)

    async def process_message(self, sender: str, message: str, is_current_user: bool, write_time: str = None):
        """处理消息"""
        write_time = write_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_message_times[sender] = write_time
        if sender == self.client.current_friend or is_current_user:
            self.add_message(message, is_current_user, format_time(write_time))
        else:
            self.unread_messages[sender] = self.unread_messages.get(sender, 0) + 1
            self.show_notification(f"用户 {sender}:", message)
        await self.update_friend_list_from_server()

    async def handle_new_message(self, response: dict):
        """处理新消息"""
        sender, message, write_time, _type = response.get("from"), response.get("message"), response.get("write_time"), response.get("type")
        if sender == self.client.current_friend:
            self.add_message(message, False, format_time(write_time))
        else:
            await self.process_message(sender, message, False, write_time)

    async def send_message(self):
        """发送消息"""
        text = self.chat_components['input'].toPlainText().strip()
        if not self.client.current_friend or not text: return
        await self.client.send_message(self.client.username, self.client.current_friend, text)
        await self.process_message(self.client.current_friend, text, True)
        self.chat_components['input'].clear()

    async def update_friend_list_from_server(self):
        """从服务器更新好友列表"""
        friends_data = await self.client.request_friend_list()
        current = self.client.current_friend
        self.friend_list.clear()
        for friend_info in sorted(friends_data, key=lambda x: (
        not x.get("online"), self.last_message_times.get(x["username"], "1970-01-01 00:00:00")), reverse=False):
            username = friend_info["username"]
            item = QListWidgetItem(self.friend_list)
            item.setSizeHint(QSize(0, 40))
            self.friend_list.setItemWidget(item, FriendItemWidget(username, friend_info.get("online", False),
                                                                  self.unread_messages.get(username, 0)))
            if username == current:
                item.setSelected(True)

    async def select_friend(self, item: QListWidgetItem):
        """选择朋友"""
        if not item:
            self.clear_chat_area(); self.client.current_friend = None; return
        widget = self.friend_list.itemWidget(item)
        selected_friend = widget.username if widget else item.data(Qt.UserRole)
        self.client.current_friend = selected_friend
        if not self.chat_components['area_widget']:
            self.setup_chat_area()
        else:
            self.chat_components['area_widget'].clearBubbles()
        response = await self.client.get_chat_history(selected_friend)
        if response and response.get("type") == "chat_history":
            bubbles = [ChatBubbleWidget(msg.get("message", ""), msg.get("write_time", ""),
                         "right" if msg.get("is_current_user") else "left", msg.get("is_current_user", False))
                         for msg in response.get("data", [])]
            for bubble in bubbles:
                self.chat_components['area_widget'].addBubble(bubble)
            if bubbles:
                QTimer.singleShot(0, self._scroll_to_bottom)
        if selected_friend in self.unread_messages:
            self.unread_messages[selected_friend] = 0
            await self.update_friend_list_from_server()

    async def check_new_messages(self):
        """检查新消息"""
        for i in range(self.friend_list.count()):
            item = self.friend_list.item(i)
            widget = self.friend_list.itemWidget(item)
            if not widget or widget.username == self.client.current_friend:
                continue
            # 如果收到的消息是新消息，并且是他人发来的，增加未读消息
            if widget.username in self.unread_messages:
                last_time = self.unread_messages.get(widget.username)
                # 判断是否收到新消息
                if last_time > self.last_message_times.get(widget.username, 0):
                    # 使用 handle_new_message 中的 sender 和 _type 来进行计数
                    if widget.username != self.client.username:
                        self.unread_messages[widget.username] = self.unread_messages.get(widget.username, 0) + 1
        # 更新好友列表
        await self.update_friend_list_from_server()

    def show_notification(self, sender: str, message: str):
        """显示通知"""
        self.notification_sender = sender.replace("用户 ", "").rstrip(":")
        self.tray_icon.showMessage(sender, message, QIcon(resource_path("icon.ico")), 2000)

    def on_notification_clicked(self):
        """点击通知后"""
        if not self.notification_sender: return
        self.show(); self.activateWindow()
        for i in range(self.friend_list.count()):
            item = self.friend_list.item(i)
            widget = self.friend_list.itemWidget(item)
            if widget and widget.username == self.notification_sender:
                self.friend_list.setCurrentItem(item)
                asyncio.create_task(self.select_friend(item))
                break
        self.notification_sender = None

    async def async_show_add_friend(self):
        """异步显示添加好友"""
        self.friend_list_timer.stop()
        dialog = QDialog(self)
        dialog.setWindowTitle("添加好友"); dialog.setFixedSize(300, 100)
        vbox = QVBoxLayout(dialog)
        vbox.addWidget(QLabel("请输入好友用户名：", dialog))
        input_field = QLineEdit(dialog)
        style_line_edit(input_field); input_field.setPlaceholderText("好友用户名"); input_field.setFixedHeight(30)
        vbox.addWidget(input_field)
        hbox = QHBoxLayout()
        cancel_btn = QPushButton("取消", dialog); style_button(cancel_btn); cancel_btn.setFixedHeight(30)
        cancel_btn.clicked.connect(dialog.reject); hbox.addWidget(cancel_btn)
        confirm_btn = QPushButton("确认", dialog); style_button(confirm_btn); confirm_btn.setFixedHeight(30)
        confirm_btn.setEnabled(False); hbox.addWidget(confirm_btn)
        vbox.addLayout(hbox)
        input_field.textChanged.connect(lambda: confirm_btn.setEnabled(bool(input_field.text().strip())))
        async def process_add_friend():
            """进程添加好友"""
            result = await self.client.add_friend(input_field.text().strip())
            self.show_return_message(result) if hasattr(self, 'show_return_message') else None
            dialog.accept()
            await self.update_friend_list_from_server()
        def key_handler(event):
            """按键处理程序"""
            if event.key() == Qt.Key_Return and confirm_btn.isEnabled():
                asyncio.create_task(process_add_friend())
            elif event.key() == Qt.Key_Escape:
                dialog.reject()
            else:
                QDialog.keyPressEvent(dialog, event)
        dialog.keyPressEvent = key_handler
        confirm_btn.clicked.connect(lambda: asyncio.create_task(process_add_friend()))
        loop = asyncio.get_running_loop(); fut = loop.create_future()
        dialog.finished.connect(lambda _: fut.set_result(None)); dialog.show()
        await fut; self.friend_list_timer.start(5000)

    def closeEvent(self, event):
        """关闭事件"""
        event.ignore()
        self.friend_list.clearSelection(); self.clear_chat_area(); self.client.current_friend = None; self.hide()

    def keyPressEvent(self, event):
        """按键事件"""
        if event.key() == Qt.Key_Escape:
            self.friend_list.clearSelection(); self.clear_chat_area(); self.client.current_friend = None
        else:
            super().keyPressEvent(event)

# 退出程序时关闭连接
def quit_app():
    """退出应用程序"""
    async def shutdown():
        """关闭"""
        try:
            if login_window.chat_client and login_window.chat_client.client_socket:
                await login_window.chat_client.close_connection()
        except Exception as e:
            print("退出时关闭连接异常:", e)
        current = asyncio.current_task()
        tasks = [t for t in asyncio.all_tasks() if t is not current]
        for t in tasks: t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await loop.shutdown_asyncgens()
        tray_icon.hide(); loop.stop(); app.quit()
    asyncio.create_task(shutdown())

def on_tray_activated(reason):
    """在托盘上激活"""
    global chat_window_global
    if reason == QSystemTrayIcon.Trigger:
        if chat_window_global:
            chat_window_global.show(); chat_window_global.activateWindow()
        else:
            login_window.show(); login_window.activateWindow()

# ---------------- 主程序入口 ----------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    tray_icon = QSystemTrayIcon(app)
    tray_icon.setIcon(QIcon(resource_path("icon.ico")))
    tray_icon.setToolTip("ChatINL")
    tray_icon.show()
    menu = QMenu()
    exit_action = menu.addAction("退出")
    exit_action.triggered.connect(quit_app)
    tray_icon.setContextMenu(menu)
    tray_icon.activated.connect(on_tray_activated)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    login_window = LoginWindow()
    login_window.show()
    global chat_window_global
    chat_window_global = None
    with loop:
        sys.exit(loop.run_forever())
