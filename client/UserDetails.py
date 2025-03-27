import asyncio
import logging
from functools import partial
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QSizePolicy, QFileDialog, QDialog, QLineEdit, QTextEdit
)
from PyQt5.QtCore import Qt, QRect, QPoint, QSize, QEvent
from PyQt5.QtGui import QPixmap, QPainter, QBrush, QPen, QColor, QFont, QImage, QIcon, QFontMetrics

from Interface_Controls import theme_manager, resource_path, StyleGenerator, FloatingLabel
from chat_client import ChatClient

class AdaptiveLabel(QLabel):
    # 保持不变，逻辑合理
    def __init__(self, text="", parent=None, margin=20):
        super().__init__(text, parent)
        self._margin = margin
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setWordWrap(False)

    def adjustWrapping(self, window_width=None):
        if not self.parent() or window_width is None:
            return
        avail_width = window_width - self._margin * 2
        fm = QFontMetrics(self.font())
        natural_width = fm.boundingRect(self.text()).width()
        self.setWordWrap(natural_width > avail_width)
        self.setMinimumWidth(0)
        self.setMaximumWidth(avail_width)
        self.updateGeometry()

    def sizeHint(self):
        if not self.parent():
            return super().sizeHint()
        window_width = self.window().width()
        avail_width = window_width - self._margin * 2
        fm = QFontMetrics(self.font())
        natural_width = fm.boundingRect(self.text()).width()
        if self.wordWrap():
            line_count = 1 + max(0, (natural_width - 1) // avail_width)
            width = min(natural_width, avail_width)
        else:
            line_count = 1
            width = natural_width
        return QSize(width, fm.height() * line_count)

    def setText(self, text: str):
        super().setText(text)
        self.adjustWrapping(self.window().width() if self.window() else None)

class AutoResizingTextEdit(QTextEdit):
    # 保持不变，逻辑合理
    def __init__(self, text="", parent=None, max_chars: Optional[int] = None):
        super().__init__(text, parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.max_chars = max_chars
        self.textChanged.connect(self.adjustHeight)
        if self.max_chars is not None:
            self.textChanged.connect(self.enforceMaxChars)

    def adjustHeight(self):
        doc_height = self.document().size().height() + 10
        new_height = max(40, int(doc_height))
        self.setMinimumHeight(new_height)
        self.updateGeometry()

    def enforceMaxChars(self):
        if self.max_chars is None:
            return
        text = self.toPlainText()
        if len(text) > self.max_chars:
            cursor = self.textCursor()
            pos = cursor.position()
            new_text = text[:self.max_chars]
            self.blockSignals(True)
            self.setPlainText(new_text)
            cursor.setPosition(min(pos, self.max_chars))
            self.setTextCursor(cursor)
            self.blockSignals(False)

class ImageCropper(QDialog):
    # 保持不变，逻辑合理
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("裁切头像")
        self.setFixedSize(400, 400)
        self.image = QImage(image_path)
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

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addStretch()
        btn = QPushButton("确认", self)
        btn.clicked.connect(self.accept)
        StyleGenerator.apply_style(btn, "button", extra="border-radius: 8px;")
        btn.setFixedSize(50, 25)
        layout.addWidget(btn, alignment=Qt.AlignCenter)

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

class AvatarWidget(QWidget):
    def __init__(self, parent=None, pixmap: Optional[QPixmap] = None,
                 upload_callback=None, online: bool = False):
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self.upload_callback = upload_callback
        self.online = online
        self.setAttribute(Qt.WA_Hover, True)

        self.pixmap_label = QLabel(self)
        self.pixmap_label.setFixedSize(80, 80)
        self.pixmap_label.setScaledContents(True)
        if pixmap:
            self.pixmap_label.setPixmap(pixmap)

        # 创建上传按钮，不显示文字，仅显示图标
        self.upload_button = QPushButton(self)
        # 设置初始图标为浅色图标
        self.upload_button.setIcon(QIcon("icon/cma_icon_shallow.ico"))
        self.upload_button.setIconSize(QSize(20, 20))
        self.upload_button.setFixedSize(76, 38)
        self.upload_button.move(2, 40)
        self.upload_button.setStyleSheet("""
            background-color: rgba(0, 0, 0, 100);
            border: none;
            border-top-left-radius: 0px;
            border-top-right-radius: 0px;
            border-bottom-left-radius: 38px;
            border-bottom-right-radius: 38px;
        """)
        # 初始设置为隐藏，只有悬浮时才显示
        self.upload_button.setVisible(False)
        if upload_callback:
            self.upload_button.clicked.connect(upload_callback)
        else:
            self.upload_button.setEnabled(False)
        # 安装事件过滤器用于捕捉按钮的悬浮事件
        self.upload_button.installEventFilter(self)

        self.indicator_label = QLabel(self)
        self.indicator_label.setStyleSheet("background-color: transparent;")
        self.update_indicator()
        self.indicator_label.raise_()
        theme_manager.register(self)

    def setPixmap(self, pixmap: QPixmap):
        self.pixmap_label.setPixmap(pixmap)

    def set_online(self, online: bool):
        self.online = online
        self.update_indicator()

    def update_indicator(self):
        if self.online:
            indicator_size = 10
            pixmap = QPixmap(indicator_size + 4, indicator_size + 4)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor(theme_manager.current_theme['widget_bg']), 2))
            painter.setBrush(QColor(theme_manager.current_theme['ONLINE']))
            painter.drawEllipse(2, 2, indicator_size, indicator_size)
            painter.end()
            self.indicator_label.setPixmap(pixmap)
            radius = 40
            indicator_x = int(radius + (radius - 1) * 0.707 - (indicator_size + 4) / 2)
            indicator_y = int(radius + (radius - 1) * 0.707 - (indicator_size + 4) / 2)
            self.indicator_label.move(indicator_x, indicator_y)
            self.indicator_label.show()
        else:
            self.indicator_label.hide()

    def eventFilter(self, obj, event):
        # 对上传按钮的悬浮事件进行处理
        if obj == self.upload_button:
            if event.type() == QEvent.Enter:
                self.upload_button.setIcon(QIcon("icon/cma_icon_deep.ico"))
            elif event.type() == QEvent.Leave:
                self.upload_button.setIcon(QIcon("icon/cma_icon_shallow.ico"))
        return super().eventFilter(obj, event)

    def enterEvent(self, event):
        if self.upload_callback:
            self.upload_button.show()
        self.indicator_label.raise_()

    def leaveEvent(self, event):
        self.upload_button.hide()
        self.indicator_label.raise_()

    def update_theme(self, theme: dict):
        self.update_indicator()


