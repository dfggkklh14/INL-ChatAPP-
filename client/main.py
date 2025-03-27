#!/usr/bin/env python3
import hashlib
import json
import logging
import sys
import os
import asyncio
import ctypes
from datetime import datetime
from typing import Optional, List, Dict, Callable

from PyQt5 import sip
from PyQt5.QtCore import Qt, QSize, QTimer, QEvent, QPoint
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QGridLayout, QLineEdit,
    QHBoxLayout, QLabel, QDialog, QMessageBox, QListWidget,
    QListWidgetItem, QSystemTrayIcon, QMenu, QVBoxLayout, QAbstractItemView)
from qasync import QEventLoop

from chat_client import ChatClient
from Interface_Controls import (FriendItemWidget, OnLine, theme_manager, StyleGenerator, generate_thumbnail,
                                FloatingLabel, run_async, load_theme_mode, AddFriendDialog, resource_path,
                                create_line_edit, create_themed_message_box, format_time)
from BubbleWidget import ChatAreaWidget, ChatBubbleWidget, create_confirmation_dialog
from FileConfirmDialog import FileConfirmDialog
from MessageInput import MessageInput
from Viewer import ImageViewer
from UserDetails import UserDetails
from register_page import RegisterWindow

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# 用于闪烁任务栏图标
class FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("hwnd", ctypes.c_void_p),
        ("dwFlags", ctypes.c_uint),
        ("uCount", ctypes.c_uint),
        ("dwTimeout", ctypes.c_uint),
    ]

# 登录窗口
class LoginWindow(QDialog):
    def __init__(self, main_app: "ChatApp") -> None:
        super().__init__()
        self.main_app = main_app
        self.chat_client = ChatClient()
        self._setup_ui()
        theme_manager.register(self)

    def _setup_ui(self) -> None:
        self.setWindowTitle("ChatINL 登录")
        self.setFixedSize(280, 140)
        self.setWindowIcon(QIcon(resource_path("icon/icon.ico")))

        layout = QGridLayout(self)
        self.username_input = create_line_edit(self, "请输入账号", QLineEdit.Normal)
        self.password_input = create_line_edit(self, "请输入密码", QLineEdit.Password)
        self.login_button = QPushButton("登录", self)
        self.login_button.setMinimumHeight(30)
        StyleGenerator.apply_style(self.login_button, "button", extra="border-radius: 4px;")
        self.login_button.clicked.connect(self.on_login)

        self.register_label = QLabel("注册", self)
        self.register_label.setAlignment(Qt.AlignCenter)
        self.register_label.setStyleSheet("color: #808080;")
        self.register_label.setCursor(Qt.PointingHandCursor)
        self.register_label.enterEvent = lambda event: self.register_label.setStyleSheet(
            "color: #4aa36c; text-decoration: underline;")
        self.register_label.leaveEvent = lambda event: self.register_label.setStyleSheet(
            "color: #808080; text-decoration: none;")
        self.register_label.mousePressEvent = self.on_register

        layout.addWidget(self.username_input, 0, 1)
        layout.addWidget(self.password_input, 1, 1)
        layout.addWidget(self.login_button, 2, 1)
        layout.addWidget(self.register_label, 3, 1, alignment=Qt.AlignRight)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(2, 1)
        layout.setRowStretch(4, 1)
        self.update_theme(theme_manager.current_theme)

    def on_login(self) -> None:
        username, password = self.username_input.text().strip(), self.password_input.text().strip()
        if not username or not password:
            success_label = FloatingLabel("账号或密码不能为空", self, x_offset_ratio=0.5, y_offset_ratio=1 / 6)
            success_label.show()
            success_label.raise_()
        elif not self.chat_client or not self.chat_client.client_socket:
            success_label = FloatingLabel("未连接到服务器，请检查网络或重试", self, x_offset_ratio=0.5, y_offset_ratio=1 / 6)
            success_label.show()
            success_label.raise_()
        else:
            run_async(self.async_login(username, password))

    def on_register(self, event) -> None:
        # 隐藏登录窗口
        self.hide()
        # 创建独立的 RegisterWindow
        if not self.main_app.register_window or sip.isdeleted(self.main_app.register_window):
            self.main_app.register_window = RegisterWindow(self.chat_client, parent=None)
            self.main_app.register_window.setWindowFlags(
                self.main_app.register_window.windowFlags() | Qt.Window
            )
            self.main_app.register_window.show()
            # 连接 finished 信号到 reopen_login
            self.main_app.register_window.finished.connect(self.reopen_login)
        else:
            self.main_app.register_window.show()
            self.main_app.register_window.activateWindow()

    async def async_login(self, username: str, password: str) -> None:
        if not self.chat_client.is_authenticated:
            self.chat_client._init_connection()
        res = await self.chat_client.authenticate(username, password)
        if res == "认证成功":
            self.accept()
            await self.chat_client.start()
            if not self.main_app.chat_window:
                self.main_app.chat_window = ChatWindow(self.chat_client, self.main_app)
            self.chat_client.chat_window = self.main_app.chat_window
            self.main_app.chat_window.show()
        else:
            error_label = FloatingLabel(f"登录失败: {res}", self, x_offset_ratio=0.5, y_offset_ratio=1 / 6)
            error_label.show()
            error_label.raise_()

    def reopen_login(self):
        # 注册窗口关闭时重新显示登录窗口
        if self.main_app.register_window and not sip.isdeleted(self.main_app.register_window):
            self.main_app.register_window.deleteLater()
            self.main_app.register_window = None
        if not self.isVisible():
            self.show()
        self.activateWindow()

    def closeEvent(self, event):
        # 仅在登录窗口可见时关闭整个程序
        if self.isVisible():
            event.accept()
            self.main_app.quit_app()
        else:
            event.ignore()

    def update_theme(self, theme: dict) -> None:
        self.setStyleSheet(f"background-color: {theme['MAIN_INTERFACE']};")
        StyleGenerator.apply_style(self.username_input, "line_edit")
        StyleGenerator.apply_style(self.password_input, "line_edit")
        StyleGenerator.apply_style(self.login_button, "button", extra="border-radius: 4px;")
        self.register_label.setStyleSheet(f"color: {theme.get('adjuntar_text', '#666666')};")

