from PyQt5.QtCore import Qt, QSize, QRect
from PyQt5.QtGui import QPainter, QColor, QFont, QFontMetrics, QPixmap, QPainterPath
from PyQt5.QtWidgets import (
    QWidget, QTextEdit, QHBoxLayout, QLabel,
    QVBoxLayout, QSizePolicy
)
from dataclasses import dataclass
from typing import Optional
import asyncio

# 常量定义（聊天气泡颜色保持不变）
FONTS = {
    'MESSAGE': QFont("微软雅黑", 12),
    'TIME': QFont("微软雅黑", 8),
    'USERNAME': QFont("微软雅黑", 12, QFont.Bold)
}

COLORS = {
    'BUBBLE_USER': QColor("#aaeb7b"),   # 聊天气泡颜色不改变
    'BUBBLE_OTHER': QColor("#ffffff"),
    'ONLINE': QColor("#35fc8d"),         # 好友在线指示器使用 #2e8b57
    'UNREAD': QColor("#f04e4e")          # 未读徽章使用 #2e8b57
}

# 美化样式函数

def style_button(button):
    button.setStyleSheet("""
        QPushButton {
            background-color: #2e8b57;
            border: none;
            color: white;
            border-radius: 4px;
            padding: 6px 12px;
        }
        QPushButton:hover {
            background-color: #3ea97b;
        }
        QPushButton:pressed {
            background-color: #267f4e;
        }
        QPushButton:disabled {
            background-color: #cccccc;
        }
    """)

def style_line_edit(line_edit):
    # 保持边框和圆角，内边距由 setViewportMargins 或布局控制
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
    text_edit.setStyleSheet("""
        QTextEdit {
            border: 1px solid #dcdcdc;
            border-radius: 4px;
            padding: 1PX
        }
        QTextEdit:focus {
            border: 1px solid #2e8b57;
        }
        /* 应用滚动条美化样式 */
        QTextEdit QScrollBar:vertical {
            border: none;
            background: #f5f5f5;
            width: 8px;
            margin: 0px;
        }
        QTextEdit QScrollBar::handle:vertical {
            background: #bfbfbf;
            min-height: 30px;
            border-radius: 4px;
        }
        QTextEdit QScrollBar::handle:vertical:hover {
            background: #a8a8a8;
        }
        QTextEdit QScrollBar::add-line:vertical, QTextEdit QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QTextEdit QScrollBar::add-page:vertical, QTextEdit QScrollBar::sub-page:vertical {
            background: none;
        }
    """)

def style_list_widget(list_widget):
    list_widget.setStyleSheet("""
        QListWidget {
            border: none;
            outline: none;
            background-color: #f5f5f5;
        }
        QListWidget::item {
            border-bottom: 1px solid #dcdcdc;
            background-color: transparent;
        }
        QListWidget::item:selected {
            background-color: #2e8b57;
            color: white;
        }
        QListWidget::item:hover {
            background-color: #bfbfbf;  /* 同色系中明度较高的绿色 */
        }
        /* 应用滚动条美化样式 */
        QListWidget QScrollBar:vertical {
            border: none;
            background: #f5f5f5;
            width: 8px;
            margin: 0px;
        }
        QListWidget QScrollBar::handle:vertical {
            background: #bfbfbf;
            min-height: 30px;
            border-radius: 4px;
        }
        QListWidget QScrollBar::handle:vertical:hover {
            background: #a8a8a8;
        }
        QListWidget QScrollBar::add-line:vertical, QListWidget QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QListWidget QScrollBar::add-page:vertical, QListWidget QScrollBar::sub-page:vertical {
            background: none;
        }
    """)

def style_scrollbar(scroll_area):
    # 滑动条颜色保持不变
    scroll_area.setStyleSheet("""
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
    """)

# 自定义消息输入框
class MessageInput(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        style_text_edit(self)  # 应用 QTextEdit 的美化样式

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            if event.modifiers() & Qt.AltModifier:
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
        if self.online:
            pixmap = self._create_status_indicator()
            self.status_label.setPixmap(pixmap)
        else:
            self.status_label.clear()
        self.name_label.setText(self.username)
        if self.unread > 0:
            self.badge_label.setPixmap(self._create_badge())
        else:
            self.badge_label.clear()

    def _create_status_indicator(self):
        pixmap = QPixmap(10, 10)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(COLORS['ONLINE'])
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 10, 10)
        painter.end()
        return pixmap

    def _create_badge(self):
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

