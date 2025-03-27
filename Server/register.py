#!/usr/bin/env python3
import random
import string
import socket

from captcha.image import ImageCaptcha
import base64
from io import BytesIO
from threading import Lock
import os
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import logging
import bcrypt
from time import time

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

# 全局变量
BASE_DIR = "user_data"
captcha_sessions = {}  # 存储验证码会话
captcha_lock = Lock()
TTL = 300  # 验证码和会话有效期5分钟


def get_db_connection():
    """获取数据库连接，与主文件保持一致"""
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='Aa112211',
            database='chat_server',
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return conn
    except Error as e:
        logging.error(f"数据库连接失败: {e}")
        return None


def generate_username():
    """生成8-10位随机数字的用户名"""
    length = random.randint(8, 10)
    return ''.join(random.choices("0123456789", k=length))


def generate_captcha_image():
    """生成图形验证码"""
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))  # 增加到6位
    image = ImageCaptcha(width=200, height=80, fonts=None)  # 增大尺寸，增加可读性
    captcha_data = image.generate(captcha_text)
    buffered = BytesIO()
    image.write(captcha_text, buffered)
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return captcha_text, img_base64


def user_register(request: dict, client_sock: socket.socket) -> dict:
    """处理用户注册请求"""
    subtype = request.get("subtype")
    request_id = request.get("request_id")
    session_id = request.get("session_id", str(random.randint(100000, 999999)))  # 用于跟踪会话

    # 清理过期会话
    with captcha_lock:
        current_time = time()
        expired = [sid for sid, data in captcha_sessions.items() if current_time - data["created_at"] > TTL]
        for sid in expired:
            del captcha_sessions[sid]

    if subtype == "register_1":
        # 第一次请求：生成用户名和验证码
        username = generate_username()
        while True:  # 确保用户名唯一
            conn = get_db_connection()
            if not conn:
                return {"type": "user_register", "subtype": subtype, "status": "error",
                        "message": "数据库连接失败", "request_id": request_id}
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
                if not cursor.fetchone():
                    break
                username = generate_username()
            finally:
                conn.close()

        captcha_text, captcha_img = generate_captcha_image()
        with captcha_lock:
            captcha_sessions[session_id] = {
                "username": username,
                "captcha": captcha_text,
                "created_at": time(),
                "verified": False
            }

        response = {
            "type": "user_register",
            "subtype": subtype,
            "status": "success",
            "username": username,
            "captcha_image": captcha_img,
            "session_id": session_id,
            "request_id": request_id
        }
        return response

    elif subtype == "register_2":
        # 验证验证码
        session_id = request.get("session_id")
        user_captcha = request.get("captcha_input")

        if not user_captcha:
            return {"type": "user_register", "subtype": subtype, "status": "error",
                    "message": "验证码输入缺失", "request_id": request_id}

        with captcha_lock:
            if session_id not in captcha_sessions:
                return {"type": "user_register", "subtype": subtype, "status": "error",
                        "message": "会话无效", "request_id": request_id}
            session = captcha_sessions[session_id]
            current_time = time()
            if current_time - session["created_at"] > TTL:
                del captcha_sessions[session_id]
                return {"type": "user_register", "subtype": subtype, "status": "error",
                        "message": "会话已过期", "request_id": request_id}
            if user_captcha.upper() != session["captcha"]:
                # 验证失败，重新生成验证码
                captcha_text, captcha_img = generate_captcha_image()
                session["captcha"] = captcha_text
                session["created_at"] = current_time  # 重置时间
                return {
                    "type": "user_register",
                    "subtype": subtype,
                    "status": "fail",
                    "message": "验证码错误",
                    "captcha_image": captcha_img,
                    "session_id": session_id,
                    "request_id": request_id
                }
            # 验证成功
            session["verified"] = True
            response = {
                "type": "user_register",
                "subtype": subtype,
                "status": "success",
                "message": "验证码验证成功",
                "username": session["username"],
                "session_id": session_id,
                "request_id": request_id
            }
            return response

    if subtype == "register_3":
        # 提交用户信息
        session_id = request.get("session_id")
        password = request.get("password")
        avatar_data = request.get("avatar_data", "")  # base64编码的头像数据，可为空
        nickname = request.get("nickname", "")       # 可为空
        sign = request.get("sign", "")              # 可为空

        if not password or len(password) < 8 or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
            return {"type": "user_register", "subtype": subtype, "status": "error",
                    "message": "密码必须至少8位，包含大写字母和数字", "request_id": request_id}

        with captcha_lock:
            if session_id not in captcha_sessions or not captcha_sessions[session_id]["verified"]:
                return {"type": "user_register", "subtype": subtype, "status": "error",
                        "message": "会话无效或未验证", "request_id": request_id}
            if time() - captcha_sessions[session_id]["created_at"] > TTL:
                del captcha_sessions[session_id]
                return {"type": "user_register", "subtype": subtype, "status": "error",
                        "message": "会话已过期", "request_id": request_id}
            username = captcha_sessions[session_id]["username"]

        # 不使用哈希，直接使用明文密码
        # 原代码：hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        # 修改为直接使用 password
        plain_password = password

        # 头像处理，限制大小为2MB
        avatar_path = ""
        avatar_id = ""
        if avatar_data:
            try:
                file_data = base64.b64decode(avatar_data)
                if len(file_data) > 2 * 1024 * 1024:  # 2MB限制
                    return {"type": "user_register", "subtype": subtype, "status": "error",
                            "message": "头像文件不得超过5MB", "request_id": request_id}
                avatar_dir = os.path.join(BASE_DIR, "avatars")
                os.makedirs(avatar_dir, exist_ok=True)
                avatar_id = f"{username}_avatar_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.jpg"
                avatar_path = os.path.join(avatar_dir, avatar_id)
                with open(avatar_path, "wb") as f:
                    f.write(file_data)
            except Exception as e:
                logging.error(f"头像保存失败: {e}")
                avatar_path = ""
                avatar_id = ""

        conn = get_db_connection()
        if not conn:
            return {"type": "user_register", "subtype": subtype, "status": "error",
                    "message": "数据库连接失败", "request_id": request_id}

        try:
            cursor = conn.cursor()
            cursor.execute(''' 
                INSERT INTO users (username, password, avatars, avatar_path, names, signs)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (username, plain_password, avatar_id, avatar_path, nickname, sign))  # 使用明文密码
            conn.commit()
            with captcha_lock:
                del captcha_sessions[session_id]  # 清理会话
            return {
                "type": "user_register",
                "subtype": subtype,
                "status": "success",
                "message": "注册成功",
                "username": username,
                "request_id": request_id
            }
        except Error as e:
            logging.error(f"注册失败: {e}")
            return {"type": "user_register", "subtype": subtype, "status": "error",
                    "message": "注册失败", "request_id": request_id}
        finally:
            conn.close()

    elif subtype == "register_4":
        # 重新生成验证码
        session_id = request.get("session_id")
        with captcha_lock:
            if session_id not in captcha_sessions:
                return {"type": "user_register", "subtype": subtype, "status": "error",
                        "message": "会话无效", "request_id": request_id}
            if time() - captcha_sessions[session_id]["created_at"] > TTL:
                del captcha_sessions[session_id]
                return {"type": "user_register", "subtype": subtype, "status": "error",
                        "message": "会话已过期", "request_id": request_id}
            captcha_text, captcha_img = generate_captcha_image()
            captcha_sessions[session_id]["captcha"] = captcha_text
            captcha_sessions[session_id]["created_at"] = time()  # 重置时间
        return {
            "type": "user_register",
            "subtype": subtype,
            "status": "success",
            "captcha_image": captcha_img,
            "session_id": session_id,
            "request_id": request_id
        }

    return {"type": "user_register", "subtype": subtype, "status": "error",
            "message": "未知的子类型", "request_id": request_id}