# Interface_Controls.py
from PyQt5 import sip
from PyQt5.QtCore import Qt, QSize, QRect, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QColor, QFont, QFontMetrics, QPixmap, QPainterPath
from PyQt5.QtWidgets import QWidget, QTextEdit, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy
from dataclasses import dataclass
from typing import Optional, Any, List
import asyncio

# ---------------- 主题 ----------------
LIGHT_THEME = {
    "BUBBLE_USER": QColor("#aaeb7b"),
    "BUBBLE_OTHER": QColor("#ffffff"),
    "ONLINE": QColor("#35fc8d"),
    "OFFLINE": QColor("#D3D3D3"),
    "UNREAD": QColor("#f04e4e"),
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
    def __init__(self) -> None:
        self.themes = {"light": LIGHT_THEME, "dark": DARK_THEME}
        self.current_mode = "light"
        self.current_theme = self.themes[self.current_mode]
        self.observers: List[Any] = []
    def set_mode(self, mode: str) -> None:
        if mode in self.themes:
            self.current_mode, self.current_theme = mode, self.themes[mode]
            self.notify_observers()
    def notify_observers(self) -> None:
        for obs in self.observers:
            if not sip.isdeleted(obs) and hasattr(obs, "update_theme"):
                obs.update_theme(self.current_theme)
    def register(self, obs: Any) -> None:
        if obs not in self.observers: self.observers.append(obs)
    def unregister(self, obs: Any) -> None:
        if obs in self.observers: self.observers.remove(obs)

theme_manager = ThemeManager()

# ---------------- 字体常量 ----------------
FONTS = {
    'MESSAGE': QFont("微软雅黑", 12),
    'TIME': QFont("微软雅黑", 8),
    'USERNAME': QFont("微软雅黑", 12, QFont.Bold),
    'ONLINE_SIZE': 10
}

# ---------------- 样式函数 ----------------
def circle_button_style(btn: Any) -> None:
    t = theme_manager.current_theme
    btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['button_background']};
                border-radius: 15px;
            }}
            QPushButton:hover {{
                background-color: {t['button_hover']};
            }}
        """)

def style_label(label: QLabel) -> None:
    t = theme_manager.current_theme
    label.setStyleSheet(f"QLabel {{ color: {t['font_color']}; background-color: transparent; }}")

def _apply_button_style(btn: Any, radius: Optional[str] = "") -> None:
    t = theme_manager.current_theme
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {t['button_background']};
            border: none;
            color: {t['button_text_color']};
            {radius}
            padding: 6px 12px;
        }}
        QPushButton:hover {{ background-color: {t['button_hover']}; }}
        QPushButton:pressed {{ background-color: {t['button_pressed']}; }}
        QPushButton:disabled {{ background-color: #cccccc; }}
    """)

def style_button(btn: Any) -> None: _apply_button_style(btn)
def style_rounded_button(btn: Any) -> None: _apply_button_style(btn, "border-radius: 4px;")
def style_line_edit(le: Any, focus: bool = True) -> None:
    t = theme_manager.current_theme
    style = f"""
        QLineEdit {{
            background-color: {t['widget_bg']};
            color: {t['font_color']};
            border: 1px solid {t['line_edit_border']};
            border-radius: 4px;
            padding: 2px 5px;
        }}
    """
    if focus:
        style += f"""
            QLineEdit:focus {{ border: 1px solid {t['line_edit_focus_border']}; }}
            QLineEdit::placeholder {{ color: {t['line_edit_border']}; }}
        """
    le.setStyleSheet(style)
    if focus:
        pal = le.palette()
        pal.setColor(pal.Text, QColor(t['font_color']))
        pal.setColor(pal.Foreground, QColor(t['font_color']))
        le.setPalette(pal)

def get_scrollbar_style() -> str:
    t = theme_manager.current_theme
    return f"""
    QScrollBar:vertical {{
        border: none;
        background: {t['list_background']};
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {t['line_edit_border']};
        min-height: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {t['line_edit_focus_border']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    """

