# Interface_Controls.py
import asyncio
import os
import sys
from typing import Optional, Any, List

from PIL import Image
import imageio

from PyQt5 import sip
from PyQt5.QtCore import Qt, QEasingCurve, QPropertyAnimation, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QFontMetrics, QPixmap, QImage, QIcon, QPainterPath
from PyQt5.QtWidgets import QWidget, QTextEdit, QHBoxLayout, QLabel, QVBoxLayout, QGraphicsOpacityEffect, QGridLayout


# ---------- 实用函数 ----------

def resource_path(relative_path: str) -> str:
    """
    获取资源文件的绝对路径，兼容 PyInstaller 打包。
    """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath('.'))
    return os.path.join(base_path, relative_path)

# ---------- 主题设置 ----------

LIGHT_THEME = {
    "BUBBLE_USER": QColor("#aaeb7b"),
    "BUBBLE_OTHER": QColor("#ffffff"),
    "ONLINE": QColor("#35fc8d"),
    "OFFLINE": QColor("#D3D3D3"),
    "UNREAD": QColor("#f04e4e"),
    "Confirm_bg":QColor("#ffffff"),
    "chat_bg": "#e9e9e9",
    "widget_bg": "#ffffff",
    "font_color": "#000000",
    "button_background": "#2e8b57",
    "button_hover": "#3ea97b",
    "button_pressed": "#267f4e",
    "button_text_color": "#ffffff",
    "line_edit_border": "#9e9e9e",
    "line_edit_focus_border": "#2e8b57",
    "text_edit_border": "#dcdcdc",
    "text_edit_focus_border": "#2e8b57",
    "list_background": "#ffffff",
    "list_item_hover": "#bfbfbf",
    "list_item_selected": "#2e8b57",
    "MAIN_INTERFACE": "#f0f0f0",
    "title_bar_bg": "#f0f0f0",
    "title_bar_text": "#000000",
    "input_background": "#ffffff"
}

DARK_THEME = {
    **LIGHT_THEME,
    "ONLINE": QColor("#66ff66"),
    "OFFLINE": QColor("#888888"),
    "UNREAD": QColor("#ff6666"),
    "Confirm_bg":QColor("#333333"),
    "chat_bg": "#222222",
    "widget_bg": "#333333",
    "font_color": "#ffffff",
    "button_background": "#3a8f5a",
    "button_hover": "#4aa36c",
    "button_pressed": "#2a6b44",
    "line_edit_border": "#555555",
    "line_edit_focus_border": "#4aa36c",
    "text_edit_border": "#555555",
    "list_background": "#333333",
    "list_item_hover": "#555555",
    "list_item_selected": "#4aa36c",
    "MAIN_INTERFACE": "#222222",
    "title_bar_bg": "#222222",
    "title_bar_text": "#ffffff",
    "input_background": "#1b1b1b"
}


# ---------- 风格管理 ----------

