# Interface_Controls.py
import os
import asyncio
from dataclasses import dataclass
from msilib.schema import SelfReg
from typing import Optional, Any, List, Tuple

from PIL import Image
import imageio  # 修改导入，去掉 ffmpeg 插件依赖

from PyQt5 import sip
from PyQt5.QtCore import Qt, QSize, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QFontMetrics, QPixmap, QImage, QIcon, QPainterPath
from PyQt5.QtWidgets import (
    QWidget, QTextEdit, QHBoxLayout, QLabel, QVBoxLayout, QDialog,
    QGridLayout, QPushButton, QApplication, QScrollArea, QMessageBox, QMenu, QFileDialog, QSizePolicy, QProgressBar
)

# ---------------- 主题设置 ----------------
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
    **LIGHT_THEME,
    "ONLINE": QColor("#66ff66"),
    "OFFLINE": QColor("#888888"),
    "UNREAD": QColor("#ff6666"),
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
    'FILE_NAME':QFont("微软雅黑", 10),
    'FILE_SIZE':QFont("微软雅黑", 8),
    'USERNAME': QFont("微软雅黑", 12, QFont.Bold),
    'ONLINE_SIZE': 10
}

# ---------------- 样式工具函数 ----------------
def style_progress_bar(pb: QProgressBar) -> None:
    t = theme_manager.current_theme
    pb.setStyleSheet(f"""
        QProgressBar {{
            border: 1px solid {t['line_edit_border']};
            border-radius: 5px;
            background-color: {t['widget_bg']};
            text-align: center;
            color: {t['font_color']};
        }}
        QProgressBar::chunk {{
            background-color: {t['button_background']};
            border-radius: 3px;
        }}
    """)

def style_label(label: QLabel) -> None:
    t = theme_manager.current_theme
    label.setStyleSheet(f"color: {t['font_color']}; background-color: transparent;")

