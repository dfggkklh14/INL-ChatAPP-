#!/usr/bin/env python3
import mysql.connector
from moviepy import VideoFileClip
from mysql.connector import Error, MySQLConnection
import socket
from threading import Lock, Timer, Thread
import json
from datetime import datetime
import logging
import os
import base64

import imageio
from PIL import Image
from cryptography.fernet import Fernet
from mysql.connector.abstracts import MySQLConnectionAbstract
from mysql.connector.pooling import PooledMySQLConnection

# 配置日志记录，支持中文调试信息
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

# 服务器配置
SERVER_CONFIG = {
    'HOST': '26.102.137.22',  # 服务器地址
    'PORT': 13746,            # 服务器端口
    'DB_CONFIG': {            # MySQL 数据库配置
        'host': 'localhost',  # 数据库主机地址
        'user': 'root',  # 数据库用户名
        'password': 'Aa112211',  # 数据库密码
        'database': 'chat_server',  # 数据库名称
        'charset': 'utf8mb4',  # 支持中文字符集
        'collation': 'utf8mb4_unicode_ci'
    },
    'LOGGING': {
        'LEVEL': logging.DEBUG,
        'FORMAT': '%(asctime)s %(levelname)s: %(message)s'
    }
}

# 加密密钥
ENCRYPTION_KEY = b'JZ-fJzE7kZDhSyvxCL6odNCB7cP3SdBAnjHR3d2LhcI='
fernet = Fernet(ENCRYPTION_KEY)

# 全局变量
clients = {}
upload_sessions = {}
clients_lock = Lock()
conversations = {}
conversations_lock = Lock()
BASE_DIR = "user_data"
SYNC_INTERVAL = 600  # 同步间隔10分钟

def get_db_connection() -> MySQLConnection | PooledMySQLConnection | MySQLConnectionAbstract:
    try:
        conn = mysql.connector.connect(**SERVER_CONFIG['DB_CONFIG'])
        return conn
    except Error as e:
        logging.error(f"数据库连接失败: {e}")
        return None

