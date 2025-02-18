# Interface_Controls.py
from PyQt5 import sip
from PyQt5.QtCore import Qt, QSize, QRect
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QPixmap, QPainterPath
)
from PyQt5.QtWidgets import (
    QWidget, QTextEdit, QHBoxLayout, QLabel, QVBoxLayout,
    QSizePolicy, QScrollArea
)
from dataclasses import dataclass
from typing import Optional, Any
import asyncio

# ---------------- 主题管理 ----------------
# 定义浅色与深色主题颜色方案（聊天气泡颜色始终使用浅色方案）
LIGHT_THEME = {
    "BUBBLE_USER": QColor("#aaeb7b"),
    "BUBBLE_OTHER": QColor("#ffffff"),
    "ONLINE": QColor("#35fc8d"),
    "OFFLINE": QColor("#D3D3D3"),
    "UNREAD": QColor("#f04e4e"),
    "chat_bg": "#e9e9e9",
    "widget_bg": "#ffffff",        # 普通控件背景色
    "font_color": "#000000",         # 普通文字颜色
    "button_background": "#2e8b57",
    "button_hover": "#3ea97b",
    "button_pressed": "#267f4e",
    "button_text_color": "#ffffff",  # 按钮文字颜色
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
}

DARK_THEME = {
    "BUBBLE_USER": LIGHT_THEME["BUBBLE_USER"],
    "BUBBLE_OTHER": LIGHT_THEME["BUBBLE_OTHER"],
    "ONLINE": QColor("#66ff66"),
    "OFFLINE": QColor("#888888"),
    "UNREAD": QColor("#ff6666"),
    "chat_bg": "#222222",
    "widget_bg": "#333333",
    "font_color": "#ffffff",
    "button_background": "#3a8f5a",
    "button_hover": "#4aa36c",
    "button_pressed": "#2a6b44",
    "button_text_color": "#ffffff",
    "line_edit_border": "#555555",
    "line_edit_focus_border": "#4aa36c",
    "text_edit_border": "#555555",
    "text_edit_focus_border": "#2e8b57",
    "list_background": "#333333",
    "list_item_hover": "#555555",
    "list_item_selected": "#4aa36c",
    "MAIN_INTERFACE": "#222222",
    "title_bar_bg": "#222222",
    "title_bar_text": "#ffffff",
}


class ThemeManager:
    """
    主题管理器：保存当前主题，并通知所有注册的观察者更新主题。
    """
    def __init__(self) -> None:
        self.themes = {"light": LIGHT_THEME, "dark": DARK_THEME}
        self.current_mode: str = "light"
        self.current_theme: dict = self.themes[self.current_mode]
        self.observers: list[Any] = []  # 存储需要响应主题更新的控件

    def set_mode(self, mode: str) -> None:
        """设置主题模式，并通知所有观察者"""
        if mode in self.themes:
            self.current_mode = mode
            self.current_theme = self.themes[mode]
            self.notify_observers()

    def notify_observers(self) -> None:
        """遍历所有观察者，调用其 update_theme 方法"""
        for obs in self.observers:
            if not sip.isdeleted(obs) and hasattr(obs, "update_theme"):
                obs.update_theme(self.current_theme)

    def register(self, observer: Any) -> None:
        """注册观察者"""
        if observer not in self.observers:
            self.observers.append(observer)

    def unregister(self, observer: Any) -> None:
        """注销观察者"""
        if observer in self.observers:
            self.observers.remove(observer)


theme_manager = ThemeManager()

# ---------------- 字体常量 ----------------
FONTS = {
    'MESSAGE': QFont("微软雅黑", 12),
    'TIME': QFont("微软雅黑", 8),
    'USERNAME': QFont("微软雅黑", 12, QFont.Bold),
    'ONLINE_SIZE': 10
}

# ---------------- 样式函数 ----------------

def style_label(label: QLabel) -> None:
    """
    为 QLabel 设置当前主题的文字颜色及背景色
    """
    theme = theme_manager.current_theme
    label.setStyleSheet(f"""
        QLabel {{
            color: {theme['font_color']};
            background-color: transparent;
        }}
    """)