class UserDetails(QWidget):
    def __init__(self, client: ChatClient, parent: Optional[QWidget] = None,
                 avatar: Optional[QPixmap] = None, name: str = None, sign: str = None,
                 username: str = "", online: bool = False, from_info_button: bool = False,
                 from_online: bool = False):
        super().__init__(parent)
        self.client = client
        self.avatar = avatar
        self.name = name or username
        self.sign = sign or "这个人很懒，什么都没写"
        self.username = username
        self.online = online
        self.from_info_button = from_info_button
        self.from_online = from_online
        self.edit_widgets = {}
        self._init_ui()
        theme_manager.register(self)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5)

        # 头像与基本信息区域
        self.container1 = QWidget(self)
        self.container1.setStyleSheet(f"background-color: {theme_manager.current_theme['widget_bg']}; border-radius: 10px;")
        self.container1.setMinimumHeight(100)
        self.container1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(self.container1)
        hbox.setContentsMargins(10, 10, 10, 10)
        hbox.setSpacing(10)

        self.avatar_widget = AvatarWidget(
            self,
            pixmap=self.create_round_avatar(self.avatar),
            upload_callback=self.upload_avatar if self.from_info_button and not self.from_online else None,
            online=self.online
        )
        hbox.addWidget(self.avatar_widget)

        info = QWidget(self.container1)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(10, 10, 10, 10)
        info_layout.setSpacing(5)

        self.name_container, self.name_label, self.name_edit_button = self._create_editable_field(
            "name", self.name, QFont("微软雅黑", 14, QFont.Bold)
        )
        info_layout.addWidget(self.name_container)

        self.online_label = QLabel("在线" if self.online else "离线", info)
        self.online_label.setFont(QFont("微软雅黑", 10))
        self.online_label.setStyleSheet("color: #35fc8d;" if self.online else f"color: {theme_manager.current_theme['font_color']};")
        info_layout.addWidget(self.online_label)

        self.id_label = QLabel(f"ID: {self.username}", info)
        self.id_label.setFont(QFont("微软雅黑", 10))
        StyleGenerator.apply_style(self.id_label, "label")
        info_layout.addWidget(self.id_label)
        info_layout.addStretch()

        hbox.addWidget(info)
        hbox.addStretch()
        main_layout.addWidget(self.container1)

        # 个人简介区域
        self.container2 = QWidget(self)
        self.container2.setStyleSheet(f"background-color: {theme_manager.current_theme['widget_bg']}; border-radius: 10px;")
        self.container2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        vbox = QVBoxLayout(self.container2)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(5)

        self.intro_label = QLabel("个人简介", self.container2)
        self.intro_label.setFont(QFont("微软雅黑", 11, QFont.Bold))
        StyleGenerator.apply_style(self.intro_label, "label")
        vbox.addWidget(self.intro_label, alignment=Qt.AlignLeft)

        self.sign_container, self.sign_label, self.sign_edit_button = self._create_editable_field(
            "sign", self.sign, QFont("微软雅黑", 9)
        )
        vbox.addWidget(self.sign_container, alignment=Qt.AlignLeft)
        main_layout.addWidget(self.container2)

        if not self.from_info_button:
            self.delete_button = QPushButton("删除好友", self)
            StyleGenerator.apply_style(self.delete_button, "button", extra="font-size: 14px; font-family: 微软雅黑; padding: 10px; border-radius: 8px;")
            self.delete_button.setFixedHeight(50)
            self.delete_button.clicked.connect(self.confirm_delete)
            main_layout.addWidget(self.delete_button)

        main_layout.addStretch()

    def _create_editable_field(self, key: str, text: str, font: QFont):
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label = AdaptiveLabel(text, container) if key == "sign" else QLabel(text, container)
        label.setFont(font)
        StyleGenerator.apply_style(label, "label")

        edit_button = QPushButton(container)
        edit_button.setFixedSize(17, 17)
        edit_button.setIcon(QIcon(resource_path("icon/revise_icon_shallow.ico")))
        edit_button.setStyleSheet("background: none; border: none;")
        editable = not self.from_online or key == "name"
        edit_button.setVisible(False)
        if editable:
            edit_button.clicked.connect(partial(self._toggle_editing, key))
            # 使用局部函数处理悬停事件
            def container_enter_event(event, key=key, btn=edit_button):
                if key not in self.edit_widgets:
                    btn.show()
            def container_leave_event(event, key=key, btn=edit_button):
                if key not in self.edit_widgets:
                    btn.hide()
            container.enterEvent = container_enter_event
            container.leaveEvent = container_leave_event
            def btn_enter_event(event, btn=edit_button):
                btn.setIcon(QIcon(resource_path("icon/revise_icon_deep.ico")))
            def btn_leave_event(event, btn=edit_button):
                btn.setIcon(QIcon(resource_path("icon/revise_icon_shallow.ico")))
            edit_button.enterEvent = btn_enter_event
            edit_button.leaveEvent = btn_leave_event
        layout.addWidget(label)
        layout.addWidget(edit_button)
        layout.addStretch()
        return container, label, edit_button

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            for key, (_, editor, _) in list(self.edit_widgets.items()):
                if obj is editor:
                    self._cancel_editing(key)
                    return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 对所有处于编辑状态的编辑器重新计算宽度和字体
        for key in self.edit_widgets:
            _, editor, _ = self.edit_widgets[key]
            self.adjustEditorWidthAndFont(editor, key)
        if "sign" not in self.edit_widgets:
            self.sign_label.adjustWrapping(self.width())

    def _toggle_editing(self, key: str):
        if key in self.edit_widgets:
            self._cancel_editing(key)
        else:
            for active_key in list(self.edit_widgets.keys()):
                self._cancel_editing(active_key)
            label = self.name_label if key == "name" else self.sign_label
            self._start_editing(key, label, label.parent())

    def _cancel_editing(self, key: str):
        if key not in self.edit_widgets:
            return
        edit_widget, _, label = self.edit_widgets.pop(key)
        parent_layout = edit_widget.parent().layout()
        parent_layout.replaceWidget(edit_widget, label)
        label.show()
        edit_widget.deleteLater()
        edit_button = self.name_edit_button if key == "name" else self.sign_edit_button
        edit_button.setVisible(True)
        if key == "sign":
            self.sign_label.adjustWrapping(self.width())

    def _save_edit(self, key: str, editor, label: QLabel, edit_widget: QWidget):
        new_text = editor.toPlainText().strip() if isinstance(editor, QTextEdit) else editor.text().strip()
        if new_text != label.text():
            label.setText(new_text)
            asyncio.create_task(self._update_profile(field_type=key, field_value=new_text))
        self._cancel_editing(key)

    async def _update_profile(self, field_type: str = None, field_value: str = None, avatar_pixmap: QPixmap = None):
        original_value = getattr(self, field_type, None) if field_type else None
        resp = None
        if avatar_pixmap:
            resp = await self.client.upload_avatar(avatar_pixmap)
        elif field_type and field_value:
            method = self.client.update_friend_remarks if field_type == "name" and self.from_online else getattr(
                self.client, f"update_{field_type}")
            target = self.username if self.from_online else field_value
            resp = await method(target, field_value) if self.from_online else await method(field_value)

        if resp:
            if resp.get("status") == "success":
                # 根据 field_type 或头像更新选择提示
                msg_map = {
                    "sign": "签名更新成功",
                    "name": "昵称更新成功" if not self.from_online else resp.get("message") ,
                    None: "头像上传成功"
                }
                FloatingLabel(msg_map[field_type], self).show()
                if avatar_pixmap:
                    self.avatar = avatar_pixmap
                    self.update_avatar()
                elif field_type:
                    setattr(self, field_type, field_value)
                    if self.from_online and hasattr(self.parent().parent(), 'update_friend_list'):
                        await self.parent().parent().update_friend_list()
            else:
                # 使用服务器返回的错误消息
                error_msg = resp.get("message", "未知错误")
                FloatingLabel(f"更新失败: {error_msg}", self).show()
                if field_type:
                    setattr(self, field_type, original_value)
                    (self.name_label if field_type == "name" else self.sign_label).setText(original_value)

    def adjustEditorWidthAndFont(self, editor, key):
        """
        动态调整编辑器宽度和字体大小：
        - 根据编辑区域（名字或签名）设置不同的可用宽度和默认字体大小
        - 考虑按钮的空间，确保输入框不会与按钮重叠
        - 对于名字输入框，当宽度达到118时开始减小字体
        - 对于签名输入框，当宽度超过可用范围时减小字体
        """
        # 按钮宽度（20 + 20） + 间距（5 * 2）
        button_space = 50

        if key == "sign":
            available_width = self.container2.width() - 30 - button_space
            default_font_size = 10
            font_weight = QFont.Normal
        elif key == "name":
            available_width = self.container1.width() - 50 - button_space
            default_font_size = 14
            font_weight = QFont.Bold
        else:
            available_width = editor.width() - button_space
            default_font_size = 10
            font_weight = QFont.Normal

        min_font_size = 8  # 最小字体大小

        # 获取编辑框文本内容
        if isinstance(editor, QLineEdit):
            text = editor.text() or ""
        elif isinstance(editor, QTextEdit):
            text = editor.toPlainText() or ""
        else:
            text = ""

        # 初始化字体和测量工具
        font = QFont("微软雅黑", default_font_size, font_weight)
        fm = QFontMetrics(font)
        natural_width = fm.boundingRect(text).width() + 10
        new_font_size = default_font_size

        if key == "name" and natural_width >= 140:
            while natural_width >= 140 and new_font_size > min_font_size:
                new_font_size -= 1
                font.setPointSize(new_font_size)
                fm = QFontMetrics(font)
                natural_width = fm.boundingRect(text).width() + 20

        # 处理签名输入框：宽度超限时减小字体
        elif key == "sign" and natural_width > available_width and new_font_size > min_font_size:
            while natural_width > available_width and new_font_size > min_font_size:
                new_font_size -= 1
                font.setPointSize(new_font_size)
                fm = QFontMetrics(font)
                natural_width = fm.boundingRect(text).width() + 10

        # 应用字体
        editor.setFont(font)
        # 设置宽度，确保不与按钮重叠
        new_width = max(50, min(natural_width, available_width))
        editor.setFixedWidth(new_width)
        if isinstance(editor, QTextEdit):
            editor.document().setTextWidth(new_width)
            editor.adjustHeight()

    def _start_editing(self, key: str, label: QLabel, parent_widget: QWidget):
        layout = parent_widget.layout()
        edit_widget = QWidget(parent_widget)
        edit_layout = QHBoxLayout(edit_widget)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(5)  # 增加间距，确保按钮和输入框之间有空间

        if key == "name":
            editor = QLineEdit(label.text(), edit_widget)
            editor.setFont(QFont("微软雅黑", 14, QFont.Bold))
            editor.setMaxLength(15)  # 名字最大长度为15
            StyleGenerator.apply_style(editor, "line_edit")
        else:  # key == "sign"
            editor = AutoResizingTextEdit(label.text(), edit_widget, max_chars=100)
            editor.setFont(QFont("微软雅黑", 10))
            StyleGenerator.apply_style(editor, "text_edit")
            editor.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
            editor.adjustHeight()

        editor.installEventFilter(self)
        editor.textChanged.connect(partial(self.adjustEditorWidthAndFont, editor, key))
        self.adjustEditorWidthAndFont(editor, key)

        edit_layout.addWidget(editor)

        # 添加确认按钮（使用 yes_icon.ico）
        confirm_btn = QPushButton("", edit_widget)
        confirm_btn.setFixedSize(20, 20)
        confirm_btn.setIcon(QIcon(resource_path("icon/yes_icon.ico")))
        confirm_btn.setStyleSheet("background: none; border: none;")
        confirm_btn.clicked.connect(partial(self._save_edit, key, editor, label, edit_widget))
        edit_layout.addWidget(confirm_btn)

        # 添加取消按钮（使用 no_icon.ico）
        cancel_btn = QPushButton("", edit_widget)
        cancel_btn.setFixedSize(20, 20)
        cancel_btn.setIcon(QIcon(resource_path("icon/no_icon.ico")))
        cancel_btn.setStyleSheet("background: none; border: none;")
        cancel_btn.clicked.connect(partial(self._cancel_editing, key))
        edit_layout.addWidget(cancel_btn)

        edit_layout.addStretch()

        layout.replaceWidget(label, edit_widget)
        label.hide()
        edit_widget.show()
        editor.setFocus()
        self.edit_widgets[key] = (edit_widget, editor, label)
        if key == "name":
            self.name_edit_button.hide()
        else:
            self.sign_edit_button.hide()

    def create_round_avatar(self, pixmap, size=80):
        result = QPixmap(size, size)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.setBrush(QBrush(scaled))
        else:
            # 使用默认头像图标
            default_avatar = QPixmap(resource_path("icon/default_avatar.ico"))
            if default_avatar.isNull():
                # 如果加载失败，回退到纯色填充
                painter.setBrush(QBrush(QColor("#35fc8d")))
            else:
                scaled_default = default_avatar.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                painter.setBrush(QBrush(scaled_default))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(theme_manager.current_theme['ONLINE' if self.online else 'OFFLINE'], 2))
        painter.drawEllipse(1, 1, size - 2, size - 2)
        painter.end()
        return result

    def upload_avatar(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择头像", "", "Image Files (*.jpg *.jpeg *.png)")
        if file_path:
            cropper = ImageCropper(file_path, self)
            if cropper.exec_() == QDialog.Accepted:
                self.avatar = QPixmap.fromImage(cropper.get_cropped_image())
                self.update_avatar()
                asyncio.create_task(self._update_profile(avatar_pixmap=self.avatar))

    def update_avatar(self):
        self.avatar_widget.setPixmap(self.create_round_avatar(self.avatar))

    def update_status(self, online: bool):
        self.online = online
        self.online_label.setText("在线" if online else "离线")
        self.online_label.setStyleSheet("color: #35fc8d;" if online else f"color: {theme_manager.current_theme['font_color']};")
        self.avatar_widget.set_online(online)
        self.update_avatar()

    def update_theme(self, theme: dict):
        self.setStyleSheet(f"background-color: {theme['MAIN_INTERFACE']};")
        self.container1.setStyleSheet(f"background-color: {theme['widget_bg']}; border-radius: 10px;")
        self.container2.setStyleSheet(f"background-color: {theme['widget_bg']}; border-radius: 10px;")
        for widget in [self.name_label, self.id_label, self.sign_label, self.intro_label]:
            StyleGenerator.apply_style(widget, "label")
        if hasattr(self, "delete_button"):
            StyleGenerator.apply_style(self.delete_button, "button", extra="font-size: 14px; font-family: 微软雅黑; padding: 10px; border-radius: 8px;")
        self.online_label.setStyleSheet("color: #35fc8d;" if self.online else f"color: {theme['font_color']};")
        self.update_avatar()

    def confirm_delete(self):
        reply = QMessageBox.question(self, "确认删除", f'确定要删除好友 "{self.name}" 吗？',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            logging.debug(f"已确认删除好友: {self.name} (ID: {self.username})")
        else:
            logging.debug("取消删除操作")