class StyleGenerator:
    """
    根据当前主题生成并应用 QSS 样式。
    """
    _BASE_STYLES = {
        "menu": (
            "QMenu {{ background-color: {widget_bg}; color: {font_color}; border: 1px solid {line_edit_border}; padding: 2px; }}"
            "QMenu::item {{ background-color: transparent; padding: 5px 20px 5px 10px; color: {font_color}; }}"
            "QMenu::item:selected {{ background-color: {list_item_selected}; color: {button_text_color}; }}"
            "QMenu::item:hover {{ background-color: {list_item_hover}; color: {font_color}; }}"
        ),
        "button": (
            "QPushButton {{ background-color: {button_background}; border: none; color: {button_text_color}; padding: 0px; {extra} }}"
            "QPushButton:hover {{ background-color: {button_hover}; }}"
            "QPushButton:pressed {{ background-color: {button_pressed}; }}"
            "QPushButton:disabled {{ background-color: #cccccc; }}"
        ),
        "label": "color: {font_color}; background-color: transparent;",
        "progress_bar": (
            "QProgressBar {{ border: 1px solid {line_edit_border}; border-radius: 5px; background-color: {widget_bg}; text-align: center; color: {font_color}; }}"
            "QProgressBar::chunk {{ background-color: {button_background}; border-radius: 3px; }}"
        ),
        "text_edit": (
            "QTextEdit {{ background-color: {widget_bg}; color: {font_color}; border: 1px solid {text_edit_border}; padding: 1px; }}"
            "QTextEdit:focus {{ border: 1px solid {text_edit_focus_border}; }}"
        ),
        "scrollbar": (
            "QScrollBar:vertical {{ border: none; background: {list_background}; width: 8px; margin: 0; }}"
            "QScrollBar::handle:vertical {{ background: {line_edit_border}; min-height: 30px; border-radius: 4px; }}"
            "QScrollBar::handle:vertical:hover {{ background: {line_edit_focus_border}; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}"
        ),
        "list_widget": (
            "QListWidget {{ background-color: {list_background}; color: {font_color}; border: none; outline: none; }}"
            "QListWidget::item {{ border-bottom: 1px solid {line_edit_border}; background-color: transparent; }}"
            "QListWidget::item:selected {{ background-color: {list_item_selected}; color: {button_text_color}; }}"
            "QListWidget::item:hover {{ background-color: {list_item_hover}; }}"
        ),
        "line_edit": {
            "base": (
                "QLineEdit {{ background-color: {widget_bg}; color: {font_color}; border: 1px solid {line_edit_border}; "
                "border-radius: 4px; padding: 2px 5px; }}"
            ),
            "focus": (
                "QLineEdit:focus {{ border: 1px solid {line_edit_focus_border}; }}"
                "QLineEdit::placeholder {{ color: {line_edit_border}; }}"
            )
        }
    }

    @staticmethod
    def apply_style(widget: QWidget, style_type: str, extra: str = "") -> None:
        """
        为指定控件应用样式
        """
        t = theme_manager.current_theme
        template = StyleGenerator._BASE_STYLES.get(style_type, "")
        if isinstance(template, dict):
            qss = template.get("base", "").format(**t)
        else:
            qss = template.format(**t, extra=extra)
        widget.setStyleSheet(qss)
        if style_type != "menu":
            theme_manager.register(widget)

class ThemeManager:
    """
    主题管理器，负责切换主题及通知所有观察者。
    """
    def __init__(self) -> None:
        self.themes = {"light": LIGHT_THEME, "dark": DARK_THEME}
        self.current_mode = "light"
        self.current_theme = self.themes[self.current_mode]
        self.observers: List[Any] = []

    def set_mode(self, mode: str) -> None:
        if mode in self.themes:
            self.current_theme = self.themes[mode]
            self.current_theme = self.themes[mode]
            self.notify_observers()

    def notify_observers(self) -> None:
        for obs in self.observers[:]:  # 用切片防止遍历时修改列表出错
            if not sip.isdeleted(obs) and hasattr(obs, "update_theme"):
                obs.update_theme(self.current_theme)

    def register(self, obs: Any) -> None:
        if obs not in self.observers:
            self.observers.append(obs)

    def unregister(self, obs: Any) -> None:
        if obs in self.observers:
            self.observers.remove(obs)

    def clear_observers(self) -> None:
        """清理所有观察者"""
        for obs in self.observers[:]:  # 使用切片避免修改时迭代问题
            if not sip.isdeleted(obs):
                self.unregister(obs)

theme_manager = ThemeManager()

# ---------- 字体常量 ----------

FONTS = {
    'MESSAGE': QFont("微软雅黑", 12),
    'TIME': QFont("微软雅黑", 8),
    'FILE_NAME': QFont("微软雅黑", 10),
    'FILE_SIZE': QFont("微软雅黑", 8),
    'USERNAME': QFont("微软雅黑", 12, QFont.Bold),
    'ONLINE_SIZE': 10
}