def _apply_button_style(button: Any, border_radius: str = "") -> None:
    """
    为 QPushButton 设置样式（包含圆角、背景、文字颜色等）。
    """
    theme = theme_manager.current_theme
    button.setStyleSheet(f"""
        QPushButton {{
            background-color: {theme['button_background']};
            border: none;
            color: {theme['button_text_color']};
            {border_radius}
            padding: 6px 12px;
        }}
        QPushButton:hover {{
            background-color: {theme['button_hover']};
        }}
        QPushButton:pressed {{
            background-color: {theme['button_pressed']};
        }}
        QPushButton:disabled {{
            background-color: #cccccc;
        }}
    """)

def style_button(button: Any) -> None:
    _apply_button_style(button)

def style_rounded_button(button: Any) -> None:
    _apply_button_style(button, "border-radius: 4px;")

def login_style_line_edit(line_edit: Any) -> None:
    """
    设置登录界面 QLineEdit 样式
    """
    theme = theme_manager.current_theme
    line_edit.setStyleSheet(f"""
        QLineEdit {{
            background-color: {theme['widget_bg']};
            color: {theme['font_color']};
            border: 1px solid {theme['line_edit_border']};
            border-radius: 4px;
            padding: 2px 5px;
        }}
    """)

def style_line_edit(line_edit: Any) -> None:
    """
    设置 QLineEdit 的样式，包括 placeholder 和焦点状态。
    """
    theme = theme_manager.current_theme
    line_edit.setStyleSheet(f"""
        QLineEdit {{
            background-color: {theme['widget_bg']};
            color: {theme['font_color']};
            border: 1px solid {theme['line_edit_border']};
            border-radius: 4px;
            padding: 2px 5px;
        }}
        QLineEdit:focus {{
            border: 1px solid {theme['line_edit_focus_border']};
            color: {theme['font_color']};
        }}
        QLineEdit::placeholder {{
            color: {theme['line_edit_border']};
        }}
    """)
    # 双保险：通过 QPalette 设置文本颜色
    palette = line_edit.palette()
    palette.setColor(palette.Text, QColor(theme['font_color']))
    palette.setColor(palette.Foreground, QColor(theme['font_color']))
    line_edit.setPalette(palette)

def get_scrollbar_style() -> str:
    """
    返回当前主题下垂直滚动条的样式字符串
    """
    theme = theme_manager.current_theme
    return f"""
    QScrollBar:vertical {{
        border: none;
        background: {theme['list_background']};
        width: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {theme['line_edit_border']};
        min-height: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {theme['line_edit_focus_border']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
    """

def style_text_edit(text_edit: QTextEdit) -> None:
    """
    设置 QTextEdit 的样式及其滚动条样式
    """
    theme = theme_manager.current_theme
    text_edit.setStyleSheet(f"""
        QTextEdit {{
            background-color: {theme['widget_bg']};
            color: {theme['font_color']};
            border: 1px solid {theme['text_edit_border']};
            padding: 1px;
        }}
        QTextEdit:focus {{
            border: 1px solid {theme['text_edit_focus_border']};
        }}
    """)
    scroll_bar = text_edit.verticalScrollBar()
    if scroll_bar:
        scroll_bar.setStyleSheet(get_scrollbar_style())

def style_list_widget(list_widget: Any) -> None:
    """
    设置 QListWidget 的样式
    """
    theme = theme_manager.current_theme
    list_widget.setStyleSheet(f"""
        QListWidget {{
            background-color: {theme['list_background']};
            color: {theme['font_color']};
            border: none;
            outline: none;
        }}
        QListWidget::item {{
            border-bottom: 1px solid {theme['line_edit_border']};
            background-color: transparent;
        }}
        QListWidget::item:selected {{
            background-color: {theme['list_item_selected']};
            color: {theme['button_text_color']};
        }}
        QListWidget::item:hover {{
            background-color: {theme['list_item_hover']};
        }}
        QListWidget QScrollBar:vertical {{
            {get_scrollbar_style().replace("QScrollBar", "QListWidget QScrollBar")}
        }}
    """)

def style_scrollbar(scroll_area: Any) -> None:
    """
    为给定的滚动区域设置滚动条样式
    """
    scroll_area.setStyleSheet(get_scrollbar_style())