# 聊天记录显示区容器（聊天气泡颜色保持不变）
class ChatAreaWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(self.layout)

    def addBubble(self, bubble):
        wrapper = QWidget()
        hlayout = QHBoxLayout(wrapper)
        hlayout.setContentsMargins(0, 0, 0, 0)
        if bubble.align == "right":
            hlayout.addStretch()
            hlayout.addWidget(bubble)
        else:
            hlayout.addWidget(bubble)
            hlayout.addStretch()
        self.layout.addWidget(wrapper)

    def clearBubbles(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def resizeEvent(self, event):
        current_width = self.width()
        ChatBubbleWidget.config.chat_area_width = current_width
        self._update_all_bubbles()
        super().resizeEvent(event)

    def _update_all_bubbles(self):
        for i in range(self.layout.count()):
            wrapper = self.layout.itemAt(i).widget()
            if wrapper:
                for j in range(wrapper.layout().count()):
                    widget = wrapper.layout().itemAt(j).widget()
                    if isinstance(widget, ChatBubbleWidget):
                        widget.updateBubbleSize()

# 自定义绘制消息气泡控件（聊天气泡颜色保持不变）
@dataclass
class BubbleConfig:
    """气泡配置数据类"""
    chat_area_width: int = 650
    h_padding: int = 8
    v_padding: int = 5
    gap: int = 3
    triangle_size: int = 10
    triangle_height: int = 10

class ChatBubbleWidget(QWidget):
    config = BubbleConfig()

    def __init__(self, message: str, time_str: str, align: str = 'left',
                 is_current_user: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setup_ui(message, time_str, align, is_current_user)

    def setup_ui(self, message: str, time_str: str, align: str, is_current_user: bool):
        self.align = 'right' if is_current_user else align
        self.is_current_user = is_current_user
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

    def _insertZeroWidthSpace(self, text):
        lines = text.split('\n')
        processed_lines = []
        for line in lines:
            if ' ' not in line:
                processed_lines.append("\u200B".join(line))
            else:
                processed_lines.append(line)
        return '\n'.join(processed_lines)

    def _calculateSizes(self):
        available_width = int(self.config.chat_area_width * 0.6)
        fm_msg = QFontMetrics(FONTS['MESSAGE'])
        natural_text_width = fm_msg.width(self.message.replace('\u200B', ''))
        doc = self.text_message.document()
        lines = self.message.split('\n')
        total_height = fm_msg.height() * len(lines)

        if natural_text_width < available_width:
            self.text_message.setFixedWidth(natural_text_width + 2 * self.config.h_padding)
            chosen_text_width = natural_text_width
            text_size = QSize(chosen_text_width, total_height)
        else:
            self.text_message.setFixedWidth(available_width + 2 * self.config.h_padding)
            doc.setTextWidth(available_width)
            text_size = doc.size().toSize()
            chosen_text_width = available_width

        fm_time = QFontMetrics(FONTS['TIME'])
        time_width = fm_time.width(self.time_str)
        time_height = fm_time.height()
        time_size = QSize(time_width, time_height)

        bubble_content_width = max(chosen_text_width, time_width)
        bubble_width = int(bubble_content_width + 2 * self.config.h_padding)
        bubble_height = int(text_size.height() + time_height + 2 * self.config.v_padding + self.config.gap)

        return (
            QSize(bubble_width, bubble_height),
            text_size,
            time_size,
            chosen_text_width
        )

    def sizeHint(self):
        bubble_size, _, _, _ = self._calculateSizes()
        return QSize(bubble_size.width() + self.config.triangle_size, bubble_size.height())

    def updateBubbleSize(self):
        bubble_size, text_size, time_size, chosen_text_width = self._calculateSizes()
        bubble_x = 0 if self.align == "right" else self.config.triangle_size
        self._bubble_rect = QRect(bubble_x, 0, bubble_size.width(), bubble_size.height())

        self.text_message.setGeometry(
            bubble_x + self.config.h_padding,
            self.config.v_padding,
            chosen_text_width,
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
        self.updateBubbleSize()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.bubble_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self._bubble_rect, 10, 10)

        triangle_y = self._bubble_rect.top() + (self._bubble_rect.height() - self.config.triangle_height) // 2
        triangle = QPainterPath()
        if self.align == "right":
            triangle.moveTo(self._bubble_rect.right() + self.config.triangle_size, triangle_y + self.config.triangle_height // 2)
            triangle.lineTo(self._bubble_rect.right(), triangle_y)
            triangle.lineTo(self._bubble_rect.right(), triangle_y + self.config.triangle_height)
        else:
            triangle.moveTo(self._bubble_rect.left() - self.config.triangle_size, triangle_y + self.config.triangle_height // 2)
            triangle.lineTo(self._bubble_rect.left(), triangle_y)
            triangle.lineTo(self._bubble_rect.left(), triangle_y + self.config.triangle_height)
        triangle.closeSubpath()
        painter.drawPath(triangle)
        super().paintEvent(event)
