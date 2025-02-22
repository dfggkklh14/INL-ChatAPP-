# Interface_Controls.py
from PyQt5 import sip
from PyQt5.QtCore import Qt, QSize, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QFontMetrics, QPixmap, QPainterPath
from PyQt5.QtWidgets import (
    QWidget, QTextEdit, QHBoxLayout, QLabel, QVBoxLayout, QSizePolicy, QDialog,
    QGridLayout, QPushButton, QApplication, QScrollArea, QFrame
)
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
    """管理主题切换及观察者通知"""
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
        if obs not in self.observers:
            self.observers.append(obs)

    def unregister(self, obs: Any) -> None:
        if obs in self.observers:
            self.observers.remove(obs)

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
    """设置圆形按钮的样式"""
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
    """设置标签样式"""
    t = theme_manager.current_theme
    label.setStyleSheet(f"QLabel {{ color: {t['font_color']}; background-color: transparent; }}")

def _apply_button_style(btn: Any, radius: Optional[str] = "") -> None:
    """内部按钮样式设置函数"""
    t = theme_manager.current_theme
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {t['button_background']};
            border: none;
            color: {t['button_text_color']};
            padding: 0px;
            {radius}
        }}
        QPushButton:hover {{ background-color: {t['button_hover']}; }}
        QPushButton:pressed {{ background-color: {t['button_pressed']}; }}
        QPushButton:disabled {{ background-color: #cccccc; }}
    """)

def style_button(btn: Any) -> None:
    _apply_button_style(btn)

def style_rounded_button(btn: Any) -> None:
    _apply_button_style(btn, "border-radius: 4px;")

def style_line_edit(le: Any, focus: bool = True) -> None:
    """设置单行编辑框样式"""
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
    """返回滚动条样式字符串"""
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
    """设置多行文本编辑框样式"""
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
    """设置列表控件样式"""
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
        QListWidget QScrollBar:vertical {{
            {get_scrollbar_style().replace("QScrollBar", "QListWidget QScrollBar")}
        }}
    """)

def style_scrollbar(sa: Any) -> None:
    """设置滚动条样式"""
    sa.setStyleSheet(get_scrollbar_style())

def create_msg_box(parent: QWidget, title: str, text: str) -> 'QMessageBox':
    """创建消息对话框"""
    from PyQt5.QtWidgets import QMessageBox
    mb = QMessageBox(parent)
    mb.setWindowTitle(title)
    mb.setText(text)
    mb.setIcon(QMessageBox.Information)
    t = theme_manager.current_theme
    mb.setStyleSheet(f"QLabel {{ color: {t.get('TEXT_COLOR', '#ffffff')}; }}")
    btn = mb.addButton("确认", QMessageBox.AcceptRole)
    style_rounded_button(btn)
    for lbl in mb.findChildren(QLabel):
        style_label(lbl)
    return mb

# ---------------- 自定义控件 ----------------
class EmoticonPopup(QDialog):
    """
    表情选择弹窗，采用非模态显示，点击表情后发出信号，
    当弹窗失去焦点时自动关闭。
    """
    emoticonClicked = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup)
        self.setWindowTitle("选择表情")
        self.setFocusPolicy(Qt.StrongFocus)

        # 配置参数
        scroll_area_width = 370
        scroll_area_height = 250
        btn_size = 40
        emo_font_size = "25px"
        spacing = 5

        # 创建 QScrollArea，固定尺寸，多余表情通过垂直滚动查看（无横向滚动条）
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.verticalScrollBar().setStyleSheet(get_scrollbar_style())
        scroll_area.setFixedSize(scroll_area_width, scroll_area_height)

        # 内容部件及其网格布局，边距和间距较小
        content_widget = QWidget()
        grid_layout = QGridLayout(content_widget)
        grid_layout.setContentsMargins(spacing, spacing, spacing, spacing)
        grid_layout.setSpacing(spacing)

        # 定义大量表情
        emoticons = [
            "😀", "😁", "😂", "🤣", "😃", "😄", "😅", "😆",
            "😉", "😊", "😋", "😎", "😍", "😘", "🥰", "😗",
            "😙", "😚", "🙂", "🤗", "🤩", "🤔", "🤨", "😐",
            "😑", "😶", "🙄", "😏", "😣", "😥", "😮", "🤐",
            "😯", "😪", "😫", "🥱", "😴", "😌", "😛", "😜",
            "😝", "🤤", "😒", "😓", "😔", "😕", "🙃", "🤑",
            "😲", "☹️", "🙁", "😖", "😞", "😟", "😤", "😢",
            "😭", "😦", "😧", "😨", "😩", "🤯", "😬", "😰",
            "😱", "🥵", "🥶", "😳", "🤪", "😵", "😡", "😠",
            "🤬", "😷", "🤒", "🤕", "🤢", "🤮", "🤧", "😇",
            "💖", "💙", "💚", "💛", "💜", "🧡", "❤️", "🤍",
            "🤎", "🖤", "💔", "❣️", "💌", "💋", "👑", "🎉",
            "🎂", "🎁", "🌹", "🌸", "🌺", "🌻", "🌼", "🌷",
            "🌴", "🌵", "🍀", "🍎", "🍊", "🍓", "🍒", "🍑",
            "🍍", "🍉", "🍇", "🍓", "🍍", "🍔", "🍕", "🍣",
            "🍿", "🍩", "🍪", "🍦", "🥧", "🍫", "🍬", "🍭",
            "🥚", "🍳", "🍞", "🍩", "🥯", "🥨", "🥒", "🥬",
            "🍅", "🥕", "🥔", "🍠", "🍗", "🍖", "🍤", "🍖",
            "🍛", "🍜", "🍣", "🍲", "🥗", "🍙", "🍚", "🍘"
        ]
        # 计算每行可容纳的表情个数
        max_cols = scroll_area_width // (btn_size + spacing)
        row, col = 0, 0
        # 设置抗锯齿字体
        font = QFont(FONTS['MESSAGE'])
        font.setHintingPreference(QFont.PreferNoHinting)
        font.setStyleStrategy(QFont.PreferAntialias)
        for emo in emoticons:
            btn = QPushButton(emo, content_widget)
            btn.setFixedSize(btn_size, btn_size)
            btn.setFont(font)
            btn.setStyleSheet(f"font-size: {emo_font_size}; border: none; background: transparent;")
            # 使用默认参数捕获当前 emo，发出信号
            btn.clicked.connect(lambda checked, e=emo: self.emoticonClicked.emit(e))
            grid_layout.addWidget(btn, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        content_widget.setLayout(grid_layout)
        scroll_area.setWidget(content_widget)

        # 主布局设置
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)
        self.setFixedSize(scroll_area.size())

    def focusOutEvent(self, event) -> None:
        """当弹窗失去焦点时自动关闭"""
        super().focusOutEvent(event)
        self.close()

