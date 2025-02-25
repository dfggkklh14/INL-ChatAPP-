# Interface_Controls.py
import os
import asyncio
from dataclasses import dataclass
from typing import Optional, Any, List, Tuple

from PIL import Image
import imageio

from PyQt5 import sip
from PyQt5.QtCore import Qt, QSize, QRect, pyqtSignal, QPoint
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

# ---------------- 样式管理 ----------------
class StyleGenerator:
    _BASE_STYLES = {
        "menu": "QMenu {{ background-color: {widget_bg}; color: {font_color}; border: 1px solid {line_edit_border}; padding: 2px; }}"
                "QMenu::item {{ background-color: transparent; padding: 5px 20px 5px 10px; color: {font_color}; }}"
                "QMenu::item:selected {{ background-color: {list_item_selected}; color: {button_text_color}; }}"
                "QMenu::item:hover {{ background-color: {list_item_hover}; color: {font_color}; }}",
        "button": ("QPushButton {{ background-color: {button_background}; border: none; color: {button_text_color}; padding: 0px; {extra} }}"
                   "QPushButton:hover {{ background-color: {button_hover}; }}"
                   "QPushButton:pressed {{ background-color: {button_pressed}; }}"
                   "QPushButton:disabled {{ background-color: #cccccc; }}"),
        "label": "color: {font_color}; background-color: transparent;",
        "progress_bar": "QProgressBar {{ border: 1px solid {line_edit_border}; border-radius: 5px; background-color: {widget_bg}; text-align: center; color: {font_color}; }}"
                        "QProgressBar::chunk {{ background-color: {button_background}; border-radius: 3px; }}",
        "text_edit": "QTextEdit {{ background-color: {widget_bg}; color: {font_color}; border: 1px solid {text_edit_border}; padding: 1px; }}"
                     "QTextEdit:focus {{ border: 1px solid {text_edit_focus_border}; }}",
        "scrollbar": "QScrollBar:vertical {{ border: none; background: {list_background}; width: 8px; margin: 0; }}"
                     "QScrollBar::handle:vertical {{ background: {line_edit_border}; min-height: 30px; border-radius: 4px; }}"
                     "QScrollBar::handle:vertical:hover {{ background: {line_edit_focus_border}; }}"
                     "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
                     "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}",
        "list_widget":
                     "QListWidget {{ background-color: {list_background}; color: {font_color}; border: none; outline: none; }}"
                     "QListWidget::item {{ border-bottom: 1px solid {line_edit_border}; background-color: transparent; }}"
                     "QListWidget::item:selected {{ background-color: {list_item_selected}; color: {button_text_color}; }}"
                     "QListWidget::item:hover {{ background-color: {list_item_hover}; }}",
        "line_edit": {
            "base": "QLineEdit {{ background-color: {widget_bg}; color: {font_color}; border: 1px solid {line_edit_border}; "
                    "border-radius: 4px; padding: 2px 5px; }}",
            "focus": "QLineEdit:focus {{ border: 1px solid {line_edit_focus_border}; }} "
                     "QLineEdit::placeholder {{ color: {line_edit_border}; }}"
        }
    }

    @staticmethod
    def apply_style(widget, style_type: str, extra: str = "") -> None:
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
def get_scrollbar_style() -> str:
    t = theme_manager.current_theme
    return f"""
    QScrollBar:vertical {{border: none; background: {t['list_background']}; width: 8px; margin: 0;}}
    QScrollBar::handle:vertical {{background: {t['line_edit_border']}; min-height: 30px; border-radius: 4px;}}
    QScrollBar::handle:vertical:hover {{ background: {t['line_edit_focus_border']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    """

def style_text_edit(te: QTextEdit) -> None:
    StyleGenerator.apply_style(te, "text_edit")
    te.verticalScrollBar().setStyleSheet(get_scrollbar_style())

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