def init_db():
    """初始化 MySQL 数据库和表结构"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username VARCHAR(255) PRIMARY KEY,
                password VARCHAR(255),
                avatars VARCHAR(255),
                avatar_path VARCHAR(512),
                names VARCHAR(255),
                signs TEXT
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS friends (
                username VARCHAR(255),
                friend VARCHAR(255),
                Remarks VARCHAR(255),
                PRIMARY KEY (username, friend),
                FOREIGN KEY (username) REFERENCES users(username),
                FOREIGN KEY (friend) REFERENCES users(username)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                sender VARCHAR(255),
                receiver VARCHAR(255),
                message TEXT,
                write_time DATETIME,
                attachment_type VARCHAR(50),
                attachment_path VARCHAR(512),
                original_file_name VARCHAR(255),
                thumbnail_path VARCHAR(512),
                file_size BIGINT,
                duration FLOAT,
                reply_to BIGINT,
                reply_preview TEXT,
                FOREIGN KEY (sender) REFERENCES users(username),
                FOREIGN KEY (receiver) REFERENCES users(username),
                FOREIGN KEY (reply_to) REFERENCES messages(id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                username VARCHAR(255),
                friend VARCHAR(255),
                lastmessageid BIGINT,
                lastupdatetime DATETIME,
                PRIMARY KEY (username, friend),
                FOREIGN KEY (username) REFERENCES users(username),
                FOREIGN KEY (friend) REFERENCES users(username),
                FOREIGN KEY (lastmessageid) REFERENCES messages(id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        ''')
        conn.commit()
        logging.info("数据库初始化成功")
    except Error as e:
        logging.error(f"数据库初始化失败: {e}")
    finally:
        conn.close()

def load_conversations_to_memory():
    """将会话数据加载到内存"""
    conn = get_db_connection()
    if not conn:
        logging.error("无法加载会话数据到内存：数据库连接失败")
        return
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT c.username, c.friend, m.id, m.sender, m.receiver, m.message, m.write_time, 
                   m.attachment_type, m.original_file_name, m.reply_to, m.reply_preview, c.lastupdatetime
            FROM conversations c
            LEFT JOIN messages m ON c.lastmessageid = m.id
        ''')
        rows = cursor.fetchall()
        with conversations_lock:
            for row in rows:
                sorted_key = tuple(sorted([row['username'], row['friend']]))
                conversations[sorted_key] = {
                    'last_message': {
                        'rowid': row['id'],
                        'sender': row['sender'],
                        'receiver': row['receiver'],
                        'message': row['message'],
                        'write_time': row['write_time'].strftime('%Y-%m-%d %H:%M:%S'),
                        'attachment_type': row['attachment_type'],
                        'original_file_name': row['original_file_name'],
                        'reply_to': row['reply_to'],
                        'reply_preview': row['reply_preview']
                    },
                    'last_update_time': row['lastupdatetime']
                }
                logging.debug(f"加载会话 {row['username']}-{row['friend']} 到内存")
    except Error as e:
        logging.error(f"加载会话数据失败: {e}")
    finally:
        conn.close()

def generate_reply_preview(reply_to_id: int) -> dict:
    """生成回复预览"""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT sender, message, attachment_type, original_file_name 
            FROM messages 
            WHERE id = %s
        ''', (reply_to_id,))
        row = cursor.fetchone()
        if row:
            content = f"[{row['attachment_type']}]: {row['original_file_name']}" if row['attachment_type'] and row['original_file_name'] else (row['message'] if row['message'] else "空消息")
            return {"sender": row['sender'], "content": content}
        return None
    except Error as e:
        logging.error(f"生成回复预览失败: {e}")
        return None
    finally:
        conn.close()

def recv_all(sock: socket.socket, length: int) -> bytes:
    """接收指定长度的数据"""
    data = b""
    while len(data) < length:
        packet = sock.recv(length - len(data))
        if not packet:
            return None
        data += packet
    return data

def send_response(client_sock: socket.socket, response: dict):
    """发送加密响应"""
    try:
        plaintext = json.dumps(response, ensure_ascii=False).encode('utf-8')
        ciphertext = fernet.encrypt(plaintext)
        length_header = len(ciphertext).to_bytes(4, byteorder='big')
        client_sock.sendall(length_header + ciphertext)
    except Exception as e:
        logging.error(f"发送响应失败: {e}")

def sync_conversation_to_db(username: str, friend: str):
    """同步会话数据到数据库"""
    with conversations_lock:
        sorted_key = tuple(sorted([username, friend]))
        if sorted_key not in conversations:
            return
        last_update_time = conversations[sorted_key]['last_update_time']
    current_time = datetime.now()
    if (current_time - last_update_time).total_seconds() >= SYNC_INTERVAL:
        conn = get_db_connection()
        if not conn:
            logging.error(f"同步会话 {username}-{friend} 到数据库失败：数据库连接失败")
            return
        try:
            cursor = conn.cursor()
            last_message = conversations[sorted_key]['last_message']
            cursor.execute('''
                INSERT INTO conversations (username, friend, lastmessageid, lastupdatetime)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE lastmessageid = %s, lastupdatetime = %s
            ''', (sorted_key[0], sorted_key[1], last_message['rowid'], last_update_time,
                  last_message['rowid'], last_update_time))
            conn.commit()
            logging.debug(f"会话 {username}-{friend} 已同步到数据库")
        except Error as e:
            logging.error(f"同步会话 {username}-{friend} 到数据库失败: {e}")
        finally:
            conn.close()

def schedule_sync(user1: str, user2: str):
    """调度会话同步"""
    timer = Timer(SYNC_INTERVAL, sync_conversation_to_db, args=(user1, user2))
    timer.daemon = True
    timer.start()

def update_user_profile(request: dict, client_sock: socket.socket) -> dict:
    """更新用户资料"""
    req_type = request.get("type")
    username = request.get("username")
    request_id = request.get("request_id")
    new_sign = request.get("sign") if req_type == "update_sign" else None
    new_nickname = request.get("new_name") if req_type == "update_name" else None
    file_data_b64 = request.get("file_data") if req_type == "upload_avatar" else None

    conn = get_db_connection()
    if not conn:
        return {"type": req_type, "status": "error", "message": "数据库连接失败", "request_id": request_id}
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username, avatars, avatar_path, signs FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user:
            return {"type": req_type, "status": "error", "message": "用户不存在", "request_id": request_id}

        if req_type == "upload_avatar" and file_data_b64:
            avatar_dir = os.path.join(BASE_DIR, "avatars")
            os.makedirs(avatar_dir, exist_ok=True)
            original_file_name = f"{username}_avatar_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.jpg"
            avatar_path = os.path.join(avatar_dir, original_file_name)
            try:
                file_data = base64.b64decode(file_data_b64)
                with open(avatar_path, "wb") as f:
                    f.write(file_data)
                logging.debug(f"头像保存成功: {avatar_path}")
            except Exception as e:
                logging.error(f"头像保存失败: {e}")
                return {"type": req_type, "status": "error", "message": "头像保存失败", "request_id": request_id}

        update_fields = []
        update_values = []
        if new_sign is not None:
            update_fields.append("signs = %s")
            update_values.append(new_sign)
        if new_nickname is not None:
            update_fields.append("names = %s")
            update_values.append(new_nickname)
        if 'original_file_name' in locals():
            update_fields.append("avatars = %s")
            update_fields.append("avatar_path = %s")
            update_values.extend([original_file_name, avatar_path])

        if update_fields:
            sql = f"UPDATE users SET {', '.join(update_fields)} WHERE username = %s"
            update_values.append(username)
            cursor.execute(sql, tuple(update_values))
            conn.commit()
            logging.debug(f"更新用户信息成功: {req_type}，用户: {username}")
    except Error as e:
        logging.error(f"更新用户信息失败: {e}")
        return {"type": req_type, "status": "error", "message": "数据库更新失败", "request_id": request_id}
    finally:
        conn.close()

    response = {"type": req_type, "status": "success", "message": "更新成功", "request_id": request_id}
    if req_type == "upload_avatar" and 'original_file_name' in locals():
        response["avatar_id"] = original_file_name
    return response

def update_friend_remarks(request: dict, client_sock: socket.socket) -> dict:
    """更新好友备注"""
    username = request.get("username")
    friend = request.get("friend")
    remarks = request.get("remarks")
    request_id = request.get("request_id")

    conn = get_db_connection()
    if not conn:
        return {"type": "Update_Remarks", "status": "error", "message": "数据库连接失败", "request_id": request_id}
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM friends WHERE username = %s AND friend = %s", (username, friend))
        if not cursor.fetchone():
            return {"type": "Update_Remarks", "status": "error", "message": f"{friend} 不是您的好友", "request_id": request_id}
        cursor.execute("UPDATE friends SET Remarks = %s WHERE username = %s AND friend = %s", (remarks, username, friend))
        conn.commit()
        logging.debug(f"好友备注更新成功: {username} -> {friend}，备注: {remarks}")
    except Error as e:
        logging.error(f"更新好友备注失败: {e}")
        return {"type": "Update_Remarks", "status": "error", "message": "更新备注失败", "request_id": request_id}
    finally:
        conn.close()

    response = {"type": "Update_Remarks", "status": "success",
                "message": f"已将 {friend} 的备注更新为 {remarks}",
                "request_id": request_id, "friend": friend, "remarks": remarks}
    logging.debug(f"更新备注返回响应: {response}")
    return response


def push_friends_list(username: str):
    """推送好友列表并在每个好友项中包含会话数据，去掉重复的 time 字段"""
    conn = get_db_connection()
    if not conn:
        logging.error("数据库连接失败，无法推送好友列表")
        return
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT f.friend, f.Remarks FROM friends f WHERE f.username = %s", (username,))
        friend_rows = cursor.fetchall()
        friends = []

        for row in friend_rows:
            friend_username = row['friend']
            remarks = row['Remarks']
            cursor.execute("SELECT avatars, names, signs FROM users WHERE username = %s", (friend_username,))
            user_info = cursor.fetchone()
            avatar_id = user_info['avatars'] if user_info and user_info['avatars'] else ""
            name = user_info['names'] if user_info and user_info['names'] else friend_username
            sign = user_info['signs'] if user_info and user_info['signs'] else ""
            display_name = remarks if remarks else name

            # 获取该好友的最后会话消息
            last_message_data = None
            with conversations_lock:
                sorted_key = tuple(sorted([username, friend_username]))
                convo_data = conversations.get(sorted_key)
                if convo_data:
                    last_message = convo_data["last_message"]
                    # 根据消息类型设置 content
                    if last_message["attachment_type"] == "file":
                        content = "[文件]"
                    elif last_message["attachment_type"] == "image":
                        content = "[图片]"
                    elif last_message["attachment_type"] == "video":
                        content = "[视频]"
                    else:
                        content = last_message["message"]

                    last_message_data = {
                        "sender": last_message["sender"],
                        "content": content,
                        "last_update_time": convo_data['last_update_time'].strftime('%Y-%m-%d %H:%M:%S')
                    }

            # 构建好友项，直接包含会话数据
            friend_item = {
                "username": friend_username,
                "avatar_id": avatar_id,
                "name": display_name,
                "sign": sign,
                "online": friend_username in clients,
                "conversations": last_message_data  # 如果没有会话，则为 None
            }
            friends.append(friend_item)

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
    """推送好友更新"""
    push_friends_list(username)
    conn = get_db_connection()
    if not conn:
        logging.error("数据库连接失败，无法获取相关好友信息")
        return
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM friends WHERE friend = %s", (username,))
        related_users = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"获取相关好友列表失败: {e}")
        related_users = []
    finally:
        conn.close()
    for user in related_users:
        push_friends_list(user)

def authenticate(request: dict, client_sock: socket.socket) -> dict:
    """用户认证"""
    username = request.get("username")
    password = request.get("password")
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        return {"type": "authenticate", "status": "error", "message": "数据库连接失败", "request_id": request_id}
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
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
        logging.info(f"用户 {username} 认证失败")
        return {"type": "authenticate", "status": "fail", "message": "账号或密码错误", "request_id": request_id}

def send_message(request: dict, client_sock: socket.socket) -> dict:
    """发送消息"""
    from_user = request.get("from")
    to_user = request.get("to")
    message = request.get("message")
    reply_to = request.get("reply_to")
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    request_id = request.get("request_id")

    reply_preview = None
    if reply_to is not None:
        reply_preview_data = generate_reply_preview(reply_to)
        if reply_preview_data:
            reply_preview = json.dumps(reply_preview_data, ensure_ascii=False)
        else:
            reply_preview = json.dumps({"sender": "未知用户", "content": "消息不可用"}, ensure_ascii=False)

    conn = get_db_connection()
    if not conn:
        return {"type": "send_message", "status": "error", "message": "数据库连接失败", "request_id": request_id}
    try:
        cursor = conn.cursor()
        cursor.execute(''' 
            INSERT INTO messages (sender, receiver, message, write_time, reply_to, reply_preview)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (from_user, to_user, message, current_time, reply_to, reply_preview))
        rowid = cursor.lastrowid
        conn.commit()

        last_message = {
            "rowid": rowid,
            "sender": from_user,
            "receiver": to_user,
            "message": message,
            "write_time": current_time,
            "attachment_type": None,
            "original_file_name": None,
            "reply_to": reply_to,
            "reply_preview": reply_preview
        }
        update_conversation_last_message(from_user, to_user, last_message)

        # conversations 直接使用 message 作为值
        conversations = message

        # 推送消息给接收者
        push_response = {
            "type": "new_message",
            "from": from_user,
            "to": to_user,
            "message": message,
            "write_time": current_time,
            "reply_to": reply_to,
            "reply_preview": reply_preview,
            "rowid": rowid,
            "conversations": conversations
        }
        with clients_lock:
            if to_user in clients:
                send_response(clients[to_user], push_response)

        # 返回给发送者的响应
        return {
            "type": "send_message",
            "status": "success",
            "message": f"消息已发送给 {to_user}",
            "request_id": request_id,
            "rowid": rowid,
            "reply_to": reply_to,
            "reply_preview": reply_preview,
            "conversations": conversations
        }
    except Error as e:
        logging.error(f"发送消息失败: {e}")
        return {"type": "send_message", "status": "error", "message": "消息发送失败", "request_id": request_id}
    finally:
        conn.close()

def send_media(request: dict, client_sock: socket.socket) -> dict:
    logging.debug(f"收到 send_media 请求: {request}")
    from_user = request.get("from")
    to_user = request.get("to")
    original_file_name = request.get("file_name")
    file_type = request.get("file_type")
    message = request.get("message", "")
    reply_to = request.get("reply_to")
    request_id = request.get("request_id")
    file_data_b64 = request.get("file_data", "")
    total_size = request.get("total_size", 0)

    # 保持原始文件夹结构
    if file_type == "file":
        upload_dir = os.path.join(BASE_DIR, "files")
    elif file_type == "image":
        upload_dir = os.path.join(BASE_DIR, "images")
    elif file_type == "video":
        upload_dir = os.path.join(BASE_DIR, "videos")
    else:
        upload_dir = os.path.join(BASE_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    if request_id not in upload_sessions:
        unique_file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{original_file_name}"
        file_path = os.path.join(upload_dir, unique_file_name)
        upload_sessions[request_id] = {"file_path": file_path, "total_size": total_size, "received_size": 0,
                                       "unique_file_name": unique_file_name}
    session = upload_sessions[request_id]
    file_path = session["file_path"]
    unique_file_name = session["unique_file_name"]

    if file_data_b64:
        try:
            file_data = base64.b64decode(file_data_b64)
            with open(file_path, "ab") as f:
                f.write(file_data)
            session["received_size"] += len(file_data)
            logging.debug(f"写入文件: {file_path}，大小: {len(file_data)}")
            return {"type": "send_media", "status": "success", "message": "分块接收中", "request_id": request_id}
        except Exception as e:
            logging.error(f"文件写入失败: {e}")
            return {"type": "send_media", "status": "error", "message": "文件写入失败", "request_id": request_id}
    else:
        file_size = session["received_size"]
        thumbnail_path = ""
        duration = 0

        if not os.path.exists(file_path):
            logging.error(f"文件未找到: {file_path}")
            return {"type": "send_media", "status": "error", "message": "文件保存失败，路径未找到", "request_id": request_id}

        if file_type == "image":
            try:
                image = Image.open(file_path)
                image.thumbnail((350, 350))
                thumbnail_filename = f"thumb_{unique_file_name}"
                thumbnail_path = os.path.join(upload_dir, thumbnail_filename)
                image.save(thumbnail_path, format=image.format)
                logging.debug(f"生成图片缩略图: {thumbnail_path}")
                if not os.path.exists(thumbnail_path):
                    logging.error(f"缩略图文件未生成: {thumbnail_path}")
            except Exception as e:
                logging.error(f"生成图片缩略图失败: {e}, 文件路径: {file_path}")
                thumbnail_path = ""
        elif file_type == "video":
            try:
                reader = imageio.get_reader(file_path)
                frame = reader.get_data(0)
                thumb_image = Image.fromarray(frame)
                thumb_image.thumbnail((350, 350), Image.Resampling.NEAREST)
                thumbnail_filename = f"thumb_{unique_file_name}.jpg"
                thumbnail_path = os.path.join(upload_dir, thumbnail_filename)
                thumb_image.save(thumbnail_path, "JPEG")
                video = VideoFileClip(file_path)
                duration = video.duration
                video.close()
                reader.close()
                logging.debug(f"生成视频缩略图: {thumbnail_path}, 时长: {duration}秒")
                if not os.path.exists(thumbnail_path):
                    logging.error(f"缩略图文件未生成: {thumbnail_path}")
            except Exception as e:
                logging.error(f"生成视频缩略图失败: {e}, 文件路径: {file_path}")
                thumbnail_path = ""
                duration = 0

        reply_preview = None
        if reply_to:
            reply_preview_data = generate_reply_preview(reply_to)
            if reply_preview_data:
                reply_preview = json.dumps(reply_preview_data, ensure_ascii=False)
            else:
                reply_preview = json.dumps({"sender": "未知用户", "content": "消息不可用"}, ensure_ascii=False)

        conn = get_db_connection()
        if not conn:
            return {"type": "send_media", "status": "error", "message": "数据库连接失败", "request_id": request_id}
        try:
            cursor = conn.cursor()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logging.debug(f"插入参数: sender={from_user}, receiver={to_user}, message={message}, "
                          f"write_time={current_time}, attachment_type={file_type}, attachment_path={file_path}, "
                          f"original_file_name={original_file_name}, thumbnail_path={thumbnail_path}, "
                          f"file_size={file_size}, duration={duration}, reply_to={reply_to}, reply_preview={reply_preview}")
            cursor.execute(''' 
                INSERT INTO messages (sender, receiver, message, write_time, attachment_type, attachment_path, 
                                      original_file_name, thumbnail_path, file_size, duration, reply_to, reply_preview)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (from_user, to_user, message, current_time, file_type, file_path, original_file_name, thumbnail_path, file_size, duration, reply_to, reply_preview))
            rowid = cursor.lastrowid
            conn.commit()

            last_message = {
                "rowid": rowid,
                "sender": from_user,
                "receiver": to_user,
                "message": message,
                "write_time": current_time,
                "attachment_type": file_type,
                "original_file_name": original_file_name,
                "reply_to": reply_to,
                "reply_preview": reply_preview
            }
            update_conversation_last_message(from_user, to_user, last_message)

            # 根据文件类型设置 conversations
            if file_type == "file":
                conversations = "[文件]"
            elif file_type == "image":
                conversations = "[图片]"
            elif file_type == "video":
                conversations = "[视频]"
            else:
                conversations = message  # 默认使用 message

            # 推送消息给接收者
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
                "rowid": rowid,
                "conversations": conversations
            }
            if thumbnail_path and os.path.exists(thumbnail_path):
                push_payload["thumbnail_path"] = thumbnail_path
            else:
                logging.warning(f"缩略图未推送: {thumbnail_path} 不存在或未生成")

            with clients_lock:
                if to_user in clients:
                    send_response(clients[to_user], push_payload)

            # 返回给发送者的响应
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
                "text_message": message,
                "conversations": conversations
            }
        except Error as e:
            logging.error(f"保存媒体消息失败: {e}")
            return {"type": "send_media", "status": "error", "message": "保存失败", "request_id": request_id}
        finally:
            conn.close()


def delete_messages(request: dict, client_sock: socket.socket) -> dict:
    """删除消息（支持单条和批量删除）"""
    username = request.get("username")
    rowids = request.get("rowids", []) if request.get("rowids") else [request.get("rowid")] if request.get("rowid") else []
    request_id = request.get("request_id")

    if not rowids:
        return {"type": "messages_deleted", "status": "error", "message": "未指定要删除的消息", "request_id": request_id}

    conn = get_db_connection()
    if not conn:
        return {"type": "messages_deleted", "status": "error", "message": "数据库连接失败", "request_id": request_id}

    try:
        cursor = conn.cursor(dictionary=True)
        # 检查权限并获取消息
        cursor.execute('''SELECT id, sender, receiver FROM messages WHERE id IN (%s) AND (sender = %s OR receiver = %s)'''
                       % (','.join(['%s'] * len(rowids)), '%s', '%s'), tuple(rowids + [username, username]))
        messages_to_delete = cursor.fetchall()
        if not messages_to_delete:
            return {"type": "messages_deleted", "status": "error", "message": "消息不存在或无权限", "request_id": request_id}

        # 删除相关记录
        cursor.execute('DELETE FROM conversations WHERE lastmessageid IN (%s)' % ','.join(['%s'] * len(rowids)), tuple(rowids))
        cursor.execute('DELETE FROM messages WHERE id IN (%s)' % ','.join(['%s'] * len(rowids)), tuple(rowids))
        conn.commit()

        # 更新会话并获取最新状态
        affected_pairs = {tuple(sorted([msg['sender'], msg['receiver']])) for msg in messages_to_delete}
        conversations_content = ""
        write_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 默认删除时间
        for user1, user2 in affected_pairs:
            # 获取最新消息
            cursor.execute('''SELECT id, sender, receiver, message, write_time, attachment_type, original_file_name, 
                            reply_to, reply_preview FROM messages 
                            WHERE (sender = %s AND receiver = %s) OR (sender = %s AND receiver = %s) 
                            ORDER BY write_time DESC LIMIT 1''', (user1, user2, user2, user1))
            latest_msg = cursor.fetchone()
            if latest_msg:
                conversations_content = "[文件]" if latest_msg['attachment_type'] == "file" else \
                                      "[图片]" if latest_msg['attachment_type'] == "image" else \
                                      "[视频]" if latest_msg['attachment_type'] == "video" else \
                                      latest_msg['message'] or ""
                write_time = latest_msg['write_time'].strftime('%Y-%m-%d %H:%M:%S')
                last_message = {
                    "rowid": latest_msg['id'],
                    "sender": latest_msg['sender'],
                    "receiver": latest_msg['receiver'],
                    "message": latest_msg['message'],
                    "write_time": write_time,
                    "attachment_type": latest_msg['attachment_type'],
                    "original_file_name": latest_msg['original_file_name'],
                    "reply_to": latest_msg['reply_to'],
                    "reply_preview": latest_msg['reply_preview']
                }
                update_conversation_last_message(user1, user2, last_message)
            else:
                conversations_content = ""
                write_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                # 会话清空时，更新 conversations 表为 NULL
                with conversations_lock:
                    sorted_key = tuple(sorted([user1, user2]))
                    if sorted_key in conversations:
                        del conversations[sorted_key]
                cursor.execute('''INSERT INTO conversations (username, friend, lastmessageid, lastupdatetime)
                                VALUES (%s, %s, NULL, %s)
                                ON DUPLICATE KEY UPDATE lastmessageid = NULL, lastupdatetime = %s''',
                               (user1, user2, write_time, write_time))
                conn.commit()

            # 构建推送内容
            push_payload = {
                "type": "messages_deleted",
                "from": username,
                "to": user2 if user1 == username else user1,
                "deleted_rowids": [msg['id'] for msg in messages_to_delete],
                "conversations": conversations_content,
                "write_time": write_time
            }
            # 推送给会话另一方
            other_user = user2 if user1 == username else user1
            with clients_lock:
                if other_user in clients and other_user != username:
                    send_response(clients[other_user], push_payload)

        return_data = {
            "type": "messages_deleted",
            "status": "success",
            "message": f"成功删除 {len(messages_to_delete)} 条消息",
            "request_id": request_id,
            "deleted_rowids": [msg['id'] for msg in messages_to_delete],
            "conversations": conversations_content,
            "write_time": write_time
        }
        # 返回响应
        logging.debug(f"delete_message返回:{return_data}\ndelete_message推送:{push_payload}")
        return return_data

    except Error as e:
        logging.error(f"删除消息失败: {e}")
        return {"type": "messages_deleted", "status": "error", "message": "删除消息失败", "request_id": request_id}
    finally:
        conn.close()

def get_conversations(request: dict, client_sock: socket.socket) -> dict:
    """获取用户会话列表"""
    username = request.get("username")
    request_id = request.get("request_id")
    conversations_list = []
    with conversations_lock:
        for (user1, user2), data in conversations.items():
            if user1 == username or user2 == username:
                other_user = user2 if user1 == username else user1
                conversations_list.append({
                    "with_user": other_user,
                    "last_message": data['last_message'],
                    "last_update_time": data['last_update_time'].strftime('%Y-%m-%d %H:%M:%S')
                })
    conversations_list.sort(key=lambda x: x["last_update_time"], reverse=True)
    response = {"type": "get_conversations", "status": "success", "conversations": conversations_list, "request_id": request_id}
    send_response(client_sock, response)
    return response

def update_conversation_last_message(username: str, friend: str, message: dict):
    """更新会话的最后消息，不推送任何消息"""
    sorted_key = tuple(sorted([username, friend]))
    write_time = message['write_time']  # 使用消息的 write_time
    with conversations_lock:
        conversations[sorted_key] = {'last_message': message, 'last_update_time': datetime.strptime(write_time, '%Y-%m-%d %H:%M:%S')}
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(''' 
                INSERT INTO conversations (username, friend, lastmessageid, lastupdatetime)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE lastmessageid = %s, lastupdatetime = %s
            ''', (sorted_key[0], sorted_key[1], message['rowid'], write_time, message['rowid'], write_time))
            conn.commit()
            logging.debug(f"会话 {username}-{friend} 已立即同步到数据库")
        except Error as e:
            logging.error(f"同步会话 {username}-{friend} 到数据库失败: {e}")
        finally:
            conn.close()


def get_chat_history_paginated(request: dict, client_sock: socket.socket) -> dict:
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
        cursor = conn.cursor(dictionary=True)
        offset = (page - 1) * page_size
        cursor.execute('''
            SELECT id AS rowid, write_time, sender, receiver, message, attachment_type, attachment_path, 
                   original_file_name, thumbnail_path, file_size, duration, reply_to, reply_preview
            FROM messages
            WHERE (sender = %s AND receiver = %s) OR (sender = %s AND receiver = %s)
            ORDER BY write_time DESC, id DESC
            LIMIT %s OFFSET %s
        ''', (username, friend, friend, username, page_size, offset))
        rows = cursor.fetchall()
    except Exception as e:
        logging.error(f"查询聊天记录失败: {e}")
        rows = []
    finally:
        conn.close()
    history = []
    for row in rows:
        raw_thumbnail_path = row['thumbnail_path']
        # 如果是相对路径，基于当前工作目录解析
        if raw_thumbnail_path and not os.path.isabs(raw_thumbnail_path):
            normalized_thumbnail_path = os.path.join(os.getcwd(), raw_thumbnail_path)
        else:
            normalized_thumbnail_path = raw_thumbnail_path if raw_thumbnail_path else ""

        record = {"rowid": row['rowid'], "write_time": row['write_time'].strftime('%Y-%m-%d %H:%M:%S'),
                  "username": row['sender'], "friend_username": row['receiver'],
                  "message": row['message'], "reply_to": row['reply_to'], "reply_preview": row['reply_preview']}
        if row['attachment_type']:
            record["attachment_type"] = row['attachment_type']
            record["file_id"] = os.path.basename(row['attachment_path'])
            record["original_file_name"] = row['original_file_name']
            record["thumbnail_path"] = normalized_thumbnail_path  # 使用规范化后的路径
            record["file_size"] = row['file_size']
            record["duration"] = row['duration']
            if normalized_thumbnail_path:
                exists = os.path.exists(normalized_thumbnail_path)
                logging.debug(f"检查路径存在性: {repr(normalized_thumbnail_path)}, 结果: {exists}")
        history.append(record)
    resp = {"type": "chat_history", "status": "success", "chat_history": history, "request_id": request_id}
    send_response(client_sock, resp)
    return resp

def add_friend(request: dict, client_sock: socket.socket) -> dict:
    """添加好友"""
    username = request.get("username")
    friend = request.get("friend")
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        return {"type": "add_friend", "status": "error", "message": "数据库连接失败", "request_id": request_id}
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (friend,))
        if not cursor.fetchone():
            return {"type": "add_friend", "status": "error", "message": f"用户 {friend} 不存在，无法添加", "request_id": request_id}
        cursor.execute("SELECT * FROM friends WHERE username = %s AND friend = %s", (username, friend))
        if cursor.fetchone():
            return {"type": "add_friend", "status": "fail", "message": f"{friend} 已是您的好友", "request_id": request_id}
        cursor.execute('INSERT INTO friends (username, friend) VALUES (%s, %s)', (username, friend))
        cursor.execute('INSERT INTO friends (username, friend) VALUES (%s, %s)', (friend, username))
        conn.commit()
        response = {"type": "add_friend", "status": "success", "message": f"{friend} 已添加为您的好友", "request_id": request_id}
    except Error as e:
        logging.error(f"添加好友失败: {e}")
        response = {"type": "add_friend", "status": "error", "message": "添加好友失败", "request_id": request_id}
    finally:
        conn.close()
    if response.get("status") == "success":
        push_friends_update(username)
        push_friends_update(friend)
    return response

def handle_client(client_sock: socket.socket, client_addr):
    """处理客户端连接"""
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
                logging.debug(f"收到请求：{request}")
            except Exception as e:
                logging.error(f"数据解密或JSON解析错误：{e}")
                send_response(client_sock, {"status": "error", "message": "请求格式错误"})
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
            elif req_type == "Update_Remarks":
                response = update_friend_remarks(request, client_sock)
            elif req_type == "delete_messages":
                response = delete_messages(request, client_sock)
            elif req_type == "exit":
                response = {"type": "exit", "status": "success", "message": f"{request.get('username')} 已退出", "request_id": request.get("request_id")}
                send_response(client_sock, response)
                logging.info(f"客户端 {client_addr} 请求退出")
                break
            else:
                response = {"status": "error", "message": "未知的请求类型", "request_id": request.get("request_id")}

            if response:
                send_response(client_sock, response)
    except ConnectionResetError:
        logging.warning(f"客户端 {client_addr} 强制断开连接")
    except Exception as e:
        logging.error(f"处理客户端请求时出现异常：{e}")
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
    """获取用户信息"""
    username = request.get("username")
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        return {"type": "get_user_info", "status": "error", "message": "数据库连接失败", "request_id": request_id}
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username, avatars, names, signs FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if user:
            avatar_id = user['avatars'] if user['avatars'] else ""
            response = {"type": "get_user_info", "status": "success", "username": user['username'],
                        "avatar_id": avatar_id, "name": user['names'] if user['names'] else user['username'],
                        "sign": user['signs'] if user['signs'] else "", "request_id": request_id}
        else:
            response = {"type": "get_user_info", "status": "error", "message": "用户不存在", "request_id": request_id}
    except Error as e:
        logging.error(f"查询用户信息失败: {e}")
        response = {"type": "get_user_info", "status": "error", "message": "查询失败", "request_id": request_id}
    finally:
        conn.close()
    logging.debug(f"发送用户信息响应：{response}")
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
            cursor.execute("SELECT attachment_path FROM messages WHERE attachment_path LIKE %s", (f"%{file_id}",))
            result = cursor.fetchone()
            if result:
                file_path = result[0]
            else:
                cursor.execute("SELECT avatar_path FROM users WHERE avatars = %s", (file_id,))
                result = cursor.fetchone()
                file_path = result[0] if result else None
            logging.debug(f"查询文件：file_id={file_id}, file_path={file_path}")
    except Error as e:
        logging.error(f"查询文件路径失败: {e}")
        file_path = None
    finally:
        conn.close()

    # 如果 file_path 是相对路径，确保基于当前工作目录解析
    if file_path and not os.path.isabs(file_path):
        file_path = os.path.join(os.getcwd(), file_path)

    if not file_path or not os.path.exists(file_path):
        logging.error(f"文件不存在: file_id={file_id}, path={file_path}")
        resp = {"type": "download_media", "status": "error", "message": f"文件不存在: {file_id}",
                "request_id": request_id}
        send_response(client_sock, resp)
        return resp

    file_size = os.path.getsize(file_path)
    chunk_size = 1024 * 1024  # 1MB 分块大小

    try:
        with open(file_path, "rb") as f:
            f.seek(offset)
            chunk = f.read(chunk_size)
            is_complete = (offset + len(chunk) >= file_size) or not chunk
            if not chunk:
                resp = {"type": "download_media", "status": "success", "file_size": file_size, "offset": offset, "is_complete": is_complete, "request_id": request_id, "file_data": ""}
            else:
                encoded_data = base64.b64encode(chunk).decode('utf-8')
                resp = {"type": "download_media", "status": "success", "file_size": file_size, "offset": offset, "is_complete": is_complete, "request_id": request_id, "file_data": encoded_data}
            send_response(client_sock, resp)
            logging.debug(f"发送下载块: file_id={file_id}, offset={offset}, size={len(chunk)}, path={file_path}")
        return resp
    except Exception as e:
        logging.error(f"文件下载失败: {e}, path={file_path}")
        resp = {"type": "download_media", "status": "error", "message": f"文件下载失败: {e}", "request_id": request_id}
        send_response(client_sock, resp)
        return resp

def start_server():
    """启动服务器"""
    init_db()
    load_conversations_to_memory()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((SERVER_CONFIG['HOST'], SERVER_CONFIG['PORT']))
    server_sock.listen(5)
    logging.info(f"服务器启动，监听 {SERVER_CONFIG['HOST']}:{SERVER_CONFIG['PORT']}")
    try:
        while True:
            client_sock, client_addr = server_sock.accept()
            Thread(target=handle_client, args=(client_sock, client_addr), daemon=True).start()
    except KeyboardInterrupt:
        logging.info("服务器正在关闭……")
    finally:
        server_sock.close()

if __name__ == '__main__':
    logging.info(f"当前工作目录: {os.getcwd()}")
    start_server()