# ---------------- 自定义控件 ----------------

class MessageInput(QTextEdit):
    """
    自定义消息输入框，支持回车发送（Shift+Enter 换行）。
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        style_text_edit(self)

    def keyPressEvent(self, event: Any) -> None:
        if event.key() == Qt.Key_Return:
            if event.modifiers() & Qt.ShiftModifier:
                self.insertPlainText('\n')
                self.move_cursor_to_bottom()
            else:
                if self.parent():
                    asyncio.create_task(self.parent().send_message())
            event.accept()
        else:
            super().keyPressEvent(event)

    def move_cursor_to_bottom(self) -> None:
        cursor = self.textCursor()
        cursor.movePosition(cursor.End)
        self.setTextCursor(cursor)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class FriendItemWidget(QWidget):
    """
    自定义好友列表项控件，显示用户名、在线状态和未读消息徽标。
    """
    def __init__(self, username: str, online: bool = False, unread: int = 0,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.username: str = username
        self.online: bool = online
        self.unread: int = unread
        self._init_ui()
        self.update_display()

    def _init_ui(self) -> None:
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)
        self.status_label = QLabel(self)
        self.status_label.setFixedSize(15, 15)
        self.name_label = QLabel(self)
        self.name_label.setFont(FONTS['USERNAME'])
        self.badge_label = QLabel(self)
        self.badge_label.setFixedSize(15, 15)
        self.layout.addWidget(self.status_label)
        self.layout.addWidget(self.name_label)
        self.layout.addStretch()
        self.layout.addWidget(self.badge_label)

    def update_display(self) -> None:
        """更新在线状态、用户名和未读徽标显示"""
        if self.online:
            self.status_label.setPixmap(create_status_indicator(True))
        else:
            self.status_label.clear()
        self.name_label.setText(self.username)
        if self.unread > 0:
            self.badge_label.setPixmap(create_badge(self.unread))
        else:
            self.badge_label.clear()

    def update_theme(self, theme: dict) -> None:
        """
        根据当前主题更新控件内部各子控件样式。
        注意：原先直接对 self 调用 style_label 不合理，现分别更新各标签样式。
        """
        if not sip.isdeleted(self.name_label):
            style_label(self.name_label)
        if not sip.isdeleted(self.badge_label):
            self.badge_label.setStyleSheet("background-color: transparent;")
        if not sip.isdeleted(self.status_label):
            self.status_label.setStyleSheet("background-color: transparent;")
        self.update_display()


def create_status_indicator(online: bool) -> QPixmap:
    """
    创建在线状态指示图标（圆形）。
    """
    size = FONTS['ONLINE_SIZE']
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    color = theme_manager.current_theme['ONLINE'] if online else theme_manager.current_theme['OFFLINE']
    painter.setBrush(color)
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.end()
    return pixmap


def create_badge(unread: int) -> QPixmap:
    """
    创建未读消息徽标（带数字）。
    """
    size = 15
    badge = QPixmap(size, size)
    badge.fill(Qt.transparent)
    painter = QPainter(badge)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(theme_manager.current_theme['UNREAD'])
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("", 10, QFont.Bold))
    painter.drawText(badge.rect(), Qt.AlignCenter, str(unread))
    painter.end()
    return badge


class OnLine(QWidget):
    """
    在线状态显示控件，显示用户名及在线状态。
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.username: str = ""
        self.online: bool = False
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._init_ui()

    def _init_ui(self) -> None:
        self.main_font = QFont("微软雅黑", 10)
        self.username_font = QFont("微软雅黑", 12)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(2)
        self.username_label = QLabel(self)
        self.username_label.setFont(self.username_font)
        self.username_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.layout.addWidget(self.username_label)
        self.status_layout = QHBoxLayout()
        self.status_layout.setContentsMargins(0, 0, 0, 0)
        self.status_layout.setSpacing(5)
        self.status_icon_label = QLabel(self)
        self.status_icon_label.setFixedSize(FONTS['ONLINE_SIZE'], FONTS['ONLINE_SIZE'])
        self.status_icon_label.setStyleSheet("border: none;")
        self.status_text_label = QLabel(self)
        self.status_text_label.setFont(self.main_font)
        self.status_text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status_layout.addWidget(self.status_icon_label)
        self.status_layout.addWidget(self.status_text_label)
        self.status_layout.addStretch()
        self.layout.addLayout(self.status_layout)

    def update_status(self, username: str, online: bool) -> None:
        """
        更新在线状态显示
        """
        self.username = username
        self.online = online
        self.username_label.setText(username)
        self.status_icon_label.setPixmap(create_status_indicator(online))
        self.status_text_label.setText("在线" if online else "离线")

    def update_theme(self, theme: dict) -> None:
        style_label(self.username_label)
        style_label(self.status_text_label)
        self.setStyleSheet(f"background-color: {theme['widget_bg']};")