def generate_thumbnail(file_path: str, file_type: str, output_dir: str = "Chat_DATA/Chat_thumbnails") -> Optional[str]:
    """生成图片或视频的缩略图并返回缩略图路径"""
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.basename(file_path)
    thumbnail_path = os.path.join(output_dir, f"thumb_{base_name}")

    if not os.path.exists(file_path):
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
        self.setAcceptDrops(True)  # 启用拖放支持

        self.text_edit = CustomTextEdit(self)
        self.text_edit.setFont(FONTS['MESSAGE'])
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlaceholderText("请输入消息")
        style_text_edit(self.text_edit)
        self.text_edit.sendMessage.connect(self.on_send_message)

        self.emoticon_button = QPushButton("😊", self)
        self.emoticon_button.clicked.connect(self.show_emoticon_popup)
        self.emoticon_button.setFixedSize(30, 35)
        StyleGenerator.apply_style(self.emoticon_button, "button")

        self.plus_button = QPushButton("+", self)
        self.plus_button.setFixedSize(30, 35)
        StyleGenerator.apply_style(self.plus_button, "button")
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
        StyleGenerator.apply_style(self, "menu")
        menu.exec_(self.plus_button.mapToGlobal(self.plus_button.rect().bottomLeft()))

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if file_paths:
            chat_window = self.window()
            if hasattr(chat_window, 'send_multiple_media'):
                asyncio.create_task(chat_window.send_multiple_media(file_paths))

    def send_file(self, file_type: str):
        filters = {
            'file': "所有文件 (*.*)",
            'image': "图片文件 (*.jpg *.jpeg *.png *.gif *.bmp)",
            'video': "视频文件 (*.mp4 *.avi *.mkv *.mov *.wmv)"
        }
        file_paths, _ = QFileDialog.getOpenFileNames(self, f"选择{file_type}", "", filters.get(file_type, ""))
        if not file_paths:
            return

        chat_window = self.window()
        if chat_window and hasattr(chat_window, 'send_multiple_media'):
            asyncio.create_task(chat_window.send_multiple_media(file_paths))
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
            StyleGenerator.apply_style(self.name_label, "label")
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
        StyleGenerator.apply_style(self.username_label, "label")
        StyleGenerator.apply_style(self.status_text_label, "label")
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
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if file_paths:
            chat_window = self.window()
            if hasattr(chat_window, 'send_multiple_media'):
                asyncio.create_task(chat_window.send_multiple_media(file_paths))

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
        self.bubble_containers.append(container)  # 记录到 bubble_containers
        bubble.updateBubbleSize()
        QApplication.processEvents()
        self.update()

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
    h_padding: int = 3
    v_padding: int = 3
    triangle_size: int = 10
    triangle_height: int = 10
    file_h_padding: int = 3      # 文件消息独立的左右边距
    file_v_padding: int = 3      # 文件消息独立的上下边距