class ChatWindow(QWidget):
    def __init__(self, client: ChatClient, main_app: "ChatApp") -> None:
        super().__init__()
        self.update_lock = asyncio.Lock()
        self.send_lock = asyncio.Lock()
        self.client = client
        self.main_app = main_app
        self.auto_scrolling = False
        self.last_message_times: Dict[str, str] = {}
        self.current_page = 1
        self.page_size = 20
        self.loading_history = False
        self.has_more_history = True
        self.chat_components: Dict[str, Optional[QWidget]] = {k: None for k in ['area_widget', 'input', 'send_button', 'online', 'chat', 'right_panel']}
        self.scroll_to_bottom_btn: Optional[QPushButton] = None
        self.add_friend_dialog: Optional[AddFriendDialog] = None
        self.user_details_right = None
        self.is_selection_mode = False
        self.selection_buttons_widget = None
        self._setup_window()
        self._setup_ui()
        theme_manager.register(self)
        self.active_bubbles = {}
        self.image_viewer = None
        self.image_list = []
        self.user_details_widget = None

        # 连接信号
        self.client.friend_list_updated.connect(lambda friends: asyncio.create_task(self.update_friend_list(friends=friends)))
        self.client.conversations_updated.connect(lambda friends, affected_users, deleted_rowids, show_floating_label: asyncio.create_task(self.update_conversations(friends, affected_users, deleted_rowids, show_floating_label)))
        self.client.new_message_received.connect(lambda res: asyncio.create_task(self.handle_new_message(res)))
        self.client.new_media_received.connect(lambda res: asyncio.create_task(self.handle_new_message(res)))

    def _setup_window(self) -> None:
        self.setWindowTitle(f"ChatINL 用户: {self.client.username}")
        self.setWindowIcon(QIcon(resource_path("icon/icon.ico")))
        self.setMinimumSize(500, 550)
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
        self.update_theme(theme_manager.current_theme)

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
        # 定义模式列表和图标映射
        self.modes = ["light", "dark"]
        self.mode_icons = {
            "light": "icon/Day_Icon.ico",
            "dark": "icon/Night_Icon.ico"
        }
        self.current_mode_index = self.modes.index(theme_manager.current_mode)  # 初始化当前模式索引

        # 创建单个切换按钮
        self.theme_toggle_button = QPushButton(self)
        self.theme_toggle_button.setFixedHeight(30)
        StyleGenerator.apply_style(self.theme_toggle_button, "button", extra="border-radius: 4px;")
        self.theme_toggle_button.setIcon(QIcon(resource_path(self.mode_icons[theme_manager.current_mode])))
        self.theme_toggle_button.setIconSize(QSize(15, 15))
        self.theme_toggle_button.clicked.connect(self.toggle_theme_mode)
        layout.addWidget(self.theme_toggle_button)

        # 添加“信息”按钮（保持不变）
        info_btn = QPushButton(self)
        info_btn.setFixedHeight(30)
        StyleGenerator.apply_style(info_btn, "button", extra="border-radius: 4px;")
        info_btn.setIcon(QIcon(resource_path("icon/information_icon.ico")))
        info_btn.setIconSize(QSize(15, 15))
        info_btn.clicked.connect(lambda: run_async(self.show_user_info()))
        layout.addWidget(info_btn)

        # 添加退出按钮
        self.logout_button = QPushButton(self)
        self.logout_button.setFixedHeight(30)
        StyleGenerator.apply_style(self.logout_button, "button", extra="border-radius: 4px;")
        self.logout_button.setIcon(QIcon(resource_path("icon/quit_icon.ico")))
        self.logout_button.setIconSize(QSize(15, 15))
        self.logout_button.clicked.connect(self.on_logout)
        layout.addWidget(self.logout_button)

    def on_logout(self):
        # 创建确认对话框
        msg_box = create_themed_message_box(self, "退出登录", "您确定要退出当前登录吗？", True)
        # 执行对话框并获取用户选择
        if msg_box.exec_() == QMessageBox.RejectRole:
            return  # 如果用户选择取消，则直接返回
        async def async_logout():
            # 发送退出请求
            if self.client:
                await self.client.logout()
            # 关闭当前窗口
            self.close()
            # 清理客户端状态
            self.client.is_authenticated = False
            self.client.username = None
            self.client.current_friend = None
            # 重新创建登录窗口
            self.main_app.login_window = LoginWindow(self.main_app)
            self.main_app.login_window.show()
            # 清理聊天窗口
            if self.main_app.chat_window:
                self.main_app.chat_window.deleteLater()
                self.main_app.chat_window = None
        run_async(async_logout())

    def toggle_theme_mode(self) -> None:
        # 切换到下一个模式
        self.current_mode_index = (self.current_mode_index + 1) % len(self.modes)
        new_mode = self.modes[self.current_mode_index]
        # 更新主题
        theme_manager.set_mode(new_mode)
        self.update_theme(theme_manager.current_theme)
        # 更新按钮图标
        self.theme_toggle_button.setIcon(QIcon(resource_path(self.mode_icons[new_mode])))
        mode_name = "浅色模式" if new_mode == "light" else "深色模式"
        floating_label = FloatingLabel(f"已切换到{mode_name}", self)
        floating_label.show()
        floating_label.raise_()

    async def show_user_info(self) -> None:
        if not self.client.is_authenticated:
            QMessageBox.critical(self, "错误", "未登录，无法查看用户信息")
            return
        self.friend_list.clearSelection()
        self.client.current_friend = None
        # 检查并清理现有的 self.user_details_right
        if self.user_details_right and not sip.isdeleted(self.user_details_right):
            theme_manager.unregister(self.user_details_right)
            self.user_details_right.hide()
            self.right_layout.removeWidget(self.user_details_right)
            self.user_details_right.deleteLater()
            self.user_details_right = None
            self.chat_components['right_panel'].setFixedWidth(0)
            if not self.isMaximized():
                self.resize(self.width() - 330, self.height())
        self.clear_chat_area()  # 清理其他组件
        resp = await self.client.get_user_info()
        if resp.get("status") != "success":
            QMessageBox.critical(self, "错误", f"获取用户信息失败: {resp.get('message', '未知错误')}")
            self.default_label.show()
            return
        # 创建新的 UserDetails
        avatar_id = resp.get("avatar_id")
        avatar = None
        cache_dir = os.path.join(os.path.dirname(__file__), "Chat_DATA", "avatars")
        os.makedirs(cache_dir, exist_ok=True)
        save_path = os.path.join(cache_dir, avatar_id) if avatar_id else None

        if avatar_id and os.path.exists(save_path):
            avatar = QPixmap(save_path)
            if avatar.isNull():
                os.remove(save_path)
                avatar = None

        if not avatar and avatar_id:
            resp_download = await self.client.download_media(avatar_id, save_path, "avatar")
            if resp_download.get("status") == "success":
                avatar = QPixmap(save_path)
                if avatar.isNull():
                    os.remove(save_path)
                    avatar = None

        self.user_details_widget = UserDetails(
            client=self.client,
            parent=self.content_widget,
            avatar=avatar,
            name=resp.get("name"),
            sign=resp.get("sign"),
            username=resp.get("username"),
            online=True,
            from_info_button=True
        )
        self.default_label.hide()
        self.content_layout.addWidget(self.user_details_widget, 0, 0, 1, 1)
        self.content_layout.setRowStretch(0, 1)
        self.content_layout.setColumnStretch(0, 1)
        theme_manager.register(self.user_details_widget)

    def enter_selection_mode(self) -> None:
        """进入多选模式"""
        if self.is_selection_mode or not self.chat_components.get('chat'):
            return
        self.is_selection_mode = True
        # 通知 OnLine 控件显示选择模式按钮
        if online := self.chat_components.get('online'):
            online.show_selection_buttons(self)

    def exit_selection_mode(self) -> None:
        """退出多选模式"""
        if not self.is_selection_mode:
            return
        self.is_selection_mode = False
        # 通知 OnLine 控件隐藏选择模式按钮
        if online := self.chat_components.get('online'):
            online.hide_selection_buttons()
        chat_area = self.chat_components.get('chat')
        if chat_area:
            chat_area.clear_selection()

    async def delete_selected_messages(self) -> None:
        chat_area = self.chat_components.get('chat')
        if not chat_area or not self.is_selection_mode:
            return
        selected_rowids = chat_area.get_selected_rowids()
        if not selected_rowids:
            QMessageBox.information(self, "提示", "请先选择要删除的消息")
            return
        reply = create_confirmation_dialog(self, "确认删除", f"您确定要删除 {len(selected_rowids)} 条选中的消息吗？此操作无法撤销。")
        if reply == QMessageBox.No:
            return
        resp = await self.client.delete_messages(selected_rowids)
        if resp.get("status") == "success":
            self.exit_selection_mode()
        else:
            QMessageBox.critical(self, "错误", f"删除失败: {resp.get('message', '未知错误')}")

    def remove_from_image_list(self, file_ids: List[str]) -> None:
        """从 image_list 中移除指定的 file_id"""
        if not file_ids or not self.image_list:
            return

        original_len = len(self.image_list)
        # 移除匹配的 file_id
        self.image_list = [(fid, fname) for fid, fname in self.image_list if fid not in file_ids]
        removed_count = original_len - len(self.image_list)

        # 同步移除 active_bubbles 中对应的条目（可选）
        for rowid, bubble in list(self.active_bubbles.items()):
            if bubble.file_id in file_ids:
                del self.active_bubbles[rowid]
        if self.image_viewer and not sip.isdeleted(self.image_viewer) and self.image_viewer.isVisible():
            if not self.image_list:
                self.image_viewer.hide_viewer()  # 如果 image_list 为空，关闭查看器
            else:
                current_file_id = self.image_viewer.image_list[self.image_viewer.current_index][
                    0] if self.image_viewer.image_list else None
                if current_file_id in file_ids:
                    # 当前查看的图片被删除，尝试移动到下一张或关闭
                    new_index = min(self.image_viewer.current_index, len(self.image_list) - 1)
                    if new_index < 0:
                        self.image_viewer.hide_viewer()
                    else:
                        self.image_viewer.set_image_list(self.image_list, new_index)
                else:
                    # 更新列表并保持当前图片位置
                    new_index = next((i for i, (fid, _) in enumerate(self.image_list) if fid == current_file_id), 0)
                    self.image_viewer.set_image_list(self.image_list, new_index)

    def _on_friend_clicked(self, username: str):
        """处理 OnLine 点击信号"""
        asyncio.create_task(self.show_friend_details_from_online(username))

    async def show_friend_details_from_online(self, username: str):
        """从 OnLine 控件显示好友详情"""
        if not self.client.is_authenticated:
            QMessageBox.critical(self, "错误", "未登录，无法查看用户信息")
            return

        # 如果 UserDetails 已经存在，直接返回，不做任何操作
        if self.user_details_right and not sip.isdeleted(self.user_details_right):
            return

        friend_info = next((f for f in self.client.friends if f.get("username") == username), None)
        if not friend_info:
            QMessageBox.critical(self, "错误", "未找到该好友信息")
            return

        avatar_id = friend_info.get("avatar_id")
        avatar = None
        cache_dir = os.path.join(os.path.dirname(__file__), "Chat_DATA", "avatars")
        os.makedirs(cache_dir, exist_ok=True)
        save_path = os.path.join(cache_dir, avatar_id) if avatar_id else None

        if avatar_id and os.path.exists(save_path):
            avatar = QPixmap(save_path)
            if avatar.isNull():
                os.remove(save_path)
                avatar = None

        if not avatar and avatar_id:
            resp = await self.client.download_media(avatar_id, save_path, "avatar")
            if resp.get("status") == "success":
                avatar = QPixmap(save_path)
                if avatar.isNull():
                    os.remove(save_path)
                    avatar = None

        self.user_details_right = UserDetails(
            client=self.client,
            parent=self.chat_components['right_panel'],
            avatar=avatar,
            name=friend_info.get("name"),
            sign=friend_info.get("sign"),
            username=username,
            online=friend_info.get("online", False),
            from_online=True
        )
        self.right_layout.addWidget(self.user_details_right)

        # 设置 right_panel 宽度并调整窗口大小
        desired_width = 330
        if self.chat_components['right_panel'].width() != desired_width:
            self.chat_components['right_panel'].setFixedWidth(desired_width)
            # 如果不是最大化状态，增加窗口宽度
            if not self.isMaximized():
                self.resize(self.width() + desired_width, self.height())

        theme_manager.register(self.user_details_right)

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
        self.add_button.setFixedSize(158, 40)
        StyleGenerator.apply_style(self.add_button, "button")
        self.add_button.setIcon(QIcon(resource_path("icon/Add_Icon.ico")))
        self.add_button.setIconSize(QSize(25, 25))
        self.add_button.clicked.connect(lambda: run_async(self.async_show_add_friend()))

        top_layout.addWidget(self.mode_switch_button)
        top_layout.addWidget(self.add_button)
        top_layout.addStretch()

        self.friend_list = QListWidget(panel)
        self.friend_list.setSelectionMode(QListWidget.SingleSelection)
        self.friend_list.setFocusPolicy(Qt.StrongFocus)
        self.friend_list.setFixedWidth(180)  # 设置固定宽度为 180
        StyleGenerator.apply_style(self.friend_list, "list_widget")
        self.friend_list.verticalScrollBar().setStyleSheet(
            StyleGenerator._BASE_STYLES["scrollbar"].format(**theme_manager.current_theme))
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
        self.default_label.setPixmap(QIcon(resource_path("icon/icon.ico")).pixmap(128, 128))
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
            self.friend_list.setStyleSheet(
                f"QListWidget {{ background-color: {theme['list_background']}; color: {theme['font_color']}; border: none; outline: none; }}"
                f"QListWidget::item {{ border-bottom: 1px solid {theme['line_edit_border']}; background-color: transparent; }}"
                f"QListWidget::item:selected {{ background-color: {theme['list_item_selected']}; color: {theme['button_text_color']}; }}"
                f"QListWidget::item:hover {{ background-color: {theme['list_item_hover']}; }}"
            )
        self.friend_list.verticalScrollBar().setStyleSheet(
            StyleGenerator._BASE_STYLES["scrollbar"].format(**theme))
        if chat := self.chat_components.get('chat'):
            chat.setStyleSheet(f"background-color: {theme['chat_bg']}; border: none;")
            chat.verticalScrollBar().setStyleSheet(
                StyleGenerator._BASE_STYLES["scrollbar"].format(**theme))
        if input_widget := self.chat_components.get('input'):
            StyleGenerator.apply_style(input_widget.text_edit, "text_edit")
        if send_btn := self.chat_components.get('send_button'):
            StyleGenerator.apply_style(send_btn, "button")
        if online := self.chat_components.get('online'):
            online.update_theme(theme)
        if self.add_friend_dialog and self.add_friend_dialog.isVisible():
            self.add_friend_dialog.update_theme(theme)
        if self.scroll_to_bottom_btn:
            StyleGenerator.apply_style(self.scroll_to_bottom_btn, "button", extra="border-radius: 15px;")
        if hasattr(self, 'image_viewer') and self.image_viewer is not None and not sip.isdeleted(self.image_viewer):
            self.image_viewer.setStyleSheet(f"background-color: rgba(0, 0, 0, 220);")
            StyleGenerator.apply_style(self.image_viewer.prev_button, "button", extra="border-radius: 25px;")
            StyleGenerator.apply_style(self.image_viewer.next_button, "button", extra="border-radius: 25px;")
            StyleGenerator.apply_style(self.image_viewer.close_button, "button", extra="border-radius: 15px;")
        # 修改此处：确保 user_details_widget 已实例化
        if hasattr(self, 'user_details_widget') and self.user_details_widget is not None and not sip.isdeleted(
                self.user_details_widget):
            self.user_details_widget.update_theme(theme)
        if self.selection_buttons_widget and not sip.isdeleted(self.selection_buttons_widget):
            for btn in self.selection_buttons_widget.findChildren(QPushButton):
                StyleGenerator.apply_style(btn, "button", extra="border-radius: 4px;")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)

        chat_area = self.chat_components.get('chat')
        if not chat_area:
            return

        sb = chat_area.verticalScrollBar()
        old_value = sb.value()
        anchor_bubble = None
        anchor_offset = None
        viewport_top = old_value
        for item in chat_area.bubble_items:  # 使用 bubble_items 而非 bubble_containers
            container = chat_area.itemWidget(item)
            for widget in container.children():
                if isinstance(widget, ChatBubbleWidget):
                    bubble_top = widget.mapTo(chat_area, QPoint(0, 0)).y()
                    if bubble_top >= viewport_top:
                        anchor_bubble = widget
                        anchor_offset = bubble_top - viewport_top
                        break
            if anchor_bubble:
                break
        if not anchor_bubble:
            anchor_offset = 0

        if self.scroll_to_bottom_btn:
            self._position_scroll_button()

        if (self.image_viewer and not sip.isdeleted(self.image_viewer) and
                self.image_viewer.isVisible() and self.chat_components.get('area_widget')):
            area_widget = self.chat_components['area_widget']
            self.image_viewer.setGeometry(area_widget.geometry())

        for child in self.findChildren(FileConfirmDialog):
            if child.isVisible():
                child._update_content_width()
                child._adjust_size_and_position()
                child.update()

        if (self.chat_components.get('right_panel') and
                self.user_details_right and not sip.isdeleted(self.user_details_right)):
            self.chat_components['right_panel'].setFixedWidth(330)

        def restore_scroll_position():
            if not chat_area or sip.isdeleted(chat_area):
                return
            sb = chat_area.verticalScrollBar()
            new_max = sb.maximum()
            if anchor_bubble and not sip.isdeleted(anchor_bubble):
                new_bubble_top = anchor_bubble.mapTo(chat_area, QPoint(0, 0)).y()
                new_value = max(0, new_bubble_top - anchor_offset)
            else:
                new_value = 0 if old_value == 0 else min(old_value, new_max)
            new_value = min(new_value, new_max)
            sb.setValue(new_value)
            chat_area.viewport().update()

        QTimer.singleShot(0, restore_scroll_position)

    def clear_chat_area(self) -> None:
        # 清理 self.user_details_right
        if self.user_details_right and not sip.isdeleted(self.user_details_right):
            theme_manager.unregister(self.user_details_right)
            self.user_details_right.hide()
            self.right_layout.removeWidget(self.user_details_right)
            self.user_details_right.deleteLater()
            self.user_details_right = None
            if not self.isMaximized() and self.chat_components['right_panel'].width() > 0:
                self.resize(self.width() - 330, self.height())
            self.chat_components['right_panel'].setFixedWidth(0)

        if self.image_viewer and not sip.isdeleted(self.image_viewer):
            theme_manager.unregister(self.image_viewer)
            self.image_viewer.hide_viewer()

        # 清理聊天组件
        for comp in self.chat_components.values():
            if comp and not sip.isdeleted(comp):
                comp.deleteLater()
        self.chat_components = {k: None for k in ['area_widget', 'input', 'send_button', 'online', 'chat', 'right_panel']}

        # 清理滚动按钮
        if self.scroll_to_bottom_btn and not sip.isdeleted(self.scroll_to_bottom_btn):
            self.scroll_to_bottom_btn.deleteLater()
            self.scroll_to_bottom_btn = None

        # 清理 self.user_details_widget
        if self.user_details_widget and not sip.isdeleted(self.user_details_widget):
            theme_manager.unregister(self.user_details_widget)
            self.user_details_widget.hide()
            self.content_layout.removeWidget(self.user_details_widget)
            self.user_details_widget.deleteLater()
            self.user_details_widget = None

        self.default_label.show()

    def setup_chat_area(self) -> None:
        self.default_label.hide()
        if self.chat_components.get('chat'):
            self.clear_chat_area()

        self.chat_components['right_panel'] = QWidget(self)
        self.chat_components['right_panel'].setFixedWidth(0)
        self.right_layout = QVBoxLayout(self.chat_components['right_panel'])
        self.right_layout.setContentsMargins(0, 0, 0, 0)

        self.chat_components['area_widget'] = QWidget(self)
        area_layout = QGridLayout(self.chat_components['area_widget'])
        area_layout.setContentsMargins(0, 0, 0, 0)
        area_layout.setSpacing(0)

        self.chat_components['online'] = OnLine(self.client, self)
        self.chat_components['online'].setStyleSheet("border: none; background-color: #ffffff;")
        self.chat_components['online'].setFixedHeight(50)
        self.chat_components['online'].friend_clicked.connect(self._on_friend_clicked)

        self.chat_components['chat'] = ChatAreaWidget(self)
        self.chat_components['chat'].setStyleSheet(f"background-color: {theme_manager.current_theme['chat_bg']}; border: none;")
        self.chat_components['chat'].verticalScrollBar().setStyleSheet(StyleGenerator._BASE_STYLES["scrollbar"].format(**theme_manager.current_theme))
        sb = self.chat_components['chat'].verticalScrollBar()
        sb.valueChanged.connect(self.on_scroll_changed)
        self._create_scroll_button(theme_manager.current_theme)

        self.chat_components['input'] = MessageInput(self)
        self.chat_components['input'].setFixedHeight(70)

        area_layout.addWidget(self.chat_components['online'], 0, 0, 1, 2)
        area_layout.addWidget(self.chat_components['chat'], 1, 0, 1, 1)
        area_layout.addWidget(self.chat_components['input'], 2, 0, 1, 1)
        area_layout.addWidget(self.chat_components['right_panel'], 1, 1, 2, 1)

        area_layout.setColumnStretch(0, 1)
        area_layout.setColumnStretch(1, 0)
        area_layout.setRowStretch(1, 1)
        area_layout.setRowStretch(2, 0)

        self.content_layout.addWidget(self.chat_components['area_widget'], 0, 0, 1, 2)
        self.update_theme(theme_manager.current_theme)

    def _create_scroll_button(self, theme: dict) -> None:
        if not self.scroll_to_bottom_btn and self.chat_components.get('chat'):
            self.scroll_to_bottom_btn = QPushButton(self.chat_components['chat'].viewport())
            self.scroll_to_bottom_btn.setFixedSize(30, 30)
            self.scroll_to_bottom_btn.clicked.connect(lambda: [self.adjust_scroll(), self.scroll_to_bottom_btn.hide()])
            StyleGenerator.apply_style(self.scroll_to_bottom_btn, "button", extra="border-radius: 15px;")
            self.scroll_to_bottom_btn.setIcon(QIcon(resource_path("icon/arrow_down.ico")))
            self.scroll_to_bottom_btn.setIconSize(QSize(15, 15))
            self.scroll_to_bottom_btn.hide()
            self.scroll_to_bottom_btn.raise_()  # 提升到顶层

    def show_image_viewer(self, file_id: str, original_file_name: str) -> None:
        if not self.image_viewer or not self.chat_components.get('area_widget'):
            return
        current_index = next((i for i, (fid, _) in enumerate(self.image_list) if fid == file_id), 0)
        self.image_viewer.set_image_list(image_list=self.image_list, start_index=current_index, parent=self.chat_components.get('area_widget'))
        self.image_viewer.show()
        self.image_viewer.raise_()

    def _reset_chat_area(self) -> None:
        self.clear_chat_area()
        self.setup_chat_area()
        self.current_page = 1
        self.has_more_history = True
        if self.image_viewer and not sip.isdeleted(self.image_viewer):
            theme_manager.unregister(self.image_viewer)
            self.image_viewer.deleteLater()
        self.image_viewer = ImageViewer(parent=self.chat_components['area_widget'])  # 传入父级窗口
        self.image_viewer.hide()
        theme_manager.register(self.image_viewer)
        self.image_list.clear()

    def on_scroll_button_clicked(self) -> None:
        self.adjust_scroll()
        if self.client.current_friend:
            self.client.clear_unread_messages(self.client.current_friend)
            run_async(self.update_friend_list(affected_users=[self.client.current_friend]))  # 精准更新当前好友
        self.scroll_to_bottom_btn.hide()

    def on_scroll_changed(self, value: int) -> None:
        chat = self.chat_components.get('chat')
        if not chat or self.loading_history or self.auto_scrolling:
            return

        sb = chat.verticalScrollBar()
        if value == 0 and self.has_more_history:
            run_async(self.load_chat_history(reset=False))
        self._check_scroll_position()
        if self.scroll_to_bottom_btn and self.scroll_to_bottom_btn.isVisible():
            self.scroll_to_bottom_btn.raise_()
        if self.client.current_friend and self.client.unread_messages.get(self.client.current_friend, 0) > 0 and not self.auto_scrolling and sb.maximum() - sb.value() <= 5:
            old_unread = self.client.unread_messages.get(self.client.current_friend, 0)
            self.client.clear_unread_messages(self.client.current_friend)
            if old_unread > 0:  # 仅当未读消息数变化时更新
                run_async(self.update_friend_list(affected_users=[self.client.current_friend]))  # 精准更新

    def _scroll_to_bottom(self) -> None:
        QApplication.processEvents()
        chat = self.chat_components.get('chat')
        if chat:
            sb = chat.verticalScrollBar()
            sb.setValue(sb.maximum())
            self._check_scroll_position()
        self.auto_scrolling = False

    def adjust_scroll(self) -> None:
        self.auto_scrolling = True
        if self.chat_components.get('chat'):
            self.chat_components['chat'].update()
        QApplication.processEvents()
        QTimer.singleShot(0, self._scroll_to_bottom)
        # 直接清零未读计数
        if self.client.current_friend:
            old_unread = self.client.unread_messages.get(self.client.current_friend, 0)
            self.client.clear_unread_messages(self.client.current_friend)
            if old_unread > 0:
                asyncio.create_task(self.update_friend_list(affected_users=[self.client.current_friend]))

    def _check_scroll_position(self) -> None:
        sb = self.chat_components['chat'].verticalScrollBar()
        should_show = (self.client.current_friend and self.client.unread_messages.get(self.client.current_friend, 0) > 0 and sb.maximum() - sb.value() > 50)
        self._create_scroll_button(theme_manager.current_theme)
        if should_show:
            self._position_scroll_button()
            self.scroll_to_bottom_btn.show()
        else:
            self.scroll_to_bottom_btn.hide()

    def _position_scroll_button(self) -> None:
        if self.scroll_to_bottom_btn and (chat := self.chat_components.get('chat')):
            viewport = chat.viewport()
            x = max(10, viewport.width() - self.scroll_to_bottom_btn.width() - 10)
            y = max(10, viewport.height() - self.scroll_to_bottom_btn.height() - 10)
            self.scroll_to_bottom_btn.move(x, y)
            self.scroll_to_bottom_btn.raise_()  # 确保每次移动后仍在顶层

    def should_scroll_to_bottom(self) -> bool:
        sb = self.chat_components['chat'].verticalScrollBar()
        return sb.value() > sb.maximum() - self.chat_components['chat'].viewport().height()  # 靠近底部

    def _scroll_to_bubble(self, bubble: ChatBubbleWidget, item: QListWidgetItem) -> None:
        chat_area = self.chat_components['chat']
        self.auto_scrolling = True
        chat_area.scrollToItem(item, QAbstractItemView.PositionAtCenter)  # 滚动到目标项，居中显示
        QApplication.processEvents()
        self.auto_scrolling = False
        self._check_scroll_position()
        bubble.highlight_container_with_animation()

    async def scroll_to_message(self, target_rowid: int) -> None:
        if not self.chat_components.get('chat') or not self.client.current_friend:
            return

        chat_area = self.chat_components['chat']
        sb = chat_area.verticalScrollBar()

        # 查找目标气泡和对应的 item
        target_bubble = None
        target_item = None
        for item in chat_area.bubble_items:
            container = chat_area.itemWidget(item)
            if container and not sip.isdeleted(container):
                for widget in container.children():
                    if isinstance(widget, ChatBubbleWidget) and widget.rowid == target_rowid:
                        target_bubble = widget
                        target_item = item
                        break
                if target_bubble:
                    break

        if target_bubble and target_item:
            self._scroll_to_bubble(target_bubble, target_item)
            return

        # 如果未找到，加载更多历史记录
        while self.has_more_history:
            old_max = sb.maximum()
            await self.load_chat_history(reset=False)
            QApplication.processEvents()
            # sb.setValue(0)

            for item in chat_area.bubble_items:
                container = chat_area.itemWidget(item)
                if container and not sip.isdeleted(container):
                    for widget in container.children():
                        if isinstance(widget, ChatBubbleWidget) and widget.rowid == target_rowid:
                            target_bubble = widget
                            target_item = item
                            break
                    if target_bubble:
                        break

            if target_bubble and target_item:
                self._scroll_to_bubble(target_bubble, target_item)
                break
            elif sb.maximum() == old_max:
                QMessageBox.information(self, "提示", f"未找到消息 #{target_rowid}，可能是太早的消息或已被删除")
                break

    async def add_message(self, message: str, is_current: bool, tstr: str, message_type: str = 'text',
                          file_id: str = None, original_file_name: str = None, thumbnail_path: str = None,
                          file_size: str = None, duration: str = None) -> None:
        bubble = ChatBubbleWidget(
            message, tstr, "right" if is_current else "left", is_current,
            message_type, file_id, original_file_name, thumbnail_path, file_size, duration
        )
        self.chat_components['chat'].addBubble(bubble)  # 追加到末尾
        if bubble.rowid:
            self.active_bubbles[bubble.rowid] = bubble
        if message_type == 'image' and file_id:
            self.image_list.append((file_id, original_file_name or f"image_{file_id}"))
        if is_current or self.should_scroll_to_bottom():
            self.adjust_scroll()

    def generate_reply_preview(self, reply_to: Optional[int]) -> Optional[str]:
        """根据 reply_to_id 从 active_bubbles 生成 reply_preview"""
        if reply_to and reply_to in self.active_bubbles:
            replied_bubble = self.active_bubbles[reply_to]
            sender = self.client.username if replied_bubble.is_current_user else self.client.current_friend
            if replied_bubble.message_type == 'text':
                content = replied_bubble.message
            elif replied_bubble.message_type in ('image', 'video', 'file'):
                content = f"[{replied_bubble.message_type}]: {replied_bubble.original_file_name or '未知文件'}"
            else:
                content = "消息内容不可用"
            reply_preview = json.dumps({"sender": sender, "content": content})
            return reply_preview
        return None

    async def send_message(self) -> None:
        text = self.chat_components['input'].text_edit.toPlainText().strip()
        if not text or not self.client.current_friend:
            return
        reply_to = getattr(self.client, 'reply_to_id', None)
        reply_preview = self.generate_reply_preview(reply_to)

        wt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bubble = ChatBubbleWidget(text, format_time(wt), "right", True, "text", reply_to=reply_to, reply_preview=reply_preview)
        self.chat_components['chat'].addBubble(bubble)
        self.chat_components['input'].remove_reply_preview()
        self.adjust_scroll()

        resp = await self.client.send_message(self.client.current_friend, text, reply_to)
        # 信号已处理后续逻辑，这里只更新 UI
        if resp.get("status") == "success":
            bubble.rowid = resp.get("rowid")
            bubble.reply_to = resp.get("reply_to")
            bubble.reply_preview = reply_preview or resp.get("reply_preview")
            self.chat_components['input'].text_edit.clear()
            if reply_to:
                self.client.reply_to_id = None
            if bubble.rowid:
                self.active_bubbles[bubble.rowid] = bubble
        else:
            if bubble.parent():
                self.chat_components['chat'].layout().removeWidget(bubble.parent())
                bubble.parent().deleteLater()
            self.adjust_scroll()

    async def send_multiple_media(self, file_paths: List[str], message: str = "") -> None:
        async with self.send_lock:
            if not self.client.current_friend:
                msg_box = create_themed_message_box(self, "错误", "未选择好友，无法发送文件", False)
                msg_box.exec_()
                return
            if not self.chat_components.get('chat'):
                self.setup_chat_area()

            dialog = FileConfirmDialog(file_paths, self)
            theme_manager.register(dialog)
            fut = asyncio.get_running_loop().create_future()

            def on_dialog_finished(result):
                if not fut.done():
                    fut.set_result(result)
                dialog.deleteLater()

            dialog.finished.connect(on_dialog_finished)
            dialog.show()
            result = await fut

            if result != QDialog.Accepted:
                return

            message = dialog.text_edit.toPlainText().strip()
            reply_to = getattr(self.client, 'reply_to_id', None)
            reply_preview = self.generate_reply_preview(reply_to)

            bubbles = {}
            for file_path in file_paths:
                file_type = self.client._detect_file_type(file_path)
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                file_size_str = f"{file_size_mb:.2f} MB"
                thumbnail_path = generate_thumbnail(file_path, file_type, output_dir=os.path.join(os.path.dirname(__file__), "Chat_DATA", "thumbnails")) if file_type in ('image', 'video') else None
                wt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                bubble = ChatBubbleWidget(
                    message, format_time(wt), "right", True, file_type, None,
                    os.path.basename(file_path), thumbnail_path, file_size_str, None,
                    reply_to=reply_to,
                    reply_preview=reply_preview,
                    thumbnail_local_path=thumbnail_path
                )
                self.chat_components['chat'].addBubble(bubble)
                bubbles[file_path] = bubble
            self.chat_components['input'].remove_reply_preview()
            self.adjust_scroll()

            async def progress_callback(type_, progress, filename):
                file_path = next((fp for fp in bubbles if os.path.basename(fp) == filename), None)
                if file_path and type_ == "upload":
                    bubbles[file_path].update_progress(progress)
                    QApplication.processEvents()

            results = await self.client.send_multiple_media(self.client.current_friend, file_paths, progress_callback, message=message, reply_to=reply_to)
            for file_path, res in zip(file_paths, results):
                bubble = bubbles[file_path]
                if res.get("status") == "success":
                    bubble.file_id = res.get("file_id")
                    bubble.duration = res.get("duration")
                    bubble.complete_progress()
                    bubble.rowid = res.get("rowid")
                    bubble.reply_to = res.get("reply_to")
                    bubble.reply_preview = res.get("reply_preview") or reply_preview
                    if self.client._detect_file_type(file_path) == "image" and bubble.file_id:
                        self.image_list.append((bubble.file_id, bubble.original_file_name))
                    if reply_to:
                        self.client.reply_to_id = None
                    if bubble.rowid:
                        self.active_bubbles[bubble.rowid] = bubble
                else:
                    bubble_container = bubble.parent()
                    if bubble_container:
                        self.chat_components['chat'].layout().removeWidget(bubble_container)
                        bubble_container.deleteLater()
                    bubble.complete_progress()
            self.adjust_scroll()

    async def handle_new_message(self, res: dict) -> None:
        sender = res["from"]
        wt = res["write_time"]
        msg_type = res.get("type", "new_message")
        rowid = res.get("rowid")
        reply_to = res.get("reply_to")
        reply_preview = res.get("reply_preview")
        msg = res.get("message", "")

        file_id = res.get("file_id")
        file_type = res.get("file_type")
        original_file_name = res.get("original_file_name")
        thumbnail_path = res.get("thumbnail_local_path")
        file_size = res.get("file_size")
        duration = res.get("duration")
        file_size_str = None
        if file_size and isinstance(file_size, (int, float)):
            file_size_mb = file_size / (1024 * 1024)
            file_size_str = f"{file_size_mb:.2f} MB"
        elif file_size:
            file_size_str = file_size
        self.last_message_times[sender] = wt
        if sender == self.client.current_friend:
            if not self.chat_components.get('chat'):
                self.setup_chat_area()
            bubble_type = file_type if msg_type == "new_media" else "text"
            bubble = ChatBubbleWidget(msg, format_time(wt), "left", False, bubble_type,
                                      file_id, original_file_name, thumbnail_path, file_size_str, duration,
                                      rowid=rowid, reply_to=reply_to, reply_preview=reply_preview)
            self.chat_components['chat'].addBubble(bubble)  # 追加到末尾
            if bubble.rowid:
                self.active_bubbles[bubble.rowid] = bubble
            if bubble_type == "image" and file_id:
                self.image_list.append((file_id, original_file_name or f"image_{file_id}"))
            if self.should_scroll_to_bottom():
                self.adjust_scroll()
                self.client.clear_unread_messages(sender)
                await self.update_friend_list(affected_users=[sender])
            else:
                self._check_scroll_position()
        notification_msg = (
            msg if msg_type == "new_message" else f"收到新的{ {'image': '图片', 'video': '视频', 'file': '文件'}.get(file_type, '未知')}: {original_file_name or '未知文件'}")
        if msg and msg_type == "new_media":
            notification_msg += f"\n附加消息: {msg}"
        self.show_notification(f"用户 {sender}:", notification_msg)

    def _sort_friends(self, friends: List[dict]) -> List[dict]:
        """根据最后消息时间排序好友，处理 conversations 为 None 的情况"""
        online = sorted(
            [f for f in friends if f and f.get("online")],
            key=lambda x: x.get("conversations", {}).get("last_update_time", "1970-01-01 00:00:00") if x.get(
                "conversations") else "1970-01-01 00:00:00",
            reverse=True
        )
        offline = sorted(
            [f for f in friends if f and not f.get("online")],
            key=lambda x: x.get("conversations", {}).get("last_update_time", "1970-01-01 00:00:00") if x.get(
                "conversations") else "1970-01-01 00:00:00",
            reverse=True
        )
        return online + offline

    async def update_conversations(self, friends: List[dict], affected_users: Optional[List[str]] = None,
                                   deleted_rowids: List[int] = None, show_floating_label: bool = False) -> None:
        chat_area = self.chat_components.get('chat')
        if affected_users:
            await self.update_friend_list(affected_users=affected_users)
            if chat_area and deleted_rowids:
                await chat_area.remove_bubbles_by_rowids(deleted_rowids, show_floating_label=show_floating_label)
        else:
            await self.update_friend_list(friends=friends)

    async def update_friend_list(self, friends: Optional[List[dict]] = None,
                                 affected_users: Optional[List[str]] = None) -> None:
        async with self.update_lock:
            try:
                friends = friends or self.client.friends or []
                unique_friends = {f["username"]: f for f in friends if f and "username" in f}
                friends = list(unique_friends.values())
                current_friend = self.client.current_friend

                cache_dir = os.path.join(os.path.dirname(__file__), "Chat_DATA", "avatars")
                os.makedirs(cache_dir, exist_ok=True)

                sorted_friends = self._sort_friends(friends)

                if affected_users:
                    # 精准更新
                    for uname in affected_users:
                        friend = next((f for f in sorted_friends if f.get("username") == uname), None)
                        if not friend:
                            continue
                        name = friend.get("name", uname)
                        conv = friend.get("conversations")
                        last_message = conv.get("content", "") if conv else ""
                        last_message_time = conv.get("last_update_time", "") if conv else ""
                        unread_count = self.client.unread_messages.get(uname, 0)
                        online = friend.get("online", False)
                        avatar_id = friend.get("avatar_id", "")

                        # 检查现有项
                        for i in range(self.friend_list.count()):
                            item = self.friend_list.item(i)
                            widget = self.friend_list.itemWidget(item)
                            if widget and widget.username == uname and not sip.isdeleted(widget):
                                widget.name = name
                                widget.online = online
                                widget.unread = unread_count
                                widget.last_message_time = last_message_time
                                widget.last_message = last_message
                                widget.avatar_id = avatar_id
                                await self._update_widget_avatar(widget, avatar_id, cache_dir)
                                break
                        else:
                            # 新增项
                            item = QListWidgetItem(self.friend_list)
                            item.setSizeHint(QSize(self.friend_list.width(), 55))
                            widget = FriendItemWidget(uname, name, online, unread_count, None, last_message_time,
                                                      last_message)
                            widget.avatar_id = avatar_id
                            await self._update_widget_avatar(widget, avatar_id, cache_dir)
                            self.friend_list.setItemWidget(item, widget)
                            theme_manager.register(widget)

                else:
                    # 全量更新
                    self.friend_list.clear()
                    for friend in sorted_friends:
                        if not friend or "username" not in friend:
                            continue
                        uname = friend["username"]
                        name = friend.get("name", uname)
                        conv = friend.get("conversations")
                        last_message = conv.get("content", "") if conv else ""
                        last_message_time = conv.get("last_update_time", "") if conv else ""
                        unread_count = self.client.unread_messages.get(uname, 0)
                        online = friend.get("online", False)
                        avatar_id = friend.get("avatar_id", "")

                        item = QListWidgetItem(self.friend_list)
                        item.setSizeHint(QSize(self.friend_list.width(), 55))
                        widget = FriendItemWidget(uname, name, online, unread_count, None, last_message_time,
                                                  last_message)
                        widget.avatar_id = avatar_id
                        await self._update_widget_avatar(widget, avatar_id, cache_dir)
                        self.friend_list.setItemWidget(item, widget)
                        theme_manager.register(widget)

                    # 恢复当前选择
                    if current_friend:
                        for i in range(self.friend_list.count()):
                            item = self.friend_list.item(i)
                            widget = self.friend_list.itemWidget(item)
                            if widget and widget.username == current_friend and not sip.isdeleted(widget):
                                if not item.isSelected():
                                    item.setSelected(True)
                                if (online_widget := self.chat_components.get('online')):
                                    online_status = any(
                                        f["username"] == current_friend and f.get("online", False) for f in friends if
                                        f)
                                    online_widget.update_status(current_friend, online_status)
                                break

                self.friend_list.updateGeometry()
            except Exception as e:
                logging.error(f"更新好友列表时发生异常: {e}")

    def _normalize_friends(self, friends: List[dict]) -> str:
        """规范化好友数据以计算一致的哈希值，包括未读消息计数"""
        normalized = [
            {
                "username": f.get("username"),
                "name": f.get("name"),
                "online": f.get("online"),
                "avatar_id": f.get("avatar_id", ""),
                "last_message": f.get("conversations", {}).get("content", "") if f.get("conversations") else "",
                "last_message_time": f.get("conversations", {}).get("last_update_time", "") if f.get(
                    "conversations") else "",
                "unread_count": self.client.unread_messages.get(f.get("username", ""), 0)
            } for f in friends if f and "username" in f
        ]
        return json.dumps(normalized, sort_keys=True)

    async def _update_widget_avatar(self, widget: FriendItemWidget, avatar_id: Optional[str], cache_dir: str) -> None:
        try:
            if not avatar_id:
                widget.avatar_pixmap = None
                widget.update_display()  # 显式更新 UI
                return

            save_path = os.path.join(cache_dir, avatar_id)
            avatar_pixmap = None

            # 检查本地文件是否存在且有效
            if os.path.exists(save_path):
                avatar_pixmap = QPixmap(save_path)
                if avatar_pixmap.isNull():
                    os.remove(save_path)  # 删除无效文件
                    avatar_pixmap = None

            # 如果本地没有有效头像，下载并等待完成
            if not avatar_pixmap:
                resp = await self.client.download_media(avatar_id, save_path, "avatar")
                if resp.get("status") == "success":
                    avatar_pixmap = QPixmap(save_path)
                    if avatar_pixmap.isNull():
                        os.remove(save_path)  # 下载后仍无效，删除
                        avatar_pixmap = None
                else:
                    logging.error(f"头像下载失败: avatar_id={avatar_id}, error={resp.get('message')}")
                    avatar_pixmap = None

            # 设置头像并更新 UI
            widget.avatar_pixmap = avatar_pixmap
            widget.update_display()  # 显式触发 UI 更新
        except Exception as e:
            logging.error(f"更新头像时出错: avatar_id={avatar_id}, error={e}")
            widget.avatar_pixmap = None
            widget.update_display()  # 出错时也要更新 UI

    async def load_chat_history(self, reset: bool = False) -> None:
        if reset:
            self._reset_chat_area()
        if not self.client.current_friend or not self.has_more_history:
            return

        self.loading_history = True
        chat = self.chat_components.get('chat')
        sb = chat.verticalScrollBar() if chat else None
        old_val = sb.value() if sb else 0
        old_max = sb.maximum() if sb else 0

        res = await self.client.get_chat_history_paginated(self.client.current_friend, self.current_page,
                                                           self.page_size)
        if res and res.get("type") == "chat_history" and (messages := res.get("data", [])):
            new_bubbles = []
            temp_image_list = []
            # 服务端返回从新到旧，反转 messages 为从旧到新
            messages = list(reversed(messages))
            for msg in messages:
                file_size = msg.get("file_size", 0)
                if isinstance(file_size, (int, float)):
                    file_size_str = f"{file_size / (1024 * 1024):.2f} MB"
                else:
                    file_size_str = file_size

                file_id = msg.get("file_id")
                attachment_type = msg.get("attachment_type")
                if file_id and attachment_type in ["image", "video"]:
                    save_path = os.path.join(self.client.thumbnail_dir, f"{file_id}_thumbnail")
                    if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
                        result = await self.client.download_media(file_id, save_path, "thumbnail")
                        if result.get("status") != "success":
                            logging.error(f"缩略图下载失败: {result.get('message')}")
                    msg["thumbnail_local_path"] = save_path

                bubble = ChatBubbleWidget(
                    msg.get("message", ""), format_time(msg.get("write_time", "")),
                    "right" if msg.get("is_current_user") else "left", msg.get("is_current_user", False),
                    attachment_type or "text", file_id, msg.get("original_file_name"),
                    msg.get("thumbnail_path"), file_size_str, msg.get("duration"),
                    rowid=msg.get("rowid"),
                    reply_to=msg.get("reply_to"),
                    reply_preview=msg.get("reply_preview"),
                    thumbnail_local_path=msg.get("thumbnail_local_path")
                )
                new_bubbles.append(bubble)
                if bubble.rowid:
                    self.active_bubbles[bubble.rowid] = bubble
                if attachment_type == "image" and file_id:
                    temp_image_list.append((file_id, msg.get("original_file_name") or f"image_{file_id}"))

            if not reset:
                existing_bubbles = []
                for item in chat.bubble_items[:]:
                    if not sip.isdeleted(item):
                        container = chat.itemWidget(item)
                        if container and not sip.isdeleted(container):
                            bubble = next((w for w in container.children() if isinstance(w, ChatBubbleWidget)), None)
                            if bubble and not sip.isdeleted(bubble):
                                existing_bubbles.append(bubble)

                all_bubbles = new_bubbles + existing_bubbles
                chat.bubble_items.clear()
                chat.clear()
                chat.addBubbles(all_bubbles)
            else:
                chat.addBubbles(new_bubbles)

            if not reset:
                self.image_list = self.image_list + list(reversed(temp_image_list))
            else:
                self.image_list = list(reversed(temp_image_list))

            def update_and_scroll():
                for bubble in new_bubbles:
                    bubble.updateBubbleSize()
                self.friend_list.update()
                QApplication.processEvents()
                if reset and sb:
                    sb.setValue(sb.maximum())
                elif sb:
                    new_max = sb.maximum()
                    new_value = old_val + (new_max - old_max)
                    sb.setValue(max(0, min(new_value, new_max)))
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
            online_status = any(f["username"] == friend and f.get("online", False) for f in self.client.friends)
            if online_widget := self.chat_components.get('online'):
                online_widget.update_status(friend, online_status)
            return
        if self.user_details_widget and not sip.isdeleted(self.user_details_widget):
            self.clear_chat_area()
        self.client.current_friend = friend
        self._reset_chat_area()
        await self.load_chat_history(reset=True)
        online_status = any(f["username"] == friend and f.get("online", False) for f in self.client.friends)
        self.chat_components['online'].update_status(friend, online_status)
        sb = self.chat_components['chat'].verticalScrollBar()
        self.adjust_scroll()
        if sb.maximum() - sb.value() <= 5:
            old_unread = self.client.unread_messages.get(friend, 0)
            self.client.clear_unread_messages(friend)
            for i in range(self.friend_list.count()):
                item = self.friend_list.item(i)
                widget = self.friend_list.itemWidget(item)
                if widget and widget.username == friend and not sip.isdeleted(widget):
                    widget.unread = 0  # 直接更新 UI 上的未读计数
                    widget.update_display()
                    break

    def show_notification(self, sender: str, msg: str) -> None:
        self.notification_sender = sender.replace("用户 ", "").rstrip(":")
        self.main_app.tray_icon.showMessage(sender, msg, QIcon(resource_path("icon/icon.ico")), 2000)
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

    async def proc_add_friend(self, dialog: AddFriendDialog) -> None:
        if friend_name := dialog.input.text().strip():
            resp = await self.client.add_friend(friend_name)  # 获取完整响应

            # 确保窗口可见
            if not self.isVisible():
                self.show()
            if self.isMinimized():
                self.showNormal()

            # 根据 status 判断结果
            if resp.get("status") == "success":
                label = FloatingLabel(f"已成功添加 {friend_name} 为好友", self)
            else:
                label = FloatingLabel(f"添加失败: {resp.get('message', '未知错误')}", self)

            label.show()
            label.raise_()
            QApplication.processEvents()
            dialog.accept()

    async def async_show_add_friend(self) -> None:
        if self.add_friend_dialog and self.add_friend_dialog.isVisible():
            self.add_friend_dialog.raise_()
            self.add_friend_dialog.activateWindow()
            return

        dialog = AddFriendDialog(self)
        self.add_friend_dialog = dialog
        fut = asyncio.get_running_loop().create_future()

        def set_future_result(_):
            if not fut.done():
                fut.set_result(None)

        dialog.finished.connect(set_future_result)
        dialog.confirm_btn.clicked.connect(lambda: run_async(self.proc_add_friend(dialog)))
        dialog.show()
        await fut
        self.add_friend_dialog = None

    def closeEvent(self, event):
        # 关闭所有打开的 FileConfirmDialog
        for dialog in self.findChildren(FileConfirmDialog):
            if not sip.isdeleted(dialog):
                dialog.close()
        # 清理聊天区域
        self.clear_chat_area()
        theme_manager.clear_observers()
        # 重置客户端状态
        self.client.current_friend = None
        self.friend_list.clearSelection()
        # 隐藏窗口，不退出程序
        event.ignore()
        self.hide()

    def keyPressEvent(self, event) -> None:
        # 在多选模式下按 Esc 退出
        if self.is_selection_mode and event.key() == Qt.Key_Escape:
            self.exit_selection_mode()
            event.accept()
            return
        # 其他按键事件处理保持不变
        input_widget = self.chat_components.get('input')
        if input_widget and input_widget.reply_widget and event.key() == Qt.Key_Escape:
            input_widget.remove_reply_preview()
            self.client.reply_to_id = None
            event.accept()
            return

        # 检查 right_panel 是否存在且已展开
        right_panel = self.chat_components.get('right_panel')
        if event.key() == Qt.Key_Escape:
            if right_panel and right_panel.isVisible() and right_panel.width() > 0:
                if self.user_details_right and not sip.isdeleted(self.user_details_right):
                    theme_manager.unregister(self.user_details_right)
                    self.user_details_right.deleteLater()
                    self.user_details_right = None
                right_panel.setFixedWidth(0)
                # 如果是非最大化状态，减少窗口宽度
                if not self.isMaximized():
                    self.resize(self.width() - 330, self.height())
                event.accept()
                return

        # 默认行为：清空选择并关闭聊天区域
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
        self.register_window: Optional[RegisterWindow] = None  # 已存在，确保正确初始化
        theme_manager.set_mode(load_theme_mode())
        self.login_window.update_theme(theme_manager.current_theme)

    def _setup_tray(self) -> None:
        self.tray_icon.setIcon(QIcon(resource_path("icon/icon.ico")))
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
            # 优先显示活动窗口：ChatWindow > RegisterWindow > LoginWindow
            window = self.chat_window or self.register_window or self.login_window
            if window and not window.isVisible():
                window.show()
            if window:
                window.activateWindow()

    def on_notification_clicked(self) -> None:
        if self.chat_window:
            self.chat_window.on_notification_clicked()

    def quit_app(self) -> None:
        async def shutdown():
            try:
                if self.login_window.chat_client:
                    await self.login_window.chat_client.close_connection()

                tasks = [t for t in asyncio.all_tasks(self.loop) if not t.done()]
                for task in tasks:
                    task.cancel()
                if tasks:
                    try:
                        await asyncio.wait(tasks, timeout=2.0)
                        logging.info(f"已取消 {len(tasks)} 个异步任务")
                    except Exception as e:
                        logging.error(f"等待任务取消失败: {e}")

                # 确保所有窗口关闭
                if self.chat_window and not sip.isdeleted(self.chat_window):
                    self.chat_window.close()
                if self.register_window and not sip.isdeleted(self.register_window):
                    self.register_window.close()
                if self.login_window and not sip.isdeleted(self.login_window):
                    self.login_window.close()

                self.tray_icon.hide()
            except Exception as e:
                logging.error(f"退出时发生错误: {e}")
            finally:
                self.loop.stop()
                QApplication.quit()

        asyncio.ensure_future(shutdown())

    def run(self) -> None:
        self.login_window.show()
        with self.loop:
            self.loop.run_forever()
        QApplication.quit()

def main() -> None:
    ChatApp().run()

if __name__ == '__main__':
    main()