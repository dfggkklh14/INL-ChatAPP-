# Interface_Controls.py
import math

from PyQt5.QtCore import Qt, QSize, QRect
from PyQt5.QtGui import QPainter, QColor, QFont, QFontMetrics, QPixmap, QPainterPath
from PyQt5.QtWidgets import QWidget, QTextEdit, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy
from dataclasses import dataclass
from typing import Optional
import asyncio

# 常量定义：字体与颜色
FONTS = {
    'MESSAGE': QFont("微软雅黑", 12),
    'TIME': QFont("微软雅黑", 8),
    'USERNAME': QFont("微软雅黑", 12, QFont.Bold),
    'ONLINE_SIZE': 10
}

COLORS = {
    'BUBBLE_USER': QColor("#aaeb7b"),
    'BUBBLE_OTHER': QColor("#ffffff"),
    'ONLINE': QColor("#35fc8d"),
    'OFFLINE': QColor("#D3D3D3"),
    'UNREAD': QColor("#f04e4e")
}

# 公共滚动条样式（后续在各控件中按选择器进行替换）
SCROLLBAR_STYLE = """
QScrollBar:vertical {
    border: none;
    background: #f5f5f5;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #bfbfbf;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #a8a8a8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
"""

# 内部函数：应用按钮样式
def _apply_button_style(button, border_radius: str = ""):
    button.setStyleSheet(f"""
        QPushButton {{
            background-color: #2e8b57;
            border: none;
            color: white;
            {border_radius}
            padding: 6px 12px;
        }}
        QPushButton:hover {{
            background-color: #3ea97b;
        }}
        QPushButton:pressed {{
            background-color: #267f4e;
        }}
        QPushButton:disabled {{
            background-color: #cccccc;
        }}
    """)

def style_button(button):
    """设置普通按钮样式"""
    _apply_button_style(button)

def style_rounded_button(button):
    """设置圆角按钮样式"""
    _apply_button_style(button, "border-radius: 4px;")

def style_line_edit(line_edit, border_radius: str = ""):
    """设置文本输入框样式，边框和圆角"""
    line_edit.setStyleSheet("""
        QLineEdit {
            border: 1px solid #dcdcdc;
            border-radius: 4px;
        }
        QLineEdit:focus {
            border: 1px solid #2e8b57;
        }
    """)

def style_text_edit(text_edit):
    """设置多行文本编辑框样式，并应用滚动条美化"""
    text_edit.setStyleSheet(f"""
        QTextEdit {{
            border: 1px solid #dcdcdc;
            padding: 1px;
        }}
        QTextEdit:focus {{
            border: 1px solid #2e8b57;
        }}
        QTextEdit QScrollBar:vertical {{
            {SCROLLBAR_STYLE.replace("QScrollBar", "QTextEdit QScrollBar")}
        }}
    """)

def style_list_widget(list_widget):
    """设置列表控件样式，并应用滚动条美化"""
    list_widget.setStyleSheet(f"""
        QListWidget {{
            border: none;
            background-color: #ffffff;
            outline: none;
        }}
        QListWidget::item {{
            border-bottom: 1px solid #dcdcdc;
            background-color: transparent;
        }}
        QListWidget::item:selected {{
            background-color: #2e8b57;
            color: white;
        }}
        QListWidget::item:hover {{
            background-color: #bfbfbf;
        }}
        QListWidget QScrollBar:vertical {{
            {SCROLLBAR_STYLE.replace("QScrollBar", "QListWidget QScrollBar")}
        }}
    """)

def style_scrollbar(scroll_area):
    """设置独立滑动条样式"""
    scroll_area.setStyleSheet(SCROLLBAR_STYLE)

