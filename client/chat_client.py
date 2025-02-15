#!/usr/bin/env python3
# chat_client.py
import socket
import json
import time
import uuid
import asyncio
from cryptography.fernet import Fernet

ENCRYPTION_KEY = b'JZ-fJzE7kZDhSyvxCL6odNCB7cP3SdBAnjHR3d2LhcI='
fernet = Fernet(ENCRYPTION_KEY)

class ChatClient:
    def __init__(self, host='26.102.137.22', port=10026):
        self.config = {
            'host': host,
            'port': port,
            'retries': 5,
            'delay': 2
        }
        self.friends = []  # 保存好友列表
        self._init_connection()

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
                    print("Decrypted data:", resp)
                except Exception as decode_err:
                    print(f"Background read task exception: {decode_err}")
                    continue

                req_id = resp.get("request_id")
                if req_id in self.pending_requests:
                    self.pending_requests.pop(req_id).set_result(resp)
                elif resp.get("type") == "new_message" and self.on_new_message_callback:
                    asyncio.create_task(self.on_new_message_callback(resp))
                elif resp.get("type") == "friend_list_update":
                    self.friends = resp.get("friends", [])
                    if self.on_friend_list_update_callback:
                        await self.on_friend_list_update_callback(self.friends)
                else:
                    print("Unmatched response:", resp)
            except Exception as e:
                print("Background read task exception:", e)
                await asyncio.sleep(1)

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

    async def send_message(self, from_user: str, to_user: str, message: str) -> dict:
        req = {
            "type": "send_message",
            "from": from_user,
            "to": to_user,
            "message": message,
            "request_id": str(uuid.uuid4())
        }
        return await self.send_request(req)

    async def add_friend(self, friend_username: str) -> str:
        req = {
            "type": "add_friend",
            "username": self.username,
            "friend": friend_username,
            "request_id": str(uuid.uuid4())
        }
        resp = await self.send_request(req)
        return resp.get("message", "添加好友失败")

    async def parse_response(self, resp: dict) -> dict:
        history = resp.get("chat_history", [])
        parsed, errors = [], []
        for entry in history:
            try:
                wt = entry.get("write_time")
                sender = entry.get("username")
                msg = entry.get("message")
                if not (wt and sender and msg):
                    raise ValueError("缺少字段")
                parsed.append({
                    "write_time": wt,
                    "sender_username": sender,
                    "message": msg,
                    "is_current_user": (sender == self.username)
                })
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
