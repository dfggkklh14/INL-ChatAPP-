#!/usr/bin/env python3
# chat_client.py
import os
import socket
import json
import time
import uuid
import asyncio
import base64
from cryptography.fernet import Fernet

def load_encryption_key():
    key = os.getenv("ENCRYPTION_KEY")
    if key:
        print("从环境变量中加载到密钥:", key)  # 调试用，运行时可去掉
        return key.encode('utf-8')
    key_file = os.path.join(os.path.dirname(__file__), "secret.key")
    print("环境变量中没有找到密钥，尝试从文件加载:", key_file)
    try:
        with open(key_file, "rb") as f:
            return f.read()
    except Exception as e:
        raise ValueError("未能加载加密密钥。请设置 ENCRYPTION_KEY 环境变量或创建 secret.key 文件。") from e

ENCRYPTION_KEY = load_encryption_key()
fernet = Fernet(ENCRYPTION_KEY)

class ChatClient:
    def __init__(self, host='26.102.137.22', port=13746):
        self.config = {
            'host': host,
            'port': port,
            'retries': 5,
            'delay': 2
        }
        self.friends = []  # 保存好友列表
        self._init_connection()
        # 新增新媒体消息回调属性
        self.on_new_media_callback = None
        self.on_progress_callback = None  # 新增进度回调属性

    def _init_connection(self):
        self.is_authenticated = False
        self.username = self.current_friend = None
        self.client_socket = None
        self.send_lock = asyncio.Lock()
        self.pending_requests = {}
        self.on_new_message_callback = None
        self.on_friend_list_update_callback = None  # 好友列表更新回调，用于其他模块更新 UI
        self._connect()

    def _connect(self):
        for _ in range(self.config['retries']):
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.config['host'], self.config['port']))
                print(f"成功连接到服务器 {self.config['host']}:{self.config['port']}")
                return
            except socket.error as e:
                print(f"连接失败: {e}")
                time.sleep(self.config['delay'])
        print("超过最大重试次数，连接失败。")

    def _pack_message(self, data: bytes) -> bytes:
        """为待发送数据添加4字节的长度头"""
        return len(data).to_bytes(4, 'big') + data

    def _encrypt(self, req: dict) -> bytes:
        plaintext = json.dumps(req, ensure_ascii=False).encode('utf-8')
        return fernet.encrypt(plaintext)

    def _decrypt(self, data: bytes) -> dict:
        decrypted = fernet.decrypt(data)
        return json.loads(decrypted.decode('utf-8'))

    def _sync_send_recv(self, req: dict) -> dict:
        try:
            ciphertext = self._encrypt(req)
            msg = self._pack_message(ciphertext)
            self.client_socket.send(msg)
            header = self._recv_all(4)
            if not header or len(header) < 4:
                raise Exception("响应头不完整")
            length = int.from_bytes(header, 'big')
            encrypted_response = self._recv_all(length)
            return self._decrypt(encrypted_response)
        except Exception as e:
            print(f"发送/接收异常: {e}")
            return {"status": "error", "message": str(e)}

    def _recv_all(self, length: int) -> bytes:
        data = b""
        while len(data) < length:
            chunk = self.client_socket.recv(length - len(data))
            if not chunk:
                raise Exception("接收数据异常")
            data += chunk
        return data

    async def _recv_async(self, length: int) -> bytes:
        data = b""
        while len(data) < length:
            chunk = await asyncio.to_thread(self.client_socket.recv, length - len(data))
            if not chunk:
                raise Exception("接收数据异常")
            data += chunk
        return data

    async def authenticate(self, username: str, password: str) -> str:
        req = {
            "type": "authenticate",
            "username": username,
            "password": password,
            "request_id": str(uuid.uuid4())
        }
        resp = await asyncio.to_thread(self._sync_send_recv, req)
        if resp.get("status") == "success":
            self.username, self.is_authenticated = username, True
            return "认证成功"
        return resp.get("message", "账号或密码错误")

    async def start_reader(self):
        while True:
            try:
                header = await self._recv_async(4)
                if len(header) < 4:
                    continue
                length = int.from_bytes(header, 'big')
                encrypted_payload = await self._recv_async(length)
                try:
                    resp = self._decrypt(encrypted_payload)
                    print("解密数据:", resp)
                except Exception as decode_err:
                    print(f"后台读取任务解密异常: {decode_err}")
                    continue

                req_id = resp.get("request_id")
                if req_id in self.pending_requests:
                    self.pending_requests.pop(req_id).set_result(resp)
                elif resp.get("type") == "new_message" and self.on_new_message_callback:
                    asyncio.create_task(self.on_new_message_callback(resp))
                elif resp.get("type") == "new_media" and self.on_new_media_callback:
                    asyncio.create_task(self.on_new_media_callback(resp))
                elif resp.get("type") == "friend_list_update":
                    self.friends = resp.get("friends", [])
                    if self.on_friend_list_update_callback:
                        await self.on_friend_list_update_callback(self.friends)
                else:
                    print("未匹配的响应:", resp)
            except Exception as e:
                print("后台读取任务异常:", e)
                await asyncio.sleep(1)

    def set_progress_callback(self, callback):
        """设置进度回调函数"""
        self.on_progress_callback = callback

    async def _send_file_chunks(self, req: dict, file_path: str, chunk_size=1024 * 1024) -> dict:
        """辅助方法：分块发送文件并更新进度"""
        file_size = os.path.getsize(file_path)
        total_sent = 0

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                chunk_b64 = base64.b64encode(chunk).decode('utf-8')
                chunk_req = req.copy()
                chunk_req["file_data"] = chunk_b64
                chunk_req["total_size"] = file_size
                chunk_req["sent_size"] = total_sent + len(chunk)

                await self.send_request(chunk_req)
                total_sent += len(chunk)

                if self.on_progress_callback:
                    progress = (total_sent / file_size) * 100
                    await self.on_progress_callback("upload", progress, os.path.basename(file_path))

        return {"status": "success"}

    async def send_request(self, req: dict) -> dict:
        try:
            async with self.send_lock:
                ciphertext = self._encrypt(req)
                msg = self._pack_message(ciphertext)
                self.client_socket.send(msg)
            fut = asyncio.get_running_loop().create_future()
            self.pending_requests[req.get("request_id")] = fut
            return await fut
        except Exception as e:
            print("发送请求异常:", e)
            return None

    async def get_chat_history_paginated(self, friend: str, page: int, page_size: int) -> dict:
        req = {
            "type": "get_chat_history_paginated",
            "username": self.username,
            "friend": friend,
            "page": page,
            "page_size": page_size,
            "request_id": str(uuid.uuid4())
        }
        resp = await self.send_request(req)
        return await self.parse_response(resp)

    async def send_message(self, to_user: str, message: str) -> dict:
        req = {
            "type": "send_message",
            "from": self.username,
            "to": to_user,
            "message": message,
            "request_id": str(uuid.uuid4())
        }
        return await self.send_request(req)

    async def send_media(self, to_user: str, file_path: str, file_type: str) -> dict:
        """发送媒体消息，支持进度更新"""
        try:
            original_file_name = os.path.basename(file_path)
            req = {
                "type": "send_media",
                "from": self.username,
                "to": to_user,
                "file_name": original_file_name,
                "file_type": file_type,
                "request_id": str(uuid.uuid4())
            }

            # 分块发送文件
            await self._send_file_chunks(req, file_path)

            # 发送完成信号（如果服务端需要）
            final_req = req.copy()
            final_req["file_data"] = ""  # 表示传输完成
            return await self.send_request(final_req)

        except Exception as e:
            print("发送媒体文件异常:", e)
            return {"status": "error", "message": str(e)}

    async def _receive_file_chunks(self, file_id: str, save_path: str, file_size: int) -> dict:
        """辅助方法：分块接收文件并更新进度"""
        total_received = 0

        with open(save_path, "wb") as f:
            while total_received < file_size:
                chunk_req = {
                    "type": "download_media",
                    "file_id": file_id,
                    "request_id": str(uuid.uuid4())
                }
                resp = await self.send_request(chunk_req)

                if resp.get("status") != "success":
                    return resp

                chunk_data = base64.b64decode(resp["file_data"])
                f.write(chunk_data)
                total_received += len(chunk_data)

                if self.on_progress_callback:
                    progress = (total_received / file_size) * 100
                    await self.on_progress_callback("download", progress, os.path.basename(save_path))

        return {"status": "success", "message": "下载成功", "save_path": save_path}

    async def download_media(self, file_id: str, save_path: str) -> dict:
        """下载媒体文件，支持进度更新"""
        # 先获取文件大小
        init_req = {
            "type": "download_media",
            "file_id": file_id,
            "request_id": str(uuid.uuid4())
        }
        init_resp = await self.send_request(init_req)

        if init_resp.get("status") != "success":
            return init_resp

        file_size = init_resp.get("file_size", 0)
        if not file_size:
            return await self._receive_file_chunks(file_id, save_path, file_size)

        return await self._receive_file_chunks(file_id, save_path, file_size)

    async def add_friend(self, friend_username: str) -> str:
        req = {
            "type": "add_friend",
            "username": self.username,
            "friend": friend_username,
            "request_id": str(uuid.uuid4())
        }
        resp = await self.send_request(req)
        return resp.get("message", "")

    async def parse_response(self, resp: dict) -> dict:
        """
        解析聊天记录响应，若存在媒体消息，则返回相关扩展字段：
          attachment_type, file_id, original_file_name, thumbnail_path, file_size, duration
        """
        history = resp.get("chat_history", [])
        parsed, errors = [], []
        for entry in history:
            try:
                parsed_entry = {
                    "write_time": entry.get("write_time"),
                    "sender_username": entry.get("username"),
                    "message": entry.get("message"),
                    "is_current_user": (entry.get("username") == self.username)
                }
                # 如果有媒体消息扩展字段，则解析
                if "attachment_type" in entry:
                    parsed_entry["attachment_type"] = entry.get("attachment_type")
                    parsed_entry["file_id"] = entry.get("file_id")
                    parsed_entry["original_file_name"] = entry.get("original_file_name")
                    parsed_entry["thumbnail_path"] = entry.get("thumbnail_path")
                    parsed_entry["file_size"] = entry.get("file_size")
                    parsed_entry["duration"] = entry.get("duration")
                parsed.append(parsed_entry)
            except Exception as ex:
                errors.append({"entry": entry, "error": str(ex)})
        res = {"type": "chat_history", "data": parsed, "request_id": resp.get("request_id")}
        if errors:
            res["errors"] = errors
        return res

    async def close_connection(self):
        try:
            req = {
                "type": "exit",
                "username": self.username,
                "request_id": str(uuid.uuid4())
            }
            await self.send_request(req)
        except Exception as e:
            print("发送退出请求异常:", e)
        try:
            self.client_socket.close()
            print("连接已关闭")
        except Exception as e:
            print("关闭 socket 异常:", e)
