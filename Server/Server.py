#!/usr/bin/env python3
import sqlite3
import socket
import threading
import json
from datetime import datetime
import logging
import os
import base64

import imageio
from PIL import Image
from cryptography.fernet import Fernet

# 配置日志记录
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

# 配置
SERVER_CONFIG = {
    'HOST': '26.102.137.22',
    'PORT': 13746,
    'DB_PATH': r'D:\AppTests\fy\chat_server.db',
    'LOGGING': {
        'LEVEL': logging.DEBUG,
        'FORMAT': '%(asctime)s %(levelname)s: %(message)s'
    }
}

# 加密密钥（双方必须共享相同密钥），这里使用预生成的密钥示例
ENCRYPTION_KEY = b'JZ-fJzE7kZDhSyvxCL6odNCB7cP3SdBAnjHR3d2LhcI='
fernet = Fernet(ENCRYPTION_KEY)

# 全局变量：存储已登录用户与对应的 socket，以及上传会话
clients = {}
upload_sessions = {}
clients_lock = threading.Lock()


def get_db_connection() -> sqlite3.Connection:
    """建立并返回数据库连接（开启 WAL 模式）"""
    try:
        conn = sqlite3.connect(SERVER_CONFIG['DB_PATH'], timeout=10, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL')
        return conn
    except sqlite3.Error as e:
        logging.error(f"数据库连接失败: {e}")
        return None


def init_db():
    """初始化数据库，创建必要的表并确保包含 avatars 和 avatar_path 字段"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn:
            cursor = conn.cursor()
            # 创建或更新 users 表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT,
                    avatars TEXT,          -- 头像文件名
                    avatar_path TEXT,      -- 头像完整路径（服务器内部使用）
                    names TEXT,            -- 昵称
                    signs TEXT             -- 个性签名
                )
            ''')
            # 创建或更新 friends 表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS friends (
                    username TEXT,
                    friend TEXT,
                    Remarks TEXT,          -- 好友的备注
                    PRIMARY KEY(username, friend),
                    FOREIGN KEY(username) REFERENCES users(username),
                    FOREIGN KEY(friend) REFERENCES users(username)
                )
            ''')
            # 创建 messages 表（保持不变）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    sender TEXT,
                    receiver TEXT,
                    message TEXT,
                    write_time TEXT,
                    attachment_type TEXT,
                    attachment_path TEXT,
                    original_file_name TEXT,
                    thumbnail_path TEXT,
                    file_size INTEGER,
                    duration REAL,
                    reply_to INTEGER,
                    reply_preview TEXT,
                    FOREIGN KEY(sender) REFERENCES users(username),
                    FOREIGN KEY(receiver) REFERENCES users(username),
                    FOREIGN KEY(reply_to) REFERENCES messages(rowid)
                )
            ''')
    except sqlite3.Error as e:
        logging.error(f"数据库初始化失败: {e}")
    finally:
        conn.close()


def generate_reply_preview(reply_to_id: int) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sender, message, attachment_type, original_file_name 
        FROM messages 
        WHERE rowid = ?
    ''', (reply_to_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        sender, message, attachment_type, original_file_name = row
        if attachment_type and original_file_name:
            content = f"[{attachment_type}]: {original_file_name}"
        else:
            content = message if message else "空消息"
        return {"sender": sender, "content": content}
    return None  # 如果未找到消息，返回 None


def recv_all(sock: socket.socket, length: int) -> bytes:
    """确保接收指定长度的数据"""
    data = b""
    while len(data) < length:
        packet = sock.recv(length - len(data))
        if not packet:
            return None
        data += packet
    return data


def send_response(client_sock: socket.socket, response: dict):
    """发送响应数据到客户端，并使用 Fernet 加密"""
    try:
        plaintext = json.dumps(response, ensure_ascii=False).encode('utf-8')
        ciphertext = fernet.encrypt(plaintext)
        length_header = len(ciphertext).to_bytes(4, byteorder='big')
        client_sock.sendall(length_header + ciphertext)
    except Exception as e:
        logging.error(f"发送响应失败: {e}")


def update_user_profile(request: dict, client_sock: socket.socket) -> dict:
    req_type = request.get("type")
    username = request.get("username")  # 用户的唯一标识符，不变
    request_id = request.get("request_id")

    # 使用更明确的变量名，避免与 username 混淆
    new_sign = request.get("sign") if req_type == "update_sign" else None
    new_nickname = request.get("new_name") if req_type == "update_name" else None  # 表示昵称 (names)
    file_data_b64 = request.get("file_data") if req_type == "upload_avatar" else None

    conn = get_db_connection()
    if not conn:
        return {"type": req_type, "status": "error", "message": "数据库连接失败", "request_id": request_id}

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, avatars, avatar_path, signs FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            if not user:
                return {"type": req_type, "status": "error", "message": "用户不存在", "request_id": request_id}

            current_username, current_avatar, current_avatar_path, current_sign = user

            # 处理头像上传
            if req_type == "upload_avatar" and file_data_b64:
                avatar_dir = os.path.join("user_data", "avatars")
                os.makedirs(avatar_dir, exist_ok=True)
                original_file_name = f"{username}_avatar_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.jpg"
                avatar_path = os.path.join(avatar_dir, original_file_name)
                try:
                    file_data = base64.b64decode(file_data_b64)
                    with open(avatar_path, "wb") as f:
                        f.write(file_data)
                    logging.debug(f"保存头像成功: {avatar_path}")
                except Exception as e:
                    logging.error(f"保存头像失败: {e}")
                    return {"type": req_type, "status": "error", "message": "头像保存失败", "request_id": request_id}

            # 构建更新字段的 SQL
            update_fields = []
            update_values = []
            if new_sign is not None:
                update_fields.append("signs = ?")
                update_values.append(new_sign)
            if new_nickname is not None:
                update_fields.append("names = ?")  # 只更新昵称字段
                update_values.append(new_nickname)
            if 'original_file_name' in locals():  # 检查是否已定义，避免未上传头像时的错误
                update_fields.append("avatars = ?")
                update_fields.append("avatar_path = ?")
                update_values.extend([original_file_name, avatar_path])

            if update_fields:
                sql = f"UPDATE users SET {', '.join(update_fields)} WHERE username = ?"
                update_values.append(username)
                cursor.execute(sql, tuple(update_values))
                conn.commit()
                logging.debug(f"数据库更新成功，类型: {req_type}, 用户: {username}")

    except sqlite3.Error as e:
        logging.error(f"更新用户信息失败: {e}")
        return {"type": req_type, "status": "error", "message": "数据库更新失败", "request_id": request_id}
    finally:
        conn.close()

    # 返回响应
    response = {
        "type": req_type,
        "status": "success",
        "message": "更新成功",
        "request_id": request_id
    }
    if req_type == "upload_avatar" and 'original_file_name' in locals():
        response["avatar_id"] = original_file_name
    return response

# 新增 update_friend_remarks 方法
def update_friend_remarks(request: dict, client_sock: socket.socket) -> dict:
    username = request.get("username")
    friend = request.get("friend")
    remarks = request.get("remarks")
    request_id = request.get("request_id")

    conn = get_db_connection()
    if not conn:
        return {"type": "Update_Remarks", "status": "error", "message": "数据库连接失败", "request_id": request_id}

    try:
        with conn:
            cursor = conn.cursor()
            # 检查好友关系是否存在
            cursor.execute("SELECT * FROM friends WHERE username = ? AND friend = ?", (username, friend))
            if not cursor.fetchone():
                return {"type": "Update_Remarks", "status": "error", "message": f"{friend} 不是您的好友",
                        "request_id": request_id}
            # 更新 Remarks 字段
            cursor.execute("UPDATE friends SET Remarks = ? WHERE username = ? AND friend = ?",
                          (remarks, username, friend))
            conn.commit()
            logging.debug(f"更新好友备注成功，用户: {username}, 好友: {friend}, 备注: {remarks}")
    except sqlite3.Error as e:
        logging.error(f"更新好友备注失败: {e}")
        return {"type": "Update_Remarks", "status": "error", "message": "更新备注失败", "request_id": request_id}
    finally:
        conn.close()

    response = {
        "type": "Update_Remarks",
        "status": "success",
        "message": f"已将 {friend} 的备注更新为 {remarks}",
        "request_id": request_id,
        "friend": friend,
        "remarks": remarks
    }
    return response


def push_friends_list(username: str):
    conn = get_db_connection()
    if not conn:
        logging.error("数据库连接失败，无法推送好友列表")
        return
    try:
        with conn:
            cursor = conn.cursor()
            # 从 friends 表获取好友列表
            cursor.execute("""
                SELECT f.friend, f.Remarks 
                FROM friends f 
                WHERE f.username = ?
            """, (username,))
            friend_rows = cursor.fetchall()

            # 准备好友信息列表
            friends = []
            for friend_username, remarks in friend_rows:
                # 从 users 表获取 avatar_id、name 和 sign
                cursor.execute("""
                    SELECT avatars, names, signs 
                    FROM users 
                    WHERE username = ?
                """, (friend_username,))
                user_info = cursor.fetchone()

                avatar_id = user_info[0] if user_info and user_info[0] else ""  # 处理 NULL
                name = user_info[1] if user_info and user_info[1] else friend_username  # 如果 names 为空，使用 username
                sign = user_info[2] if user_info and user_info[2] else ""  # 获取个性签名，处理 NULL

                # 根据 remarks 是否为空决定推送的显示名称
                display_name = remarks if remarks else name

                friends.append({
                    "username": friend_username,
                    "avatar_id": avatar_id,
                    "name": display_name,
                    "sign": sign,  # 新增 sign 字段
                    "online": friend_username in clients
                })
    except Exception as e:
        logging.error(f"获取好友列表失败: {e}")
        return
    finally:
        conn.close()

    with clients_lock:
        if username in clients:
            response = {
                "type": "friend_list_update",
                "status": "success",
                "friends": friends
            }
            try:
                send_response(clients[username], response)
                logging.debug(f"推送好友列表给 {username}: {response}")
            except Exception as e:
                logging.error(f"推送好友列表给 {username} 失败: {e}")


def push_friends_update(username: str):
    """
    主动推送好友列表更新：
      - 向 username 推送其好友列表（如果在线）
      - 向所有把 username 作为好友的在线用户推送好友列表更新
    """
    push_friends_list(username)
    conn = get_db_connection()
    if not conn:
        logging.error("数据库连接失败，无法获取相关好友信息")
        return
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM friends WHERE friend = ?", (username,))
            related_users = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"获取相关好友列表失败: {e}")
        related_users = []
    finally:
        conn.close()
    for user in related_users:
        push_friends_list(user)


def authenticate(request: dict, client_sock: socket.socket) -> dict:
    username = request.get("username")
    password = request.get("password")
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        return {"type": "authenticate", "status": "error", "message": "数据库连接失败", "request_id": request_id}
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            result = cursor.fetchone()
    except Exception as e:
        logging.error(f"数据库查询失败: {e}")
        result = None
    finally:
        conn.close()
    if result:
        with clients_lock:
            if username in clients:
                logging.info(f"用户 {username} 已经登录，拒绝重复登录")
                return {"type": "authenticate", "status": "fail", "message": "该账号已登录", "request_id": request_id}
            clients[username] = client_sock
        logging.info(f"用户 {username} 认证成功")
        return {"type": "authenticate", "status": "success", "message": "认证成功", "request_id": request_id}
    else:
        logging.info(f"用户 {username} 账号或密码错误")
        return {"type": "authenticate", "status": "fail", "message": "账号或密码错误", "request_id": request_id}


def send_message(request: dict, client_sock: socket.socket) -> dict:
    from_user = request.get("from")
    to_user = request.get("to")
    message = request.get("message")
    reply_to = request.get("reply_to")
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    request_id = request.get("request_id")

    # 仅当 reply_to 存在时生成 reply_preview
    reply_preview = None
    if reply_to is not None:
        reply_preview_data = generate_reply_preview(reply_to)
        if reply_preview_data:
            reply_preview = json.dumps(reply_preview_data, ensure_ascii=False)
        else:
            reply_preview = json.dumps({"sender": "未知用户", "content": "消息不可用"}, ensure_ascii=False)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (sender, receiver, message, write_time, reply_to, reply_preview)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (from_user, to_user, message, current_time, reply_to, reply_preview))
    rowid = cursor.lastrowid
    conn.commit()
    conn.close()

    push_response = {
        "type": "new_message",
        "from": from_user,
        "to": to_user,
        "message": message,
        "write_time": current_time,
        "reply_to": reply_to,
        "reply_preview": reply_preview,
        "rowid": rowid
    }
    if to_user in clients:
        send_response(clients[to_user], push_response)

    return {
        "type": "send_message",
        "status": "success",
        "message": f"消息已发送给 {to_user}",
        "request_id": request_id,
        "rowid": rowid,
        "reply_to": reply_to,
        "reply_preview": reply_preview
    }

def send_media(request: dict, client_sock: socket.socket) -> dict:
    logging.debug(f"Received send_media request: {request}")
    from_user = request.get("from")
    to_user = request.get("to")
    original_file_name = request.get("file_name")
    file_type = request.get("file_type")
    message = request.get("message", "")  # 新增：支持文本消息，默认为空
    reply_to = request.get("reply_to")  # 回复目标消息ID
    request_id = request.get("request_id")
    file_data_b64 = request.get("file_data", "")
    total_size = request.get("total_size", 0)
    sent_size = request.get("sent_size", 0)

    # 根据文件类型选择存储目录
    base_dir = "user_data"
    if file_type == "file":
        upload_dir = os.path.join(base_dir, "files")
    elif file_type == "image":
        upload_dir = os.path.join(base_dir, "images")
    elif file_type == "video":
        upload_dir = os.path.join(base_dir, "videos")
    else:
        upload_dir = os.path.join(base_dir, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # 如果是第一个分块或完整文件，生成唯一文件名并存储在会话中
    if request_id not in upload_sessions:
        unique_file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{original_file_name}"
        file_path = os.path.join(upload_dir, unique_file_name)
        upload_sessions[request_id] = {
            "file_path": file_path,
            "total_size": total_size,
            "received_size": 0,
            "unique_file_name": unique_file_name
        }
    session = upload_sessions[request_id]
    file_path = session["file_path"]
    unique_file_name = session["unique_file_name"]

    # 写入文件数据
    if file_data_b64:
        try:
            file_data = base64.b64decode(file_data_b64)
            with open(session["file_path"], "ab") as f:
                f.write(file_data)
            session["received_size"] += len(file_data)
            logging.debug(f"写入文件: path={session['file_path']}, size={len(file_data)}")
            return {"type": "send_media", "status": "success", "message": "分块接收中", "request_id": request_id}
        except Exception as e:
            logging.error(f"文件写入失败: {e}")
            return {"type": "send_media", "status": "error", "message": "文件写入失败", "request_id": request_id}
    else:
        # 分块传输完成，处理文件
        file_size = session["received_size"]
        thumbnail_path = ""
        duration = 0

        if not os.path.exists(file_path):
            logging.error(f"文件未找到: {file_path}")
            return {"type": "send_media", "status": "error", "message": "文件保存失败，路径未找到",
                    "request_id": request_id}

        if file_type == "image":
            try:
                image = Image.open(file_path)
                image.thumbnail((350, 350))
                thumbnail_filename = f"thumb_{unique_file_name}"
                thumbnail_path = os.path.join(upload_dir, thumbnail_filename)
                image.save(thumbnail_path, format=image.format)
                logging.debug(f"生成图片缩略图: {thumbnail_path}")
            except Exception as e:
                logging.error(f"生成缩略图失败: {e}")
        elif file_type == "video":
            try:
                reader = imageio.get_reader(file_path)
                frame = reader.get_data(0)
                thumb_image = Image.fromarray(frame)
                thumb_image.thumbnail((300, 300), Image.Resampling.NEAREST)
                thumbnail_filename = f"thumb_{unique_file_name}.jpg"
                thumbnail_path = os.path.join(upload_dir, thumbnail_filename)
                thumb_image.save(thumbnail_path, "JPEG")
                duration = reader.get_length() / reader.get_meta_data()['fps']
                reader.close()
                logging.debug(f"生成视频缩略图: {thumbnail_path}")
            except Exception as e:
                logging.error(f"视频处理失败: {e}")

        # 仅当 reply_to 存在时生成 reply_preview
        reply_preview = None
        if reply_to:
            reply_preview_data = generate_reply_preview(reply_to)
            if reply_preview_data:
                reply_preview = json.dumps(reply_preview_data, ensure_ascii=False)
            else:
                reply_preview = json.dumps({"sender": "未知用户", "content": "消息不可用"}, ensure_ascii=False)

        # 保存媒体消息到数据库，包括文本消息
        conn = get_db_connection()
        if not conn:
            return {"type": "send_media", "status": "error", "message": "数据库连接失败", "request_id": request_id}
        try:
            with conn:
                cursor = conn.cursor()
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                            INSERT INTO messages (sender, receiver, message, write_time, attachment_type, attachment_path, 
                                                  original_file_name, thumbnail_path, file_size, duration, reply_to, reply_preview)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (from_user, to_user, message, current_time, file_type, file_path, original_file_name,
                              thumbnail_path, file_size, duration, reply_to, reply_preview))
                rowid = cursor.lastrowid
                conn.commit()
        except sqlite3.Error as e:
            logging.error(f"保存媒体消息失败: {e}")
            return {"type": "send_media", "status": "error", "message": "保存失败", "request_id": request_id}
        finally:
            conn.close()

        # 推送给接收者
        push_payload = {
            "type": "new_media",
            "status": "success",
            "from": from_user,
            "to": to_user,
            "message": message,
            "original_file_name": original_file_name,
            "file_type": file_type,
            "file_id": unique_file_name,
            "write_time": current_time,
            "file_size": file_size,
            "duration": duration,
            "reply_to": reply_to,
            "reply_preview": reply_preview,
            "rowid": rowid
        }
        if thumbnail_path:
            push_payload["thumbnail_path"] = thumbnail_path

        with clients_lock:
            if to_user in clients:
                send_response(clients[to_user], push_payload)

        del upload_sessions[request_id]
        return {
            "type": "send_media",
            "status": "success",
            "message": f"{file_type} 已发送给 {to_user}",
            "request_id": request_id,
            "file_id": unique_file_name,
            "write_time": current_time,
            "duration": duration,
            "rowid": rowid,
            "reply_to": reply_to,
            "reply_preview": reply_preview,
            "text_message": message
        }

def get_chat_history_paginated(request: dict, client_sock: socket.socket) -> dict:
    """
    分页获取聊天记录，直接返回 reply_preview 字段，避免实时联表查询。
    客户端可以根据 reply_preview 显示回复预览。
    """
    username = request.get("username")
    friend = request.get("friend")
    page = request.get("page", 1)
    page_size = request.get("page_size", 20)
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        resp = {"type": "chat_history", "status": "error", "message": "数据库连接失败", "chat_history": [],
                "request_id": request_id}
        send_response(client_sock, resp)
        return resp
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT rowid, write_time, sender, receiver, message, attachment_type, attachment_path, 
                       original_file_name, thumbnail_path, file_size, duration, reply_to, reply_preview
                FROM messages
                WHERE (sender = ? AND receiver = ?) OR (sender = ? AND receiver = ?)
                ORDER BY write_time DESC, rowid DESC
                LIMIT ? OFFSET ?
            ''', (username, friend, friend, username, page_size, (page - 1) * page_size))
            rows = cursor.fetchall()
    except Exception as e:
        logging.error(f"查询聊天记录失败: {e}")
        rows = []
    finally:
        conn.close()
    history = []
    for row in rows:
        record = {
            "rowid": row[0],
            "write_time": row[1],
            "username": row[2],
            "friend_username": row[3],
            "message": row[4],
            "reply_to": row[11],
            "reply_preview": row[12]
        }
        if row[5]:
            record["attachment_type"] = row[5]
            record["file_id"] = os.path.basename(row[6])
            record["original_file_name"] = row[7]
            record["thumbnail_path"] = row[8]
            record["file_size"] = row[9]
            record["duration"] = row[10]
        history.append(record)
    resp = {"type": "chat_history", "status": "success", "chat_history": history, "request_id": request_id}
    send_response(client_sock, resp)
    return resp


def add_friend(request: dict, client_sock: socket.socket) -> dict:
    username = request.get("username")
    friend = request.get("friend")
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        return {"type": "add_friend", "status": "error", "message": "数据库连接失败", "request_id": request_id}
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (friend,))
            if cursor.fetchone() is None:
                return {"type": "add_friend", "status": "error", "message": f"用户 {friend} 不存在，无法添加",
                        "request_id": request_id}
            cursor.execute("SELECT * FROM friends WHERE username = ? AND friend = ?", (username, friend))
            if cursor.fetchone():
                return {"type": "add_friend", "status": "fail", "message": f"{friend} 已是您的好友",
                        "request_id": request_id}
            cursor.execute('INSERT INTO friends (username, friend) VALUES (?, ?)', (username, friend))
            cursor.execute('INSERT INTO friends (username, friend) VALUES (?, ?)', (friend, username))
            conn.commit()
            response = {"type": "add_friend", "status": "success", "message": f"{friend} 已添加为您的好友",
                        "request_id": request_id}
    except sqlite3.Error as e:
        logging.error(f"添加好友失败: {e}")
        response = {"type": "add_friend", "status": "error", "message": "添加好友失败", "request_id": request_id}
    finally:
        conn.close()
    if response.get("status") == "success":
        push_friends_update(username)
        push_friends_update(friend)
    return response


def handle_client(client_sock: socket.socket, client_addr):
    logging.info(f"客户端 {client_addr} 已连接")
    logged_in_user = None
    try:
        while True:
            header = recv_all(client_sock, 4)
            if not header:
                break
            msg_length = int.from_bytes(header, 'big')
            encrypted_data = recv_all(client_sock, msg_length)
            if not encrypted_data:
                break
            try:
                decrypted_data = fernet.decrypt(encrypted_data)
                request = json.loads(decrypted_data.decode('utf-8'))
                logging.debug(f"收到的请求：{request}")
            except Exception as e:
                logging.error(f"数据解密或JSON解析错误：{e}")
                send_response(client_sock, {"status": "error", "message": "Invalid request format"})
                continue

            req_type = request.get("type")
            if req_type == "authenticate":
                response = authenticate(request, client_sock)
                send_response(client_sock, response)
                if response.get("status") == "success":
                    logged_in_user = request.get("username")
                    push_friends_update(logged_in_user)
                continue
            elif req_type == "send_message":
                response = send_message(request, client_sock)
            elif req_type == "get_user_info":
                response = get_user_info(request, client_sock)
            elif req_type == "send_media":
                response = send_media(request, client_sock)
            elif req_type in ("upload_avatar", "update_sign", "update_name"):
                response = update_user_profile(request, client_sock)
            elif req_type == "download_media":
                download_media(request, client_sock)
                continue
            elif req_type == "get_chat_history_paginated":
                get_chat_history_paginated(request, client_sock)
                continue
            elif req_type == "add_friend":
                response = add_friend(request, client_sock)
            elif req_type == "Update_Remarks":  # 新增对 Update_Remarks 的处理
                response = update_friend_remarks(request, client_sock)
            elif req_type == "exit":
                response = {"type": "exit", "status": "success", "message": f"{request.get('username')} has exited",
                            "request_id": request.get("request_id")}
                send_response(client_sock, response)
                logging.info(f"客户端 {client_addr} 请求退出")
                break
            else:
                response = {"status": "error", "message": "Unknown request type",
                            "request_id": request.get("request_id")}

            if response:
                send_response(client_sock, response)
    except ConnectionResetError:
        logging.warning(f"客户端 {client_addr} 强制断开连接")
    except Exception as e:
        logging.error(f"处理客户端请求时出现异常： {e}")
    finally:
        if logged_in_user:
            with clients_lock:
                if logged_in_user in clients and clients[logged_in_user] == client_sock:
                    del clients[logged_in_user]
                    logging.info(f"用户 {logged_in_user} 已退出")
            push_friends_update(logged_in_user)
        else:
            with clients_lock:
                for user, sock in list(clients.items()):
                    if sock == client_sock:
                        del clients[user]
                        logging.info(f"用户 {user} 已退出")
                        break
        client_sock.close()
        logging.info(f"关闭连接：{client_addr}")


def get_user_info(request: dict, client_sock: socket.socket) -> dict:
    username = request.get("username")
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        return {"type": "get_user_info", "status": "error", "message": "数据库连接失败", "request_id": request_id}

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, avatars, names, signs FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            if user:
                avatar_id = user[1] if user[1] else ""  # 只返回文件名
                response = {
                    "type": "get_user_info",
                    "status": "success",
                    "username": user[0],
                    "avatar_id": avatar_id,
                    "name": user[2] if user[2] else user[0],
                    "sign": user[3] if user[3] else "",
                    "request_id": request_id
                }
            else:
                response = {"type": "get_user_info", "status": "error", "message": "用户不存在",
                            "request_id": request_id}
    except sqlite3.Error as e:
        logging.error(f"查询用户信息失败: {e}")
        response = {"type": "get_user_info", "status": "error", "message": "查询失败", "request_id": request_id}
    finally:
        conn.close()

    logging.debug(f"发送的信息响应: {response}")
    send_response(client_sock, response)
    return response

def download_media(request: dict, client_sock: socket.socket) -> dict:
    file_id = request.get("file_id")
    request_id = request.get("request_id")
    offset = request.get("offset", 0)

    conn = get_db_connection()
    if not conn:
        resp = {"type": "download_media", "status": "error", "message": "数据库连接失败", "request_id": request_id}
        send_response(client_sock, resp)
        return resp

    try:
        with conn:
            cursor = conn.cursor()
            # 先尝试从 messages 表查找
            cursor.execute("SELECT attachment_path FROM messages WHERE attachment_path LIKE ?", (f"%{file_id}",))
            result = cursor.fetchone()
            if result:
                file_path = result[0]
            else:
                # 如果 messages 表中未找到，从 users 表查找
                cursor.execute("SELECT avatar_path FROM users WHERE avatars = ?", (file_id,))
                result = cursor.fetchone()
                file_path = result[0] if result else None
            logging.debug(f"查询文件: file_id={file_id}, file_path={file_path}")
    except sqlite3.Error as e:
        logging.error(f"查询文件路径失败: {e}")
        file_path = None
    finally:
        conn.close()

    if not file_path or not os.path.exists(file_path):
        logging.error(f"文件不存在: file_id={file_id}, path={file_path}")
        resp = {"type": "download_media", "status": "error", "message": f"文件不存在: {file_id}",
                "request_id": request_id}
        send_response(client_sock, resp)
        return resp

    file_size = os.path.getsize(file_path)
    chunk_size = 1024 * 1024  # 1MB

    try:
        with open(file_path, "rb") as f:
            f.seek(offset)
            chunk = f.read(chunk_size)
            if not chunk:
                resp = {"type": "download_media", "status": "success", "file_data": "", "file_size": file_size,
                        "offset": offset, "is_complete": True, "request_id": request_id}
            else:
                encoded_data = base64.b64encode(chunk).decode('utf-8')
                resp = {"type": "download_media", "status": "success", "file_data": encoded_data,
                        "file_size": file_size, "offset": offset, "is_complete": False, "request_id": request_id}
            send_response(client_sock, resp)
            logging.debug(f"发送下载块: file_id={file_id}, offset={offset}, size={len(chunk)}, path={file_path}")
        return resp
    except Exception as e:
        logging.error(f"文件下载失败: {e}, path={file_path}")
        resp = {"type": "download_media", "status": "error", "message": f"文件下载失败: {e}", "request_id": request_id}
        send_response(client_sock, resp)
        return resp


def start_server():
    init_db()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((SERVER_CONFIG['HOST'], SERVER_CONFIG['PORT']))
    server_sock.listen(5)
    logging.info(f"服务器启动，监听 {SERVER_CONFIG['HOST']}:{SERVER_CONFIG['PORT']}")
    try:
        while True:
            client_sock, client_addr = server_sock.accept()
            threading.Thread(target=handle_client, args=(client_sock, client_addr), daemon=True).start()
    except KeyboardInterrupt:
        logging.info("服务器正在关闭...")
    finally:
        server_sock.close()


if __name__ == '__main__':
    start_server()