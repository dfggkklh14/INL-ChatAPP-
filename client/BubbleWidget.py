import os
import json
import asyncio
from dataclasses import dataclass
from typing import Optional, Any, Tuple

from PyQt5 import sip
from PyQt5.QtCore import Qt, QSize, QRect, QPoint, pyqtSignal, QPropertyAnimation, QObject, QEvent
from PyQt5.QtGui import QPainter, QFont, QFontMetrics, QPixmap, QImage, QIcon, QPainterPath, QColor, QWheelEvent
from PyQt5.QtWidgets import (
    QWidget, QTextEdit, QHBoxLayout, QLabel, QVBoxLayout, QPushButton, QApplication, QMessageBox, QMenu, QFileDialog,
    QSizePolicy, QProgressBar, QListWidgetItem, QListWidget)

from Interface_Controls import LIGHT_THEME, FONTS, StyleGenerator, resource_path, theme_manager, FloatingLabel


def create_confirmation_dialog(parent: QWidget, title: str, message: str) -> int:
    """
    创建一个风格化的确认对话框，返回用户的选择。

    Args:
        parent: 父控件
        title: 对话框标题
        message: 对话框消息内容

    Returns:
        int: QMessageBox.Yes 或 QMessageBox.No，表示用户选择
    """
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg_box.setDefaultButton(QMessageBox.No)

    # 设置中文按钮并应用样式
    yes_button = msg_box.button(QMessageBox.Yes)
    no_button = msg_box.button(QMessageBox.No)
    yes_button.setText("是")
    no_button.setText("否")
    yes_button.setFixedSize(30, 18)
    no_button.setFixedSize(30, 18)

    # 应用当前主题样式
    theme = theme_manager.current_theme
    msg_box.setStyleSheet(f"QLabel {{ color: {theme['dialog_text_color']}; }}")
    StyleGenerator.apply_style(yes_button, "button", extra="border-radius: 5px;")
    StyleGenerator.apply_style(no_button, "button", extra="border-radius: 5px;")

    # 执行并返回结果
    return msg_box.exec_()


class BubbleTextEdit(QTextEdit):
    def __init__(self, parent=None, font=None, read_only=True, wrap_mode=QTextEdit.WidgetWidth):
        super().__init__(parent)
        self.setFont(font if font else QFont("微软雅黑", 9))
        self.setStyleSheet(
            "background: transparent; "
            "border: none; "
            "padding: 0px;"
        )
        self.setReadOnly(read_only)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.document().setDocumentMargin(0)
        self.setLineWrapMode(wrap_mode)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setFocusPolicy(Qt.StrongFocus)  # 新增焦点策略
        self.document().documentLayout().documentSizeChanged.connect(self.adjustSizeToContent)

    def focusOutEvent(self, event):
        """失去焦点时清除选中状态"""
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        super().focusOutEvent(event)

    def adjustSizeToContent(self, size):
        # 根据实际文档大小调整控件尺寸
        self.setFixedWidth(int(size.width()))
        self.setFixedHeight(int(size.height()))
        self.viewport().scroll(0, 0)  # 锁定视口

    def setTextContent(self, text: str, alignment=Qt.AlignLeft | Qt.AlignTop):
        """
        设置文本内容并应用对齐方式。

        Args:
            text: 要显示的文本
            alignment: 文本对齐方式，默认为左上对齐
        """
        self.setPlainText(text)
        self.setAlignment(alignment)