# ---------- 附加样式功能 ----------

def get_scrollbar_style() -> str:
    """
    根据当前主题返回滚动条样式字符串。
    """
    t = theme_manager.current_theme
    return (
        f"QScrollBar:vertical {{ border: none; background: {t['list_background']}; width: 8px; margin: 0; }}"
        f"QScrollBar::handle:vertical {{ background: {t['line_edit_border']}; min-height: 30px; border-radius: 4px; }}"
        f"QScrollBar::handle:vertical:hover {{ background: {t['line_edit_focus_border']}; }}"
        f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}"
    )

def style_text_edit(te: QTextEdit) -> None:
    """
    为 QTextEdit 应用样式及滚动条样式。
    """
    StyleGenerator.apply_style(te, "text_edit")
    te.verticalScrollBar().setStyleSheet(get_scrollbar_style())


def create_status_indicator(online: bool) -> QPixmap:
    """
    创建在线/离线状态图标。
    """
    size = FONTS['ONLINE_SIZE']
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    color = theme_manager.current_theme['ONLINE'] if online else theme_manager.current_theme['OFFLINE']
    painter.setBrush(color)
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.end()
    return pm


def create_badge(unread: int) -> QPixmap:
    """
    创建未读消息徽标。
    """
    size = 15
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(theme_manager.current_theme['UNREAD'])
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("", 10, QFont.Bold))
    painter.drawText(pm.rect(), Qt.AlignCenter, str(unread))
    painter.end()
    return pm