# 自定义消息输入框：支持回车发送（回车键）和 Shift+回车换行
class MessageInput(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def keyPressEvent(self, event):
        """按键事件：回车键发送消息，Alt+回车换行"""
        if event.key() == Qt.Key_Return:
            if event.modifiers() & Qt.ShiftModifier:
                self.insertPlainText('\n')
            else:
                if self.parent:
                    asyncio.create_task(self.parent.send_message())
            event.accept()
        else:
            super().keyPressEvent(event)

# 自定义好友列表项显示控件
class FriendItemWidget(QWidget):
    def __init__(self, username, online=False, unread=0, parent=None):
        super().__init__(parent)
        self.username = username
        self.online = online
        self.unread = unread
        self._init_ui()
        self.update_display()

    def _init_ui(self):
        """初始化好友项的UI布局"""
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

    def update_display(self):
        """更新在线状态及未读消息显示"""
        if self.online:
            self.status_label.setPixmap(create_status_indicator(self.online))
        else:
            self.status_label.clear()
        self.name_label.setText(self.username)
        if self.unread > 0:
            self.badge_label.setPixmap(create_badge(self))
        else:
            self.badge_label.clear()


def create_status_indicator(online: bool) -> QPixmap:
    """绘制在线/离线状态圆点"""
    size = FONTS['ONLINE_SIZE']
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(COLORS['ONLINE'] if online else COLORS['OFFLINE'])
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.end()
    return pixmap

def create_badge(self):
    """绘制未读消息徽章"""
    size = 15
    badge = QPixmap(size, size)
    badge.fill(Qt.transparent)
    painter = QPainter(badge)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(COLORS['UNREAD'])
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.setPen(QColor("white"))
    painter.setFont(QFont("", 10, QFont.Bold))
    painter.drawText(badge.rect(), Qt.AlignCenter, str(self.unread))
    painter.end()
    return badge

# 在线状态显示控件
class OnLine(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.username = ""
        self.online = False
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._init_ui()

    def _init_ui(self):
        """初始化在线状态控件布局"""
        self.main_font = QFont("微软雅黑", 10)
        self.username_font = QFont("微软雅黑", 12)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(2)

        self.username_label = QLabel(self)
        self.username_label.setFont(self.username_font)
        self.username_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.username_label.setStyleSheet("border: none;")
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
        self.status_text_label.setStyleSheet("border: none;")

        self.status_layout.addWidget(self.status_icon_label)
        self.status_layout.addWidget(self.status_text_label)
        self.status_layout.addStretch()

        self.layout.addLayout(self.status_layout)

    def update_status(self, username: str, online: bool):
        """更新在线状态显示"""
        self.username = username
        self.online = online
        self.username_label.setText(username)
        self.status_icon_label.setPixmap(create_status_indicator(online))
        self.status_text_label.setText("在线" if online else "离线")

# 聊天记录显示区容器
class ChatAreaWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("border: none; background-color: #ffffff;")
        self._init_ui()
        self.bubble_containers = []  # 保存包装后的气泡容器

    def _init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(5)
        self.setLayout(self.layout)

    def addBubble(self, bubble, index=None):
        """
        添加或插入气泡控件
        将气泡包装在一个容器中，通过水平布局控制左右对齐：
          - 如果 bubble.align 为 "right"，则在气泡左侧增加伸展项；
          - 如果为 "left"，则在气泡右侧增加伸展项。
        :param bubble: ChatBubbleWidget 对象
        :param index: 可选的插入位置（默认追加到末尾）
        """
        container = QWidget(self)
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        # 根据气泡的 align 属性设置左右对齐
        if bubble.align == "right":
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

    def clearBubbles(self):
        """
        清空所有聊天记录气泡
        """
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.bubble_containers.clear()

    def resizeEvent(self, event):
        """
        窗口大小变化时，更新所有气泡控件的尺寸
        """
        current_width = self.width()
        ChatBubbleWidget.config.chat_area_width = current_width
        self._update_all_bubbles()
        super().resizeEvent(event)

    def _update_all_bubbles(self):
        """
        更新聊天区域中所有气泡控件的尺寸
        """
        for container in self.bubble_containers:
            for j in range(container.layout().count()):
                widget = container.layout().itemAt(j).widget()
                if isinstance(widget, ChatBubbleWidget):
                    widget.updateBubbleSize()


# 气泡配置数据类
@dataclass
class BubbleConfig:
    chat_area_width: int = 650
    h_padding: int = 8
    v_padding: int = 5
    gap: int = 3
    triangle_size: int = 10
    triangle_height: int = 10


# 自定义绘制消息气泡控件
class ChatBubbleWidget(QWidget):
    config = BubbleConfig()

    def __init__(self, message: str, time_str: str, align: str = 'left',
                 is_current_user: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setup_ui(message, time_str, align, is_current_user)

    def setup_ui(self, message: str, time_str: str, align: str, is_current_user: bool):
        """初始化气泡控件，并设置文本与时间"""
        # 保证本人消息始终靠右，其它消息按传入的 align 参数处理
        self.align = 'right' if is_current_user else align
        self.is_current_user = is_current_user
        # 插入零宽空格以保证长单词自动换行
        self.message = self._insertZeroWidthSpace(message)
        self.time_str = time_str
        self.bubble_color = COLORS['BUBBLE_USER'] if self.is_current_user else COLORS['BUBBLE_OTHER']
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.text_message = QTextEdit(self)
        self.text_message.setFont(FONTS['MESSAGE'])
        self.text_message.setStyleSheet("background: transparent; border: none;")
        self.text_message.setReadOnly(True)
        self.text_message.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_message.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_message.setPlainText(self.message)

        self.label_time = QLabel(self)
        self.label_time.setFont(FONTS['TIME'])
        self.label_time.setStyleSheet("background: transparent;")
        self.label_time.setTextInteractionFlags(Qt.NoTextInteraction)
        self.label_time.setText(self.time_str)

        self._bubble_rect = QRect()

    def _insertZeroWidthSpace(self, text: str) -> str:
        """在无空格的长字符串中插入零宽空格，便于自动换行"""
        lines = text.split('\n')
        processed = [("\u200B".join(line) if ' ' not in line else line) for line in lines]
        return '\n'.join(processed)

    def _calculateSizes(self):
        """根据内容计算气泡及内部控件的尺寸"""
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
        time_width = fm_time.width(self.time_str)
        time_size = QSize(time_width, fm_time.height())

        bubble_content_width = max(chosen_width, time_width)
        bubble_width = bubble_content_width + 2 * self.config.h_padding
        bubble_height = text_size.height() + fm_time.height() + 2 * self.config.v_padding + self.config.gap

        return QSize(bubble_width, bubble_height), text_size, time_size, chosen_width

    def sizeHint(self):
        """返回气泡控件的建议尺寸"""
        bubble_size, _, _, _ = self._calculateSizes()
        return QSize(bubble_size.width() + self.config.triangle_size, bubble_size.height())

    def updateBubbleSize(self):
        """根据当前尺寸重新设置内部控件位置及气泡尺寸"""
        bubble_size, text_size, time_size, chosen_width = self._calculateSizes()
        bubble_x = 0 if self.align == "right" else self.config.triangle_size
        self._bubble_rect = QRect(bubble_x, 0, bubble_size.width(), bubble_size.height())

        self.text_message.setGeometry(
            bubble_x + self.config.h_padding,
            self.config.v_padding,
            chosen_width,
            text_size.height()
        )

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

    def resizeEvent(self, event):
        """控件尺寸变化时更新气泡尺寸"""
        self.updateBubbleSize()
        super().resizeEvent(event)

    def paintEvent(self, event):
        """自定义绘制气泡背景及三角指示"""
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
