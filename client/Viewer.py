import asyncio
import os
from typing import Optional

from PyQt5 import sip
from PyQt5.QtCore import QPoint, Qt, QRect
from PyQt5.QtGui import QPainter, QColor, QPixmap
from PyQt5.QtWidgets import QLabel, QWidget, QSizePolicy, QVBoxLayout, QPushButton, QFileDialog, QApplication, \
    QMessageBox, QMenu

from Interface_Controls import StyleGenerator, FloatingLabel

LOADING_TEXT = '<span style="color: white; font-family: Microsoft YaHei; font-size: 10pt;">加载中...</span>'


class DraggableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.offset = QPoint(0, 0)
        self.dragging = False
        self.last_pos = QPoint(0, 0)
        self._pixmap = QPixmap()
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: transparent;")

    def setPixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self._pixmap.isNull():
            viewport_center = self.rect().center()
            pixmap_center = self._pixmap.rect().center()
            x = viewport_center.x() - pixmap_center.x() + self.offset.x()
            y = viewport_center.y() - pixmap_center.y() + self.offset.y()
            painter.drawPixmap(x, y, self._pixmap)
        else:
            super().paintEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._pixmap.isNull():
            pixmap_rect = self._pixmap.rect()
            pixmap_rect.moveCenter(self.rect().center() + self.offset)
            if pixmap_rect.contains(event.pos()):
                self.dragging = True
                self.last_pos = event.pos()
            else:
                if self.parent() and hasattr(self.parent(), 'hide_viewer'):
                    self.parent().hide_viewer()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging and not self._pixmap.isNull():
            delta = event.pos() - self.last_pos
            self.last_pos = event.pos()
            new_offset = self.offset + delta
            self.offset = self.clamp_offset(new_offset)
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.dragging = False
        super().mouseReleaseEvent(event)

    def clamp_offset(self, offset: QPoint) -> QPoint:
        viewport = self.rect()
        pixmap_width = self._pixmap.width()
        pixmap_height = self._pixmap.height()

        # 如果图片小于视口，居中
        if pixmap_width <= viewport.width():
            offset.setX(0)
        else:
            max_x = (pixmap_width - viewport.width()) // 2
            offset.setX(max(-max_x, min(max_x, offset.x())))

        if pixmap_height <= viewport.height():
            offset.setY(0)
        else:
            max_y = (pixmap_height - viewport.height()) // 2
            offset.setY(max(-max_y, min(max_y, offset.y())))

        return offset

    def resetOffset(self):
        self.offset = QPoint(0, 0)
        self.update()