class ChatAreaWidget(QWidget):
    """
    聊天记录显示区域容器，自动管理聊天气泡布局与大小更新。
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._init_ui()
        self.bubble_containers: list[QWidget] = []  # 保存各个气泡容器

    def _init_ui(self) -> None:
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)

    def addBubble(self, bubble: QWidget, index: Optional[int] = None) -> None:
        """
        添加聊天气泡，如果 index 指定则插入到指定位置
        """
        container = QWidget(self)
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        if hasattr(bubble, "align") and bubble.align == "right":
            h_layout.addStretch()
            h_layout.addWidget(bubble)
        else:
            h_layout.addWidget(bubble)
            h_layout.addStretch()
        if index is None:
            self.bubble_containers.append(container)
            self.layout.addWidget(container)
        else:
            self.bubble_containers.insert(index, container)
            self.layout.insertWidget(index, container)

    def clearBubbles(self) -> None:
        """
        清空所有聊天气泡
        """
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.bubble_containers.clear()

    def resizeEvent(self, event: Any) -> None:
        current_width = self.width()
        ChatBubbleWidget.config.chat_area_width = current_width
        self._update_all_bubbles()
        super().resizeEvent(event)

    def _update_all_bubbles(self) -> None:
        for container in self.bubble_containers:
            for i in range(container.layout().count()):
                widget = container.layout().itemAt(i).widget()
                if isinstance(widget, ChatBubbleWidget):
                    widget.updateBubbleSize()


# ---------------- 聊天气泡 ----------------

@dataclass
class BubbleConfig:
    """
    气泡配置数据类，包含聊天区域宽度、内边距、气泡间隙、三角形大小等参数
    """
    chat_area_width: int = 650
    h_padding: int = 8
    v_padding: int = 5
    gap: int = 3
    triangle_size: int = 10
    triangle_height: int = 10


class ChatBubbleWidget(QWidget):
    """
    自定义聊天气泡控件，支持左右对齐，内部包含消息文本和时间戳，气泡颜色固定使用浅色方案。
    """
    config: BubbleConfig = BubbleConfig()

    def __init__(self, message: str, time_str: str, align: str = 'left',
                 is_current_user: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.align: str = 'right' if is_current_user else align
        self.is_current_user: bool = is_current_user
        self.message: str = self._insertZeroWidthSpace(message)
        self.time_str: str = time_str
        # 固定使用 LIGHT_THEME 的气泡颜色
        self.bubble_color: QColor = (LIGHT_THEME["BUBBLE_USER"] if self.is_current_user
                                     else LIGHT_THEME["BUBBLE_OTHER"])
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化内部控件"""
        self.text_message = QTextEdit(self)
        self.text_message.setFont(FONTS['MESSAGE'])
        self.text_message.setStyleSheet("background: transparent; border: none;")
        self.text_message.setReadOnly(True)
        self.text_message.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_message.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_message.setPlainText(self.message)
        self.label_time = QLabel(self)
        self.label_time.setFont(FONTS['TIME'])
        self.label_time.setStyleSheet("background: transparent; border: none;")
        self.label_time.setTextInteractionFlags(Qt.NoTextInteraction)
        self.label_time.setText(self.time_str)
        self._bubble_rect = QRect()

    def _insertZeroWidthSpace(self, text: str) -> str:
        """
        对没有空格的长字符串插入零宽空格，以便自动换行。
        """
        lines = text.split('\n')
        processed = [("\u200B".join(line) if ' ' not in line else line) for line in lines]
        return '\n'.join(processed)

    def _calculateSizes(self) -> tuple[QSize, QSize, QSize, int]:
        """
        根据消息文本和时间计算气泡的各项尺寸信息，
        返回：气泡总尺寸、文本尺寸、时间尺寸、实际文本宽度。
        """
        available_width = int(self.config.chat_area_width * 0.6)
        fm_msg = QFontMetrics(FONTS['MESSAGE'])
        natural_text_width = (fm_msg.horizontalAdvance(self.message.replace('\u200B', ''))
                              if hasattr(fm_msg, 'horizontalAdvance')
                              else fm_msg.width(self.message.replace('\u200B', '')))
        lines = self.message.split('\n')
        total_height = fm_msg.height() * len(lines)
        if natural_text_width < available_width:
            self.text_message.setFixedWidth(natural_text_width + 2 * self.config.h_padding)
            chosen_width = natural_text_width
            text_size = QSize(chosen_width, total_height)
        else:
            self.text_message.setFixedWidth(available_width + 2 * self.config.h_padding)
            self.text_message.document().setTextWidth(available_width)
            text_size = self.text_message.document().size().toSize()
            chosen_width = available_width
        fm_time = QFontMetrics(FONTS['TIME'])
        time_width = fm_time.horizontalAdvance(self.time_str) if hasattr(fm_time, 'horizontalAdvance') else fm_time.width(self.time_str)
        time_size = QSize(time_width, fm_time.height())
        bubble_content_width = max(chosen_width, time_width)
        bubble_width = bubble_content_width + 2 * self.config.h_padding
        bubble_height = text_size.height() + fm_time.height() + 2 * self.config.v_padding + self.config.gap
        return QSize(bubble_width, bubble_height), text_size, time_size, chosen_width

    def sizeHint(self) -> QSize:
        bubble_size, _, _, _ = self._calculateSizes()
        return QSize(bubble_size.width() + self.config.triangle_size, bubble_size.height())

    def updateBubbleSize(self) -> None:
        """
        根据当前控件尺寸及文本内容更新内部控件的位置和整体大小。
        """
        bubble_size, text_size, time_size, chosen_width = self._calculateSizes()
        bubble_x = 0 if self.align == "right" else self.config.triangle_size
        self._bubble_rect = QRect(bubble_x, 0, bubble_size.width(), bubble_size.height())
        self.text_message.setGeometry(
            bubble_x + self.config.h_padding,
            self.config.v_padding,
            chosen_width,
            text_size.height()
        )
        # 时间标签对齐：右对齐时放左侧，左对齐时放右侧
        time_x = (bubble_x + self.config.h_padding) if self.align == "right" else (
                bubble_x + bubble_size.width() - self.config.h_padding - time_size.width())
        self.label_time.setGeometry(
            time_x,
            self.config.v_padding + text_size.height() + self.config.gap,
            time_size.width(),
            time_size.height()
        )
        new_size = QSize(bubble_size.width() + self.config.triangle_size, bubble_size.height())
        if self.size() != new_size:
            self.setFixedSize(new_size)
        self.update()

    def resizeEvent(self, event: Any) -> None:
        self.updateBubbleSize()
        super().resizeEvent(event)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.bubble_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self._bubble_rect, 10, 10)
        triangle_y = self._bubble_rect.top() + (self._bubble_rect.height() - self.config.triangle_height) // 2
        triangle = QPainterPath()
        if self.align == "right":
            triangle.moveTo(self._bubble_rect.right() + self.config.triangle_size,
                            triangle_y + self.config.triangle_height // 2)
            triangle.lineTo(self._bubble_rect.right(), triangle_y)
            triangle.lineTo(self._bubble_rect.right(), triangle_y + self.config.triangle_height)
        else:
            triangle.moveTo(self._bubble_rect.left() - self.config.triangle_size,
                            triangle_y + self.config.triangle_height // 2)
            triangle.lineTo(self._bubble_rect.left(), triangle_y)
            triangle.lineTo(self._bubble_rect.left(), triangle_y + self.config.triangle_height)
        triangle.closeSubpath()
        painter.drawPath(triangle)
        super().paintEvent(event)
