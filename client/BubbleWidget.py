import os
import json
import asyncio
from dataclasses import dataclass
from typing import Optional, Any, Tuple, List

from PyQt5 import sip
from PyQt5.QtCore import Qt, QSize, QRect, QPoint, pyqtSignal, QPropertyAnimation, QObject, QEvent
from PyQt5.QtGui import QPainter, QFont, QFontMetrics, QPixmap, QImage, QIcon, QPainterPath, QColor
from PyQt5.QtWidgets import (
    QWidget, QTextEdit, QHBoxLayout, QLabel, QVBoxLayout, QPushButton, QApplication, QMessageBox, QMenu, QFileDialog, QSizePolicy, QProgressBar)

from Interface_Controls import LIGHT_THEME, FONTS, StyleGenerator, resource_path, theme_manager, FloatingLabel


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
        ChatBubbleWidget.config.chat_area_width = self.width() or 650
        self.setAcceptDrops(True)
        theme_manager.register(self)  # 注册到 theme_manager

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

    def _wrap_bubble(self, bubble: QWidget) -> QWidget:
        """
        根据气泡对齐方式，将气泡包装到水平布局容器中。
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
        # 使用 theme_manager 获取 chat_bg
        chat_bg = theme_manager.current_theme["chat_bg"]
        container.setStyleSheet(f"background-color: {chat_bg};")
        container.installEventFilter(bubble)
        return container

    def addBubble(self, bubble: QWidget) -> None:
        container = self._wrap_bubble(bubble)
        self.layout().addWidget(container)
        self.bubble_containers.append(container)
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
        ChatBubbleWidget.config.chat_area_width = self.width()
        for container in self.bubble_containers:
            for i in range(container.layout().count()):
                widget = container.layout().itemAt(i).widget()
                if isinstance(widget, ChatBubbleWidget):
                    widget.updateBubbleSize()
        super().resizeEvent(event)

    def update_theme(self, theme: dict) -> None:
        """更新所有 container 的背景色"""
        chat_bg = theme["chat_bg"]
        self.setStyleSheet(f"background-color: {chat_bg};")  # 更新聊天区域背景
        for container in self.bubble_containers:
            container.setStyleSheet(f"background-color: {chat_bg};")
        self.update()


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
    VIDEO_CACHE_DIR = os.path.join(os.path.dirname(__file__), "Chat_DATA", "videos")
    IMAGE_CACHE_DIR = os.path.join(os.path.dirname(__file__), "Chat_DATA", "images")  # 完整图像
    THUMBNAIL_CACHE_DIR = os.path.join(os.path.dirname(__file__), "Chat_DATA", "thumbnails")  # 缩略图

    def __init__(self, message: str, time_str: str, align: str = 'left', is_current_user: bool = False,
                 message_type: str = 'text', file_id: Optional[str] = None, original_file_name: Optional[str] = None,
                 thumbnail_path: Optional[str] = None, file_size: Optional[str] = None, duration: Optional[str] = None,
                 rowid: Optional[int] = None, reply_to: Optional[int] = None, reply_preview: Optional[str] = None,
                 parent: Optional[QWidget] = None) -> None:
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
        self._msg_box = None

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
        """创建用于显示附加消息的 QTextEdit"""
        self.message_text_edit = QTextEdit(self)
        self.message_text_edit.setFont(self.font_message)
        self.message_text_edit.setStyleSheet("background: transparent; border: none; padding: 0px;")  # 移除可能干扰的内边距
        self.message_text_edit.setPlainText(self.message)
        self.message_text_edit.setReadOnly(True)
        self.message_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.message_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.message_text_edit.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.message_text_edit.document().setDocumentMargin(0)
        self.message_text_edit.setLineWrapMode(QTextEdit.WidgetWidth)  # 按控件宽度换行

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
        self.content_widget = QTextEdit(self)
        self.content_widget.setFont(self.font_message)
        self.content_widget.setStyleSheet("background: transparent; border: none;")
        self.content_widget.setReadOnly(True)
        self.content_widget.setPlainText(self.message)
        self.content_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_widget.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.content_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.content_widget.document().setDocumentMargin(0)
        self.content_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.content_widget.customContextMenuRequested.connect(self.show_context_menu)

    def _create_image_widget(self) -> None:
        self.content_widget = QLabel(self)
        self.content_widget.setStyleSheet("background: transparent; border: none;")
        if self.thumbnail_path and os.path.exists(self.thumbnail_path):
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
        if self.thumbnail_path and os.path.exists(self.thumbnail_path):
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
        self.file_name_label.setWordWrap(False)
        self.file_name_label.setText(self.original_file_name or "未知文件")
        self.file_name_label.setCursor(Qt.PointingHandCursor)
        self.file_name_label.mousePressEvent = self.on_file_clicked

        self.file_size_label = QLabel(self)
        font = QFont(FONTS['FILE_SIZE'])
        self.file_size_label.setFont(font)
        self.file_size_label.setStyleSheet("background: transparent; border: none;")
        self.file_size_label.setText(self.file_size or "未知大小")

        file_info_layout.addWidget(self.file_name_label)
        file_info_layout.addWidget(self.file_size_label)

        if self.is_current_user:  # 自己发送（右对齐气泡）
            file_layout.addWidget(self.file_icon)
            file_layout.addWidget(self.file_info_widget)
            file_layout.setAlignment(self.file_icon, Qt.AlignLeft | Qt.AlignVCenter)
            file_layout.setAlignment(self.file_info_widget, Qt.AlignLeft | Qt.AlignVCenter)
            file_info_layout.setAlignment(self.file_size_label, Qt.AlignLeft)  # 文件大小左对齐
        else:  # 对方发送（左对齐气泡）
            file_layout.addWidget(self.file_info_widget)
            file_layout.addWidget(self.file_icon)
            file_layout.setAlignment(self.file_info_widget, Qt.AlignRight | Qt.AlignVCenter)
            file_layout.setAlignment(self.file_icon, Qt.AlignRight | Qt.AlignVCenter)
            file_info_layout.setAlignment(self.file_size_label, Qt.AlignRight)  # 文件大小右对齐

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
        chat_area_max = int(self.config.chat_area_width * 0.6)
        h_padding, v_padding = self._getPadding()
        time_size = self.label_time.sizeHint()

        # 计算内容区域尺寸
        is_media = self.message_type in ('image', 'video')
        if self.message_type == 'text':
            doc = self.content_widget.document()
            max_edit_width = chat_area_max - 2 * h_padding
            doc.setTextWidth(max_edit_width)
            ideal_width = int(doc.idealWidth())
            content_width = max(ideal_width, time_size.width())
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
            hint = self.content_widget.sizeHint()
            content_size = QSize(hint.width(), hint.height())
            content_width = hint.width()
        else:
            content_size = self.content_widget.sizeHint()
            content_width = content_size.width()

        # 计算附加消息区域尺寸
        message_size = QSize(0, 0)
        if self.message_text_edit:
            doc = self.message_text_edit.document()
            max_message_width = content_width if is_media else chat_area_max - 2 * h_padding
            doc.setTextWidth(max_message_width)  # 设置宽度以触发换行
            message_width = int(doc.idealWidth())
            if message_width > max_message_width:
                message_width = max_message_width  # 限制宽度不超过最大值
            message_height = int(doc.size().height())  # 获取换行后的实际高度
            message_size = QSize(message_width, message_height)

        # 计算回复预览区域尺寸
        reply_size = QSize(0, 0)
        if self.reply_container:
            fm_username = QFontMetrics(self.reply_username_label.font())
            fm_reply = QFontMetrics(self.reply_content_label.font())
            username_width = fm_username.horizontalAdvance(self.reply_username_label.text())
            reply_text_width = fm_reply.horizontalAdvance(self.reply_content_label.text()) + 2 * h_padding
            reply_content_width = content_width if is_media else max(
                [reply_text_width, content_width] + ([message_width] if self.message_text_edit else []))
            candidate_width = max(username_width, reply_content_width)
            max_reply_width = chat_area_max - 2 * h_padding
            reply_container_width = int(min(candidate_width, max_reply_width))
            reply_height = int(fm_username.height() + fm_reply.height() + 2 * v_padding + 2)
            reply_size = QSize(reply_container_width, reply_height)

        # 计算气泡宽度
        if is_media:
            bubble_width = content_width + 2 * h_padding  # 媒体类型固定基于缩略图宽度
            if self.reply_container:
                reply_size.setWidth(content_width)  # 回复容器宽度与缩略图一致
        else:
            width_candidates = [content_width + 2 * h_padding]
            if self.reply_container:
                width_candidates.append(reply_size.width() + 2 * h_padding)
            if self.message_text_edit:
                width_candidates.append(message_size.width() + 2 * h_padding)
            base_width = max(width_candidates)
            bubble_width = int(min(base_width, chat_area_max))

        # 计算气泡高度
        top_margin = v_padding
        reply_gap = v_padding if self.reply_container else 0
        message_gap = v_padding if self.message_text_edit else 0
        extra_height = self.progress_bar.height() if (self.progress_bar and self.progress_bar.isVisible()) else 0
        bubble_height = (top_margin +
                         (reply_size.height() if self.reply_container else 0) +
                         reply_gap +
                         content_size.height() +
                         (message_size.height() + message_gap if self.message_text_edit else 0) +
                         extra_height)
        bubble_size = QSize(bubble_width, bubble_height)
        return bubble_size, content_size, time_size, content_width, reply_size

    def updateBubbleSize(self) -> None:
        bubble_size, content_size, time_size, content_width, reply_size = self._calculateSizes()
        base_offset = 0 if self.align == "right" else self.config.triangle_size
        bx = base_offset + (1 if self.is_current_user else -1)

        # 更新气泡矩形
        self._bubble_rect = QRect(bx, 0, bubble_size.width(), bubble_size.height())
        h_padding, v_padding = self._getPadding()
        top_margin = v_padding
        reply_gap = v_padding if self.reply_container else 0

        # 计算回复容器位置
        if self.reply_container:
            reply_x = bx + h_padding
            self.reply_container.setFixedSize(reply_size)
            self.reply_container.move(reply_x, top_margin)
            y_offset = top_margin + reply_size.height() + reply_gap
        else:
            y_offset = top_margin

        # 计算内容位置
        if self.align == "right":
            content_x = bx + h_padding
        else:
            content_x = bx + h_padding if self.message_type != 'file' else bx + bubble_size.width() - content_width - h_padding
        content_y = y_offset
        self.content_widget.move(int(content_x), int(content_y))
        self.content_widget.setFixedSize(int(content_width), int(content_size.height()))

        # 计算附加消息位置
        message_y_offset = content_y + content_size.height()
        if self.message_text_edit:
            # 获取消息尺寸
            doc = self.message_text_edit.document()
            message_width = int(doc.idealWidth())
            message_height = int(doc.size().height())  # 正确计算消息高度
            # 判断是否为短消息
            is_short = self._is_short_message(message_width)
            # 动态设置对齐方式
            alignment = Qt.AlignRight if (self.align == "left" and is_short) else Qt.AlignLeft
            self.message_text_edit.setAlignment(alignment)
            # 调整X坐标
            message_x = bx + h_padding
            if self.align == "left" and is_short:
                message_x = bx + self._bubble_rect.width() - message_width - h_padding
            # 应用坐标和尺寸
            self.message_text_edit.move(int(message_x), int(message_y_offset))
            self.message_text_edit.setFixedSize(message_width, message_height)  # 使用已计算的message_height
            # 更新偏移量（修正变量名）
            message_y_offset += message_height  # 使用 += 代替错误变量名
        # 计算时间戳或进度条位置
        total_content_height = message_y_offset if self.message_text_edit else content_y + content_size.height()
        time_y = total_content_height
        # 根据消息来源调整时间戳位置
        if self.is_current_user:
            time_x = bx + h_padding  # 自己发送：靠左
        else:
            time_x = bx + bubble_size.width() - time_size.width() - h_padding  # 他人发送：靠右
        # 检查时间戳是否超出气泡高度
        required_height = time_y + time_size.height() + v_padding
        if required_height > bubble_size.height():
            bubble_size.setHeight(required_height)
            self._bubble_rect.setHeight(required_height)
        if self.progress_bar and self.progress_bar.isVisible():
            self.label_time.hide()
            self.progress_bar.move(int(content_x), int(time_y))
            self.progress_bar.setFixedWidth(int(content_width))
            self.progress_bar.show()
        else:
            self.label_time.show()
            self.label_time.move(int(time_x), int(time_y))
            self.label_time.setFixedSize(time_size)
            if self.progress_bar:
                self.progress_bar.hide()

        # 更新缩略图和播放按钮（保持不变）
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
        new_height = bubble_size.height()
        if self.progress_bar and self.progress_bar.isVisible():
            new_height += self.progress_bar.height() + v_padding
        new_size = QSize(bubble_size.width() + self.config.triangle_size, new_height)
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
            result = await self.window().client.download_media(file_id, save_path, progress_callback)
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
        try:
            os.makedirs(self.VIDEO_CACHE_DIR, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法创建视频目录: {e}")
            return

        save_path = os.path.join(self.VIDEO_CACHE_DIR, f"{self.original_file_name or file_id}.mp4")
        if os.path.exists(save_path):
            try:
                if os.path.getsize(save_path) > 0:
                    os.startfile(save_path)
                    return
                else:
                    os.remove(save_path)
            except Exception as e:
                QMessageBox.warning(self, "警告", f"缓存视频无效，将重新下载: {e}")
                os.remove(save_path) if os.path.exists(save_path) else None

        original_type = self.message_type
        self.message_type = 'video'
        await self._download_media_common(file_id, save_path, lambda: os.startfile(save_path), "视频")
        self.message_type = original_type

    def _is_short_message(self, message_width: int) -> bool:
        bubble_width = self._bubble_rect.width() - 2 * self.config.h_padding
        return message_width < bubble_width * 0.6  # 60%宽度为阈值

    async def download_media_file(self):
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
        config = download_configs.get(self.message_type, download_configs['file'])
        save_path, _ = QFileDialog.getSaveFileName(self, config['title'], config['default_name'], config['filter'])
        if not save_path:
            return

        async def success_callback():
            # 对于文件类型仅提示成功，不做打开操作
            if self.message_type == 'file':
                self.file = self.DOWNLOAD_LABELS.get('file', '文件')

        await self._download_media_common(self.file_id, save_path, success_callback, self.DOWNLOAD_LABELS.get(self.message_type, "文件"))

    def show_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        if self.message_type == 'text':
            selected_text = self.content_widget.textCursor().selectedText()
            copy_label = "复制选中" if selected_text else "复制"
            copy_action = menu.addAction(copy_label)
            copy_action.triggered.connect(self.copy_text)
        if self.message_type in self.DOWNLOAD_LABELS:
            label = self.DOWNLOAD_LABELS.get(self.message_type, "文件")
            download_action = menu.addAction(f"下载{label}")
            download_action.triggered.connect(lambda: asyncio.create_task(self.download_media_file()))
        reply_action = menu.addAction("回复")
        reply_action.triggered.connect(self.reply_to_message)

        # 添加删除选项（仅当有 rowid 时显示）
        if self.rowid is not None:
            delete_action = menu.addAction("删除")
            delete_action.triggered.connect(lambda: asyncio.create_task(self.delete_message()))

        if menu.actions():
            StyleGenerator.apply_style(self, "menu")
            menu.exec_(self.mapToGlobal(pos))

    async def delete_message(self) -> None:
        """删除当前消息，带有风格化确认弹窗，并使用 FloatingLabel 显示提示"""
        chat_window = self.window()
        if not hasattr(chat_window, 'client') or not self.rowid:
            QMessageBox.critical(self, "错误", "无法删除消息：客户端未初始化或消息ID缺失")
            return

        # 创建普通 QMessageBox
        msg_box = QMessageBox(self)
        self._msg_box = msg_box  # 保存引用以便 update_theme 使用
        msg_box.setWindowTitle("确认删除")
        msg_box.setText("您确定要删除这条消息吗？此操作无法撤销。")
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)

        # 设置中文按钮并应用样式
        yes_button = msg_box.button(QMessageBox.Yes)
        yes_button.setFixedSize(30, 18)
        no_button = msg_box.button(QMessageBox.No)
        no_button.setFixedSize(30, 18)
        yes_button.setText("是")
        no_button.setText("否")

        # 应用当前主题样式
        t = theme_manager.current_theme
        msg_box.setStyleSheet(f"QLabel {{ color: {t['dialog_text_color']}; }}")
        StyleGenerator.apply_style(yes_button, "button", extra="border-radius: 5px;")
        StyleGenerator.apply_style(no_button, "button", extra="border-radius: 5px;")

        # 执行弹窗
        reply = msg_box.exec_()

        # 弹窗关闭后清除引用
        self._msg_box = None

        if reply == QMessageBox.No:
            return

        # 调用 ChatClient 的 delete_messages 方法
        resp = await chat_window.client.delete_messages(self.rowid)
        if resp.get("status") == "success":
            # 删除成功，从界面移除气泡
            self.remove_from_chat_area()
            # 获取 ChatAreaWidget 作为父级
            chat_area = chat_window.chat_components.get('area_widget')
            if chat_area:
                floating_label = FloatingLabel("消息已删除", chat_area)
                floating_label.show()
                floating_label.raise_()  # 确保显示在最上层
                print(f"FloatingLabel created with parent: {chat_area}")
            else:
                print("ChatAreaWidget not found, falling back to QMessageBox")
                QMessageBox.information(self, "提示", "消息已删除（无法显示浮动提示）")
        else:
            QMessageBox.critical(self, "错误", f"删除失败: {resp.get('message', '未知错误')}")

    def remove_from_chat_area(self) -> None:
        """从聊天区域移除当前气泡"""
        container = self.parent()
        if not container or not isinstance(container, QWidget):
            return

        chat_area = container.parent()
        if isinstance(chat_area, ChatAreaWidget):
            # 从布局中移除容器
            chat_area.layout().removeWidget(container)
            # 从 bubble_containers 列表中移除
            if container in chat_area.bubble_containers:
                chat_area.bubble_containers.remove(container)
            # 从 active_bubbles 中移除（如果存在）
            chat_window = self.window()
            if hasattr(chat_window, 'active_bubbles') and self.rowid in chat_window.active_bubbles:
                del chat_window.active_bubbles[self.rowid]
            # 删除容器及其子控件
            container.deleteLater()
            # 更新聊天区域
            chat_area.update()
            # 调整滚动条
            if chat_window.chat_components.get('scroll'):
                chat_window.adjust_scroll()

    def on_image_clicked(self, event) -> None:
        if event.button() != Qt.LeftButton or not self.file_id:
            return

        chat_window = self.window()
        if not hasattr(chat_window, 'show_image_viewer'):
            return

        # 定义完整图像缓存路径
        try:
            os.makedirs(self.IMAGE_CACHE_DIR, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法创建图片目录: {e}")
            return

        image_path = os.path.join(self.IMAGE_CACHE_DIR, f"{self.original_file_name or self.file_id}")

        # 检查缓存
        if os.path.exists(image_path):
            try:
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    chat_window.show_image_viewer(self.file_id, self.original_file_name)
                    return
                else:
                    os.remove(image_path)  # 删除无效缓存
            except Exception as e:
                QMessageBox.warning(self, "警告", f"缓存图片无效，将重新下载: {e}")
                os.remove(image_path) if os.path.exists(image_path) else None

        # 如果没有缓存，进行下载
        async def download_and_show():
            try:
                await self._download_media_common(
                    self.file_id,
                    image_path,
                    lambda: chat_window.show_image_viewer(self.file_id, self.original_file_name),
                    "图片"
                )
            except Exception as e:
                QMessageBox.critical(self, "错误", f"下载图片时发生错误: {e}")

        asyncio.create_task(download_and_show())

    def copy_text(self) -> None:
        if self.message_type == 'text' and hasattr(self, 'content_widget'):
            clipboard = QApplication.clipboard()
            selected_text = self.content_widget.textCursor().selectedText()
            if selected_text:
                clipboard.setText(selected_text)
            else:
                full_text = self.content_widget.toPlainText()
                if full_text:
                    clipboard.setText(full_text)
                else:
                    QMessageBox.information(self, "提示", "消息内容为空，无法复制")
        else:
            QMessageBox.critical(self, "错误", "无法复制：当前不是文本消息")

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
        if self._msg_box and not sip.isdeleted(self._msg_box):
            self._msg_box.setStyleSheet(f"QLabel {{ color: {theme['dialog_text_color']}; }}")