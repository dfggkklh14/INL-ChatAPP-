import asyncio
import base64
from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPen, QBrush, QColor
from PyQt5.QtWidgets import QFileDialog, QDialog, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QGridLayout
from qasync import QtCore

from Interface_Controls import StyleGenerator, theme_manager, create_line_edit, \
    name_line_edit, FloatingLabel  # 从 Interface_Controls 导入


# 图像裁剪窗口类
class ImageCropper(QDialog):
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("裁切头像")
        self.setFixedSize(400, 400)
        self.image = QtGui.QImage(image_path)
        self.crop_size = 200
        self.crop_rect = QRect((self.width() - self.crop_size) // 2,
                               (self.height() - self.crop_size) // 2,
                               self.crop_size, self.crop_size)
        self.scale = max(self.crop_size / self.image.width(), self.crop_size / self.image.height())
        self.translation = QPoint(
            self.crop_rect.center().x() - int(self.image.width() * self.scale / 2),
            self.crop_rect.center().y() - int(self.image.height() * self.scale / 2)
        )
        self.dragging = False
        self.last_mouse_pos = QPoint()
        self.init_ui()
        self.update_theme(theme_manager.current_theme)  # 初始化时应用主题

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addStretch()
        self.confirm_btn = QPushButton("确认", self)
        self.confirm_btn.clicked.connect(self.accept)
        StyleGenerator.apply_style(self.confirm_btn, "button", extra="border-radius: 8px;")
        self.confirm_btn.setFixedSize(50, 25)
        layout.addWidget(self.confirm_btn, alignment=Qt.AlignCenter)
        theme_manager.register(self)  # 注册到主题管理器

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.translation)
        painter.scale(self.scale, self.scale)
        painter.drawImage(0, 0, self.image)
        painter.resetTransform()
        painter.setBrush(QColor(0, 0, 0, 128))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, self.width(), self.crop_rect.top())
        painter.drawRect(0, self.crop_rect.bottom(), self.width(), self.height() - self.crop_rect.bottom())
        painter.drawRect(0, self.crop_rect.top(), self.crop_rect.left(), self.crop_rect.height())
        painter.drawRect(self.crop_rect.right(), self.crop_rect.top(),
                         self.width() - self.crop_rect.right(), self.crop_rect.height())
        painter.setPen(QPen(Qt.white, 2, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.crop_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_mouse_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.pos() - self.last_mouse_pos
            self.last_mouse_pos = event.pos()
            self.translation += delta
            self.constrain_translation()
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def wheelEvent(self, event):
        delta = event.angleDelta().y() / 120
        factor = 1.1 ** delta
        new_scale = max(self.scale * factor,
                        max(self.crop_size / self.image.width(), self.crop_size / self.image.height()))
        mouse_pos = event.pos()
        image_x = (mouse_pos.x() - self.translation.x()) / self.scale
        image_y = (mouse_pos.y() - self.translation.y()) / self.scale
        self.scale = new_scale
        self.translation = QPoint(
            int(mouse_pos.x() - image_x * self.scale),
            int(mouse_pos.y() - image_y * self.scale)
        )
        self.constrain_translation()
        self.update()

    def constrain_translation(self):
        img_rect = QRect(self.translation,
                         QSize(int(self.image.width() * self.scale), int(self.image.height() * self.scale)))
        dx = dy = 0
        if img_rect.left() > self.crop_rect.left():
            dx = self.crop_rect.left() - img_rect.left()
        elif img_rect.right() < self.crop_rect.right():
            dx = self.crop_rect.right() - img_rect.right()
        if img_rect.top() > self.crop_rect.top():
            dy = self.crop_rect.top() - img_rect.top()
        elif img_rect.bottom() < self.crop_rect.bottom():
            dy = self.crop_rect.bottom() - img_rect.bottom()
        self.translation += QPoint(dx, dy)

    def get_cropped_image(self):
        x = (self.crop_rect.x() - self.translation.x()) / self.scale
        y = (self.crop_rect.y() - self.translation.y()) / self.scale
        w = self.crop_rect.width() / self.scale
        h = self.crop_rect.height() / self.scale
        return self.image.copy(QRect(int(x), int(y), int(w), int(h)))

    def update_theme(self, theme: dict):
        """更新主题，包括自身背景色"""
        self.setStyleSheet(f"background-color: {theme['widget_bg']};")
        StyleGenerator.apply_style(self.confirm_btn, "button", extra="border-radius: 8px;")


# 头像显示控件类
class AvatarWidget(QWidget):
    def __init__(self, parent=None, pixmap: QPixmap = None, upload_callback=None):
        super().__init__(parent)
        self.setFixedSize(100, 100)
        self.upload_callback = upload_callback
        self.setAttribute(Qt.WA_Hover, True)

        self.pixmap_label = QLabel(self)
        self.pixmap_label.setFixedSize(100, 100)
        self.pixmap_label.setScaledContents(True)
        if pixmap:
            self.pixmap_label.setPixmap(self.create_round_avatar(pixmap))
        else:
            default_pixmap = QPixmap("icon/default_avatar.ico")
            if not default_pixmap.isNull():
                self.pixmap_label.setPixmap(self.create_round_avatar(default_pixmap))
            else:
                temp_pixmap = QPixmap(100, 100)
                temp_pixmap.fill(QColor("#f0f0f0"))
                self.pixmap_label.setPixmap(self.create_round_avatar(temp_pixmap))

        self.upload_button = QPushButton(self)
        self.upload_button.setIcon(QIcon("icon/cma_icon_shallow.ico"))
        self.upload_button.setIconSize(QSize(20, 20))
        self.upload_button.setFixedSize(100, 50)
        self.upload_button.move(0, 50)
        self.upload_button.setStyleSheet("""
                    background-color: rgba(0, 0, 0, 100);
                    border: none;
                    border-top-left-radius: 0px;
                    border-top-right-radius: 0px;
                    border-bottom-left-radius: 50px;
                    border-bottom-right-radius: 50px;
                """)
        self.upload_button.setVisible(False)
        if upload_callback:
            self.upload_button.clicked.connect(upload_callback)
        else:
            self.upload_button.setEnabled(False)
        self.upload_button.installEventFilter(self)

        theme_manager.register(self)  # 注册到主题管理器
        self.update_theme(theme_manager.current_theme)  # 初始化时应用主题

    def setPixmap(self, pixmap: QPixmap):
        self.pixmap_label.setPixmap(self.create_round_avatar(pixmap))

    def create_round_avatar(self, pixmap, size=100):
        result = QPixmap(size, size)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.setBrush(QBrush(scaled))
        else:
            painter.setBrush(QBrush(QColor("#f0f0f0")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return result

    def eventFilter(self, obj, event):
        if obj == self.upload_button:
            if event.type() == QtCore.QEvent.Enter:
                self.upload_button.setIcon(QIcon("icon/cma_icon_deep.ico"))
            elif event.type() == QtCore.QEvent.Leave:
                self.upload_button.setIcon(QIcon("icon/cma_icon_shallow.ico"))
        return super().eventFilter(obj, event)

    def enterEvent(self, event):
        if self.upload_callback:
            self.upload_button.show()

    def leaveEvent(self, event):
        self.upload_button.hide()

    def update_theme(self, theme: dict):
        """更新主题，包括自身背景色"""
        self.setStyleSheet(f"background-color: {theme['widget_bg']}; border-radius: 50px; border: 1px solid #808080;")

class RegisterWindow(QDialog):
    def __init__(self, chat_client: "ChatClient", parent=None, user_id=None):
        super().__init__(parent)
        self.chat_client = chat_client
        self.user_id = user_id
        self.local_avatar_path = None
        self.session_id = None
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.setupUi()
        theme_manager.register(self)
        self.update_theme(theme_manager.current_theme)
        self.start_register_process()

    def setupUi(self):
        self.setObjectName("RegisterForm")
        self.resize(280, 380)
        self.setMinimumSize(QSize(280, 380))
        self.setMaximumSize(QSize(280, 380))
        self.setWindowIcon(QIcon("icon/icon.ico"))
        self.setWindowTitle("注册")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(5)
        self.main_layout.setContentsMargins(15, 15, 15, 15)

        self.avatar_widget = AvatarWidget(self, upload_callback=self.upload_avatar)

        self.id_label = QLabel()
        self.id_label.setAlignment(Qt.AlignCenter)
        font = QtGui.QFont("微软雅黑", 12)
        self.id_label.setFont(font)
        self.id_label.setText(f"ID:{self.user_id}" if self.user_id else "ID:待生成")
        self.id_label.setCursor(Qt.PointingHandCursor)
        StyleGenerator.apply_style(self.id_label, "label")

        # 添加悬浮效果
        self.id_label.enterEvent = lambda event: self.id_label.setStyleSheet(
            "color: #4aa36c; text-decoration: underline;")
        self.id_label.leaveEvent = lambda event: self.id_label.setStyleSheet(
            "color: #808080; text-decoration: none;")
        self.id_label.mousePressEvent = self.copy_user_id

        avatar_container = QWidget()
        avatar_layout = QVBoxLayout(avatar_container)
        avatar_layout.setSpacing(5)
        avatar_layout.addStretch()
        avatar_layout.addWidget(self.avatar_widget, alignment=Qt.AlignCenter)
        avatar_layout.addWidget(self.id_label, alignment=Qt.AlignCenter)
        avatar_layout.addStretch()

        self.form_widget = QWidget()
        self.register_layout = QGridLayout(self.form_widget)
        self.register_layout.setSpacing(5)
        self.register_layout.setContentsMargins(0, 0, 0, 0)

        self.input_name = name_line_edit(self, "昵称（可选）", QLineEdit.Normal)
        self.input_password = create_line_edit(self, "密码", QLineEdit.Password)
        self.second_input_password = create_line_edit(self, "确认密码", QLineEdit.Password)
        self.input_verify = create_line_edit(self, "请输入验证码", QLineEdit.Normal)

        self.image_verify_label = QLabel()
        self.image_verify_label.setFixedSize(80, 30)
        self.image_verify_label.setStyleSheet("border: 1px solid #cccccc; background-color: #ffffff;")
        self.image_verify_label.setAlignment(Qt.AlignCenter)
        self.image_verify_label.setMouseTracking(True)
        self.image_verify_label.setCursor(Qt.PointingHandCursor)
        self.image_verify_label.mousePressEvent = self.refresh_captcha

        self.register_button = QPushButton("注册")
        self.register_button.setMinimumHeight(35)
        StyleGenerator.apply_style(self.register_button, "button", extra="border-radius: 5px;")
        self.register_button.clicked.connect(self.submit_registration)

        self.register_layout.addWidget(self.input_name, 0, 0, 1, 1)
        self.register_layout.addWidget(self.input_password, 1, 0, 1, 1)
        self.register_layout.addWidget(self.second_input_password, 2, 0, 1, 1)

        self.verify_widget = QWidget()
        self.verify_layout = QGridLayout(self.verify_widget)
        self.verify_layout.setSpacing(5)
        self.verify_layout.setContentsMargins(0, 0, 0, 0)

        self.verify_layout.addWidget(self.input_verify, 0, 0, 1, 1)
        self.verify_layout.addWidget(self.image_verify_label, 0, 1, 1, 1)
        self.verify_layout.addWidget(self.register_button, 1, 0, 1, 2)

        self.register_layout.addWidget(self.verify_widget, 3, 0, 1, 1)

        self.main_layout.addWidget(avatar_container)
        self.main_layout.addWidget(self.form_widget)
        self.main_layout.addStretch()

    def copy_user_id(self, event):
        if self.user_id:
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(self.user_id)
            FloatingLabel("ID 已复制到剪贴板", self, 0.5, 1/10)

    def start_register_process(self):
        async def fetch_initial_data():
            resp = await self.chat_client.register("register_1")
            if resp.get("status") == "success":
                self.user_id = resp.get("username")
                self.session_id = resp.get("session_id")
                self.id_label.setText(f"ID:{self.user_id}")
                captcha_img = base64.b64decode(resp.get("captcha_image"))
                pixmap = QPixmap()
                pixmap.loadFromData(captcha_img)
                self.image_verify_label.setPixmap(pixmap.scaled(80, 30, Qt.KeepAspectRatio))
            else:
                FloatingLabel(resp.get("message", "无法连接服务器"), self, 0.5, 1/10)

        asyncio.ensure_future(fetch_initial_data())

    def refresh_captcha(self, event):
        async def refresh():
            if not self.session_id:
                FloatingLabel("请先获取初始验证码", self, 0.5, 1/10)
                return
            resp = await self.chat_client.register("register_4", session_id=self.session_id)
            if resp.get("status") == "success":
                captcha_img = base64.b64decode(resp.get("captcha_image"))
                pixmap = QPixmap()
                pixmap.loadFromData(captcha_img)
                self.image_verify_label.setPixmap(pixmap.scaled(80, 30, Qt.KeepAspectRatio))
            else:
                FloatingLabel(resp.get("message", "刷新验证码失败"), self, 0.5, 1/10)

        asyncio.ensure_future(refresh())

    def submit_registration(self):
        async def submit():
            captcha_input = self.input_verify.text().strip()
            password = self.input_password.text().strip()
            confirm_password = self.second_input_password.text().strip()
            nickname = self.input_name.text().strip()

            if not captcha_input or not password or not confirm_password:
                FloatingLabel("请填写完整信息", self, 0.5, 1/10)
                return
            if password != confirm_password:
                FloatingLabel("两次密码不一致", self, 0.5, 1/10)
                return

            resp = await self.chat_client.register("register_2", session_id=self.session_id,
                                                   captcha_input=captcha_input)
            if resp.get("status") != "success":
                FloatingLabel(resp.get("message", "验证码错误"), self, 0.5, 1/10)
                if "captcha_image" in resp:
                    captcha_img = base64.b64decode(resp.get("captcha_image"))
                    pixmap = QPixmap()
                    pixmap.loadFromData(captcha_img)
                    self.image_verify_label.setPixmap(pixmap.scaled(80, 30, Qt.KeepAspectRatio))
                return

            resp = await self.chat_client.register(
                "register_3",
                session_id=self.session_id,
                password=password,
                avatar=self.local_avatar_path,
                nickname=nickname,
                sign=""
            )
            if resp.get("status") == "success":
                FloatingLabel("注册成功", self, 0.5, 1/10)
                QTimer.singleShot(1000, self.accept)
            else:
                FloatingLabel(resp.get("message", "注册失败"), self, 0.5, 1/10)

        asyncio.ensure_future(submit())

    def upload_avatar(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择头像", "", "Image Files (*.jpg *.jpeg *.png)")
        if file_path:
            cropper = ImageCropper(file_path, self)
            if cropper.exec_() == QDialog.Accepted:
                cropped_image = cropper.get_cropped_image()
                pixmap = QPixmap.fromImage(cropped_image)
                self.avatar_widget.setPixmap(pixmap)
                self.local_avatar_path = pixmap

    def update_theme(self, theme: dict):
        self.setStyleSheet(f"background-color: {theme['MAIN_INTERFACE']};")
        self.id_label.setStyleSheet("color: #808080; text-decoration: none;")
        StyleGenerator.apply_style(self.input_name, "line_edit")
        StyleGenerator.apply_style(self.input_password, "line_edit")
        StyleGenerator.apply_style(self.second_input_password, "line_edit")
        StyleGenerator.apply_style(self.input_verify, "line_edit")
        StyleGenerator.apply_style(self.register_button, "button", extra="border-radius: 5px;")

    def closeEvent(self, event):
        if self.chat_client.register_active and self.chat_client.register_task:
            self.chat_client.register_active = False
            self.chat_client.register_task.cancel()

            async def cleanup_task():
                if self.chat_client.register_task is not None and isinstance(self.chat_client.register_task,
                                                                             asyncio.Task):
                    try:
                        await self.chat_client.register_task
                    except asyncio.CancelledError:
                        return
                else:
                    return

            asyncio.create_task(cleanup_task())

        for fut in self.chat_client.register_requests.values():
            if not fut.done():
                fut.cancel()
        self.chat_client.register_requests.clear()
        self.session_id = None

        event.accept()
        self.finished.emit(QDialog.Rejected)