class ChatAreaWidget(QListWidget):
    """
    基于 QListWidget 的聊天区域控件，用于容纳聊天气泡。
    """
    newBubblesAdded = pyqtSignal()

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QListWidget.MultiSelection)
        self.setFocusPolicy(Qt.NoFocus)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)  # 已启用像素级滚动
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAcceptDrops(True)
        self.bubble_items = []
        self.selected_items = []
        ChatBubbleWidget.config.chat_area_width = self.width() or 650
        theme_manager.register(self)
        self.update_theme(theme_manager.current_theme)
        self._scroll_animation = None

        # 设置滚动条的单步值和页面步长
        scrollbar = self.verticalScrollBar()
        scrollbar.setSingleStep(20)  # 每次滚动 20 像素
        scrollbar.setPageStep(60)   # 页面滚动步长设为 60 像素
        self.setSpacing(3)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if not event.isAccepted():
            urls = event.mimeData().urls()
            file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            if file_paths:
                chat_window = self.window()
                if hasattr(chat_window, 'send_multiple_media'):
                    asyncio.create_task(chat_window.send_multiple_media(file_paths))
                event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def mousePressEvent(self, event: QEvent) -> None:
        chat_window = self.window()
        if (hasattr(chat_window, 'is_selection_mode') and chat_window.is_selection_mode and
                event.button() == Qt.LeftButton):
            item = self.itemAt(event.pos())
            if item and item in self.bubble_items:
                self.toggle_item_selection(item)
                event.accept()
                return
        super().mousePressEvent(event)

    def toggle_item_selection(self, item: QListWidgetItem) -> None:
        chat_bg = theme_manager.current_theme["chat_bg"]
        container = self.itemWidget(item)
        if item in self.selected_items:
            self.selected_items.remove(item)
            container.setStyleSheet(f"background-color: {chat_bg};")
            item.setSelected(False)
        else:
            self.selected_items.append(item)
            container.setStyleSheet("background-color: #bbbbbb;")
            item.setSelected(True)
        self.viewport().update()

    def clear_selection(self) -> None:
        chat_bg = theme_manager.current_theme["chat_bg"]
        for item in self.selected_items:
            container = self.itemWidget(item)
            container.setStyleSheet(f"background-color: {chat_bg};")
            item.setSelected(False)
        self.selected_items.clear()
        self.viewport().update()

    def get_selected_rowids(self) -> list[int]:
        rowids = []
        for item in self.selected_items:
            bubble = next((w for w in self.itemWidget(item).children() if isinstance(w, ChatBubbleWidget)), None)
            if bubble and bubble.rowid:
                rowids.append(bubble.rowid)
        return rowids

    def _wrap_bubble(self, bubble: QWidget) -> QWidget:
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
        chat_bg = theme_manager.current_theme["chat_bg"]
        container.setStyleSheet(f"background-color: {chat_bg};")
        container.installEventFilter(bubble)
        return container

    def addBubble(self, bubble: QWidget) -> None:
        container = self._wrap_bubble(bubble)
        item = QListWidgetItem(self)
        item.setSizeHint(bubble.sizeHint())
        self.setItemWidget(item, container)
        self.bubble_items.append(item)  # 改为追加到末尾

    def addBubbles(self, bubbles: list[QWidget]) -> None:
        for bubble in bubbles:
            container = self._wrap_bubble(bubble)
            item = QListWidgetItem(self)
            item.setSizeHint(bubble.sizeHint())
            self.setItemWidget(item, container)
            self.bubble_items.append(item)  # 改为追加到末尾
        self.newBubblesAdded.emit()

    def wheelEvent(self, event: QWheelEvent) -> None:
        scrollbar = self.verticalScrollBar()
        delta = event.angleDelta().y()
        step = 100

        scroll_amount = -(delta // 100) * step
        current_value = scrollbar.value()
        target_value = max(scrollbar.minimum(), min(current_value + scroll_amount, scrollbar.maximum()))

        # 使用动画平滑滚动
        if self._scroll_animation:
            self._scroll_animation.stop()
        self._scroll_animation = QPropertyAnimation(scrollbar, b"value")
        self._scroll_animation.setDuration(50)  # 动画持续时间 150ms
        self._scroll_animation.setStartValue(current_value)
        self._scroll_animation.setEndValue(target_value)
        self._scroll_animation.start()

        event.accept()

    def resizeEvent(self, event) -> None:
        ChatBubbleWidget.config.chat_area_width = self.width()
        for item in self.bubble_items:
            container = self.itemWidget(item)
            for widget in container.children():
                if isinstance(widget, ChatBubbleWidget):
                    widget.updateBubbleSize()
                    item.setSizeHint(widget.sizeHint())
        super().resizeEvent(event)

    def update_theme(self, theme: dict) -> None:
        chat_bg = theme["chat_bg"]
        self.setStyleSheet(f"background-color: {chat_bg};")
        for item in self.bubble_items:
            if item not in self.selected_items:
                container = self.itemWidget(item)
                container.setStyleSheet(f"background-color: {chat_bg};")
        self.viewport().update()

    async def remove_bubbles_by_rowids(self, deleted_rowids: list[int], show_floating_label: bool = True) -> None:
        if not deleted_rowids:
            return

        items_to_remove = []
        removed_file_ids = []  # 收集被删除的图片 file_id
        for item in self.bubble_items[:]:
            container = self.itemWidget(item)
            bubble = next((w for w in container.children() if isinstance(w, ChatBubbleWidget)),
                          None) if container else None
            if bubble and bubble.rowid in deleted_rowids:
                items_to_remove.append(item)
                # 如果是图片消息，记录 file_id
                if bubble.message_type == "image" and bubble.file_id:
                    removed_file_ids.append(bubble.file_id)

        for item in items_to_remove:
            row = self.row(item)
            container = self.itemWidget(item)
            if row != -1:  # 确保 item 仍在列表中
                self.takeItem(row)
                self.bubble_items.remove(item)
                if item in self.selected_items:
                    self.selected_items.remove(item)
                if container and not sip.isdeleted(container):
                    container.deleteLater()
                else:
                    return

        if items_to_remove:
            self.viewport().update()
            chat_window = self.window()
            chat_area = chat_window.chat_components.get('area_widget')

            # 通知 ChatWindow 移除 image_list 中的图片
            if removed_file_ids and hasattr(chat_window, 'remove_from_image_list'):
                chat_window.remove_from_image_list(removed_file_ids)

            if hasattr(chat_window, 'adjust_scroll'):
                chat_window.adjust_scroll()
            if show_floating_label and chat_area:
                FloatingLabel(f"已删除 {len(items_to_remove)} 条消息", chat_area)

@dataclass
class BubbleConfig:
    chat_area_width: int = 650
    h_padding: int = 3
    v_padding: int = 3
    triangle_size: int = 10
    triangle_height: int = 10
    file_h_padding: int = 3
    file_v_padding: int = 3


class ChatBubbleWidget(QWidget):
    """
    聊天气泡控件，支持文本、图片、视频及文件消息显示。
    """
    config: BubbleConfig = BubbleConfig()
    DOWNLOAD_LABELS = {
        "file": "文件",
        "image": "图片",
        "video": "视频"
    }

    def __init__(self, message: str, time_str: str, align: str = 'left', is_current_user: bool = False,
                 message_type: str = 'text', file_id: Optional[str] = None, original_file_name: Optional[str] = None,
                 thumbnail_path: Optional[str] = None, file_size: Optional[str] = None, duration: Optional[str] = None,
                 rowid: Optional[int] = None, reply_to: Optional[int] = None, reply_preview: Optional[str] = None,
                 thumbnail_local_path: Optional[str] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.file = None
        self.align = "right" if is_current_user else align
        self.is_current_user = is_current_user
        self.message = self._insertZeroWidthSpace(message)
        self.time_str = time_str
        self.message_type = message_type
        self.file_id = file_id
        self.original_file_name = original_file_name
        self.thumbnail_path = thumbnail_path
        self.thumbnail_local_path = thumbnail_local_path  # 支持本地路径
        self.file_size = file_size
        self.duration = duration
        self.rowid = rowid
        self.reply_to = reply_to
        self.reply_preview = reply_preview
        self.bubble_color = LIGHT_THEME["BUBBLE_USER"] if self.is_current_user else LIGHT_THEME["BUBBLE_OTHER"]
        self.progress_bar = None
        self.reply_container = None
        self.reply_username_label = None
        self.reply_content_label = None
        self.message_text_edit = None
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._init_ui()
        if self.parent():
            self.parent().installEventFilter(self)
        self.installEventFilter(self)
        theme_manager.register(self)

    def _init_ui(self) -> None:
        self.font_message = QFont(FONTS['MESSAGE'])
        self.font_message.setHintingPreference(QFont.PreferNoHinting)
        self.font_message.setStyleStrategy(QFont.PreferAntialias)
        self.font_time = QFont(FONTS['TIME'])
        self.font_time.setHintingPreference(QFont.PreferNoHinting)
        self.font_time.setStyleStrategy(QFont.PreferAntialias)

        if self.reply_to is not None:
            self._create_reply_to_widget()

        if self.message_type == 'text':
            self._create_text_widget()
        elif self.message_type == 'image':
            self._create_image_widget()
            if self.message:
                self._create_message_text_edit()
        elif self.message_type == 'video':
            self._create_video_widget()
            if self.message:
                self._create_message_text_edit()
        elif self.message_type == 'file':
            self._create_file_widget()
            if self.message:
                self._create_message_text_edit()

        self.label_time = QLabel(self)
        self.label_time.setFont(self.font_time)
        self.label_time.setStyleSheet("background: transparent; border: none;")
        self.label_time.setTextInteractionFlags(Qt.NoTextInteraction)
        self.label_time.setText(self.time_str)

        self._bubble_rect = QRect()
        self._setup_progress_bar()
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def _create_message_text_edit(self) -> None:
        self.message_text_edit = BubbleTextEdit(self, font=self.font_message)
        self.message_text_edit.setTextContent(self.message)  # 设置文本内容
        self.message_text_edit.customContextMenuRequested.connect(self.show_context_menu)  # 绑定上下文菜单信号

    def _setup_progress_bar(self) -> None:
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(10)
        StyleGenerator.apply_style(self.progress_bar, "progress_bar")
        self.progress_bar.hide()

    def update_progress(self, value: float) -> None:
        if self.progress_bar:
            self.progress_bar.setValue(int(value))
            self.progress_bar.show()
            self.updateBubbleSize()

    def complete_progress(self) -> None:
        if self.progress_bar:
            self.progress_bar.hide()
            self.progress_bar.deleteLater()
            self.progress_bar = None
            self.updateBubbleSize()

    def _create_reply_to_widget(self) -> None:
        self.reply_container = QWidget(self)
        bg_color = "#90db5a" if self.is_current_user else "#ededed"
        self.reply_container.setStyleSheet(f"background: {bg_color}; border: none; border-radius: 8px;")
        reply_layout = QVBoxLayout(self.reply_container)
        reply_layout.setContentsMargins(self.config.h_padding, self.config.v_padding,
                                        self.config.h_padding, self.config.v_padding)
        reply_layout.setSpacing(2)
        self.reply_username_label = QLabel(self.reply_container)
        self.reply_username_label.setFont(QFont("微软雅黑", 8, QFont.Bold))
        self.reply_username_label.setStyleSheet("color: #000000; background: transparent; border: none;")
        self.reply_content_label = QLabel(self.reply_container)
        self.reply_content_label.setFont(QFont("微软雅黑", 8))
        self.reply_content_label.setStyleSheet("color: #000000; background: transparent; border: none;")
        self.reply_content_label.setWordWrap(False)

        # 添加点击事件
        self.reply_container.setCursor(Qt.PointingHandCursor)
        self.reply_container.mousePressEvent = self.on_reply_container_clicked

        # 填充回复内容（保持不变）
        try:
            if self.reply_preview:
                preview_data = json.loads(self.reply_preview)
                self.reply_username_label.setText(preview_data.get('sender', '未知用户'))
                raw_content = preview_data.get('content', '消息内容不可用')
                if raw_content.startswith('[image]:'):
                    filename = raw_content[len('[image]:'):].strip()
                    display_content = f"{self.DOWNLOAD_LABELS.get('image', '图片')}: {filename}"
                elif raw_content.startswith('[video]:'):
                    filename = raw_content[len('[video]:'):].strip()
                    display_content = f"{self.DOWNLOAD_LABELS.get('video', '视频')}: {filename}"
                elif raw_content.startswith('[file]:'):
                    filename = raw_content[len('[file]:'):].strip()
                    display_content = f"{self.DOWNLOAD_LABELS.get('file', '文件')}: {filename}"
                else:
                    display_content = raw_content
            else:
                self.reply_username_label.setText("未知用户")
                display_content = f"回复消息 #{self.reply_to}"
        except Exception:
            self.reply_username_label.setText("未知用户")
            display_content = "回复消息预览不可用"
        self.reply_content_label.setText(display_content)
        reply_layout.addWidget(self.reply_username_label)
        reply_layout.addWidget(self.reply_content_label)

    def _create_text_widget(self) -> None:
        self.content_widget = BubbleTextEdit(self, font=self.font_message)
        self.content_widget.setPlainText(self.message)  # 设置文本内容
        self.content_widget.setAlignment(Qt.AlignLeft | Qt.AlignTop)  # 设置对齐方式
        self.content_widget.customContextMenuRequested.connect(self.show_context_menu)  # 绑定上下文菜单信号

    def _create_image_widget(self) -> None:
        self.content_widget = QLabel(self)
        self.content_widget.setStyleSheet("background: transparent; border: none;")
        if self.thumbnail_local_path and os.path.exists(self.thumbnail_local_path):
            self.original_image = QImage(self.thumbnail_local_path)
            if self.original_image.isNull():
                self.content_widget.setText("缩略图加载失败")
                self.original_image = None
        elif self.thumbnail_path and os.path.exists(self.thumbnail_path):
            self.original_image = QImage(self.thumbnail_path)
            if self.original_image.isNull():
                self.content_widget.setText("缩略图加载失败")
                self.original_image = None
        else:
            self.content_widget.setText("缩略图不可用")
            self.original_image = None
        self.content_widget.setAlignment(Qt.AlignCenter)
        self.content_widget.setCursor(Qt.PointingHandCursor)
        self.content_widget.setMouseTracking(True)
        self.content_widget.mousePressEvent = self.on_image_clicked

    def _create_video_widget(self) -> None:
        self.content_widget = QWidget(self)
        self.content_widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(self.content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.thumbnail_label = QLabel(self.content_widget)
        self.thumbnail_label.setStyleSheet("background: transparent; border: none;")
        # 优先使用 thumbnail_local_path
        if hasattr(self, "thumbnail_local_path") and os.path.exists(self.thumbnail_local_path):
            self.original_thumbnail_pixmap = QPixmap(self.thumbnail_local_path)
        # 回退到 thumbnail_path
        elif self.thumbnail_path and os.path.exists(self.thumbnail_path):
            self.original_thumbnail_pixmap = QPixmap(self.thumbnail_path)
        else:
            self.thumbnail_label.setText(f"{self.original_file_name or '视频'} (缩略图不可用)")
            self.original_thumbnail_pixmap = None
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.thumbnail_label)
        self.play_button = QPushButton(self.content_widget)
        icon_path = "icon/play_icon_shallow.ico"
        if os.path.exists(icon_path):
            self.play_button.setIcon(QIcon(icon_path))
        else:
            self.play_button.setText("▶")
        self.play_button.setIconSize(QSize(50, 50))
        self.play_button.setStyleSheet(
            "QPushButton { background-color: transparent; border: none; qproperty-alignment: 'AlignCenter'; }"
            "QPushButton:hover { icon: url('icon/play_icon_deep.ico'); }"
        )
        self.play_button.setCursor(Qt.PointingHandCursor)
        self.play_button.clicked.connect(self.play_video)

    def _create_file_widget(self) -> None:
        """创建文件类型的聊天气泡控件，去掉文件名截断逻辑，保留悬浮显示完整文件名"""
        self.content_widget = QWidget(self)
        self.content_widget.setStyleSheet("background: transparent; border: none;")
        file_layout = QHBoxLayout(self.content_widget)
        file_layout.setContentsMargins(self.config.file_h_padding, self.config.file_v_padding,
                                       self.config.file_h_padding, self.config.file_v_padding)
        file_layout.setSpacing(5)

        self.file_icon = QLabel(self)
        self.file_icon.setStyleSheet("background: transparent; border: none;")
        self.file_icon.setPixmap(QIcon(resource_path("icon/file_icon.ico")).pixmap(40, 40))
        self.file_icon.setCursor(Qt.PointingHandCursor)
        self.file_icon.mousePressEvent = self.on_file_clicked

        self.file_info_widget = QWidget(self)
        file_info_layout = QVBoxLayout(self.file_info_widget)
        file_info_layout.setContentsMargins(0, 0, 0, 0)
        file_info_layout.setSpacing(2)

        self.file_name_label = QLabel(self)
        font = QFont(FONTS['FILE_NAME'])
        font.setBold(True)
        self.file_name_label.setFont(font)
        self.file_name_label.setStyleSheet("background: transparent; border: none;")
        original_name = self.original_file_name or "未知文件"
        self.file_name_label.setText(original_name)  # 去掉截断逻辑，直接显示完整文件名
        # 设置悬浮提示，使用主题管理器的颜色
        theme = theme_manager.current_theme
        self.file_name_label.setToolTip(original_name)
        self.file_name_label.setToolTipDuration(5000)  # 可选：设置悬浮提示显示时间（毫秒）
        self.file_name_label.setStyleSheet(
            f"QLabel {{ background: transparent; border: none; }}"
            f"QToolTip {{ background-color: {theme['widget_bg']}; color: {theme['dialog_text_color']}; border: 1px solid {theme['line_edit_border']}; }}"
        )
        self.file_name_label.setCursor(Qt.PointingHandCursor)
        self.file_name_label.mousePressEvent = self.on_file_clicked

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
            file_info_layout.setAlignment(self.file_size_label, Qt.AlignLeft)
        else:
            file_layout.addWidget(self.file_info_widget)
            file_layout.addWidget(self.file_icon)
            file_layout.setAlignment(self.file_info_widget, Qt.AlignRight | Qt.AlignVCenter)
            file_layout.setAlignment(self.file_icon, Qt.AlignRight | Qt.AlignVCenter)
            file_info_layout.setAlignment(self.file_size_label, Qt.AlignRight)

        self.file_name_label.enterEvent = self.on_file_name_enter
        self.file_name_label.leaveEvent = self.on_file_name_leave

    def on_reply_container_clicked(self, event) -> None:
        if event.button() == Qt.LeftButton and self.reply_to is not None:
            chat_window = self.window()
            if hasattr(chat_window, 'scroll_to_message'):
                asyncio.create_task(chat_window.scroll_to_message(self.reply_to))

    def on_file_name_enter(self, event) -> None:
        font = self.file_name_label.font()
        font.setUnderline(True)
        self.file_name_label.setFont(font)

    def on_file_name_leave(self, event) -> None:
        font = self.file_name_label.font()
        font.setUnderline(False)
        self.file_name_label.setFont(font)

    def on_file_clicked(self, event) -> None:
        if event.button() == Qt.LeftButton and self.file_id:
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
        return text

    def _get_scaled_size_and_pixmap(self, source, max_width=270, min_width=150, chat_area_max=None):
        original_width = source.width()
        original_height = source.height()
        aspect_ratio = original_width / original_height if original_height > 0 else 1
        if chat_area_max and chat_area_max < 270:
            content_width = min_width
        else:
            content_width = max(min_width, min(max_width, original_width))
        content_height = int(content_width / aspect_ratio)
        if isinstance(source, QImage):
            scaled_image = source.scaled(content_width, content_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pixmap = QPixmap.fromImage(scaled_image)
        else:
            pixmap = source.scaled(content_width, content_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QSize(pixmap.width(), pixmap.height()), pixmap

    def _getPadding(self) -> Tuple[int, int]:
        # 根据消息类型统一获取内边距
        if self.message_type == 'text':
            return self.config.h_padding, self.config.v_padding
        else:
            return self.config.file_h_padding, self.config.file_v_padding

    def _calculateSizes(self) -> Tuple[QSize, QSize, QSize, int, QSize]:
        """计算聊天气泡的各个部分尺寸，文件类型动态调整，截断长度减5"""
        chat_area_max = int(self.config.chat_area_width * 0.6)
        h_padding, v_padding = self._getPadding()
        time_size = self.label_time.sizeHint()

        is_media = self.message_type in ('image', 'video')
        if self.message_type == 'text':
            doc = self.content_widget.document()
            max_edit_width = chat_area_max - 2 * h_padding
            doc.setTextWidth(max_edit_width)
            fm = QFontMetrics(self.font_message)
            text_width = fm.horizontalAdvance(self.message) + 1  # 实际文本像素宽度+容差
            max_edit_width = min(chat_area_max - 2 * h_padding, text_width)
            doc.setTextWidth(max_edit_width)
            content_width = max(max_edit_width, time_size.width())
            content_height = int(doc.size().height())
            content_size = QSize(content_width, content_height)
        elif is_media:
            default_width = 150
            if self.message_type == 'image' and hasattr(self, 'original_image') and self.original_image:
                self.thumbnail_size, _ = self._get_scaled_size_and_pixmap(
                    self.original_image, max_width=270, min_width=default_width, chat_area_max=chat_area_max
                )
            elif self.message_type == 'video' and hasattr(self,
                                                          'original_thumbnail_pixmap') and self.original_thumbnail_pixmap:
                self.thumbnail_size, _ = self._get_scaled_size_and_pixmap(
                    self.original_thumbnail_pixmap, max_width=270, min_width=default_width, chat_area_max=chat_area_max
                )
            else:
                fm = QFontMetrics(self.font_message)
                default_height = fm.height() if self.message_type == 'image' else 300
                self.thumbnail_size = QSize(default_width, default_height)
            content_size = self.thumbnail_size
            content_width = self.thumbnail_size.width()
        elif self.message_type == 'file':
            # 动态调整文件名长度并计算尺寸
            fm = QFontMetrics(self.file_name_label.font())
            max_file_width = chat_area_max - self.file_icon.pixmap().width() - 2 * self.config.file_h_padding - 10  # 额外减5
            elided_name = fm.elidedText(self.original_file_name or "未知文件", Qt.ElideRight, max_file_width)
            self.file_name_label.setText(elided_name)
            content_width = fm.boundingRect(elided_name).width() + self.file_icon.pixmap().width() + 15
            content_height = self.content_widget.sizeHint().height()
            content_size = QSize(min(content_width, chat_area_max), content_height)
            content_width = content_size.width()
        else:
            content_size = self.content_widget.sizeHint()
            content_width = content_size.width()

        message_size = QSize(0, 0)
        if self.message_text_edit:
            doc = self.message_text_edit.document()
            max_message_width = content_width if is_media else chat_area_max - 2 * h_padding
            doc.setTextWidth(max_message_width)
            message_width = int(doc.idealWidth())
            if message_width > max_message_width:
                message_width = max_message_width
            message_height = int(doc.size().height())
            message_size = QSize(message_width, message_height)

        reply_size = QSize(0, 0)
        if self.reply_container:
            fm_username = QFontMetrics(self.reply_username_label.font())
            fm_reply = QFontMetrics(self.reply_content_label.font())
            username_width = fm_username.horizontalAdvance(self.reply_username_label.text())
            reply_text_width = fm_reply.horizontalAdvance(self.reply_content_label.text()) + 2 * h_padding
            reply_content_width = content_width if is_media else max(
                [reply_text_width, content_width] + ([message_width] if self.message_text_edit else [])
            )
            candidate_width = max(username_width, reply_content_width)
            max_reply_width = chat_area_max - 2 * h_padding
            reply_container_width = int(min(candidate_width, max_reply_width))
            reply_height = int(fm_username.height() + fm_reply.height() + 2 * v_padding + 2)
            reply_size = QSize(reply_container_width, reply_height)

        if is_media:
            bubble_width = content_width + 2 * h_padding
            if self.reply_container:
                reply_size.setWidth(content_width)
        else:
            width_candidates = [content_width + 2 * h_padding]
            if self.reply_container:
                width_candidates.append(reply_size.width() + 2 * h_padding)
            if self.message_text_edit:
                width_candidates.append(message_size.width() + 2 * h_padding)
            base_width = max(width_candidates)
            bubble_width = int(min(base_width, chat_area_max))

        top_margin = v_padding
        reply_gap = v_padding if self.reply_container else 0
        message_gap = v_padding if self.message_text_edit else 0
        extra_height = self.progress_bar.height() if (self.progress_bar and self.progress_bar.isVisible()) else 0
        time_gap = v_padding  # 为时间戳预留额外的间距

        bubble_height = (top_margin +
                         (reply_size.height() if self.reply_container else 0) +
                         reply_gap +
                         content_size.height() +
                         (message_size.height() + message_gap if self.message_text_edit else 0) +
                         extra_height +
                         time_size.height() + time_gap)  # 增加时间戳高度和间距

        bubble_size = QSize(bubble_width, bubble_height)

        return bubble_size, content_size, time_size, content_width, reply_size

    def updateBubbleSize(self) -> None:
        bubble_size, content_size, time_size, content_width, reply_size = self._calculateSizes()
        base_offset = 0 if self.align == "right" else self.config.triangle_size
        bx = base_offset + (1 if self.is_current_user else -1)

        self._bubble_rect = QRect(bx, 0, bubble_size.width(), bubble_size.height())
        h_padding, v_padding = self._getPadding()
        top_margin = v_padding
        reply_gap = v_padding if self.reply_container else 0

        # 回复容器位置
        if self.reply_container:
            reply_x = bx + h_padding
            self.reply_container.setFixedSize(reply_size)
            self.reply_container.move(reply_x, top_margin)
            y_offset = top_margin + reply_size.height() + reply_gap
        else:
            y_offset = top_margin

        # 内容位置调整
        if self.message_type == 'text' and not self.is_current_user:  # 对方发送的文本消息
            doc = self.content_widget.document()
            message_width = int(doc.idealWidth())
            if self._is_short_message(message_width):
                content_x = bx + bubble_size.width() - message_width - h_padding
            else:
                content_x = bx + h_padding
        elif self.align == "right":  # 当前用户发送
            content_x = bx + h_padding
        else:  # 其他情况（非文本或文件）
            content_x = bx + h_padding if self.message_type != 'file' else bx + bubble_size.width() - content_width - h_padding

        content_y = y_offset
        self.content_widget.move(int(content_x), int(content_y))
        self.content_widget.setFixedSize(int(content_width), int(content_size.height()))

        # 附加消息位置（保持不变或类似调整）
        message_y_offset = content_y + content_size.height()
        if self.message_text_edit:
            doc = self.message_text_edit.document()
            message_width = int(doc.idealWidth())
            message_height = int(doc.size().height())
            alignment = Qt.AlignLeft  # 固定文字左对齐
            self.message_text_edit.setTextContent(self.message, alignment)
            message_x = bx + h_padding  # 默认靠左，附加消息暂不调整
            self.message_text_edit.move(int(message_x), int(message_y_offset))
            self.message_text_edit.setFixedSize(message_width, message_height)
            message_y_offset += message_height + v_padding

        # 时间戳或进度条位置
        total_content_height = message_y_offset if self.message_text_edit else content_y + content_size.height()
        time_y = total_content_height
        if self.is_current_user:
            time_x = bx + h_padding
        else:
            time_x = bx + bubble_size.width() - time_size.width() - h_padding

        if self.progress_bar and self.progress_bar.isVisible():
            self.label_time.hide()
            self.progress_bar.move(int(content_x), int(time_y))
            self.progress_bar.setFixedWidth(int(content_width))
            self.progress_bar.show()
            time_y += self.progress_bar.height() + v_padding  # 进度条下方留出空间
        else:
            self.label_time.show()
            self.label_time.move(int(time_x), int(time_y))
            self.label_time.setFixedSize(time_size)
            if self.progress_bar:
                self.progress_bar.hide()

        # 确保气泡高度包含时间戳
        required_height = time_y + time_size.height() + v_padding
        if required_height > bubble_size.height():
            bubble_size.setHeight(required_height)
            self._bubble_rect.setHeight(required_height)

        # 更新缩略图和播放按钮
        if self.message_type == 'image' and hasattr(self, 'original_image') and self.original_image:
            scaled_image = self.original_image.scaled(self.thumbnail_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            rounded = self._roundedPixmap(QPixmap.fromImage(scaled_image), radius=8)
            self.content_widget.setPixmap(rounded)
        elif self.message_type == 'video' and hasattr(self,
                                                      'original_thumbnail_pixmap') and self.original_thumbnail_pixmap:
            scaled_pixmap = self.original_thumbnail_pixmap.scaled(self.thumbnail_size, Qt.KeepAspectRatio,
                                                                  Qt.SmoothTransformation)
            rounded_pixmap = self._roundedPixmap(scaled_pixmap, radius=8)
            self.thumbnail_label.setPixmap(rounded_pixmap)
            play_button_size = QSize(50, 50)
            self.play_button.setFixedSize(play_button_size)
            button_x = content_x + (self.thumbnail_size.width() - play_button_size.width()) // 2
            button_y = content_y + (self.thumbnail_size.height() - play_button_size.height()) // 2
            self.play_button.move(int(button_x), int(button_y))
            self.play_button.raise_()
        elif self.message_type == 'video':
            self.thumbnail_label.setText(f"{self.original_file_name or '视频'} (缩略图不可用)")
            self.play_button.hide()

        # 设置最终尺寸
        new_size = QSize(bubble_size.width() + self.config.triangle_size, bubble_size.height())
        if self.size() != new_size:
            self.setFixedSize(new_size)

    def sizeHint(self) -> QSize:
        bubble_size, _, _, _, _ = self._calculateSizes()
        return QSize(bubble_size.width() + self.config.triangle_size, bubble_size.height())

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

    async def _download_media_common(self, file_id: str, save_path: str, success_callback, label: str) -> None:
        async def progress_callback(type_, progress, filename):
            if type_ == "download" and filename == os.path.basename(save_path):
                self.update_progress(progress)
                QApplication.processEvents()
        try:
            download_type = self.message_type if self.message_type in ['image', 'video', 'file'] else "default"
            result = await self.window().client.download_media(
                file_id, save_path,
                download_type=download_type,  # 动态传入下载类型
                progress_callback=progress_callback
            )
            if result.get("status") == "success":
                self.complete_progress()
                success_callback()
            else:
                self.complete_progress()
                QMessageBox.critical(self, "错误", f"{label}下载失败: {result.get('message', '未知错误')}")
        except Exception as e:
            self.complete_progress()
            QMessageBox.critical(self, "错误", f"下载{label}时发生错误: {e}")

    async def download_and_play_video(self, file_id: str) -> None:
        # 从客户端获取路径基准
        client = self.window().client
        cache_root = client.cache_root
        video_dir = os.path.join(cache_root, "videos")
        # 确保视频目录存在
        os.makedirs(video_dir, exist_ok=True)
        # 定义保存路径
        save_path = os.path.join(video_dir, f"{self.original_file_name or file_id}.mp4")
        # 检查缓存是否存在且有效
        if os.path.exists(save_path):
            if os.path.getsize(save_path) > 0:
                os.startfile(save_path)
                return
            os.remove(save_path)  # 删除无效缓存
        # 下载并播放
        original_type = self.message_type
        self.message_type = 'video'
        result = await client.download_media(self.file_id, save_path, download_type="video")
        self.message_type = original_type
        if result.get("status") == "success":
            os.startfile(save_path)
        else:
            QMessageBox.critical(self, "错误", f"视频下载失败: {result.get('message', '未知错误')}")

    def _is_short_message(self, message_width: int) -> bool:
        bubble_available = self._bubble_rect.width() - 2 * self.config.h_padding
        return message_width < bubble_available * 0.8  # 60%宽度为阈值

    async def download_media_file(self):
        if not self.file_id:
            return
        client = self.window().client
        cache_root = client.cache_root
        download_configs = {
            'file': {
                'title': "保存文件",
                'dir': os.path.join(cache_root, "files"),
                'default_name': self.original_file_name or f"{self.file_id}",
                'filter': "所有文件 (*.*)"
            },
            'image': {
                'title': "保存图片",
                'dir': os.path.join(cache_root, "images"),
                'default_name': self.original_file_name or f"{self.file_id}.jpg",
                'filter': "图片文件 (*.jpg *.jpeg *.png *.gif *.bmp *.ico *.tiff *.webp *.heif *.raw)"
            },
            'video': {
                'title': "保存视频",
                'dir': os.path.join(cache_root, "videos"),
                'default_name': self.original_file_name or f"{self.file_id}.mp4",
                'filter': "视频文件 (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.mpg *.mpeg *.3gp)"
            }
        }
        config = download_configs.get(self.message_type, download_configs['file'])
        os.makedirs(config['dir'], exist_ok=True)
        save_path, _ = QFileDialog.getSaveFileName(
            self, config['title'], os.path.join(config['dir'], config['default_name']), config['filter']
        )
        if not save_path:
            return

        # 定义进度回调函数
        async def progress_callback(type_, progress, filename):
            if type_ == "download" and filename == os.path.basename(save_path):
                self.update_progress(progress)
                QApplication.processEvents()

        # 传递回调给 download_media
        result = await client.download_media(
            self.file_id, save_path, download_type=self.message_type, progress_callback=progress_callback
        )
        if result.get("status") == "success":
            self.complete_progress()  # 下载完成时清理进度条
            if self.message_type == 'file':
                self.file = self.DOWNLOAD_LABELS.get('file', '文件')
        else:
            self.complete_progress()  # 失败时也清理进度条
            QMessageBox.critical(
                self, "错误",
                f"{self.DOWNLOAD_LABELS.get(self.message_type, '文件')}下载失败: {result.get('message', '未知错误')}"
            )

    def show_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)

        # 判断触发来源
        sender = self.sender()
        is_text_bubble = self.message_type == 'text' and sender == self.content_widget
        is_message_text = sender == self.message_text_edit

        if is_text_bubble or is_message_text:
            target_widget = self.content_widget if is_text_bubble else self.message_text_edit
            selected_text = target_widget.textCursor().selectedText()
            copy_label = "复制选中" if selected_text else "复制"
            copy_action = menu.addAction(copy_label)
            copy_action.triggered.connect(lambda: self.copy_text(target_widget=target_widget))

        # 下载选项（仅对媒体类型）
        if self.message_type in self.DOWNLOAD_LABELS:
            label = self.DOWNLOAD_LABELS.get(self.message_type, "文件")
            download_action = menu.addAction(f"下载{label}")
            download_action.triggered.connect(lambda: asyncio.create_task(self.download_media_file()))

        # 回复选项
        reply_action = menu.addAction("回复")
        reply_action.triggered.connect(self.reply_to_message)

        # 进入多选模式选项
        chat_window = self.window()
        if hasattr(chat_window, 'enter_selection_mode') and not chat_window.is_selection_mode:
            select_mode_action = menu.addAction("选择")
            select_mode_action.triggered.connect(chat_window.enter_selection_mode)

        # 删除选项（仅当有 rowid 时显示）
        if self.rowid is not None:
            delete_action = menu.addAction("删除")
            delete_action.triggered.connect(lambda: asyncio.create_task(self.delete_message()))

        # 显示菜单，动态调整位置
        if menu.actions():
            StyleGenerator.apply_style(self, "menu")
            # 根据触发控件映射全局坐标
            if sender and sender in [self.content_widget, self.message_text_edit]:
                global_pos = sender.mapToGlobal(pos)  # 使用触发控件的坐标映射
            else:
                global_pos = self.mapToGlobal(pos)  # 默认使用 ChatBubbleWidget 的坐标
            menu.exec_(global_pos)

    async def delete_message(self) -> None:
        chat_window = self.window()
        if not hasattr(chat_window, 'client') or not self.rowid:
            QMessageBox.critical(self, "错误", "无法删除消息：客户端未初始化或消息ID缺失")
            return

        # 使用公用确认弹窗
        reply = create_confirmation_dialog(
            self,
            "确认删除",
            "您确定要删除这条消息吗？此操作无法撤销。"
        )
        if reply == QMessageBox.No:
            return

        # 发送删除请求
        resp = await chat_window.client.delete_messages(self.rowid)
        if resp.get("status") == "success":
            # 将 UI 更新放入事件循环，避免嵌套任务
            asyncio.create_task(self._show_delete_confirmation(chat_window.chat_components.get('area_widget')))
        else:
            QMessageBox.critical(self, "错误", f"删除失败: {resp.get('message', '未知错误')}")

    async def _show_delete_confirmation(self, chat_window) -> None:
        """异步显示删除确认提示"""
        FloatingLabel(f"已删除 1 条消息", chat_window)

    def on_image_clicked(self, event) -> None:
        if event.button() != Qt.LeftButton or not self.file_id:
            return
        chat_window = self.window()
        if not hasattr(chat_window, 'show_image_viewer'):
            return
        chat_window.show_image_viewer(self.file_id, self.original_file_name)

    def copy_text(self, target_widget=None) -> None:
        """
        复制文本内容，支持动态指定目标控件。

        Args:
            target_widget: 要复制文本的控件，默认为 None（使用 content_widget）
        """
        if not target_widget:
            target_widget = self.content_widget if self.message_type == 'text' else None

        if target_widget and isinstance(target_widget, QTextEdit):
            clipboard = QApplication.clipboard()
            selected_text = target_widget.textCursor().selectedText()
            if selected_text:
                clipboard.setText(selected_text)
            else:
                full_text = target_widget.toPlainText()
                if full_text:
                    clipboard.setText(full_text)
                else:
                    QMessageBox.information(self, "提示", "消息内容为空，无法复制")
        else:
            QMessageBox.critical(self, "错误", "无法复制：目标控件无效或不是文本消息")

    def reply_to_message(self) -> None:
        chat_window = self.window()
        if hasattr(chat_window, 'client') and hasattr(self, 'rowid'):
            chat_window.client.reply_to_id = self.rowid
            if hasattr(chat_window, 'chat_components') and chat_window.chat_components.get('input'):
                # 使用 ChatWindow.generate_reply_preview 统一生成 reply_preview
                reply_preview = chat_window.generate_reply_preview(self.rowid)
                if reply_preview:
                    chat_window.chat_components['input'].show_reply_preview(self.rowid, reply_preview)
                else:
                    # 如果生成失败，提供默认预览
                    chat_window.chat_components['input'].show_reply_preview(self.rowid, json.dumps({
                        "sender": "未知用户",
                        "content": f"消息 #{self.rowid} (无法加载预览)"
                    }))
            chat_window.chat_components['input'].text_edit.setFocus()

    def highlight_container_with_animation(self) -> None:
        """临时高亮包含此气泡的容器的背景颜色，然后恢复到聊天区域背景色"""
        container = self.parent()  # 获取父容器（bubble_container）
        if not isinstance(container, QWidget):
            return

        # 使用 theme_manager 获取 chat_bg
        chat_bg = theme_manager.current_theme["chat_bg"]
        original_color = QColor(chat_bg)  # 恢复到主题背景色
        highlight_color = QColor("#bbbbbb")

        # 创建动画对象
        self.container_animation = QPropertyAnimation(container, b"backgroundColor", self)
        self.container_animation.setDuration(1200)
        self.container_animation.setStartValue(highlight_color)
        self.container_animation.setEndValue(original_color)
        self.container_animation.valueChanged.connect(lambda color: self._update_container_color(container, color))
        self.container_animation.finished.connect(self._cleanup_container_animation)
        self.container_animation.start()

    def _update_container_color(self, container: QWidget, color: QColor) -> None:
        """更新容器的背景颜色"""
        container.setStyleSheet(f"background-color: {color.name()};")
        container.update()

    def _cleanup_container_animation(self) -> None:
        """清理动画对象"""
        if hasattr(self, 'container_animation'):
            self.container_animation.deleteLater()
            del self.container_animation

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """为自身和父容器处理双击事件"""
        if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
            # 检查是否为自身或父容器
            if (obj == self or obj == self.parent()) and self.rowid is not None:
                self.trigger_reply()
                self.trigger_reply()
                return True
        return super().eventFilter(obj, event)

    def trigger_reply(self) -> None:
        """触发回复当前消息"""
        chat_window = self.window()
        if hasattr(chat_window, 'client') and self.rowid:
            chat_window.client.reply_to_id = self.rowid
            if hasattr(chat_window, 'chat_components') and chat_window.chat_components.get('input'):
                reply_preview = chat_window.generate_reply_preview(self.rowid)  # 复用生成逻辑
                chat_window.chat_components['input'].show_reply_preview(self.rowid, reply_preview)
                chat_window.chat_components['input'].text_edit.setFocus()

    def update_theme(self, theme: dict) -> None:
        """仅更新 QMessageBox 的文本颜色"""
        pass