# 重写 QTextEdit，处理回车发送消息（不带 Shift 时发射信号）
class CustomTextEdit(QTextEdit):
    sendMessage = pyqtSignal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            event.accept()
            self.sendMessage.emit()
        else:
            super().keyPressEvent(event)

class MessageInput(QWidget):
    """
    消息输入控件，包含自定义文本输入框与表情按钮以及新增的“+”按钮，
    支持回车发送与弹出表情选择器（表情弹窗在失去焦点时关闭）。
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(70)

        self.text_edit = CustomTextEdit(self)
        self.text_edit.setFont(FONTS['MESSAGE'])
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlaceholderText("请输入消息")
        style_text_edit(self.text_edit)
        self.text_edit.sendMessage.connect(self.on_send_message)

        self.emoticon_button = QPushButton("😊", self)
        self.emoticon_button.clicked.connect(self.show_emoticon_popup)
        self.emoticon_button.setFixedSize(30, 35)
        style_button(self.emoticon_button)

        self.plus_button = QPushButton("+", self)
        self.plus_button.setFixedSize(30, 35)
        style_button(self.plus_button)

        # 使用网格布局：左侧为两个按钮（各占一行），右侧为文本输入框
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 将按钮添加到网格，确保在格子内水平居中
        layout.addWidget(self.emoticon_button, 0, 0, Qt.AlignHCenter)  # 第 0 行，第 0 列，水平居中
        layout.addWidget(self.plus_button, 1, 0, Qt.AlignHCenter)      # 第 1 行，第 0 列，水平居中
        layout.addWidget(self.text_edit, 0, 1, 2, 1)                   # 第 0-1 行，第 1 列

        # 设置行高，确保每行 35 像素
        layout.setRowMinimumHeight(0, 35)
        layout.setRowMinimumHeight(1, 35)

        # 设置列伸缩性
        layout.setColumnStretch(0, 0)  # 第 0 列固定宽度
        layout.setColumnStretch(1, 1)  # 第 1 列伸缩
        self.setLayout(layout)

        self.popup: Optional[EmoticonPopup] = None

    def on_send_message(self) -> None:
        """调用顶层窗口的发送方法"""
        parent_obj = self.window()
        if parent_obj is not None and hasattr(parent_obj, "send_message"):
            asyncio.create_task(parent_obj.send_message())

    def show_emoticon_popup(self) -> None:
        """显示表情弹窗，定位在输入框与按钮上方"""
        print("Showing emoticon popup")  # 调试日志
        self.popup = EmoticonPopup(self)
        self.popup.emoticonClicked.connect(self.insert_emoticon)
        self.popup.adjustSize()
        button_global_top_left = self.emoticon_button.mapToGlobal(self.emoticon_button.rect().topLeft())
        self.popup.move(button_global_top_left.x(), button_global_top_left.y() - self.popup.height())
        self.popup.show()

    def insert_emoticon(self, emo: str) -> None:
        """在文本框当前光标处插入选中的表情"""
        cursor = self.text_edit.textCursor()
        cursor.insertText(emo)
        self.text_edit.setTextCursor(cursor)


class FriendItemWidget(QWidget):
    """
    好友项控件，显示用户状态、名称及未读消息徽标。
    """
    def __init__(self, username: str, online: bool = False, unread: int = 0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.username, self.online, self.unread = username, online, unread
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
        # 不设置固定宽度，宽度将在 update_display 中动态计算

        self.badge_label = QLabel(self)
        self.badge_label.setFixedSize(15, 15)

        layout.addWidget(self.status_label)
        layout.addWidget(self.name_label)
        layout.addStretch()  # 保持弹性空间将 badge_label 推向右侧
        layout.addWidget(self.badge_label)
        self.setLayout(layout)

    def update_display(self) -> None:
        # 更新状态图标
        self.status_label.setPixmap(create_status_indicator(self.online) if self.online else QPixmap())

        # 设置用户名并调整宽度
        self.name_label.setText(self.username)
        font_metrics = QFontMetrics(self.name_label.font())  # 获取字体度量
        text_width = font_metrics.horizontalAdvance(self.username)  # 计算文本宽度
        self.name_label.setFixedWidth(text_width)  # 设置为文本实际宽度

        # 更新未读消息徽标
        self.badge_label.setPixmap(create_badge(self.unread) if self.unread > 0 else QPixmap())

    def update_theme(self, theme: dict) -> None:
        if not sip.isdeleted(self.name_label):
            style_label(self.name_label)
        if not sip.isdeleted(self.badge_label):
            self.badge_label.setStyleSheet("background-color: transparent;")
        if not sip.isdeleted(self.status_label):
            self.status_label.setStyleSheet("background-color: transparent;")
        self.update_display()

def create_status_indicator(online: bool) -> QPixmap:
    """生成状态指示图标"""
    size = FONTS['ONLINE_SIZE']
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(theme_manager.current_theme['ONLINE'] if online else theme_manager.current_theme['OFFLINE'])
    p.setPen(Qt.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.end()
    return pm

def create_badge(unread: int) -> QPixmap:
    """生成未读消息徽标"""
    size = 15
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(theme_manager.current_theme['UNREAD'])
    p.setPen(Qt.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.setPen(QColor("white"))
    p.setFont(QFont("", 10, QFont.Bold))
    p.drawText(pm.rect(), Qt.AlignCenter, str(unread))
    p.end()
    return pm

class OnLine(QWidget):
    """
    在线状态控件，显示用户名及在线状态文字和图标。
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.username = ""
        self.online = False
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._init_ui()

    def _init_ui(self) -> None:
        self.main_font = QFont("微软雅黑", 10)
        self.username_font = QFont("微软雅黑", 12)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        self.username_label = QLabel(self)
        self.username_label.setFont(self.username_font)
        self.username_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self.username_label)
        hl = QHBoxLayout()
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(5)
        self.status_icon_label = QLabel(self)
        self.status_icon_label.setFixedSize(FONTS['ONLINE_SIZE'], FONTS['ONLINE_SIZE'])
        self.status_icon_label.setStyleSheet("border: none;")
        self.status_text_label = QLabel(self)
        self.status_text_label.setFont(self.main_font)
        self.status_text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hl.addWidget(self.status_icon_label)
        hl.addWidget(self.status_text_label)
        hl.addStretch()
        layout.addLayout(hl)
        self.setLayout(layout)

    def update_status(self, username: str, online: bool) -> None:
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
    聊天区域控件，用于容纳聊天气泡。
    """
    newBubblesAdded = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.bubble_containers: List[QWidget] = []
        self.setLayout(layout)
        self.newBubblesAdded.connect(self.update)

    def addBubble(self, bubble: QWidget) -> None:
        wrap = QWidget()
        hl = QHBoxLayout(wrap)
        hl.setContentsMargins(0, 0, 0, 0)
        if getattr(bubble, "align", "left") == "right":
            hl.addStretch()
            hl.addWidget(bubble)
        else:
            hl.addWidget(bubble)
            hl.addStretch()
        self.layout().addWidget(wrap)
        self.layout().update()
        self.updateGeometry()

    def addBubbles(self, bubbles: List[QWidget]) -> None:
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
        self.newBubblesAdded.emit()

    def resizeEvent(self, e: Any) -> None:
        ChatBubbleWidget.config.chat_area_width = self.width()
        for cont in self.bubble_containers:
            for i in range(cont.layout().count()):
                w = cont.layout().itemAt(i).widget()
                if isinstance(w, ChatBubbleWidget):
                    w.updateBubbleSize()
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
    """
    聊天气泡控件，根据消息内容与时间自动计算尺寸，并绘制气泡背景和对话三角形。
    """
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
        # 配置消息和时间的字体（开启抗锯齿）
        font_message = QFont(FONTS['MESSAGE'])
        font_message.setHintingPreference(QFont.PreferNoHinting)
        font_message.setStyleStrategy(QFont.PreferAntialias)

        font_time = QFont(FONTS['TIME'])
        font_time.setHintingPreference(QFont.PreferNoHinting)
        font_time.setStyleStrategy(QFont.PreferAntialias)

        # 消息文本编辑框设置（只读、无边框）
        self.text_message = QTextEdit(self)
        self.text_message.setFont(font_message)
        self.text_message.setStyleSheet("background: transparent; border: none;")
        self.text_message.setReadOnly(True)
        self.text_message.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_message.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_message.setPlainText(self.message)

        # 时间标签设置
        self.label_time = QLabel(self)
        self.label_time.setFont(font_time)
        self.label_time.setStyleSheet("background: transparent; border: none;")
        self.label_time.setTextInteractionFlags(Qt.NoTextInteraction)
        self.label_time.setText(self.time_str)

        self._bubble_rect = QRect()

    def _insertZeroWidthSpace(self, text: str) -> str:
        """在每行中插入零宽空格（防止长单词导致换行问题）"""
        return '\n'.join(("\u200B".join(line) if ' ' not in line else line) for line in text.split('\n'))

    def _calculateSizes(self) -> tuple[QSize, QSize, QSize, int]:
        available = int(self.config.chat_area_width * 0.6)
        fm_msg = QFontMetrics(FONTS['MESSAGE'])
        natural = fm_msg.horizontalAdvance(self.message.replace('\u200B', ''))
        lines = self.message.split('\n')
        total = fm_msg.height() * len(lines)
        if natural < available:
            self.text_message.setFixedWidth(natural + 2 * self.config.h_padding)
            chosen, text_size = natural, QSize(natural, total)
        else:
            self.text_message.setFixedWidth(available + 2 * self.config.h_padding)
            self.text_message.document().setTextWidth(available)
            text_size = self.text_message.document().size().toSize()
            chosen = available
        fm_time = QFontMetrics(FONTS['TIME'])
        time_w = fm_time.horizontalAdvance(self.time_str) + 4
        time_size = QSize(time_w, fm_time.height())
        content_width = max(chosen, time_w)
        bubble_w = content_width + 2 * self.config.h_padding
        bubble_h = text_size.height() + fm_time.height() + 2 * self.config.v_padding + self.config.gap
        return QSize(bubble_w, bubble_h), text_size, time_size, chosen

    def sizeHint(self) -> QSize:
        s, _, tsize, _ = self._calculateSizes()
        # 确保宽度包含三角形和时间戳
        return QSize(max(s.width() + self.config.triangle_size,
                         tsize.width() + self.config.triangle_size + self.config.h_padding * 2),s.height())

    def updateBubbleSize(self) -> None:
        bubble, text, tsize, chosen = self._calculateSizes()
        bx = 0 if self.align == "right" else self.config.triangle_size
        self._bubble_rect = QRect(bx, 0, bubble.width(), bubble.height())
        self.text_message.setGeometry(bx + self.config.h_padding, self.config.v_padding, chosen, text.height())
        if self.align == "right":
            tx = bx + self.config.h_padding
        else:
            tx = min(bx + bubble.width() - self.config.h_padding - tsize.width(),
                     self.width() - tsize.width() - self.config.h_padding)  # 限制不超过控件宽度
        self.label_time.setGeometry(tx, self.config.v_padding + text.height() + self.config.gap,
                                    tsize.width(), tsize.height())
        ns = QSize(bubble.width() + self.config.triangle_size, bubble.height())
        if self.size() != ns:
            self.setFixedSize(ns)
        self.update()

    def resizeEvent(self, e: Any) -> None:
        self.updateBubbleSize()
        super().resizeEvent(e)

    def paintEvent(self, e: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(self.bubble_color)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self._bubble_rect, 10, 10)
        ty = self._bubble_rect.top() + (self._bubble_rect.height() - self.config.triangle_height) // 2
        path = QPainterPath()
        if self.align == "right":
            path.moveTo(self._bubble_rect.right() + self.config.triangle_size, ty + self.config.triangle_height // 2)
            path.lineTo(self._bubble_rect.right(), ty)
            path.lineTo(self._bubble_rect.right(), ty + self.config.triangle_height)
        else:
            path.moveTo(self._bubble_rect.left() - self.config.triangle_size, ty + self.config.triangle_height // 2)
            path.lineTo(self._bubble_rect.left(), ty)
            path.lineTo(self._bubble_rect.left(), ty + self.config.triangle_height)
        path.closeSubpath()
        p.drawPath(path)
        super().paintEvent(e)
