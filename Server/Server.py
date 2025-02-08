#!/usr/bin/env python3
# server.py
import sqlite3
import socket
import threading
import json
from datetime import datetime
import logging
from cryptography.fernet import Fernet

# 配置日志记录
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

# 配置
SERVER_CONFIG = {
    'HOST': 'your host',
    'PORT': 'your port',
    'DB_PATH': r'D:\AppTests\fy\chat_server.db',
    'LOGGING': {
        'LEVEL': logging.DEBUG,
        'FORMAT': '%(asctime)s %(levelname)s: %(message)s'
    }
}

# 加密密钥（双方必须共享相同密钥）
ENCRYPTION_KEY = b'JZ-fJzE7kZDhSyvxCL6odNCB7cP3SdBAnjHR3d2LhcI='
fernet = Fernet(ENCRYPTION_KEY)

# 全局变量
clients = {}  # 存储已登录用户与对应的socket
clients_lock = threading.Lock()

def get_db_connection() -> sqlite3.Connection:
    """建立并返回数据库连接（开启WAL模式）"""
    try:
        conn = sqlite3.connect(SERVER_CONFIG['DB_PATH'], timeout=10, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL')
        return conn
    except sqlite3.Error as e:
        logging.error(f"数据库连接失败: {e}")
        return None

def init_db():
    """初始化数据库，创建必要的表"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
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
        conn.commit()
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
    """发送响应数据到客户端，并使用Fernet加密"""
    try:
        plaintext = json.dumps(response, ensure_ascii=False).encode('utf-8')
        ciphertext = fernet.encrypt(plaintext)
        length_header = len(ciphertext).to_bytes(4, byteorder='big')
        client_sock.sendall(length_header + ciphertext)
    except Exception as e:
        logging.error(f"发送响应失败: {e}")

def authenticate(request: dict, client_sock: socket.socket) -> dict:
    username = request.get("username")
    password = request.get("password")
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        return {"type": "authenticate", "status": "error", "message": "数据库连接失败", "request_id": request_id}
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    result = cursor.fetchone()
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
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO messages (sender, receiver, message, write_time)
            VALUES (?, ?, ?, ?)
        ''', (from_user, to_user, message, current_time))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"写入消息失败: {e}")
        conn.close()
        return {"type": "send_message", "status": "error", "message": "消息保存失败", "request_id": request_id}
    # 推送消息给在线的接收方
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
    conn.close()
    return {"type": "send_message", "status": "success", "message": f"消息已发送给 {to_user}", "request_id": request_id}

def get_chat_history(request: dict, client_sock: socket.socket) -> dict:
    username = request.get("username")
    friend = request.get("friend")
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        response = {
            "type": "chat_history",
            "status": "error",
            "message": "数据库连接失败",
            "chat_history": [],
            "request_id": request_id
        }
        send_response(client_sock, response)
        return response
    cursor = conn.cursor()
    cursor.execute('''
        SELECT write_time, sender, receiver, message FROM messages
        WHERE (sender = ? AND receiver = ?) OR (sender = ? AND receiver = ?)
        ORDER BY write_time
    ''', (username, friend, friend, username))
    messages = cursor.fetchall()
    conn.close()
    history = []
    for msg in messages:
        history.append({
            "write_time": msg[0],
            "username": msg[1],
            "friend_username": msg[2],
            "message": msg[3],
            "verify": f"{msg[1]}+{msg[2]}+is_Vei"
        })
    response = {
        "type": "chat_history",
        "status": "success",
        "chat_history": history,
        "request_id": request_id
    }
    send_response(client_sock, response)
    return response

def add_friend(request: dict, client_sock: socket.socket) -> dict:
    username = request.get("username")
    friend = request.get("friend")
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        return {"type": "add_friend", "status": "error", "message": "数据库连接失败", "request_id": request_id}
    cursor = conn.cursor()
    # 检查好友是否存在
    cursor.execute("SELECT * FROM users WHERE username = ?", (friend,))
    if cursor.fetchone() is None:
        conn.close()
        return {"type": "add_friend", "status": "error", "message": f"用户 {friend} 不存在，无法添加", "request_id": request_id}
    # 检查好友关系是否已存在
    cursor.execute("SELECT * FROM friends WHERE username = ? AND friend = ?", (username, friend))
    if cursor.fetchone():
        conn.close()
        return {"type": "add_friend", "status": "fail", "message": f"{friend} 已是您的好友", "request_id": request_id}
    try:
        # 添加双向好友关系
        cursor.execute('INSERT INTO friends (username, friend) VALUES (?, ?)', (username, friend))
        cursor.execute('INSERT INTO friends (username, friend) VALUES (?, ?)', (friend, username))
        conn.commit()
        response = {"type": "add_friend", "status": "success", "message": f"{friend} 已添加为您的好友", "request_id": request_id}
    except sqlite3.Error as e:
        logging.error(f"添加好友失败: {e}")
        response = {"type": "add_friend", "status": "error", "message": "添加好友失败", "request_id": request_id}
    finally:
        conn.close()
    return response

def get_friends(request: dict, client_sock: socket.socket) -> dict:
    username = request.get("username")
    request_id = request.get("request_id")
    conn = get_db_connection()
    if not conn:
        response = {"type": "get_friends", "status": "error", "message": "数据库连接失败", "request_id": request_id}
        send_response(client_sock, response)
        return response
    cursor = conn.cursor()
    cursor.execute('SELECT friend FROM friends WHERE username = ?', (username,))
    friend_names = [row[0] for row in cursor.fetchall()]
    conn.close()
    # 构造好友列表，每个好友为字典，增加在线状态
    friends = []
    with clients_lock:
        for friend in friend_names:
            friends.append({
                "username": friend,
                "online": friend in clients  # 如果好友在在线列表中，则视为在线
            })
    response = {"type": "get_friends", "status": "success", "friends": friends, "request_id": request_id}
    send_response(client_sock, response)
    return response

def handle_client(client_sock: socket.socket, client_addr):
    logging.info(f"客户端 {client_addr} 已连接")
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
                # 解密并解析请求数据
                decrypted_data = fernet.decrypt(encrypted_data)
                request = json.loads(decrypted_data.decode('utf-8'))
                logging.debug(f"收到请求: {request}")
            except Exception as e:
                logging.error(f"数据解密或JSON解析错误: {e}")
                send_response(client_sock, {"status": "error", "message": "请求格式无效"})
                continue

            req_type = request.get("type")
            if req_type == "authenticate":
                response = authenticate(request, client_sock)
            elif req_type == "send_message":
                response = send_message(request, client_sock)
            elif req_type == "get_chat_history":
                get_chat_history(request, client_sock)
                continue
            elif req_type == "add_friend":
                response = add_friend(request, client_sock)
            elif req_type == "get_friends":
                get_friends(request, client_sock)
                continue
            elif req_type == "exit":
                response = {"type": "exit", "status": "success", "message": f"{request.get('username')} 已退出", "request_id": request.get("request_id")}
                send_response(client_sock, response)
                logging.info(f"客户端 {client_addr} 请求退出")
                break
            else:
                response = {"status": "error", "message": "未知请求类型", "request_id": request.get("request_id")}

            if response:
                send_response(client_sock, response)
    except ConnectionResetError:
        logging.warning(f"客户端 {client_addr} 强制断开连接")
    except Exception as e:
        logging.error(f"处理客户端请求时异常: {e}")
    finally:
        with clients_lock:
            for user, sock in list(clients.items()):
                if sock == client_sock:
                    del clients[user]
                    logging.info(f"用户 {user} 已退出")
                    break
        client_sock.close()
        logging.info(f"关闭连接: {client_addr}")

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