class ImageViewer(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.image_list = []
        self.current_index = -1
        self.original_pixmap = QPixmap()  # 原始未缩放的图片
        self.scale_factor = 1.0  # 缩放比例，初始为1.0
        self.loading = False
        self.scroll_area = None

        self._init_ui()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.image_label = DraggableLabel(self)
        layout.addWidget(self.image_label)

        self.prev_button = QPushButton("<", self)
        self.prev_button.setFixedSize(50, 50)
        StyleGenerator.apply_style(self.prev_button, "button", extra="border-radius: 25px;")
        self.prev_button.clicked.connect(self.show_prev_image)

        self.next_button = QPushButton(">", self)
        self.next_button.setFixedSize(50, 50)
        StyleGenerator.apply_style(self.next_button, "button", extra="border-radius: 25px;")
        self.next_button.clicked.connect(self.show_next_image)

        self.close_button = QPushButton("×", self)
        self.close_button.setFixedSize(30, 30)
        StyleGenerator.apply_style(self.close_button, "button", extra="border-radius: 15px;")
        self.close_button.clicked.connect(self.hide_viewer)

        self.setLayout(layout)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        super().paintEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 保留按钮位置调整逻辑
        button_y = (self.height() - 50) // 2
        self.prev_button.move(10, button_y)
        self.next_button.move(self.width() - 60, button_y)
        self.close_button.move(self.width() - 40, 10)
        self.update_image()

    def update_image(self):
        if not self.original_pixmap.isNull():
            viewport = self.image_label.size()
            orig_width = self.original_pixmap.width()
            orig_height = self.original_pixmap.height()

            # 计算适合视口的最小缩放比例：最长边等于视口对应边
            longest_side = max(orig_width, orig_height)
            if longest_side == orig_width:
                min_scale = viewport.width() / orig_width
            else:
                min_scale = viewport.height() / orig_height

            # 使用当前缩放比例，但不得小于 min_scale
            effective_scale = max(min_scale, self.scale_factor)

            # 计算缩放后的尺寸
            scaled_width = int(orig_width * effective_scale)
            scaled_height = int(orig_height * effective_scale)
            scaled_pixmap = self.original_pixmap.scaled(
                scaled_width, scaled_height,
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.offset = self.image_label.clamp_offset(self.image_label.offset)

    def wheelEvent(self, event):
        if not self.loading and not self.original_pixmap.isNull():
            # 计算鼠标在图片上的相对位置
            viewport_center = self.image_label.rect().center()
            pixmap = self.image_label._pixmap
            pixmap_center = pixmap.rect().center()
            pixmap_x = viewport_center.x() - pixmap_center.x() + self.image_label.offset.x()
            pixmap_y = viewport_center.y() - pixmap_center.y() + self.image_label.offset.y()
            rel_x = (event.pos().x() - pixmap_x) / self.scale_factor
            rel_y = (event.pos().y() - pixmap_y) / self.scale_factor

            # 计算最小缩放比例
            viewport = self.image_label.size()
            orig_width = self.original_pixmap.width()
            orig_height = self.original_pixmap.height()
            longest_side = max(orig_width, orig_height)
            min_scale = (viewport.width() / orig_width if longest_side == orig_width
                        else viewport.height() / orig_height)

            # 更新缩放比例
            delta = event.angleDelta().y()
            if delta > 0:
                self.scale_factor = min(5.0, self.scale_factor + 0.2)
            elif delta < 0:
                self.scale_factor = max(min_scale, self.scale_factor - 0.2)

            self.update_image()
            new_pixmap = self.image_label._pixmap
            new_pixmap_x = viewport_center.x() - new_pixmap.width() // 2
            new_pixmap_y = viewport_center.y() - new_pixmap.height() // 2
            self.image_label.offset = QPoint(
                int(viewport_center.x() - rel_x * self.scale_factor - new_pixmap_x),
                int(viewport_center.y() - rel_y * self.scale_factor - new_pixmap_y)
            )
            self.image_label.offset = self.image_label.clamp_offset(self.image_label.offset)
            self.image_label.update()
            event.accept()

    def set_image_list(self, image_list, start_index):
        self.image_list = image_list
        self.current_index = start_index
        self.scale_factor = 1.0  # 初始值，实际由 update_image 调整
        self.update_buttons()
        self.original_pixmap = QPixmap()
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(LOADING_TEXT)
        self.image_label.resetOffset()
        asyncio.create_task(self.load_image())

    async def load_image(self):
        if self.current_index < 0 or self.current_index >= len(self.image_list):
            return
        self.loading = True
        self.original_pixmap = QPixmap()
        self.image_label.setPixmap(QPixmap())
        file_id, original_file_name = self.image_list[self.current_index]
        client = self.window().client
        image_dir = os.path.join(client.cache_root, "images")  # 使用 chat_client.py 的 cache_root
        os.makedirs(image_dir, exist_ok=True)
        save_path = os.path.join(image_dir, original_file_name or file_id)  # 不强制加 .jpg

        try:
            if not os.path.exists(save_path):  # 检查缓存，避免重复下载
                result = await client.download_media(file_id, save_path, "image")
                if result.get("status") != "success":
                    self.image_label.setText("图片加载失败")
                    self.original_pixmap = QPixmap()
                    return
            self.original_pixmap = QPixmap(save_path)
            if not self.original_pixmap.isNull() and self.original_pixmap.height() > 0:
                viewport = self.image_label.size()
                orig_width = self.original_pixmap.width()
                orig_height = self.original_pixmap.height()
                longest_side = max(orig_width, orig_height)
                self.scale_factor = (viewport.width() / orig_width if longest_side == orig_width
                                     else viewport.height() / orig_height)
                self.update_image()
            else:
                self.image_label.setText("图片加载失败")
                self.original_pixmap = QPixmap()
        except Exception as e:
            self.image_label.setText(f"加载错误: {str(e)}")
            self.original_pixmap = QPixmap()
        finally:
            self.loading = False

    def show_prev_image(self):
        if self.current_index < len(self.image_list) - 1 and not self.loading:
            self.current_index += 1
            self.scale_factor = 1.0
            self.update_buttons()
            asyncio.create_task(self.load_image())

    def show_next_image(self):
        if self.current_index > 0 and not self.loading:
            self.current_index -= 1
            self.scale_factor = 1.0
            self.update_buttons()
            asyncio.create_task(self.load_image())

    def update_buttons(self):
        self.prev_button.setEnabled(self.current_index < len(self.image_list) - 1)
        self.next_button.setEnabled(self.current_index > 0)

    def hide_viewer(self):
        self.image_label.resetOffset()
        self.hide()
        if self.scroll_area and not sip.isdeleted(self.scroll_area):
            if hasattr(self, '_previous_scroll_value'):
                self.scroll_area.verticalScrollBar().setValue(self._previous_scroll_value)
            self.scroll_area.verticalScrollBar().setEnabled(True)
            self.scroll_area.horizontalScrollBar().setEnabled(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.original_pixmap.isNull():
            pixmap = self.image_label._pixmap
            offset_x = (self.image_label.width() - pixmap.width()) // 2 + self.image_label.offset.x()
            offset_y = (self.image_label.height() - pixmap.height()) // 2 + self.image_label.offset.y()
            pixmap_rect = QRect(offset_x, offset_y, pixmap.width(), pixmap.height())
            click_pos = self.image_label.mapFromParent(event.pos())
            if not pixmap_rect.contains(click_pos):
                self.hide_viewer()
                return
        super().mousePressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        self.update_image()

    def keyPressEvent(self, event):
        """处理键盘事件，支持 ESC 键关闭和左右键翻页"""
        if event.key() == Qt.Key_Escape:
            self.hide_viewer()
            event.accept()
        elif event.key() == Qt.Key_Left and not self.loading:
            # 左键显示上一张图片
            if self.current_index < len(self.image_list) - 1:
                self.show_prev_image()
            event.accept()
        elif event.key() == Qt.Key_Right and not self.loading:
            # 右键显示下一张图片
            if self.current_index > 0:
                self.show_next_image()
            event.accept()
        else:
            super().keyPressEvent(event)

    def show_context_menu(self, pos: QPoint) -> None:
        if self.original_pixmap.isNull() or self.loading:
            return
        menu = QMenu(self)
        copy_action = menu.addAction("复制图片")
        copy_action.triggered.connect(self.copy_image_to_clipboard)
        download_action = menu.addAction("下载图片")
        download_action.triggered.connect(self.download_image)
        StyleGenerator.apply_style(menu, "menu")
        menu.exec_(self.mapToGlobal(pos))

    def copy_image_to_clipboard(self) -> None:
        """将当前图片复制到剪贴板"""
        if not self.original_pixmap.isNull():
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(self.original_pixmap)
            # 使用 FloatingLabel 显示提示
            floating_label = FloatingLabel("图片已复制到剪贴板", self)
            floating_label.show()
            floating_label.raise_()

    def download_image(self) -> None:
        """下载当前图片到本地"""
        if not self.original_pixmap.isNull() and self.current_index >= 0:
            file_id, original_file_name = self.image_list[self.current_index]
            default_name = original_file_name or f"image_{file_id}.jpg"
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存图片",
                default_name,
                "图片文件 (*.jpg, *.jpeg, *.png, *.gif, *.bmp, *.webp, *.tiff, *.ico)"
            )
            if save_path:
                try:
                    if self.original_pixmap.save(save_path):
                        QMessageBox.information(self, "成功", "图片已保存")
                    else:
                        QMessageBox.critical(self, "错误", "保存图片失败")
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"保存图片时发生错误: {str(e)}")