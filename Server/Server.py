#!/usr/bin/env python3
# server.py
import sqlite3
import socket
import threading
import json
from datetime import datetime
import logging
from io import BytesIO
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

# 全局变量：存储已登录用户与对应的 socket
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
    """初始化数据库，创建必要的表，并扩展媒体消息字段"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn:
            cursor = conn.cursor()
            # 创建用户、好友、消息表（如果不存在）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS friends (
                    username TEXT,
                    friend TEXT,
                    PRIMARY KEY(username, friend),
                    FOREIGN KEY(username) REFERENCES users(username),
                    FOREIGN KEY(friend) REFERENCES users(username)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    sender TEXT,
                    receiver TEXT,
                    message TEXT,
                    write_time TEXT,
                    FOREIGN KEY(sender) REFERENCES users(username),
                    FOREIGN KEY(receiver) REFERENCES users(username)
                )
            ''')
            # 检查并扩展媒体附件字段（如果不存在则添加）
            cursor.execute("PRAGMA table_info(messages)")
            columns = [col[1] for col in cursor.fetchall()]
            if "attachment_type" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN attachment_type TEXT")
            if "attachment_path" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN attachment_path TEXT")
            if "original_file_name" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN original_file_name TEXT")
            if "thumbnail_path" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN thumbnail_path TEXT")
            if "file_size" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN file_size INTEGER")
            if "duration" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN duration REAL")
    except sqlite3.Error as e:
        logging.error(f"数据库初始化失败: {e}")
    finally:
        conn.close()


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


def push_friends_list(username: str):
    """
    获取指定用户的好友列表并推送到该用户。
    仅当用户在线时才会发送。
    """
    conn = get_db_connection()
    if not conn:
        logging.error("数据库连接失败，无法推送好友列表")
        return
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT friend FROM friends WHERE username = ?", (username,))
            friend_names = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"获取好友列表失败: {e}")
        return
    finally:
        conn.close()

    friends = [{"username": friend, "online": friend in clients} for friend in friend_names]
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
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        return {"type": "send_message", "status": "error", "message": "数据库连接失败", "request_id": request_id}
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages (sender, receiver, message, write_time)
                VALUES (?, ?, ?, ?)
            ''', (from_user, to_user, message, current_time))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"写入消息失败: {e}")
        return {"type": "send_message", "status": "error", "message": "消息保存失败", "request_id": request_id}
    finally:
        conn.close()
    with clients_lock:
        if to_user in clients:
            push_response = {
                "type": "new_message",
                "status": "success",
                "from": from_user,
                "to": to_user,
                "message": message,
                "write_time": current_time
            }
            try:
                send_response(clients[to_user], push_response)
            except Exception as e:
                logging.error(f"推送消息给 {to_user} 失败: {e}")
    return {"type": "send_message", "status": "success", "message": f"消息已发送给 {to_user}", "request_id": request_id}


def send_media(request: dict, client_sock: socket.socket) -> dict:
    """处理发送媒体消息，支持分块传输并按类型存储"""
    from_user = request.get("from")
    to_user = request.get("to")
    original_file_name = request.get("file_name")
    file_type = request.get("file_type")
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

    # 如果是第一个分块或完整文件，生成文件名并存储在会话中
    if request_id not in upload_sessions:
        unique_file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{original_file_name}"
        file_path = os.path.join(upload_dir, unique_file_name)
        upload_sessions[request_id] = {
            "file_path": file_path,
            "total_size": total_size,
            "received_size": 0,
            "unique_file_name": unique_file_name  # 存储文件名以确保一致性
        }

    session = upload_sessions[request_id]
    file_path = session["file_path"]  # 使用会话中的文件路径
    unique_file_name = session["unique_file_name"]

    # 如果有数据，写入文件
    if file_data_b64:
        try:
            file_data = base64.b64decode(file_data_b64)
            with open(session["file_path"], "ab") as f:
                f.write(file_data)
            session["received_size"] += len(file_data)
            logging.debug(f"写入文件: path={session['file_path']}, size={len(file_data)}")
        except Exception as e:
            logging.error(f"文件写入失败: {e}")
            return {"type": "send_media", "status": "error", "message": "文件写入失败", "request_id": request_id}
    else:
        # 传输完成，处理文件
        file_size = session["received_size"]
        thumbnail_path = ""
        duration = 0

        # 验证文件是否存在
        if not os.path.exists(file_path):
            logging.error(f"文件未找到: {file_path}")
            return {"type": "send_media", "status": "error", "message": "文件保存失败，路径未找到",
                    "request_id": request_id}

        # 为图片和视频生成缩略图
        if file_type == "image":
            try:
                image = Image.open(file_path)
                image.thumbnail((500, 500))
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
                thumb_image.thumbnail((500, 500), Image.Resampling.LANCZOS)
                thumbnail_filename = f"thumb_{unique_file_name}.jpg"
                thumbnail_path = os.path.join(upload_dir, thumbnail_filename)
                thumb_image.save(thumbnail_path, "JPEG")
                duration = reader.get_length() / reader.get_meta_data()['fps']
                reader.close()
                logging.debug(f"生成视频缩略图: {thumbnail_path}")
            except Exception as e:
                logging.error(f"视频处理失败: {e}")

        # 保存到数据库
        conn = get_db_connection()
        if not conn:
            return {"type": "send_media", "status": "error", "message": "数据库连接失败", "request_id": request_id}
        try:
            with conn:
                cursor = conn.cursor()
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                logging.debug(f"保存媒体消息: attachment_path={file_path}, original_file_name={original_file_name}")
                cursor.execute('''
                        INSERT INTO messages (sender, receiver, message, write_time, attachment_type, attachment_path, original_file_name, thumbnail_path, file_size, duration)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                from_user, to_user, "", current_time, file_type, file_path, original_file_name, thumbnail_path,
                file_size, duration))
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
            "original_file_name": original_file_name,
            "file_type": file_type,
            "file_id": unique_file_name,  # 使用固定的 unique_file_name
            "write_time": current_time,
            "file_size": file_size,
            "duration": duration
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
            "file_id": unique_file_name,  # 确保一致
            "write_time": current_time,
            "duration": duration
        }

    return {"type": "send_media", "status": "success", "message": "分块接收中", "request_id": request_id}

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
            # 使用精确匹配查询 attachment_path
            cursor.execute("SELECT attachment_path FROM messages WHERE attachment_path LIKE ?", (f"%{file_id}",))
            result = cursor.fetchone()
            file_path = result[0] if result else None
            logging.debug(f"查询文件: file_id={file_id}, attachment_path={file_path}")
    except sqlite3.Error as e:
        logging.error(f"查询文件路径失败: {e}")
        file_path = None
    finally:
        conn.close()

    if not file_path or not os.path.exists(file_path):
        logging.error(f"文件不存在: file_id={file_id}, path={file_path}")
        resp = {"type": "download_media", "status": "error", "message": f"文件不存在: {file_id}", "request_id": request_id}
        send_response(client_sock, resp)
        return resp
    file_size = os.path.getsize(file_path)
    chunk_size = 1024 * 1024  # 1MB

    try:
        with open(file_path, "rb") as f:
            f.seek(offset)
            chunk = f.read(chunk_size)
            if not chunk:
                resp = {
                    "type": "download_media",
                    "status": "success",
                    "file_data": "",
                    "file_size": file_size,
                    "offset": offset,
                    "is_complete": True,
                    "request_id": request_id
                }
            else:
                encoded_data = base64.b64encode(chunk).decode('utf-8')
                resp = {
                    "type": "download_media",
                    "status": "success",
                    "file_data": encoded_data,
                    "file_size": file_size,
                    "offset": offset,
                    "is_complete": False,
                    "request_id": request_id
                }
            send_response(client_sock, resp)
            logging.debug(f"发送下载块: file_id={file_id}, offset={offset}, size={len(chunk)}, path={file_path}")
        return resp
    except Exception as e:
        logging.error(f"文件下载失败: {e}, path={file_path}")
        resp = {"type": "download_media", "status": "error", "message": f"文件下载失败: {e}", "request_id": request_id}
        send_response(client_sock, resp)
        return resp

def get_chat_history_paginated(request: dict, client_sock: socket.socket) -> dict:
    """处理分页获取聊天记录请求，同时返回附件信息（如果存在）"""
    username = request.get("username")
    friend = request.get("friend")
    page = request.get("page", 1)
    page_size = request.get("page_size", 20)
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        resp = {
            "type": "chat_history",
            "status": "error",
            "message": "数据库连接失败",
            "chat_history": [],
            "request_id": request_id
        }
        send_response(client_sock, resp)
        return resp
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT rowid, write_time, sender, receiver, message, attachment_type, attachment_path, original_file_name, thumbnail_path, file_size, duration 
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
            "write_time": row[1],
            "username": row[2],
            "friend_username": row[3],
            "message": row[4],
        }
        if row[5]:
            record["attachment_type"] = row[5]
            # 仅返回随机文件名作为 file_id，而非完整路径
            record["file_id"] = os.path.basename(row[6]) if row[6] else ""
            record["original_file_name"] = row[7]
            record["thumbnail_path"] = row[8]
            record["file_size"] = row[9]
            record["duration"] = row[10]
        history.append(record)
    resp = {
        "type": "chat_history",
        "status": "success",
        "chat_history": history,
        "request_id": request_id
    }
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
            # 检查好友是否存在
            cursor.execute("SELECT * FROM users WHERE username = ?", (friend,))
            if cursor.fetchone() is None:
                return {"type": "add_friend", "status": "error", "message": f"用户 {friend} 不存在，无法添加",
                        "request_id": request_id}
            # 检查好友关系是否已存在
            cursor.execute("SELECT * FROM friends WHERE username = ? AND friend = ?", (username, friend))
            if cursor.fetchone():
                return {"type": "add_friend", "status": "fail", "message": f"{friend} 已是您的好友",
                        "request_id": request_id}
            # 添加双向好友关系
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
                logging.debug(f"Received request: {request}")
            except Exception as e:
                logging.error(f"Data decryption or JSON parsing error: {e}")
                send_response(client_sock, {"status": "error", "message": "Invalid request format"})
                continue

            req_type = request.get("type")
            if req_type == "authenticate":
                response = authenticate(request, client_sock)
                send_response(client_sock, response)
                if response.get("status") == "success":
                    logged_in_user = request.get("username")
                    # 登录成功后主动推送好友列表更新（包括向在线好友推送更新）
                    push_friends_update(logged_in_user)
                continue
            elif req_type == "send_message":
                response = send_message(request, client_sock)
            elif req_type == "send_media":
                response = send_media(request, client_sock)
            elif req_type == "download_media":
                download_media(request, client_sock)
                continue
            elif req_type == "get_chat_history_paginated":
                get_chat_history_paginated(request, client_sock)
                continue
            elif req_type == "add_friend":
                response = add_friend(request, client_sock)
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
