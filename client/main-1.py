#!/usr/bin/env python3
import sys, asyncio
from datetime import datetime, timedelta
from PyQt5.QtCore import QTimer, Qt, QSize
from PyQt5.QtGui import QPainter, QPixmap, QColor, QFont
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QGridLayout, QTextEdit, QLineEdit,
    QVBoxLayout, QHBoxLayout, QLabel, QDialog, QMessageBox, QListWidget,
    QListWidgetItem, QTextBrowser, QSystemTrayIcon, QStyle, QMenu
)
from qasync import QEventLoop
from chat_client_1 import ChatClient
from Interface_Controls import style_button, style_line_edit, style_text_edit, style_list_widget

# 自定义好友列表项显示控件
class FriendItemWidget(QWidget):
    def __init__(self, username, online=False, unread=0, parent=None):
        super().__init__(parent)
        self.username = username
        self.online = online
        self.unread = unread
        self.init_ui()

    def init_ui(self):
        # 不固定高度，让布局自动决定
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)
        self.layout.setAlignment(Qt.AlignVCenter)  # 所有元素在垂直方向居中对齐

        # 状态图标
        self.status_label = QLabel(self)
        self.status_label.setFixedSize(15, 15)  # 控制状态图标的大小
        self.status_label.setAlignment(Qt.AlignCenter)

        # 好友名称，设置加粗和大字号
        self.name_label = QLabel(self)
        font = QFont("微软雅黑")
        font.setBold(True)
        font.setPointSize(12)  # 设置字体大小
        self.name_label.setFont(font)
        self.name_label.setAlignment(Qt.AlignVCenter)  # 确保文本垂直居中

        # 未读消息徽章
        self.badge_label = QLabel(self)
        self.badge_label.setFixedSize(15, 15)  # 控制徽章的大小
        self.badge_label.setAlignment(Qt.AlignCenter)

        # 添加控件到布局
        self.layout.addWidget(self.status_label)
        self.layout.addWidget(self.name_label)
        self.layout.addStretch(1)  # 拉伸填充剩余空间，确保控件垂直居中
        self.layout.addWidget(self.badge_label)

        self.update_display()

    def update_display(self):
        # 在线时显示绿色小圆点，否则不显示
        if self.online:
            pixmap = QPixmap(10, 10)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor("#86f08b"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, 10, 10)  # 控制圆点大小
            painter.end()
            self.status_label.setPixmap(pixmap)
        else:
            self.status_label.clear()

        # 显示好友名称
        self.name_label.setText(self.username)

        # 如果有未读消息，则显示红色徽章（白色数字）；否则清空徽章
        if self.unread > 0:
            size = 15
            badge = QPixmap(size, size)
            badge.fill(Qt.transparent)
            painter = QPainter(badge)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor("#e94b4b"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, size, size)  # 控制徽章大小
            painter.setPen(QColor("white"))
            font = QFont()
            font.setBold(True)
            font.setPointSize(10)  # 设置徽章上的字体大小
            painter.setFont(font)
            painter.drawText(badge.rect(), Qt.AlignCenter, str(self.unread))
            painter.end()
            self.badge_label.setPixmap(badge)
        else:
            self.badge_label.clear()