def _apply_button_style(btn: Any, extra: str = "") -> None:
    t = theme_manager.current_theme
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {t['button_background']};
            border: none;
            color: {t['button_text_color']};
            padding: 0px;
            {extra}
        }}
        QPushButton:hover {{ background-color: {t['button_hover']}; }}
        QPushButton:pressed {{ background-color: {t['button_pressed']}; }}
        QPushButton:disabled {{ background-color: #cccccc; }}
    """)

def style_button(btn: Any) -> None:
    _apply_button_style(btn)

def style_rounded_button(btn: Any) -> None:
    _apply_button_style(btn, "border-radius: 4px;")

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
        QListWidget QScrollBar:vertical {{
            {get_scrollbar_style().replace("QScrollBar", "QListWidget QScrollBar")}
        }}
    """)

def style_scrollbar(widget: Any) -> None:
    widget.setStyleSheet(get_scrollbar_style())

def create_msg_box(parent: QWidget, title: str, text: str) -> QMessageBox:
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

# ---------------- 实用函数 ----------------
def create_status_indicator(online: bool) -> QPixmap:
    size = FONTS['ONLINE_SIZE']
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    color = theme_manager.current_theme['ONLINE'] if online else theme_manager.current_theme['OFFLINE']
    p.setBrush(color)
    p.setPen(Qt.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.end()
    return pm

def create_badge(unread: int) -> QPixmap:
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

def generate_thumbnail(file_path: str, file_type: str, output_dir: str = "thumbnails") -> Optional[str]:
    """生成图片或视频的缩略图并返回缩略图路径"""
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(file_path)
    thumbnail_path = os.path.join(output_dir, f"thumb_{base_name}")

    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return None

    try:
        if file_type == 'image':
            with Image.open(file_path) as img:
                img.thumbnail((500, 500))
                ext = os.path.splitext(file_path)[1].lower()
                format_map = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.gif': 'GIF', '.bmp': 'BMP'}
                fmt = format_map.get(ext, 'JPEG')
                thumbnail_path += '.jpg' if fmt == 'JPEG' else ext
                img.convert('RGB').save(thumbnail_path, fmt) if fmt == 'JPEG' else img.save(thumbnail_path, fmt)
        elif file_type == 'video':
            thumbnail_path += '.jpg'
            # 使用 imageio 读取视频第一帧
            reader = imageio.get_reader(file_path)
            frame = reader.get_data(0)  # 获取第一帧
            img = Image.fromarray(frame)
            img.thumbnail((300, 300), Image.Resampling.LANCZOS)  # 调整大小，保持纵横比
            img.save(thumbnail_path, "JPEG")
            reader.close()  # 关闭 reader
        return thumbnail_path if os.path.exists(thumbnail_path) else None
    except Exception as e:
        print(f"生成缩略图失败: {file_path}, 错误: {e}")
        return None

# ---------------- 自定义控件 ----------------
class EmoticonPopup(QDialog):
    """
    表情选择弹窗，非模态显示，点击表情后发出信号，
    弹窗失去焦点时自动关闭。
    """
    emoticonClicked = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup)
        self.setWindowTitle("选择表情")
        self.setFocusPolicy(Qt.StrongFocus)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.verticalScrollBar().setStyleSheet(get_scrollbar_style())
        scroll_area.setFixedSize(370, 250)

        content_widget = QWidget()
        grid_layout = QGridLayout(content_widget)
        grid_layout.setContentsMargins(5, 5, 5, 5)
        grid_layout.setSpacing(5)

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
        btn_size = 40
        max_cols = scroll_area.width() // (btn_size + 5)
        row = col = 0
        font = QFont(FONTS['MESSAGE'])
        font.setHintingPreference(QFont.PreferNoHinting)
        font.setStyleStrategy(QFont.PreferAntialias)
        for emo in emoticons:
            btn = QPushButton(emo, content_widget)
            btn.setFixedSize(btn_size, btn_size)
            btn.setFont(font)
            btn.setStyleSheet("font-size: 25px; border: none; background: transparent;")
            btn.clicked.connect(lambda checked, e=emo: self.emoticonClicked.emit(e))
            grid_layout.addWidget(btn, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        content_widget.setLayout(grid_layout)
        scroll_area.setWidget(content_widget)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)
        self.setLayout(main_layout)
        self.setFixedSize(scroll_area.size())

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.close()

class CustomTextEdit(QTextEdit):
    sendMessage = pyqtSignal()
    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            event.accept()
            self.sendMessage.emit()
        else:
            super().keyPressEvent(event)

class MessageInput(QWidget):
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
        self.plus_button.clicked.connect(self.show_plus_menu)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.emoticon_button, 0, 0, Qt.AlignHCenter)
        layout.addWidget(self.plus_button, 1, 0, Qt.AlignHCenter)
        layout.addWidget(self.text_edit, 0, 1, 2, 1)
        layout.setRowMinimumHeight(0, 35)
        layout.setRowMinimumHeight(1, 35)
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        self.setLayout(layout)

        self.popup: Optional[EmoticonPopup] = None

    def on_send_message(self) -> None:
        parent_obj = self.window()
        if parent_obj and hasattr(parent_obj, "send_message"):
            asyncio.create_task(parent_obj.send_message())

    def show_emoticon_popup(self) -> None:
        self.popup = EmoticonPopup(self)
        self.popup.emoticonClicked.connect(self.insert_emoticon)
        self.popup.adjustSize()
        btn_pos = self.emoticon_button.mapToGlobal(self.emoticon_button.rect().topLeft())
        self.popup.move(btn_pos.x(), btn_pos.y() - self.popup.height())
        self.popup.show()

    def insert_emoticon(self, emo: str) -> None:
        cursor = self.text_edit.textCursor()
        cursor.insertText(emo)
        self.text_edit.setTextCursor(cursor)

    def show_plus_menu(self):
        menu = QMenu(self)
        file_filters = {
            'file': ("文件", "所有文件 (*.*)"),
            'image': ("图片", "图片文件 (*.jpg *.jpeg *.png *.gif *.bmp)"),
            'video': ("视频", "视频文件 (*.mp4 *.avi *.mkv *.mov *.wmv)")
        }
        for f_type, (label, filt) in file_filters.items():
            menu.addAction(label, lambda ft=f_type: self.send_file(ft))
        menu.exec_(self.plus_button.mapToGlobal(self.plus_button.rect().bottomLeft()))

    def send_file(self, file_type: str):
        filters = {
            'file': "所有文件 (*.*)",
            'image': "图片文件 (*.jpg *.jpeg *.png *.gif *.bmp)",
            'video': "视频文件 (*.mp4 *.avi *.mkv *.mov *.wmv)"
        }
        file_path, _ = QFileDialog.getOpenFileName(self, f"选择{file_type}", "", filters.get(file_type, ""))
        if file_path:
            chat_window = self.window()
            if chat_window and hasattr(chat_window, 'send_media'):
                asyncio.create_task(chat_window.send_media(file_path, file_type))
            else:
                QMessageBox.critical(self, "错误", "无法发送文件：未找到聊天窗口")

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
            style_label(self.name_label)
        if not sip.isdeleted(self.badge_label):
            self.badge_label.setStyleSheet("background-color: transparent;")
        if not sip.isdeleted(self.status_label):
            self.status_label.setStyleSheet("background-color: transparent;")
        self.update_display()

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
        # 使用当前宽度或默认值初始化聊天区域宽度
        ChatBubbleWidget.config.chat_area_width = self.width() or 650

    def _wrap_bubble(self, bubble: QWidget) -> QWidget:
        """
        将气泡控件包装在一个水平容器中，根据气泡的对齐属性自动添加伸缩空间。
        """
        container = QWidget(self)
        hl = QHBoxLayout(container)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        if getattr(bubble, "align", "left") == "right":
            hl.addStretch()
            hl.addWidget(bubble)
        else:
            hl.addWidget(bubble)
            hl.addStretch()
        return container

    def addBubble(self, bubble: QWidget) -> None:
        container = self._wrap_bubble(bubble)
        self.layout().addWidget(container)
        bubble.updateBubbleSize()

    def addBubbles(self, bubbles: List[QWidget]) -> None:
        for bubble in bubbles:
            container = self._wrap_bubble(bubble)
            self.bubble_containers.insert(0, container)
            self.layout().insertWidget(0, container)
            bubble.updateBubbleSize()
        self.newBubblesAdded.emit()

    def resizeEvent(self, event: Any) -> None:
        ChatBubbleWidget.config.chat_area_width = self.width()  # 动态更新宽度
        for container in self.bubble_containers:
            for i in range(container.layout().count()):
                widget = container.layout().itemAt(i).widget()
                if isinstance(widget, ChatBubbleWidget):
                    widget.updateBubbleSize()
        super().resizeEvent(event)

