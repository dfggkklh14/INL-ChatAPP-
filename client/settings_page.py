import sys
from PyQt5.QtWidgets import QApplication, QFrame, QWidget, QHBoxLayout, QListWidget, QVBoxLayout, QLabel, QListWidgetItem, QPushButton
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QPainter
from Interface_Controls import StyleGenerator, theme_manager, FONTS  # 引入主题和样式管理及字体常量


class SettingsFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置 QFrame 仅左下角和右下角为圆角，其它角为 0
        self.setWindowFlags(Qt.Widget)
        self.setStyleSheet(f"""
            background-color: {theme_manager.current_theme['chat_bg']};
            border-top-left-radius: 0;
            border-top-right-radius: 0;
            border-bottom-left-radius: 10px;
            border-bottom-right-radius: 10px;
        """)

        # 标题栏部分：仅左上角和右上角为圆角，其它角为 0
        self.title_bar = QWidget(self)
        self.title_bar.setFixedHeight(30)
        self.title_bar.setStyleSheet(f"""
            background-color: {theme_manager.current_theme['list_background']};
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            border-bottom-left-radius: 0;
            border-bottom-right-radius: 0;
        """)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(5, 0, 5, 0)

        self.title_label = QLabel("设置")
        self.title_label.setStyleSheet(f"color: {theme_manager.current_theme['font_color']}; font-weight: bold;")
        self.title_label.setFont(QFont("微软雅黑", 10))

        self.close_button = QPushButton("×", self.title_bar)
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                color: #808080;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
                text-align: center;
                border-radius: 0;  /* 明确无圆角 */
            }
            QPushButton:hover {
                background-color: #4aa36c;
                border-radius: 12px;
                color: white;
            }
        """)
        self.close_button.clicked.connect(self.parent().close)

        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.close_button)

        if parent:
            self.adjust_size(parent.size())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.title_bar)

        # 内容区域
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.category_list = QListWidget()
        categories = ["显示设置", "声音设置", "网络设置", "其他设置"]
        for category in categories:
            item = QListWidgetItem(category)
            item.setFont(FONTS['USERNAME'])
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.category_list.addItem(item)

        self.category_list.setMaximumWidth(180)
        StyleGenerator.apply_style(self.category_list, "list_widget")
        self.category_list.verticalScrollBar().setStyleSheet(
            StyleGenerator._BASE_STYLES["scrollbar"].format(**theme_manager.current_theme)
        )
        self.category_list.setSpacing(5)
        # 设置大类列表仅左下角为圆角，其它角明确设置为 0
        self.category_list.setStyleSheet(
            self.category_list.styleSheet() +
            "border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 10px; border-bottom-right-radius: 0;"
        )

        self.settings_area = QWidget()
        settings_layout = QVBoxLayout(self.settings_area)
        settings_layout.setContentsMargins(10, 10, 10, 10)
        self.settings_label = QLabel("请选择左侧的设置类别")
        self.settings_label.setAlignment(Qt.AlignCenter)
        StyleGenerator.apply_style(self.settings_label, "label")
        settings_layout.addWidget(self.settings_label)

        content_layout.addWidget(self.category_list)
        content_layout.addWidget(self.settings_area)
        main_layout.addWidget(content_widget)

        self.category_list.currentItemChanged.connect(self.update_settings)
        theme_manager.register(self)
        self.category_list.setFocus()

    def adjust_size(self, parent_size):
        q1_width = parent_size.width()
        q1_height = parent_size.height()
        q2_width = int(q1_width * 0.7)
        q2_height = int(q1_height * 0.7)
        self.resize(q2_width, q2_height)
        self.move((q1_width - q2_width) // 2, (q1_height - q2_height) // 2)

    def update_settings(self, current, previous):
        if current:
            self.settings_label.setText(f"当前选择: {current.text()} 的详细设置")

    def update_theme(self, theme: dict):
        StyleGenerator.apply_style(self.category_list, "list_widget")
        self.category_list.verticalScrollBar().setStyleSheet(
            StyleGenerator._BASE_STYLES["scrollbar"].format(**theme)
        )
        StyleGenerator.apply_style(self.settings_label, "label")
        self.setStyleSheet(f"""
            background-color: {theme['chat_bg']};
            border-top-left-radius: 0;
            border-top-right-radius: 0;
            border-bottom-left-radius: 10px;
            border-bottom-right-radius: 10px;
        """)
        self.title_bar.setStyleSheet(f"""
            background-color: {theme['list_background']};
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            border-bottom-left-radius: 0;
            border-bottom-right-radius: 0;
        """)
        self.title_label.setStyleSheet(f"color: {theme['font_color']}; font-weight: bold;")
        self.close_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                color: #808080;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
                text-align: center;
                border-radius: 0;
            }
            QPushButton:hover {
                background-color: #4aa36c;
                border-radius: 12px;
                color: white;
            }
        """)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.parent():
                self.parent().keyPressEvent(event)
            event.ignore()  # 阻止 QFrame 默认关闭行为
        else:
            super().keyPressEvent(event)


class SettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint)
        if parent:
            self.resize(parent.size())
        self.q2 = SettingsFrame(self)

    def mousePressEvent(self, event):
        if not self.q2.geometry().contains(event.pos()):
            self.close()

    def resizeEvent(self, event):
        if self.q2:
            self.q2.adjust_size(self.size())
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        super().paintEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)