class LoginWindow(QDialog):
    """
    登录窗口：通过输入账号密码登录，成功后启动后台数据读取任务，并显示聊天主界面。
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("INL")
        self.setFixedSize(250, 110)
        self.chat_client = ChatClient()  # 创建客户端实例
        self.chat_window = None
        self._init_ui()
        self.login_button.clicked.connect(self.on_login)

    def _init_ui(self):
        layout = QGridLayout(self)
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("请输入账号")
        self.username_input.setMinimumHeight(30)
        style_line_edit(self.username_input)
        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(30)
        style_line_edit(self.password_input)
        self.login_button = QPushButton("登录", self)
        self.login_button.setMinimumHeight(30)
        style_button(self.login_button)
        layout.addWidget(self.username_input, 0, 1)
        layout.addWidget(self.password_input, 1, 1)
        layout.addWidget(self.login_button, 2, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(2, 1)

    def show_error_message(self, message: str):
        QMessageBox.critical(self, "错误", message)

    def on_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        if not username or not password:
            return self.show_error_message("账号或密码不能为空")
        if not self.chat_client or not self.chat_client.client_socket:
            return self.show_error_message("未连接到服务器，请检查网络或重试")
        asyncio.create_task(self.async_login(username, password))

    async def async_login(self, username: str, password: str):
        result = await self.chat_client.authenticate(username, password)
        if result == "认证成功":
            self.accept()  # 关闭登录窗口
            asyncio.create_task(self.chat_client.start_reader())
            if self.chat_window is None:
                # 将全局托盘图标传入聊天窗口，不再重复创建
                self.chat_window = ChatWindow(self.chat_client, tray_icon)
            self.chat_client.on_new_message_callback = self.chat_window.handle_new_message
            self.chat_window.show()
            await self.chat_window.update_friend_list_from_server()
        elif result == "该账号已登录":
            self.show_error_message("该账号已登录")
        else:
            self.show_error_message("账号或密码错误")

class ChatWindow(QWidget):
    """
    聊天主窗口：
      - 左侧显示好友列表（使用自定义的 FriendItemWidget 显示在线状态和未读消息）
      - 右侧为聊天记录显示区
      - 底部为消息输入和发送按钮
    """
    def __init__(self, chat_client: ChatClient, tray_icon: QSystemTrayIcon):
        super().__init__()
        self.client = chat_client
        self.setWindowTitle(f"INL 用户: {self.client.username}")
        self.setGeometry(100, 100, 650, 500)
        self.setMinimumSize(650, 500)
        self.tray_icon = tray_icon
        self.last_message_times = {}  # 存储各好友最新消息时间
        self.unread_messages = {}     # 存储每个好友的未读消息计数
        self._init_ui()
        self.new_message_timer = QTimer(self)
        self.new_message_timer.timeout.connect(lambda: asyncio.create_task(self.check_new_messages()))
        self.new_message_timer.start(10000)
        # 定时刷新好友列表（包括在线状态），实现近似实时更新
        self.friend_list_timer = QTimer(self)
        self.friend_list_timer.timeout.connect(lambda: asyncio.create_task(self.update_friend_list_from_server()))
        self.friend_list_timer.start(5000)

    def _init_ui(self):
        layout = QGridLayout(self)
        # 好友列表容器宽度恢复为 110 像素
        self.friend_list = QListWidget(self)
        self.friend_list.setFixedWidth(110)
        self.friend_list.setSelectionMode(QListWidget.SingleSelection)
        self.friend_list.setFocusPolicy(Qt.NoFocus)
        style_list_widget(self.friend_list)
        self.add_button = QPushButton("添加好友", self)
        style_button(self.add_button)
        self.add_button.clicked.connect(lambda: asyncio.create_task(self.async_show_add_friend()))
        self.chat_browser = QTextBrowser(self)
        self.chat_browser.setReadOnly(True)
        self.message_input = QTextEdit(self)
        self.message_input.setPlaceholderText("输入消息")
        self.message_input.setFixedHeight(60)
        style_text_edit(self.message_input)
        self.send_button = QPushButton("发送", self)
        self.send_button.setFixedSize(110, 60)
        style_button(self.send_button)
        layout.addWidget(self.add_button, 0, 0)
        layout.addWidget(self.friend_list, 1, 0, 2, 1)
        layout.addWidget(self.chat_browser, 0, 1, 2, 2)
        layout.addWidget(self.message_input, 2, 1)
        layout.addWidget(self.send_button, 2, 2)
        layout.setColumnStretch(1, 1)
        self.friend_list.itemClicked.connect(lambda item: asyncio.create_task(self.select_friend(item)))
        self.send_button.clicked.connect(lambda: asyncio.create_task(self.send_message()))

    def show_return_message(self, message: str):
        QMessageBox.information(self, "消息", message)

    async def async_show_add_friend(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("添加好友")
        dialog.setFixedSize(300, 100)
        vbox = QVBoxLayout(dialog)
        label = QLabel("请输入好友用户名：", dialog)
        vbox.addWidget(label)
        input_field = QLineEdit(dialog)
        style_line_edit(input_field)
        input_field.setPlaceholderText("好友用户名")
        input_field.setFixedHeight(30)
        vbox.addWidget(input_field)
        hbox = QHBoxLayout()
        cancel_btn = QPushButton("取消", dialog)
        style_button(cancel_btn)
        cancel_btn.setFixedHeight(30)
        cancel_btn.clicked.connect(dialog.reject)
        hbox.addWidget(cancel_btn)
        confirm_btn = QPushButton("确认", dialog)
        style_button(confirm_btn)
        confirm_btn.setFixedHeight(30)
        confirm_btn.setEnabled(False)
        hbox.addWidget(confirm_btn)
        vbox.addLayout(hbox)
        input_field.textChanged.connect(lambda: confirm_btn.setEnabled(bool(input_field.text().strip())))

        async def process_add_friend():
            friend_username = input_field.text().strip()
            result = await self.client.add_friend(friend_username)
            self.show_return_message(result)
            dialog.accept()
            await self.update_friend_list_from_server()

        confirm_btn.clicked.connect(lambda: asyncio.create_task(process_add_friend()))
        future = asyncio.get_running_loop().create_future()
        dialog.finished.connect(lambda _: future.set_result(None))
        dialog.show()
        await future

    def add_message(self, _sender: str, message: str, is_current_user: bool, time_str: str):
        sender = self.client.username if is_current_user else _sender
        align = "right" if is_current_user else "left"
        html = f'''
        <table style="width:100%; border-collapse: collapse; margin-bottom:10px; text-align:{align};">
          <tr>
            <td style="vertical-align:top;">
              <div style="display:inline-block; padding:5px; border-radius:5px; text-align:{align};">
                <div style="font-weight:bold; margin-bottom:2px;">{sender}</div>
                <div style="margin:3px 0;">{message}</div>
                <div style="font-size:10px; color:#666;">{time_str}</div>
              </div>
            </td>
          </tr>
        </table>
        '''
        self.chat_browser.append(html)
        self.chat_browser.verticalScrollBar().setValue(self.chat_browser.verticalScrollBar().maximum())

    async def send_message(self):
        if not self.client.current_friend:
            print("没有选中好友，无法发送消息")
            return
        text = self.message_input.toPlainText().strip()
        if text:
            await self.client.send_message(self.client.username, self.client.current_friend, text)
            current_time = datetime.now().strftime("%H:%M")
            self.add_message(self.client.username, text, True, current_time)
            self.message_input.clear()

    async def update_friend_list_from_server(self):
        # 从服务器获取好友列表（每个好友包含 username 与 online 字段）
        friends_data = await self.client.request_friend_list()
        # 保留当前选中好友名称，避免刷新后丢失选中效果
        current = self.client.current_friend
        self.friend_list.clear()
        for friend_info in friends_data:
            friend_username = friend_info.get("username")
            online = friend_info.get("online", False)
            unread = self.unread_messages.get(friend_username, 0)
            widget = FriendItemWidget(friend_username, online, unread)
            item = QListWidgetItem(self.friend_list)
            # 设置好友项尺寸提示，保持项高度约 40 像素
            item.setSizeHint(QSize(0, 40))
            self.friend_list.addItem(item)
            self.friend_list.setItemWidget(item, widget)
            # 若该好友为当前聊天对象，则选中该项
            if friend_username == current:
                item.setSelected(True)

    async def select_friend(self, item: QListWidgetItem):
        widget = self.friend_list.itemWidget(item)
        if widget:
            selected_friend = widget.username
        else:
            selected_friend = item.data(Qt.UserRole)
        self.client.current_friend = selected_friend
        self.chat_browser.clear()
        response = await self.client.get_chat_history(selected_friend)
        if response and response.get("type") == "chat_history":
            for msg in response.get("data", []):
                display_name = self.client.username if msg.get("is_current_user") else msg.get("sender_username", selected_friend)
                self.add_message(display_name, msg.get("message", ""),
                                 msg.get("is_current_user", False), msg.get("write_time", ""))
        else:
            print("聊天记录为空或响应错误。")
        # 清空该好友的未读消息计数，并刷新好友列表
        if selected_friend in self.unread_messages:
            self.unread_messages[selected_friend] = 0
            await self.update_friend_list_from_server()

    async def check_new_messages(self):
        for i in range(self.friend_list.count()):
            item = self.friend_list.item(i)
            widget = self.friend_list.itemWidget(item)
            if not widget:
                continue
            friend = widget.username
            if friend == self.client.current_friend:
                continue
            history = await self.client.get_chat_history(friend)
            if history and history.get("data"):
                last_msg = history["data"][-1]
                last_time = last_msg["write_time"]
                if friend not in self.last_message_times:
                    self.last_message_times[friend] = last_time
                elif last_time != self.last_message_times[friend]:
                    self.last_message_times[friend] = last_time
                    self.unread_messages[friend] = self.unread_messages.get(friend, 0) + 1
                    await self.update_friend_list_from_server()

    def show_notification(self, sender: str, message: str):
        self.tray_icon.showMessage(sender, message, QSystemTrayIcon.Information, 3000)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            if event.modifiers() == Qt.ControlModifier:
                self.message_input.insertPlainText("\n")
            else:
                asyncio.create_task(self.send_message())
        else:
            super().keyPressEvent(event)

    async def handle_new_message(self, response: dict):
        sender = response.get("from")
        message = response.get("message")
        write_time = response.get("write_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        try:
            ts = datetime.strptime(write_time, "%Y-%m-%d %H:%M:%S")
            formatted_time = ts.strftime("%H:%M") if (datetime.now()-ts) < timedelta(days=1) else ts.strftime("%m.%d %H:%M")
        except Exception:
            formatted_time = datetime.now().strftime("%H:%M")
        if sender == self.client.current_friend:
            self.add_message(sender, message, False, formatted_time)
        else:
            self.unread_messages[sender] = self.unread_messages.get(sender, 0) + 1
            await self.update_friend_list_from_server()
            self.show_notification(f"用户 {sender}:", message)

def quit_app():
    """
    退出处理：调用客户端关闭连接，然后退出应用及事件循环
    """
    async def shutdown():
        try:
            if login_window.chat_client and login_window.chat_client.client_socket:
                await login_window.chat_client.close_connection()
        except Exception as e:
            print("退出时关闭连接异常:", e)
        tray_icon.hide()
        loop.stop()
        app.quit()
    asyncio.create_task(shutdown())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    tray_icon = QSystemTrayIcon(app)
    tray_icon.setIcon(app.style().standardIcon(QStyle.SP_ComputerIcon))
    tray_icon.show()
    menu = QMenu()
    exit_action = menu.addAction("退出")
    exit_action.triggered.connect(quit_app)
    tray_icon.setContextMenu(menu)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    login_window = LoginWindow()
    login_window.show()
    with loop:
        sys.exit(loop.run_forever())
