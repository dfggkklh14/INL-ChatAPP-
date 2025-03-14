import math
import os
from typing import List, Optional, Tuple

from PyQt5 import sip
from PyQt5.QtCore import Qt, QSize, QEvent
from PyQt5.QtGui import QColor, QPainter, QPixmap, QIcon
from PyQt5.QtWidgets import QLabel, QDialog, QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QGridLayout, QApplication

from Interface_Controls import StyleGenerator, theme_manager, FONTS, style_text_edit, generate_thumbnail, resource_path
from MessageInput import CustomTextEdit, EmoticonPopup


class FileConfirmDialog(QDialog):
    MAX_GRID_ROWS = 3
    SPACING = 2

    def __init__(self, file_paths: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._update_content_width()
        self._validate_file_paths()
        self._init_ui()
        self._adjust_size_and_position()
        if self.parent():
            self.parent().installEventFilter(self)

    def _validate_file_paths(self) -> None:
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.ico'}
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
        image_count = 0
        file_count = 0
        filtered_paths = []
        for path in self.file_paths:
            ext = os.path.splitext(path)[1].lower()
            if ext in image_extensions:
                if image_count < 9:
                    image_count += 1
                    filtered_paths.append(path)
            elif ext in video_extensions:
                filtered_paths.append(path)
            else:
                if file_count < 5:
                    file_count += 1
                    filtered_paths.append(path)
        self.file_paths = filtered_paths[:5] if file_count > 0 else filtered_paths[:9]

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.content_widget = QWidget(self)
        self.content_widget.setFixedWidth(self.CONTENT_WIDTH)
        self.content_widget.setStyleSheet("background: transparent")
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.file_display_layout = QVBoxLayout()
        self.file_display_layout.setContentsMargins(5, 5, 0, 0)
        self._populate_file_display()
        content_layout.addLayout(self.file_display_layout)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 5, 0, 0)
        input_layout.setSpacing(0)

        self.emoticon_button = QPushButton("😊")
        self.emoticon_button.setFixedSize(45, 35)
        StyleGenerator.apply_style(self.emoticon_button, "button", extra="border-bottom-left-radius: 10px;")
        self.emoticon_button.clicked.connect(self.show_emoticon_popup)

        self.text_edit = CustomTextEdit()
        self.text_edit.setFont(FONTS['MESSAGE'])
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlaceholderText("输入附加消息（可选）")
        self.text_edit.setFixedHeight(35)
        style_text_edit(self.text_edit)
        self.text_edit.sendMessage.connect(self.accept)
        theme_manager.register(self.text_edit)

        self.send_button = QPushButton("发送")
        self.send_button.setFixedSize(45, 35)
        StyleGenerator.apply_style(self.send_button, "button", extra="border-bottom-right-radius: 10px;")
        self.send_button.clicked.connect(self.accept)

        input_layout.addWidget(self.emoticon_button)
        input_layout.addWidget(self.text_edit, 1)
        input_layout.addWidget(self.send_button)

        content_layout.addLayout(input_layout)
        main_layout.addStretch()
        main_layout.addWidget(self.content_widget, 0, Qt.AlignHCenter)
        main_layout.addStretch()

        self.popup = None

    def _update_content_width(self) -> None:
        """根据窗口宽度动态更新 CONTENT_WIDTH，最小值为 300"""
        if self.parent() and isinstance(self.parent(), QWidget):
            window_width = self.parent().width()
        else:
            window_width = QApplication.desktop().screenGeometry().width()

        if window_width < 500:
            self.CONTENT_WIDTH = 300
        else:
            calculated_width = int(window_width * 0.35)
            self.CONTENT_WIDTH = max(300, calculated_width)

        if hasattr(self, 'content_widget'):
            self.content_widget.setFixedWidth(self.CONTENT_WIDTH)

    def _populate_file_display(self) -> None:
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.ico'}
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
        is_all_images = all(os.path.splitext(p)[1].lower() in image_extensions for p in self.file_paths)
        if not is_all_images:
            # 非纯图片情况：单行显示，缩略图大小为 60x60，等比放大尽量填满容器，调整对齐
            self.file_display_layout.setSpacing(5)  # 设置每个项之间的垂直间距为 5
            for file_path in self.file_paths:
                ext = os.path.splitext(file_path)[1].lower()
                file_layout = QHBoxLayout()
                file_layout.setContentsMargins(0, 0, 0, 0)
                file_layout.setSpacing(5)

                # 缩略图容器
                icon_label = QLabel()
                icon_label.setFixedSize(60, 60)  # 固定为 60x60
                if ext in image_extensions or ext in video_extensions:
                    thumbnail_path = generate_thumbnail(file_path, 'image' if ext in image_extensions else 'video')
                    if thumbnail_path and os.path.exists(thumbnail_path):
                        pixmap = QPixmap(thumbnail_path).scaled(60, 60, Qt.KeepAspectRatioByExpanding,
                                                                Qt.SmoothTransformation)
                        icon_label.setPixmap(pixmap)
                    else:
                        icon_label.setText("缩略图不可用")
                else:
                    pixmap = QIcon(resource_path("icon/file_icon.ico")).pixmap(60, 60)
                    icon_label.setPixmap(pixmap)
                icon_label.setStyleSheet("background: transparent; border: none;")
                icon_label.setAlignment(Qt.AlignCenter)  # 居中显示

                # 文件信息容器（垂直布局：文件名 + 文件大小）
                file_info_layout = QVBoxLayout()
                file_info_layout.setContentsMargins(0, 0, 0, 0)
                file_info_layout.setSpacing(0)  # 文件名和文件大小间距设为 0

                # 文件名（下对齐）
                name_label = QLabel(os.path.basename(file_path))
                name_label.setFont(FONTS['FILE_NAME'])
                StyleGenerator.apply_style(name_label, "label")
                file_info_layout.addWidget(name_label, alignment=Qt.AlignBottom)

                # 文件大小（上对齐，根据大小选择单位）
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)  # 转换为 MB
                if file_size_mb < 0.01:  # 小于 0.01 MB 时显示为 KB
                    file_size_kb = os.path.getsize(file_path) / 1024  # 转换为 KB
                    size_label = QLabel(f"{file_size_kb:.2f} KB")
                else:
                    size_label = QLabel(f"{file_size_mb:.2f} MB")
                size_label.setFont(FONTS['FILE_SIZE'])
                StyleGenerator.apply_style(size_label, "label")
                file_info_layout.addWidget(size_label, alignment=Qt.AlignTop)

                file_layout.addWidget(icon_label)
                file_layout.addLayout(file_info_layout)
                file_layout.addStretch()
                self.file_display_layout.addLayout(file_layout)
        else:
            # 纯图片情况：保持原有网格布局不变
            available_width = self.CONTENT_WIDTH - 20
            n = len(self.file_paths)
            columns, rows, thumb_size = self._get_grid_configuration(n, available_width, self.SPACING)
            grid_layout = QGridLayout()
            grid_layout.setContentsMargins(0, 0, 0, 0)
            grid_layout.setSpacing(self.SPACING)
            for i, file_path in enumerate(self.file_paths):
                thumbnail_label = QLabel()
                thumbnail_label.setAlignment(Qt.AlignCenter)
                thumbnail_path = generate_thumbnail(file_path, 'image')
                if thumbnail_path and os.path.exists(thumbnail_path):
                    pixmap = QPixmap(thumbnail_path).scaled(thumb_size, thumb_size, Qt.KeepAspectRatio,
                                                            Qt.SmoothTransformation)
                    thumbnail_label.setPixmap(pixmap)
                else:
                    thumbnail_label.setText("缩略图不可用")
                thumbnail_label.setFixedSize(thumb_size, thumb_size)
                row = i // columns
                col = i % columns
                grid_layout.addWidget(thumbnail_label, row, col, Qt.AlignCenter)
            self.file_display_layout.addLayout(grid_layout)
            self.file_display_layout.addStretch()

    def _get_grid_configuration(self, n: int, available_width: int, spacing: int = 2) -> Tuple[int, int, int]:
        max_cols = 3
        columns = min(n, max_cols)
        rows = math.ceil(n / columns)
        thumb_size = (available_width - (columns - 1) * spacing) // columns
        return columns, rows, thumb_size

    def _adjust_size_and_position(self) -> None:
        """调整对话框大小和位置，确保实时同步父窗口并防止溢出"""
        if self.parent() and isinstance(self.parent(), QWidget):
            parent = self.parent()
            # 使用最新的父窗口矩形
            parent_rect = parent.rect()
            global_pos = parent.mapToGlobal(parent_rect.topLeft())

            # 计算 content_widget 高度
            content_height = self.content_widget.sizeHint().height()

            # 设置对话框大小覆盖整个父窗口
            self.setGeometry(global_pos.x(), global_pos.y(), parent_rect.width(), parent_rect.height())

            # 更新 CONTENT_WIDTH
            self._update_content_width()
            self.content_widget.setFixedWidth(self.CONTENT_WIDTH)

            # 居中 content_widget 并防止溢出
            x = max(0, (parent_rect.width() - self.CONTENT_WIDTH) // 2)  # 确保 x 不为负
            y = (parent_rect.height() - content_height) // 2
            # 检查边界，确保 content_widget 不超出父窗口
            x = min(x, parent_rect.width() - self.CONTENT_WIDTH)  # 限制右侧溢出
            y = max(0, min(y, parent_rect.height() - content_height))  # 限制顶部和底部溢出
            self.content_widget.setFixedHeight(content_height)
            self.content_widget.move(x, y)
        else:
            # 无父窗口时，居中于屏幕
            screen = QApplication.desktop().screenGeometry()
            content_height = self.content_widget.sizeHint().height()
            self.setGeometry(
                (screen.width() - self.CONTENT_WIDTH) // 2,
                (screen.height() - content_height) // 2,
                self.CONTENT_WIDTH,
                content_height
            )

    def sizeHint(self) -> QSize:
        base_height = 45
        file_count = len(self.file_paths)
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.ico'}
        if file_count > 0 and all(os.path.splitext(p)[1].lower() in image_extensions for p in self.file_paths):
            available_width = self.CONTENT_WIDTH - 20
            _, rows, thumb_size = self._get_grid_configuration(file_count, available_width, self.SPACING)
            display_rows = min(rows, self.MAX_GRID_ROWS)
            grid_height = display_rows * thumb_size + (display_rows - 1) * self.SPACING
            return QSize(self.CONTENT_WIDTH, base_height + grid_height)
        else:
            return QSize(self.CONTENT_WIDTH, base_height + file_count * 65)

    def show_emoticon_popup(self) -> None:
        self.popup = EmoticonPopup(self)
        self.popup.emoticonClicked.connect(self.insert_emoticon)
        btn_pos = self.emoticon_button.mapToGlobal(self.emoticon_button.rect().topLeft())
        self.popup.move(btn_pos.x(), btn_pos.y() - self.popup.height())
        self.popup.show()

    def insert_emoticon(self, emo: str) -> None:
        cursor = self.text_edit.textCursor()
        cursor.insertText(emo)
        self.text_edit.setTextCursor(cursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        content_rect = self.content_widget.geometry()
        bubble_color = theme_manager.current_theme["Confirm_bg"]
        painter.setBrush(bubble_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(content_rect, 10, 10)
        super().paintEvent(event)

    def eventFilter(self, obj, event):
        """监听父窗口变化并立即更新"""
        if obj == self.parent():
            if event.type() == QEvent.Resize:
                self._update_content_width()  # 更新宽度
                self._adjust_size_and_position()  # 立即调整位置和大小
                self.update()  # 强制重绘
            elif event.type() == QEvent.Move:
                self._adjust_size_and_position()  # 移动时调整位置
        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:
        """处理对话框关闭事件，确保清理"""
        if self.popup and not sip.isdeleted(self.popup):
            self.popup.close()
        theme_manager.unregister(self)  # 从主题管理器中移除
        super().closeEvent(event)

    def update_theme(self, theme: dict) -> None:
        self.update()  # 重绘以更新圆角矩形颜色
        StyleGenerator.apply_style(self.text_edit, "text_edit")  # 手动更新样式
        StyleGenerator.apply_style(self.emoticon_button, "button", extra="border-bottom-left-radius: 10px;")
        StyleGenerator.apply_style(self.send_button, "button", extra="border-bottom-right-radius: 10px;")
        for i in range(self.file_display_layout.count()):
            item = self.file_display_layout.itemAt(i)
            if item and item.layout():
                layout = item.layout()
                for j in range(layout.count()):
                    widget = layout.itemAt(j).widget()
                    if isinstance(widget, QLabel):
                        StyleGenerator.apply_style(widget, "label")