def style_text_edit(te: QTextEdit) -> None:
    t = theme_manager.current_theme
    te.setStyleSheet(f"""
        QTextEdit {{
            background-color: {t['widget_bg']};
            color: {t['font_color']};
            border: 1px solid {t['text_edit_border']};
            padding: 1px;
        }}
        QTextEdit:focus {{ border: 1px solid {t['text_edit_focus_border']}; }}
    """)
    if te.verticalScrollBar():
        te.verticalScrollBar().setStyleSheet(get_scrollbar_style())

def style_list_widget(lw: Any) -> None:
    t = theme_manager.current_theme
    lw.setStyleSheet(f"""
        QListWidget {{
            background-color: {t['list_background']};
            color: {t['font_color']};
            border: none;
            outline: none;
        }}
        QListWidget::item {{
            border-bottom: 1px solid {t['line_edit_border']};
            background-color: transparent;
        }}
        QListWidget::item:selected {{
            background-color: {t['list_item_selected']};
            color: {t['button_text_color']};
        }}
        QListWidget::item:hover {{ background-color: {t['list_item_hover']}; }}
        QListWidget QScrollBar:vertical {{{get_scrollbar_style().replace("QScrollBar", "QListWidget QScrollBar")}}}
    """)

def style_scrollbar(sa: Any) -> None:
    sa.setStyleSheet(get_scrollbar_style())

def create_msg_box(parent: QWidget, title: str, text: str) -> 'QMessageBox':
    from PyQt5.QtWidgets import QMessageBox
    mb = QMessageBox(parent)
    mb.setWindowTitle(title)
    mb.setText(text)
    mb.setIcon(QMessageBox.Information)
    t = theme_manager.current_theme
    mb.setStyleSheet(f"QLabel {{ color: {t.get('TEXT_COLOR', '#ffffff')}; }}")
    btn = mb.addButton("确认", QMessageBox.AcceptRole)
    style_rounded_button(btn)
    for lbl in mb.findChildren(QLabel): style_label(lbl)
    return mb

# ---------------- 自定义控件 ----------------
class MessageInput(QTextEdit):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptRichText(False)
        style_text_edit(self)

    def keyPressEvent(self, e: Any) -> None:
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            if e.modifiers() & Qt.ShiftModifier:
                self.insertPlainText('\n')
                self._move_cursor_to_bottom()
            else:
                parent_obj = self.window()
                if parent_obj is not None and hasattr(parent_obj, "send_message"):
                    asyncio.create_task(parent_obj.send_message())
            e.accept()
            return
        super().keyPressEvent(e)

    def _move_cursor_to_bottom(self) -> None:
        cur = self.textCursor()
        cur.movePosition(cur.End)
        self.setTextCursor(cur)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