class ChatBubbleWidget(QWidget):
    config: BubbleConfig = BubbleConfig()
    DOWNLOAD_LABELS = {
        "file": "文件",
        "image": "图片",
        "video": "视频"
    }
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
        self._setup_progress_bar()
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def _setup_progress_bar(self) -> None:
        """初始化进度条，初始隐藏"""
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(10)
        StyleGenerator.apply_style(self.progress_bar, "progress_bar")
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
            max_width = 270
            min_width = 150
            scaled_image = image.scaledToWidth(max_width, Qt.SmoothTransformation)
            content_width = max(min_width, min(max_width, image.width()))
            if content_width < max_width:
                scaled_image = image.scaledToWidth(content_width, Qt.SmoothTransformation)
            pixmap = QPixmap.fromImage(scaled_image)
            rounded = self._roundedPixmap(pixmap, radius=8)
            self.content_widget.setPixmap(rounded)
            self.thumbnail_size = QSize(scaled_image.width(), scaled_image.height())
        else:
            self.content_widget.setText("图片加载失败")
            self.thumbnail_size = QSize(0, 0)
        self.content_widget.setAlignment(Qt.AlignCenter)
        self.content_widget.setCursor(Qt.PointingHandCursor)
        self.content_widget.setMouseTracking(True)  # 启用鼠标跟踪
        self.content_widget.mousePressEvent = self.on_image_clicked  # 直接绑定事件

    def on_image_clicked(self, event):
        print(f"Image clicked: file_id={self.file_id}, name={self.original_file_name}")
        if self.file_id and self.message_type == 'image':
            chat_window = self.window()
            if hasattr(chat_window, 'show_image_viewer'):
                asyncio.create_task(chat_window.show_image_viewer(self.file_id, self.original_file_name))

    def add_video(self):
        self.content_widget = QWidget(self)
        self.content_widget.setStyleSheet("background: transparent; border: none;")
        video_layout = QVBoxLayout(self.content_widget)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(0)

        # 缩略图
        self.thumbnail_label = QLabel(self.content_widget)  # 父控件设为 content_widget
        self.thumbnail_label.setStyleSheet("background: transparent; border: none;")
        if self.thumbnail_path and os.path.exists(self.thumbnail_path):
            pixmap = QPixmap(self.thumbnail_path)
            max_width = 270
            min_width = 150
            scaled_pixmap = pixmap.scaledToWidth(max_width, Qt.SmoothTransformation)
            content_width = max(min_width, min(max_width, pixmap.width()))
            if content_width < max_width:
                scaled_pixmap = pixmap.scaledToWidth(content_width, Qt.SmoothTransformation)
            rounded_pixmap = self._roundedPixmap(scaled_pixmap, radius=8)
            self.thumbnail_label.setPixmap(rounded_pixmap if not rounded_pixmap.isNull() else QPixmap())
            self.thumbnail_size = QSize(scaled_pixmap.width(), scaled_pixmap.height())
        else:
            self.thumbnail_label.setText(f"{self.original_file_name or '视频'} (缩略图不可用)")
            self.thumbnail_size = QSize(0, 0)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)

        # 播放按钮
        self.play_button = QPushButton(self.content_widget)  # 父控件设为 content_widget
        icon_path = "play_icon_shallow.ico"
        if os.path.exists(icon_path):
            self.play_button.setIcon(QIcon(icon_path))
        else:
            self.play_button.setText("▶")
        self.play_button.setIconSize(QSize(50, 50))
        self.play_button.setFixedSize(self.thumbnail_size.width(), self.thumbnail_size.height())
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                qproperty-alignment: 'AlignCenter';
            }
            QPushButton:hover {
                icon: url('play_icon_deep.ico');
            }
        """)
        self.play_button.setCursor(Qt.PointingHandCursor)
        self.play_button.clicked.connect(self.play_video)

        # 将缩略图添加到布局
        video_layout.addWidget(self.thumbnail_label)
        # 不将按钮添加到布局，而是手动设置位置并叠放
        self.play_button.move(0, 0)  # 与缩略图左上角对齐
        self.play_button.raise_()  # 确保按钮在缩略图上方

        video_layout.addStretch()

    def sdd_file(self):
        self.content_widget = QWidget(self)
        self.content_widget.setStyleSheet("background: transparent; border: none;")
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
        self.file_icon.setCursor(Qt.PointingHandCursor)  # 设置手形光标
        self.file_icon.mousePressEvent = self.on_file_clicked  # 添加点击事件

        # 文件信息容器
        self.file_info_widget = QWidget(self)
        file_info_layout = QVBoxLayout(self.file_info_widget)
        file_info_layout.setContentsMargins(0, 0, 0, 0)
        file_info_layout.setSpacing(2)

        # 文件名
        self.file_name_label = QLabel(self)
        font = QFont(FONTS['FILE_NAME'])
        font.setBold(True)
        self.file_name_label.setFont(font)
        self.file_name_label.setStyleSheet("""
            background: transparent; 
            border: none;
        """)
        self.file_name_label.setWordWrap(False)
        self.file_name_label.setText(self.original_file_name or "未知文件")
        self.file_name_label.setCursor(Qt.PointingHandCursor)  # 设置手形光标
        self.file_name_label.mousePressEvent = self.on_file_clicked  # 添加点击事件

        # 文件大小
        self.file_size_label = QLabel(self)
        font = QFont(FONTS['FILE_SIZE'])
        self.file_size_label.setFont(font)
        self.file_size_label.setStyleSheet("background: transparent; border: none;")
        self.file_size_label.setText(self.file_size or "未知大小")

        file_info_layout.addWidget(self.file_name_label)
        file_info_layout.addWidget(self.file_size_label)

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

        # 添加悬浮效果
        self.file_name_label.enterEvent = self.on_file_name_enter
        self.file_name_label.leaveEvent = self.on_file_name_leave

    def on_file_name_enter(self, event):
        """文件名悬浮时显示下划线"""
        font = self.file_name_label.font()
        font.setUnderline(True)
        self.file_name_label.setFont(font)

    def on_file_name_leave(self, event):
        """离开时移除下划线"""
        font = self.file_name_label.font()
        font.setUnderline(False)
        self.file_name_label.setFont(font)

    def on_file_clicked(self, event):
        """文件名或图标点击事件"""
        if self.file_id:
            asyncio.create_task(self.download_media_file())

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
        available = int(self.config.chat_area_width * 0.6)  # 用于文本气泡

        # 计算时间文本尺寸
        fm_time = QFontMetrics(self.font_time)
        time_width = fm_time.horizontalAdvance(self.time_str)
        time_height = fm_time.height()
        time_size = QSize(time_width, time_height)
        min_content_width = time_width

        if self.message_type == 'text':
            fm_msg = QFontMetrics(self.font_message)
            natural_width = fm_msg.boundingRect(0, 0, 0, 0, Qt.TextSingleLine, self.message).width()
            if natural_width < available:
                chosen = max(natural_width, min_content_width)
            else:
                chosen = available
            self.content_widget.setFixedWidth(chosen)
            wrapped_height = fm_msg.boundingRect(
                0, 0, chosen, 0, Qt.TextWordWrap, self.message.rstrip('\n')
            ).height()
            if not self.message.strip():
                wrapped_height = fm_msg.height()
            content_size = QSize(chosen, wrapped_height)
            content_width = chosen

        elif self.message_type in ('image', 'video'):
            if hasattr(self, 'thumbnail_size') and self.thumbnail_size.width() > 0:
                # 使用缩略图的实际尺寸
                content_width = self.thumbnail_size.width()  # 已限制在 150-300 之间
                # 如果是横向缩略图（宽 > 高），高度等于缩略图高度，否则按比例计算
                if self.thumbnail_size.width() > self.thumbnail_size.height():
                    content_height = self.thumbnail_size.height()
                else:
                    content_height = self.thumbnail_size.height()
                content_size = QSize(content_width, content_height)
            else:
                # 缩略图不可用时，使用默认宽度和文本高度
                fm_msg = QFontMetrics(FONTS['MESSAGE'])
                base_text = self.original_file_name or "视频缩略图不可用"
                content_width = 150  # 最小宽度
                content_height = fm_msg.height() if self.message_type == 'image' else 300  # 视频默认高度
                content_size = QSize(content_width, content_height)
            self.content_widget.adjustSize()

        elif self.message_type == 'file':
            max_width = available
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
            content_size = QSize(0, 0)
            content_width = min_content_width

        # 计算气泡整体尺寸
        padding_h = self.config.file_h_padding if self.message_type in ('file', 'image', 'video') else self.config.h_padding
        padding_v = self.config.file_v_padding if self.message_type in ('file', 'image', 'video') else self.config.v_padding
        bubble_width = max(content_width, time_width) + 2 * padding_h
        bubble_height = content_size.height() + padding_v + time_size.height()
        if self.progress_bar and self.progress_bar.isVisible():
            bubble_height += self.progress_bar.height()
        bubble_size = QSize(bubble_width, bubble_height)
        return bubble_size, content_size, time_size, content_width

    def sizeHint(self) -> QSize:
        bubble_size, _, _, _ = self._calculateSizes()
        return QSize(bubble_size.width() + self.config.triangle_size, bubble_size.height())

    def updateBubbleSize(self) -> None:
        bubble_size, content_size, time_size, content_width = self._calculateSizes()
        bx = 0 if self.align == "right" else self.config.triangle_size
        self._bubble_rect = QRect(bx, 0, bubble_size.width(), bubble_size.height())

        h_pad = self.config.file_h_padding if self.message_type in ('file', 'image', 'video') else self.config.h_padding
        v_pad = self.config.file_v_padding if self.message_type in ('file', 'image', 'video') else self.config.v_padding

        content_y = v_pad
        if self.progress_bar and self.progress_bar.isVisible():
            progress_y = content_y + content_size.height()
            time_y = progress_y + self.progress_bar.height()
        else:
            progress_y = content_y
            time_y = content_y + content_size.height()

        bubble_right = bx + bubble_size.width()
        if self.align == "right":
            content_x = bx + h_pad
            time_x = content_x
            progress_x = content_x
        else:
            content_x = bubble_right - content_width - h_pad
            time_x = bubble_right - time_size.width() - h_pad
            progress_x = content_x

        content_x = max(bx + h_pad, min(content_x, bubble_right - content_width - h_pad))
        time_x = max(bx + h_pad, min(time_x, bubble_right - time_size.width() - h_pad))

        self.content_widget.move(content_x, content_y)
        self.content_widget.setFixedSize(content_width, content_size.height())
        self.label_time.move(time_x, time_y)
        self.label_time.setFixedSize(time_size.width(), time_size.height())
        if self.progress_bar and self.progress_bar.isVisible():
            self.progress_bar.move(progress_x, progress_y)
            self.progress_bar.setFixedWidth(content_width)
        new_size = QSize(bubble_size.width() + self.config.triangle_size, bubble_size.height())
        if self.size() != new_size:
            self.setFixedSize(new_size)

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
        video_dir = os.path.join(os.getcwd(), "Chat_DATA", "videos")
        try:
            os.makedirs(video_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法创建视频目录: {e}")
            return
        save_path = os.path.join(video_dir, f"{self.original_file_name or file_id}.mp4")
        async def progress_callback(type_, progress, filename):
            if type_ == "download" and filename == os.path.basename(save_path):
                self.update_progress(progress)
                QApplication.processEvents()
        try:
            # 临时修改 message_type 为 video，仅用于下载
            original_type = self.message_type
            self.message_type = 'video'
            result = await self.window().client.download_media(file_id, save_path, progress_callback)
            self.message_type = original_type  # 恢复原始类型
            if result.get("status") == "success":
                self.complete_progress()
                os.startfile(save_path)
            else:
                self.complete_progress()
                QMessageBox.critical(self, "错误", f"视频下载失败: {result.get('message', '未知错误')}")
        except Exception as e:
            self.complete_progress()
            QMessageBox.critical(self, "错误", f"下载视频时发生错误: {e}")

    async def download_media_file(self):
        """统一下载文件、图片或视频的方法，根据类型自动选择逻辑"""
        if not self.file_id:
            return
        download_configs = {
            'file': {
                'title': "保存文件",
                'default_name': self.original_file_name or "file",
                'filter': "所有文件 (*.*)"
            },
            'image': {
                'title': "保存图片",
                'default_name': self.original_file_name or "image.jpg",
                'filter': "图片文件 (*.jpg *.jpeg *.png *.gif *.bmp *.ico *.tiff *.webp *.heif *.raw)"
            },
            'video': {
                'title': "保存视频",
                'default_name': self.original_file_name or "video.mp4",
                'filter': "视频文件 (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.mpg *.mpeg *.3gp)"
            }
        }
        config = download_configs.get(self.message_type, download_configs['file'])  # 默认使用文件配置
        save_path, _ = QFileDialog.getSaveFileName(self, config['title'], config['default_name'], config['filter'])
        if not save_path:
            return
        async def progress_callback(type_, progress, filename):
            if type_ == "download" and filename == os.path.basename(save_path):
                self.update_progress(progress)
                QApplication.processEvents()
        try:
            result = await self.window().client.download_media(self.file_id, save_path, progress_callback)
            if result.get("status") == "success":
                self.complete_progress()
                QMessageBox.information(self, "成功", f"{self.message_type}下载完成")
            else:
                self.complete_progress()
                QMessageBox.critical(self, "错误", f"{self.message_type}下载失败: {result.get('message', '未知错误')}")
        except Exception as e:
            self.complete_progress()
            QMessageBox.critical(self, "错误", f"下载{self.message_type}时发生错误: {e}")

    def show_context_menu(self, pos: QPoint) -> None:
        """显示右键菜单，根据消息类型提供中文下载选项"""
        if not self.file_id:  # 如果没有 file_id，不显示菜单
            return
        menu = QMenu(self)
        if self.message_type in self.DOWNLOAD_LABELS:
            label = self.DOWNLOAD_LABELS.get(self.message_type, "文件")  # 默认值为“文件”
            download_action = menu.addAction(f"下载{label}")
            download_action.triggered.connect(lambda: asyncio.create_task(self.download_media_file()))
        if menu.actions():  # 只有当有可用动作时才显示菜单
            StyleGenerator.apply_style(self, "menu")
            menu.exec_(self.mapToGlobal(pos))
