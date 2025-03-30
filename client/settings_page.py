import json
import logging
import os
import sys
from PyQt5.QtWidgets import QApplication, QFrame, QWidget, QHBoxLayout, QListWidget, QVBoxLayout, QLabel, \
    QListWidgetItem, QPushButton, QFileDialog, QLineEdit, QFormLayout, QStackedWidget, QCheckBox, QMessageBox, QComboBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QPainter
from Interface_Controls import StyleGenerator, theme_manager, FONTS, FloatingLabel


class SettingsFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Widget)
        self.setup_ui_style()
        self.create_title_bar()
        self.setup_main_layout()
        self.create_category_list()
        self.create_settings_area()
        self.create_all_pages()
        self.load_config_data()
        self.connect_all_signals()
        theme_manager.register(self)
        self.category_list.setFocus()
        self.category_list.setCurrentRow(0)  # 选中第一个项（显示设置）
        self.update_settings(self.category_list.currentItem(), None)

    def setup_ui_style(self):
        # 保持原始样式字符串格式
        self.setStyleSheet(f"""
            background-color: {theme_manager.current_theme['chat_bg']};
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            border-bottom-left-radius: 10px;
            border-bottom-right-radius: 10px;
        """)

    def create_title_bar(self):
        # 完全保持原始标题栏变量名和结构
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
                border-radius: 0;
            }
            QPushButton:hover {
                background-color: #4aa36c;
                border-radius: 12px;
                color: white;
            }
        """)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.close_button)

    def setup_main_layout(self):
        # 保持原始布局变量名
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.title_bar)

        self.content_widget = QWidget()
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.content_widget)

    def create_category_list(self):
        # 完全保持原始列表控件名称
        self.category_list = QListWidget()
        categories = ["显示设置", "声音设置", "网络设置", "通知设置", "其他设置"]
        for category in categories:
            item = QListWidgetItem(category)
            item.setFont(FONTS['settingClass'])
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.category_list.addItem(item)

        self.category_list.setMaximumWidth(120)
        self.category_list.verticalScrollBar().setStyleSheet(
            StyleGenerator._BASE_STYLES["scrollbar"].format(**theme_manager.current_theme)
        )
        self.category_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.category_list.setStyleSheet(f"""
                QListWidget {{
                    background-color: {theme_manager.current_theme['list_background']};
                    border-top-left-radius: 0;
                    border-top-right-radius: 0;
                    border-bottom-left-radius: 10px;
                    border-bottom-right-radius: 0;
                    color: {theme_manager.current_theme['font_color']};
                    outline: none;
                }}
                QListWidget::item {{
                    padding: 8px 10px;
                    color: {theme_manager.current_theme['font_color']};
                    border: none;
                    border-bottom: 1px solid #808080;  /* 添加底部横线 */
                    width: 100px;  /* 设置宽度为 100px */
                }}
                QListWidget::item:selected {{
                    background-color: #4aa36c;
                    color: white;
                    border: none;
                }}
                QListWidget::item:hover {{
                    background-color: {theme_manager.current_theme['list_item_selected']};  /* 悬浮时的背景色 */
                }}
                QListWidget::item:selected:focus {{
                    outline: none;
                }}
            """)
        self.content_layout.addWidget(self.category_list)

    def create_settings_area(self):
        # 保持原始设置区域变量名
        self.settings_area = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_area)
        self.settings_layout.setContentsMargins(10, 10, 10, 10)

        self.stacked_widget = QStackedWidget()
        self.settings_layout.addWidget(self.stacked_widget)
        self.content_layout.addWidget(self.settings_area)

    def create_all_pages(self):
        self.create_display_settings_page()
        self.sound_settings_widget = QWidget()
        self.network_settings_widget = QWidget()
        self.create_notification_page()
        self.create_other_settings_page()

        self.stacked_widget.addWidget(self.display_settings_widget)
        self.stacked_widget.addWidget(self.sound_settings_widget)
        self.stacked_widget.addWidget(self.network_settings_widget)
        self.stacked_widget.addWidget(self.notification_settings_widget)
        self.stacked_widget.addWidget(self.other_settings_widget)

    def create_display_settings_page(self):
        """创建显示设置页面，包含主题选择下拉框"""
        self.display_settings_widget = QWidget()
        display_layout = QFormLayout(self.display_settings_widget)

        # 添加主题选择下拉框
        self.theme_label = QLabel("主题模式:")
        self.theme_label.setFont(QFont("微软雅黑", 10))
        StyleGenerator.apply_style(self.theme_label, "label")
        self.theme_combo = QComboBox()
        self.theme_combo.setFixedHeight(25)
        self.theme_combo.addItems(["浅色模式", "深色模式"])  # 添加选项
        current_mode = "浅色模式" if theme_manager.current_mode == "light" else "深色模式"
        self.theme_combo.setCurrentText(current_mode)  # 设置当前主题
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)  # 连接信号
        self.theme_combo.setFont(QFont("微软雅黑", 10) )
        StyleGenerator.apply_style(self.theme_combo, "combo_box")  # 应用样式（不包含字体设置）

        display_layout.addRow(self.theme_label, self.theme_combo)

    def on_theme_changed(self, theme_text):
        """处理主题切换"""
        mode = "light" if theme_text == "浅色模式" else "dark"
        if mode != theme_manager.current_mode:
            theme_manager.set_mode(mode)
            FloatingLabel(f"已切换到{theme_text}", self, x_offset_ratio=0.5, y_offset_ratio=5 / 6).show()

    def create_notification_page(self):
        # 保持原始通知设置变量名
        self.notification_settings_widget = QWidget()
        notification_layout = QFormLayout(self.notification_settings_widget)
        self.notification_checkbox = QCheckBox("启用通知")
        StyleGenerator.apply_style(self.notification_checkbox, "checkbox")
        self.notification_checkbox.setChecked(True)
        notification_layout.addWidget(self.notification_checkbox)

    def create_other_settings_page(self):
        self.other_settings_widget = QWidget()
        other_layout = QVBoxLayout(self.other_settings_widget)
        other_layout.setContentsMargins(10, 10, 10, 10)
        other_layout.setSpacing(10)

        # 缓存路径部分
        self.cache_path_label = QLabel("缓存路径:")
        self.cache_path_label.setFont(QFont("微软雅黑", 10))
        StyleGenerator.apply_style(self.cache_path_label, "label")

        self.cache_path_edit = QLineEdit()
        self.cache_path_edit.setFont(QFont("微软雅黑", 10))
        self.cache_path_edit.setFixedHeight(25)
        StyleGenerator.apply_style(self.cache_path_edit, "line_edit")
        self.cache_path_edit.setReadOnly(True)

        self.browse_button = QPushButton("浏览")
        StyleGenerator.apply_style(self.browse_button, "button", extra = "border-radius: 5px;")
        self.browse_button.setFixedSize(50, 20)

        cache_path_layout = QHBoxLayout()
        cache_path_layout.addWidget(self.cache_path_edit)
        cache_path_layout.addWidget(self.browse_button)

        # 将标签和输入框组合在一行
        cache_row_layout = QHBoxLayout()
        cache_row_layout.addWidget(self.cache_path_label)
        cache_row_layout.addLayout(cache_path_layout)
        other_layout.addLayout(cache_row_layout)

        # 添加伸缩项，确保退出按钮在底部
        other_layout.addStretch()

        # 添加退出登录按钮
        self.logout_button = QPushButton("退出登录")
        self.logout_button.setFixedSize(120, 30)
        StyleGenerator.apply_style(self.logout_button, "button", extra="border-radius: 4px;")
        self.logout_button.clicked.connect(self.parent().parent().on_logout)
        other_layout.addWidget(self.logout_button, alignment=Qt.AlignCenter)

        # 注册主题管理器
        theme_manager.register(self.cache_path_edit)
        theme_manager.register(self.cache_path_label)
        theme_manager.register(self.logout_button)

    def load_config_data(self):
        # 保持原始配置加载逻辑
        config_dir = os.path.join(os.path.dirname(__file__), "Chat_DATA", "config")
        config_path = os.path.join(config_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding='utf-8') as f:
                config = json.load(f)
            cache_path = config.get("cache_path", os.path.join(os.path.dirname(__file__), "Chat_DATA"))
            notifications_enabled = config.get("notifications_enabled", True)
            self.notification_checkbox.setChecked(notifications_enabled)
        else:
            cache_path = os.path.join(os.path.dirname(__file__), "Chat_DATA")
            self.notification_checkbox.setChecked(True)
        self.cache_path_edit.setText(cache_path)

    def connect_all_signals(self):
        # 保持原始信号连接方式
        self.category_list.currentItemChanged.connect(self.update_settings)
        self.close_button.clicked.connect(self.parent().close)
        self.browse_button.clicked.connect(self.browse_cache_path)
        self.notification_checkbox.stateChanged.connect(self.on_notification_toggle)

    def update_settings(self, current, previous):
        # 保持原始页面切换逻辑
        if current:
            category = current.text()
            if category == "显示设置":
                self.stacked_widget.setCurrentWidget(self.display_settings_widget)
            elif category == "声音设置":
                self.stacked_widget.setCurrentWidget(self.sound_settings_widget)
            elif category == "网络设置":
                self.stacked_widget.setCurrentWidget(self.network_settings_widget)
            elif category == "通知设置":
                self.stacked_widget.setCurrentWidget(self.notification_settings_widget)
            elif category == "其他设置":
                self.stacked_widget.setCurrentWidget(self.other_settings_widget)

    def save_config(self, **kwargs):
        # 保持原始配置保存方法
        config_dir = os.path.join(os.path.dirname(__file__), "Chat_DATA", "config")
        config_path = os.path.join(config_dir, "config.json")

        os.makedirs(config_dir, exist_ok=True)
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding='utf-8') as f:
                    config = json.load(f)
            except Exception as e:
                logging.error(f"读取配置文件失败: {e}")

        for key, value in kwargs.items():
            if config.get(key) != value:
                config[key] = value

        try:
            with open(config_path, "w", encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存配置文件失败: {e}")
            raise

    def browse_cache_path(self):
        # 保持原始路径选择逻辑
        new_path = QFileDialog.getExistingDirectory(self, "选择缓存目录", self.cache_path_edit.text())
        if new_path:
            self.cache_path_edit.setText(new_path)
            try:
                self.save_config(cache_path=new_path)
                FloatingLabel("缓存路径已更改，请重启应用以应用新设置。", self, x_offset_ratio=0.5,
                              y_offset_ratio=5 / 6).show()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

    def on_notification_toggle(self, state):
        # 保持原始通知开关处理
        try:
            self.save_config(notifications_enabled=bool(state))
            status = "开启" if state else "关闭"
            FloatingLabel(f"通知已{status}", self, x_offset_ratio=0.5, y_offset_ratio=5 / 6).show()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

    def adjust_size(self, parent_size):
        # 保持原始尺寸调整逻辑
        q1_width = parent_size.width()
        q1_height = parent_size.height()
        q2_width = int(q1_width * 0.7)
        q2_height = int(q1_height * 0.7)
        self.resize(q2_width, q2_height)
        self.move((q1_width - q2_width) // 2, (q1_height - q2_height) // 2)

    def update_theme(self, theme: dict):
        self.setStyleSheet(f"""
            background-color: {theme['chat_bg']};
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
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
        self.category_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {theme['list_background']};
                border-top-left-radius: 0;
                border-top-right-radius: 0;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 0;
                color: {theme['font_color']};
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px 10px;
                color: {theme['font_color']};
                border: none;
            }}
            QListWidget::item:selected {{
                background-color: #4aa36c;
                color: white;
                border: none;
            }}
            QListWidget::item:selected:focus {{
                outline: none;
            }}
        """)
        self.title_label.setStyleSheet(f"color: {theme['font_color']}; font-weight: bold;")
        StyleGenerator.apply_style(self.cache_path_label, "label")
        StyleGenerator.apply_style(self.notification_checkbox, "checkbox")
        StyleGenerator.apply_style(self.theme_label, "label")
        StyleGenerator.apply_style(self.theme_combo, "combo_box")
        StyleGenerator.apply_style(self.cache_path_edit, "line_edit")


class SettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 保持原始窗口设置
        self.setWindowFlags(Qt.FramelessWindowHint)
        if parent:
            self.resize(parent.size())
        self.q2 = SettingsFrame(self)

    def mousePressEvent(self, event):
        # 保持原始点击事件处理
        if not self.q2.geometry().contains(event.pos()):
            self.close()

    def resizeEvent(self, event):
        # 保持原始尺寸事件处理
        if self.q2:
            self.q2.adjust_size(self.size())
        super().resizeEvent(event)

    def paintEvent(self, event):
        # 保持原始绘制逻辑
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        super().paintEvent(event)

    def keyPressEvent(self, event):
        # 保持原始按键处理
        if event.key() == Qt.Key_Escape:
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)