class FriendItemWidget(QWidget):
    def __init__(self, username: str, online: bool = False, unread: int = 0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.username, self.online, self.unread = username, online, unread
        self._init_ui(); self.update_display()

    def _init_ui(self) -> None:
        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(5,5,5,5)
        self.layout().setSpacing(5)
        self.status_label = QLabel(self); self.status_label.setFixedSize(15,15)
        self.name_label = QLabel(self); self.name_label.setFont(FONTS['USERNAME'])
        self.badge_label = QLabel(self); self.badge_label.setFixedSize(15,15)
        self.layout().addWidget(self.status_label)
        self.layout().addWidget(self.name_label)
        self.layout().addStretch()
        self.layout().addWidget(self.badge_label)

    def update_display(self) -> None:
        self.status_label.setPixmap(create_status_indicator(self.online) if self.online else QPixmap())
        self.name_label.setText(self.username)
        self.badge_label.setPixmap(create_badge(self.unread) if self.unread > 0 else QPixmap())

    def update_theme(self, theme: dict) -> None:
        if not sip.isdeleted(self.name_label): style_label(self.name_label)
        if not sip.isdeleted(self.badge_label): self.badge_label.setStyleSheet("background-color: transparent;")
        if not sip.isdeleted(self.status_label): self.status_label.setStyleSheet("background-color: transparent;")
        self.update_display()

def create_status_indicator(online: bool) -> QPixmap:
    size = FONTS['ONLINE_SIZE']
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(theme_manager.current_theme['ONLINE'] if online else theme_manager.current_theme['OFFLINE'])
    p.setPen(Qt.NoPen); p.drawEllipse(0,0,size,size); p.end()
    return pm

def create_badge(unread: int) -> QPixmap:
    size = 15; pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(theme_manager.current_theme['UNREAD']); p.setPen(Qt.NoPen)
    p.drawEllipse(0,0,size,size)
    p.setPen(QColor("white")); p.setFont(QFont("", 10, QFont.Bold))
    p.drawText(pm.rect(), Qt.AlignCenter, str(unread)); p.end(); return pm

class OnLine(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.username = ""; self.online = False; self.setAttribute(Qt.WA_StyledBackground, True)
        self._init_ui()

    def _init_ui(self) -> None:
        self.main_font, self.username_font = QFont("微软雅黑", 10), QFont("微软雅黑", 12)
        self.setLayout(QVBoxLayout()); self.layout().setContentsMargins(5,5,5,5); self.layout().setSpacing(2)
        self.username_label = QLabel(self); self.username_label.setFont(self.username_font)
        self.username_label.setAlignment(Qt.AlignLeft|Qt.AlignVCenter); self.layout().addWidget(self.username_label)
        hl = QHBoxLayout(); hl.setContentsMargins(0,0,0,0); hl.setSpacing(5)
        self.status_icon_label = QLabel(self); self.status_icon_label.setFixedSize(FONTS['ONLINE_SIZE'], FONTS['ONLINE_SIZE'])
        self.status_icon_label.setStyleSheet("border: none;")
        self.status_text_label = QLabel(self); self.status_text_label.setFont(self.main_font)
        self.status_text_label.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        hl.addWidget(self.status_icon_label); hl.addWidget(self.status_text_label); hl.addStretch()
        self.layout().addLayout(hl)

    def update_status(self, username: str, online: bool) -> None:
        self.username, self.online = username, online
        self.username_label.setText(username)
        self.status_icon_label.setPixmap(create_status_indicator(online))
        self.status_text_label.setText("在线" if online else "离线")

    def update_theme(self, theme: dict) -> None:
        style_label(self.username_label); style_label(self.status_text_label)
        self.setStyleSheet(f"background-color: {theme['widget_bg']};")

class ChatAreaWidget(QWidget):
    newBubblesAdded = pyqtSignal()
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setLayout(QVBoxLayout()); self.layout().setAlignment(Qt.AlignTop)
        self.layout().setContentsMargins(5,5,5,5); self.layout().setSpacing(5)
        self.bubble_containers: List[QWidget] = []
        self.newBubblesAdded.connect(self.update)

    def addBubble(self, bubble):
        wrap = QWidget(); hl = QHBoxLayout(wrap)
        hl.setContentsMargins(0,0,0,0)
        if getattr(bubble, "align", "left")=="right": hl.addStretch(), hl.addWidget(bubble)
        else: hl.addWidget(bubble), hl.addStretch()
        self.layout().addWidget(wrap); self.layout().update(); self.updateGeometry()

    def addBubbles(self, bubbles: List[QWidget]) -> None:
        ChatBubbleWidget.config.chat_area_width = self.width()  # 在添加前更新宽度
        for bubble in bubbles:
            cont = QWidget(self)
            hl = QHBoxLayout(cont)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(0)
            if hasattr(bubble, "align") and bubble.align == "right":
                hl.addStretch()
                hl.addWidget(bubble)
            else:
                hl.addWidget(bubble)
                hl.addStretch()
            self.bubble_containers.insert(0, cont)
            self.layout().insertWidget(0, cont)
        # 延迟更新尺寸，确保布局生效
        QTimer.singleShot(0, lambda: [b.updateBubbleSize() for b in bubbles])
        self.newBubblesAdded.emit()

    def resizeEvent(self, e: Any) -> None:
        ChatBubbleWidget.config.chat_area_width = self.width()
        for cont in self.bubble_containers:
            for i in range(cont.layout().count()):
                w = cont.layout().itemAt(i).widget()
                if isinstance(w, ChatBubbleWidget): w.updateBubbleSize()
        super().resizeEvent(e)

@dataclass
class BubbleConfig:
    chat_area_width: int = 650
    h_padding: int = 8
    v_padding: int = 5
    gap: int = 3
    triangle_size: int = 10
    triangle_height: int = 10

class ChatBubbleWidget(QWidget):
    config: BubbleConfig = BubbleConfig()
    def __init__(self, message: str, time_str: str, align: str = 'left', is_current_user: bool = False,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.align = "right" if is_current_user else align
        self.is_current_user = is_current_user
        self.message = self._insertZeroWidthSpace(message)
        self.time_str = time_str
        self.bubble_color = LIGHT_THEME["BUBBLE_USER"] if self.is_current_user else LIGHT_THEME["BUBBLE_OTHER"]
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._init_ui()

    def _init_ui(self) -> None:
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
        return '\n'.join(( "\u200B".join(line) if ' ' not in line else line ) for line in text.split('\n'))

    def _calculateSizes(self) -> tuple[QSize, QSize, QSize, int]:
        available = int(self.config.chat_area_width * 0.6)
        fm_msg = QFontMetrics(FONTS['MESSAGE'])
        natural = fm_msg.horizontalAdvance(self.message.replace('\u200B','')) if hasattr(fm_msg, 'horizontalAdvance') else fm_msg.width(self.message.replace('\u200B',''))
        lines = self.message.split('\n'); total = fm_msg.height()*len(lines)
        if natural < available:
            self.text_message.setFixedWidth(natural + 2*self.config.h_padding)
            chosen, text_size = natural, QSize(natural, total)
        else:
            self.text_message.setFixedWidth(available + 2*self.config.h_padding)
            self.text_message.document().setTextWidth(available)
            text_size = self.text_message.document().size().toSize()
            chosen = available
        fm_time = QFontMetrics(FONTS['TIME'])
        time_w = fm_time.horizontalAdvance(self.time_str) if hasattr(fm_time, 'horizontalAdvance') else fm_time.width(self.time_str)
        time_size = QSize(time_w, fm_time.height())
        content_width = max(chosen, time_w)
        bubble_w = content_width + 2*self.config.h_padding
        bubble_h = text_size.height() + fm_time.height() + 2*self.config.v_padding + self.config.gap
        return QSize(bubble_w, bubble_h), text_size, time_size, chosen

    def sizeHint(self) -> QSize:
        s, _, _, _ = self._calculateSizes()
        return QSize(s.width()+self.config.triangle_size, s.height())

    def updateBubbleSize(self) -> None:
        bubble, text, tsize, chosen = self._calculateSizes()
        bx = 0 if self.align=="right" else self.config.triangle_size
        self._bubble_rect = QRect(bx, 0, bubble.width(), bubble.height())
        self.text_message.setGeometry(bx+self.config.h_padding, self.config.v_padding, chosen, text.height())
        tx = bx+self.config.h_padding if self.align=="right" else bx+bubble.width()-self.config.h_padding-tsize.width()
        self.label_time.setGeometry(tx, self.config.v_padding+text.height()+self.config.gap, tsize.width(), tsize.height())
        ns = QSize(bubble.width()+self.config.triangle_size, bubble.height())
        if self.size()!=ns: self.setFixedSize(ns)
        self.update()

    def resizeEvent(self, e: Any) -> None:
        self.updateBubbleSize(); super().resizeEvent(e)

    def paintEvent(self, e: Any) -> None:
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(self.bubble_color); p.setPen(Qt.NoPen)
        p.drawRoundedRect(self._bubble_rect, 10, 10)
        ty = self._bubble_rect.top() + (self._bubble_rect.height()-self.config.triangle_height)//2
        path = QPainterPath()
        if self.align=="right":
            path.moveTo(self._bubble_rect.right()+self.config.triangle_size, ty+self.config.triangle_height//2)
            path.lineTo(self._bubble_rect.right(), ty); path.lineTo(self._bubble_rect.right(), ty+self.config.triangle_height)
        else:
            path.moveTo(self._bubble_rect.left()-self.config.triangle_size, ty+self.config.triangle_height//2)
            path.lineTo(self._bubble_rect.left(), ty); path.lineTo(self._bubble_rect.left(), ty+self.config.triangle_height)
        path.closeSubpath(); p.drawPath(path); super().paintEvent(e)