def generate_thumbnail(file_path: str, file_type: str, output_dir: str = "Chat_DATA/Chat_thumbnails") -> Optional[str]:
    """
    生成图片或视频的缩略图，并返回缩略图路径。
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(file_path)
    thumbnail_path = os.path.join(output_dir, f"thumb_{base_name}")

    if not os.path.exists(file_path):
        return None

    try:
        if file_type == 'image':
            with Image.open(file_path) as img:
                img.thumbnail((450, 450))
                ext = os.path.splitext(file_path)[1].lower()
                format_map = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.gif': 'GIF', '.bmp': 'BMP'}
                fmt = format_map.get(ext, 'JPEG')
                thumbnail_path += '.jpg' if fmt == 'JPEG' else ext
                if fmt == 'JPEG':
                    img.convert('RGB').save(thumbnail_path, fmt)
                else:
                    img.save(thumbnail_path, fmt)
        elif file_type == 'video':
            thumbnail_path += '.jpg'
            reader = imageio.get_reader(file_path)
            frame = reader.get_data(0)
            img = Image.fromarray(frame)
            img.thumbnail((350, 350), Image.Resampling.NEAREST)
            img.save(thumbnail_path, "JPEG")
            reader.close()
        return thumbnail_path if os.path.exists(thumbnail_path) else None
    except Exception:
        return None


# ---------- 自定义小部件 ----------

class FloatingLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowFlags(Qt.Widget)  # 保持作为子控件，确保位置正确

        # 设置样式
        self.setStyleSheet(
            f"background-color: {theme_manager.current_theme['widget_bg']}; "
            "border-radius: 10px; "
            f"color: {theme_manager.current_theme['font_color']}; "
            "padding: 8px;"
        )
        self.setFont(QFont("微软雅黑", 10))
        self.adjustSize()

        # 设置透明度效果
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self.opacity_effect)

        if parent:
            self.parent = parent
            self.update_position()
            parent.installEventFilter(self)

        QTimer.singleShot(1000, self.start_fade_out)

    def update_position(self):
        """更新位置到父窗口中心偏下"""
        if self.parent:
            parent_rect = self.parent.geometry()
            self.move(
                parent_rect.center().x() - self.width() // 2,
                parent_rect.center().y() + parent_rect.height() // 3 - self.height() // 2
            )

    def start_fade_out(self):
        """启动淡出动画，0.5秒内消失"""
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(500)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.finished.connect(self.close)
        self.animation.start()

    def eventFilter(self, obj, event):
        """监听父窗口调整大小事件"""
        if obj == self.parent and event.type() == event.Resize:
            self.update_position()
            return False  # 事件未完全处理，允许继续传递
        return super().eventFilter(obj, event)  # 其他情况交给父类处理

class FriendItemWidget(QWidget):
    """
    好友项控件，显示用户状态、名称及未读消息徽标。
    """
    def __init__(self, username: str, online: bool = False, unread: int = 0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.username = username
        self.online = online
        self.unread = unread
        self._init_ui()
        self.update_display()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.status_label = QLabel(self)
        self.status_label.setFixedSize(15, 15)

        self.name_label = QLabel(self)
        self.name_label.setFont(FONTS['USERNAME'])

        self.badge_label = QLabel(self)
        self.badge_label.setFixedSize(15, 15)

        layout.addWidget(self.status_label)
        layout.addWidget(self.name_label)
        layout.addStretch()
        layout.addWidget(self.badge_label)
        self.setLayout(layout)

    def update_display(self) -> None:
        self.status_label.setPixmap(create_status_indicator(self.online) if self.online else QPixmap())
        self.name_label.setText(self.username)
        metrics = QFontMetrics(self.name_label.font())
        self.name_label.setFixedWidth(metrics.horizontalAdvance(self.username))
        self.badge_label.setPixmap(create_badge(self.unread) if self.unread > 0 else QPixmap())

    def update_theme(self, theme: dict) -> None:
        if not sip.isdeleted(self.name_label):
            StyleGenerator.apply_style(self.name_label, "label")
        if not sip.isdeleted(self.badge_label):
            self.badge_label.setStyleSheet("background-color: transparent;")
        if not sip.isdeleted(self.status_label):
            self.status_label.setStyleSheet("background-color: transparent;")
        self.update_display()


class OnLine(QWidget):
    # 定义一个信号，传递 username
    friend_clicked = pyqtSignal(str)

    def __init__(self, client: 'ChatClient', parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.client = client
        self.username = ""
        self.name = ""
        self.online = False
        self.avatar_pixmap = None
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._init_ui()
        # 添加点击事件
        self.avatar_label.mousePressEvent = self._on_click
        self.name_label.mousePressEvent = self._on_click
        self.avatar_label.setCursor(Qt.PointingHandCursor)
        self.name_label.setCursor(Qt.PointingHandCursor)

    def _init_ui(self) -> None:
        self.main_font = QFont("微软雅黑", 10)
        self.username_font = QFont("微软雅黑", 12)
        layout = QGridLayout(self)  # 使用 QGridLayout 替代 QVBoxLayout 以支持多列布局
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 头像区域
        self.avatar_label = QLabel(self)
        self.avatar_label.setFixedSize(40, 40)  # 设置头像大小
        self.avatar_label.setScaledContents(True)  # 缩放内容以适应标签
        self.avatar_label.setStyleSheet("border: none; background-color: transparent;")
        layout.addWidget(self.avatar_label, 0, 0, 2, 1, Qt.AlignLeft | Qt.AlignVCenter)  # 占 1 列，跨 2 行

        # 用户名/名称区域
        self.name_label = QLabel(self)
        self.name_label.setFont(self.username_font)
        self.name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self.name_label, 0, 1, 1, 1)  # 第 0 行，第 1 列

        # 在线状态区域
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(5)

        self.status_icon_label = QLabel(self)
        self.status_icon_label.setFixedSize(FONTS['ONLINE_SIZE'], FONTS['ONLINE_SIZE'])
        self.status_icon_label.setStyleSheet("border: none;")

        self.status_text_label = QLabel(self)
        self.status_text_label.setFont(self.main_font)
        self.status_text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        status_layout.addWidget(self.status_icon_label)
        status_layout.addWidget(self.status_text_label)
        status_layout.addStretch()

        layout.addLayout(status_layout, 1, 1, 1, 1)  # 第 1 行，第 1 列
        layout.setColumnStretch(2, 1)  # 增加一列用于拉伸

        self.setLayout(layout)

    def _on_click(self, event):
        """处理头像或名字点击事件"""
        if event.button() == Qt.LeftButton and self.username:
            self.friend_clicked.emit(self.username)

    def update_status(self, username: str, online: bool) -> None:
        self.username = username
        self.online = online

        # 从 self.client.friends 中获取 name 和头像信息
        friend_info = next((f for f in self.client.friends if f.get("username") == username), None)
        self.name = friend_info.get("name", username) if friend_info else username

        # 更新名称显示
        self.name_label.setText(self.name)
        self.status_icon_label.setPixmap(create_status_indicator(online))
        self.status_text_label.setText("在线" if online else "离线")

        # 更新头像
        self._update_avatar(friend_info.get("avatar_id") if friend_info else None)

    def _update_avatar(self, avatar_id: Optional[str]) -> None:
        """
        更新头像，先检查本地缓存，若无则从服务器下载。
        """
        if not avatar_id:
            self.avatar_pixmap = None
            self.avatar_label.setPixmap(self._create_default_avatar())
            return

        # 本地缓存路径
        cache_dir = os.path.join(os.path.dirname(__file__), "Chat_DATA", "avatars")
        os.makedirs(cache_dir, exist_ok=True)
        save_path = os.path.join(cache_dir, avatar_id)

        # 检查本地缓存是否存在
        if os.path.exists(save_path):
            self.avatar_pixmap = QPixmap(save_path)
            if not self.avatar_pixmap.isNull():
                self.avatar_label.setPixmap(self._create_round_avatar(self.avatar_pixmap))
                return
            else:
                os.remove(save_path)  # 删除无效缓存

        # 如果本地无缓存或缓存无效，下载头像
        asyncio.create_task(self._download_avatar(avatar_id, save_path))

    async def _download_avatar(self, avatar_id: str, save_path: str) -> None:
        """
        从服务器下载头像并更新显示。
        """
        resp = await self.client.download_media(avatar_id, save_path)
        if resp.get("status") == "success":
            self.avatar_pixmap = QPixmap(save_path)
            if not self.avatar_pixmap.isNull():
                self.avatar_label.setPixmap(self._create_round_avatar(self.avatar_pixmap))
            else:
                self.avatar_label.setPixmap(self._create_default_avatar())
                if os.path.exists(save_path):
                    os.remove(save_path)  # 删除无效文件
        else:
            self.avatar_pixmap = None
            self.avatar_label.setPixmap(self._create_default_avatar())

    def _create_round_avatar(self, pixmap: QPixmap, size: int = 40) -> QPixmap:
        """
        创建圆形头像。
        """
        result = QPixmap(size, size)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)

        scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled)
        painter.end()
        return result

    def _create_default_avatar(self, size: int = 40) -> QPixmap:
        """
        创建默认头像（当没有头像数据时使用）。
        """
        result = QPixmap(size, size)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(theme_manager.current_theme['ONLINE' if self.online else 'OFFLINE']))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return result

    def update_theme(self, theme: dict) -> None:
        StyleGenerator.apply_style(self.name_label, "label")
        StyleGenerator.apply_style(self.status_text_label, "label")
        self.setStyleSheet(f"background-color: {theme['widget_bg']};")
        # 更新头像显示（重新应用主题颜色）
        if self.avatar_pixmap and not self.avatar_pixmap.isNull():
            self.avatar_label.setPixmap(self._create_round_avatar(self.avatar_pixmap))
        else:
            self.avatar_label.setPixmap(self._create_default_avatar())