@dataclass
class BubbleConfig:
    chat_area_width: int = 650
    h_padding: int = 5
    v_padding: int = 5
    time_padding: int = 8
    gap: int = 5
    triangle_size: int = 10
    triangle_height: int = 10
    file_h_padding: int = 5      # 文件消息独立的左右边距
    file_v_padding: int = 5      # 文件消息独立的上下边距

class ChatBubbleWidget(QWidget):
    config: BubbleConfig = BubbleConfig()

    def __init__(self, message: str, time_str: str, align: str = 'left', is_current_user: bool = False,
                 message_type: str = 'text', file_id: Optional[str] = None, original_file_name: Optional[str] = None,
                 thumbnail_path: Optional[str] = None, file_size: Optional[str] = None, duration: Optional[str] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.align = "right" if is_current_user else align
        self.is_current_user = is_current_user
        self.message = self._insertZeroWidthSpace(message)
        self.time_str = time_str
        self.message_type = message_type
        self.file_id = file_id
        self.original_file_name = original_file_name
        self.thumbnail_path = thumbnail_path
        self.file_size = file_size
        self.duration = duration
        self.bubble_color = LIGHT_THEME["BUBBLE_USER"] if self.is_current_user else LIGHT_THEME["BUBBLE_OTHER"]
        self.progress_bar = None  # 新增进度条属性
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._init_ui()

    def _init_ui(self) -> None:
        self.font_message = QFont(FONTS['MESSAGE'])
        self.font_message.setHintingPreference(QFont.PreferNoHinting)
        self.font_message.setStyleStrategy(QFont.PreferAntialias)
        self.font_time = QFont(FONTS['TIME'])
        self.font_time.setHintingPreference(QFont.PreferNoHinting)
        self.font_time.setStyleStrategy(QFont.PreferAntialias)

        if self.message_type == 'text':
            self.add_text()
        elif self.message_type == 'image':
            self.add_image()
        elif self.message_type == 'video':
            self.add_video()
        elif self.message_type == 'file':
            self.sdd_file()
        else:
            self.content_widget = QTextEdit(self)
            self.content_widget.setFont(self.font_message)
            self.content_widget.setStyleSheet("background: transparent; border: none;")
            self.content_widget.setReadOnly(True)
            self.content_widget.setPlainText(self.message)

        self.label_time = QLabel(self)
        self.label_time.setFont(self.font_time)
        self.label_time.setStyleSheet("background: transparent; border: none;")
        self.label_time.setTextInteractionFlags(Qt.NoTextInteraction)
        self.label_time.setText(self.time_str)

        self._bubble_rect = QRect()
        self._setup_progress_bar()  # 新增进度条初始化

    def _setup_progress_bar(self) -> None:
        """初始化进度条，初始隐藏"""
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(10)
        style_progress_bar(self.progress_bar)
        self.progress_bar.hide()

    def update_progress(self, value: float) -> None:
        """更新进度条值"""
        if self.progress_bar:
            self.progress_bar.setValue(int(value))
            self.progress_bar.show()
            self.updateBubbleSize()

    def complete_progress(self) -> None:
        """完成时隐藏并销毁进度条"""
        if self.progress_bar:
            self.progress_bar.hide()
            self.progress_bar.deleteLater()
            self.progress_bar = None
            self.updateBubbleSize()

    def add_text(self):
        self.content_widget = QLabel(self)
        self.content_widget.setFont(self.font_message)
        self.content_widget.setStyleSheet("background: transparent; border: none;")
        self.content_widget.setText(self.message)
        self.content_widget.setWordWrap(True)
        # 根据对齐方向设置文本对齐
        self.content_widget.setAlignment(
            Qt.AlignRight | Qt.AlignTop if self.align == "left" else Qt.AlignLeft | Qt.AlignTop)

    def add_image(self):
        self.content_widget = QLabel(self)
        self.content_widget.setStyleSheet("background: transparent; border: none;")
        if self.thumbnail_path and os.path.exists(self.thumbnail_path):
            image = QImage(self.thumbnail_path)
            scaled_image = image.scaledToHeight(300, Qt.SmoothTransformation)
            pixmap = QPixmap.fromImage(scaled_image)
            rounded = self._roundedPixmap(pixmap, radius=8)
            self.content_widget.setPixmap(rounded)
        else:
            self.content_widget.setText("图片加载失败")
        self.content_widget.setAlignment(Qt.AlignCenter)

    def add_video(self):
        self.content_widget = QWidget(self)
        self.content_widget.setStyleSheet("background: transparent; border: none;")
        video_layout = QHBoxLayout(self.content_widget)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(5)
        self.thumbnail_label = QLabel(self)
        self.thumbnail_label.setStyleSheet("background: transparent; border: none;")
        if self.thumbnail_path and os.path.exists(self.thumbnail_path):
            pixmap = QPixmap(self.thumbnail_path).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            rounded_pixmap = self._roundedPixmap(pixmap, radius=8)  # 添加圆角处理
            self.thumbnail_label.setPixmap(rounded_pixmap if not rounded_pixmap.isNull() else QPixmap())
        if self.thumbnail_label.pixmap() is None or self.thumbnail_label.pixmap().isNull():
            self.thumbnail_label.setText(f"{self.original_file_name or '视频'} (缩略图不可用)")
        self.play_button = QPushButton("播放", self)
        self.play_button.setFixedSize(50, 30)
        style_button(self.play_button)
        self.play_button.clicked.connect(self.play_video)
        video_layout.addWidget(self.thumbnail_label)
        video_layout.addWidget(self.play_button)

    def sdd_file(self):
        self.content_widget = QWidget(self)
        self.content_widget.setStyleSheet("background: transparent; border: none;")
        # 使用文件消息独立的边距
        file_layout = QHBoxLayout(self.content_widget)
        file_layout.setContentsMargins(self.config.file_h_padding,
                                       self.config.file_v_padding,
                                       self.config.file_h_padding,
                                       self.config.file_v_padding)
        file_layout.setSpacing(5)

        # 文件图标
        self.file_icon = QLabel(self)
        self.file_icon.setStyleSheet("background: transparent; border: none;")
        self.file_icon.setPixmap(QIcon("icon.ico").pixmap(40, 40))
        self.file_icon.setFixedSize(40, 40)

        # 文件信息容器
        self.file_info_widget = QWidget(self)
        file_info_layout = QVBoxLayout(self.file_info_widget)
        file_info_layout.setContentsMargins(0, 0, 0, 0)
        file_info_layout.setSpacing(2)

        # 文件名：使用 FONTS['TIME'] 字体，单行显示，超长部分省略，并在悬浮时显示完整内容
        self.file_name_label = QLabel(self)
        font = QFont(FONTS['FILE_NAME'])
        font.setBold(True)  # 设置字体为粗体
        self.file_name_label.setFont(font)  # 应用加粗后的字体
        self.file_name_label.setStyleSheet("background: transparent; border: none;")
        self.file_name_label.setWordWrap(False)
        self.file_name_label.setText(self.original_file_name or "未知文件")

        # 文件大小
        self.file_size_label = QLabel(self)
        self.file_size_label.setFont(self.font_time)
        font = QFont(FONTS['FILE_SIZE'])
        self.file_size_label.setFont(font)
        self.file_size_label.setStyleSheet("background: transparent; border: none;")
        self.file_size_label.setText(self.file_size or "未知大小")

        file_info_layout.addWidget(self.file_name_label)
        file_info_layout.addWidget(self.file_size_label)

        # 根据发送者调整布局：自己发的图标在左，对方发的图标在右
        if self.is_current_user:
            file_layout.addWidget(self.file_icon)
            file_layout.addWidget(self.file_info_widget)
            file_layout.setAlignment(self.file_icon, Qt.AlignLeft | Qt.AlignVCenter)
            file_layout.setAlignment(self.file_info_widget, Qt.AlignLeft | Qt.AlignVCenter)
        else:
            file_layout.addWidget(self.file_info_widget)
            file_layout.addWidget(self.file_icon)
            file_layout.setAlignment(self.file_info_widget, Qt.AlignRight | Qt.AlignVCenter)
            file_layout.setAlignment(self.file_icon, Qt.AlignRight | Qt.AlignVCenter)

    def _roundedPixmap(self, pixmap: QPixmap, radius: int) -> QPixmap:
        rounded = QPixmap(pixmap.size())
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        return rounded

    def _insertZeroWidthSpace(self, text: str) -> str:
        # 分割行并移除末尾空行
        lines = text.rstrip('\n').split('\n')
        return '\n'.join(("\u200B".join(line) if ' ' not in line else line) for line in lines)

    def _calculateSizes(self) -> Tuple[QSize, QSize, QSize, int]:
        """
        计算气泡、内容和时间的尺寸，进度条（如果显示）位于时间戳上方。
        返回: (bubble_size, content_size, time_size, content_width)
            - bubble_size: 整个气泡的尺寸（宽高）
            - content_size: 内容区域的尺寸（宽高）
            - time_size: 时间文本的尺寸（宽高）
            - content_width: 内容区域的实际宽度（用于定位）
        """
        # 最大可用宽度（聊天区域的60%）
        available_width = int(self.config.chat_area_width * 0.6)

        # 计算时间文本尺寸
        fm_time = QFontMetrics(self.font_time)
        time_width = fm_time.horizontalAdvance(self.time_str) + 4  # 加点余量
        time_height = fm_time.height()
        time_size = QSize(time_width, time_height)
        min_content_width = time_width + self.config.time_padding  # 内容最小宽度基于时间

        # 根据消息类型计算内容尺寸
        if self.message_type == 'text':
            # 文本消息
            fm_msg = QFontMetrics(self.font_message)
            natural_width = fm_msg.boundingRect(0, 0, 0, 0, Qt.TextSingleLine, self.message).width()
            content_width = min(max(natural_width, min_content_width), available_width)
            self.content_widget.setFixedWidth(content_width)
            content_height = fm_msg.boundingRect(
                0, 0, content_width, 0, Qt.TextWordWrap, self.message.rstrip('\n')
            ).height() or fm_msg.height()  # 空文本时至少一行高
            content_size = QSize(content_width, content_height)

        elif self.message_type in ('image', 'video'):
            # 图片或视频消息
            if self.thumbnail_path and os.path.exists(self.thumbnail_path):
                pixmap = QPixmap(self.thumbnail_path)
                content_width = min(pixmap.scaledToHeight(300, Qt.SmoothTransformation).width(), 300)
                content_height = 300
            else:
                fm_msg = QFontMetrics(FONTS['MESSAGE'])
                base_text = self.original_file_name or "视频缩略图不可用"
                content_width = min(fm_msg.horizontalAdvance(base_text), available_width)
                content_height = 300
            if self.message_type == 'video':
                content_width += 50  # 播放按钮宽度
            content_size = QSize(content_width, content_height)
            self.content_widget.adjustSize()

        elif self.message_type == 'file':
            # 文件消息
            max_width = available_width
            fm_file = QFontMetrics(self.file_name_label.font())
            full_name = self.original_file_name or "未知文件"
            elided_name = fm_file.elidedText(full_name, Qt.ElideRight, max_width)
            self.file_name_label.setText(elided_name)
            self.file_name_label.setToolTip(full_name)
            self.file_name_label.setMaximumWidth(max_width)
            self.file_size_label.setText(self.file_size or "未知大小")
            self.file_name_label.adjustSize()
            self.file_size_label.adjustSize()
            self.file_info_widget.adjustSize()
            self.content_widget.adjustSize()
            content_size = self.content_widget.sizeHint()
            content_width = content_size.width()

        else:
            # 默认情况
            content_size = QSize(0, 0)
            content_width = min_content_width

        # 计算气泡整体尺寸（内容 -> 进度条 -> 时间）
        if self.message_type in ('file', 'image', 'video'):
            padding_h = self.config.file_h_padding
            padding_v = self.config.file_v_padding
            bubble_width = content_width + 2 * padding_h
            bubble_height = content_size.height() + padding_v  # 内容高度加上顶部内边距
            if self.progress_bar and self.progress_bar.isVisible():
                bubble_height += self.progress_bar.height() + self.config.gap  # 进度条高度
            bubble_height += time_size.height() + self.config.gap  # 时间戳高度
        else:
            padding_h = self.config.h_padding
            padding_v = self.config.v_padding
            bubble_width = max(content_width, time_width) + 2 * padding_h
            bubble_height = content_size.height() + padding_v + time_size.height() + self.config.gap

        bubble_size = QSize(bubble_width, bubble_height)
        return bubble_size, content_size, time_size, content_width

    def sizeHint(self) -> QSize:
        bubble_size, _, _, _ = self._calculateSizes()
        return QSize(bubble_size.width() + self.config.triangle_size, bubble_size.height())

    def updateBubbleSize(self) -> None:
        """根据计算的尺寸更新气泡布局，进度条在时间戳上方"""
        bubble_size, content_size, time_size, content_width = self._calculateSizes()
        bx = 0 if self.align == "right" else self.config.triangle_size
        self._bubble_rect = QRect(bx, 0, bubble_size.width(), bubble_size.height())

        # 设置内边距
        h_pad = self.config.file_h_padding if self.message_type == 'file' else self.config.h_padding
        v_pad = self.config.file_v_padding if self.message_type == 'file' else self.config.v_padding

        # 计算各部分的Y坐标（内容 -> 进度条 -> 时间）
        content_y = v_pad
        if self.progress_bar and self.progress_bar.isVisible():
            progress_y = content_y + content_size.height() + self.config.gap
            time_y = progress_y + self.progress_bar.height() + self.config.gap
        else:
            progress_y = content_y  # 无进度条时占位
            time_y = content_y + content_size.height() + self.config.gap

        # 计算X坐标（根据对齐方向）
        bubble_right = bx + bubble_size.width()
        if self.align == "right":
            content_x = bx + h_pad
            time_x = content_x
            progress_x = content_x
        else:
            content_x = bubble_right - content_width - h_pad
            time_x = bubble_right - time_size.width() - h_pad
            progress_x = content_x

        # 限制X坐标范围
        content_x = max(bx + h_pad, min(content_x, bubble_right - content_width - h_pad))
        time_x = max(bx + h_pad, min(time_x, bubble_right - time_size.width() - h_pad))

        # 更新控件位置和大小
        self.content_widget.move(content_x, content_y)
        self.content_widget.setFixedSize(content_width, content_size.height())
        self.label_time.move(time_x, time_y)
        self.label_time.setFixedSize(time_size.width(), time_size.height())
        if self.progress_bar and self.progress_bar.isVisible():
            self.progress_bar.move(progress_x, progress_y)
            self.progress_bar.setFixedWidth(content_width)

        # 设置气泡整体大小
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
        painter.drawPath(path)
        super().paintEvent(event)

    def play_video(self) -> None:
        if self.file_id:
            asyncio.create_task(self.download_and_play_video(self.file_id))

    async def download_and_play_video(self, file_id: str) -> None:
        save_path = f"temp_video_{file_id}.mp4"

        # 设置下载进度回调
        async def progress_callback(type_, progress, filename):
            if type_ == "download":
                self.update_progress(progress)
                QApplication.processEvents()

        self.window().client.set_progress_callback(progress_callback)

        result = await self.window().client.download_media(file_id, save_path)
        self.window().client.set_progress_callback(None)

        if result.get("status") == "success":
            self.complete_progress()
            os.startfile(save_path)
        else:
            self.complete_progress()
            QMessageBox.critical(self, "错误", "视频下载失败")
