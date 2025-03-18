#!/usr/bin/env python3
# chat_client.py
import copy
import logging
import os
import socket
import json
import time
import uuid
import asyncio
import base64
from typing import List, Optional, Callable

from PyQt5.QtCore import QBuffer
from PyQt5.QtGui import QPixmap
from cryptography.fernet import Fernet

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)


def load_encryption_key():
    key = os.getenv("ENCRYPTION_KEY")
    if key:
        return key.encode('utf-8')
    key_file = os.path.join(os.path.dirname(__file__), "secret.key")
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
        self.is_running = True
        self.reader_task = None
        self.friends = []  # 包含所有好友信息和会话数据
        self.unread_messages = {}  # 保留未读消息计数
        self.on_conversations_update_callback = None
        self._init_connection()
        self.cache_root = os.path.join(os.path.dirname(__file__), "Chat_DATA")
        self.avatar_dir = os.path.join(self.cache_root, "avatars")
        self.thumbnail_dir = os.path.join(self.cache_root, "thumbnails")
        os.makedirs(self.avatar_dir, exist_ok=True)
        os.makedirs(self.thumbnail_dir, exist_ok=True)

    def _init_connection(self):
        self.is_authenticated = False
        self.username = self.current_friend = None
        self.client_socket = None
        self.send_lock = asyncio.Lock()
        self.pending_requests = {}
        self.on_new_message_callback = None
        self.on_friend_list_update_callback = None
        self.on_new_media_callback = None
        self.on_update_remarks_callback = None
        self.reply_to_id = None
        self._connect()

    def _connect(self):
        for _ in range(self.config['retries']):
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.config['host'], self.config['port']))
                return
            except socket.error as e:
                time.sleep(self.config['delay'])

    def _pack_message(self, data: bytes) -> bytes:
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
            return {"status": "error", "message": str(e)}

    def _recv_all(self, length: int) -> bytes:
        data = b""
        while len(data) < length:
            chunk = self.client_socket.recv(length - len(data))
            if not chunk:
                raise Exception("接收数据异常")
            data += chunk
        return data

    async def _recv_async(self, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = await asyncio.get_event_loop().sock_recv(self.client_socket, size - len(data))
            if not chunk:
                raise ConnectionError("连接断开")
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

    async def update_friend_remarks(self, friend: str, remarks: str) -> dict:
        req = {
            "type": "Update_Remarks",
            "username": self.username,
            "friend": friend,
            "remarks": remarks,
            "request_id": str(uuid.uuid4())
        }
        resp = await self.send_request(req)
        if resp.get("status") == "success":
            for f in self.friends:
                if f.get("username") == friend:
                    f["name"] = remarks
                    break
            if self.on_friend_list_update_callback:
                await self.on_friend_list_update_callback(self.friends)
        return resp

    def get_friend_remarks(self, friend_username: str) -> str:
        for friend in self.friends:
            if friend.get("username") == friend_username:
                return friend.get("name", friend_username)
        return friend_username

    async def start_reader(self):
        while True:
            try:
                header = await self._recv_async(4)
                if len(header) < 4:
                    logging.warning("接收到的头部数据不完整，继续等待")
                    continue
                length = int.from_bytes(header, 'big')
                encrypted_payload = await self._recv_async(length)
                resp = self._decrypt(encrypted_payload)

                req_id = resp.get("request_id")
                if req_id in self.pending_requests:
                    self.pending_requests.pop(req_id).set_result(resp)
                elif resp.get("type") in ["new_message", "new_media"] and (
                        self.on_new_message_callback or self.on_new_media_callback):
                    await self.parsing_new_message_or_media(resp)
                elif resp.get("type") == "friend_list_update":
                    self.friends = resp.get("friends", [])
                    if self.on_friend_list_update_callback:
                        asyncio.create_task(self.on_friend_list_update_callback(self.friends))
                    if self.on_conversations_update_callback:
                        asyncio.create_task(self.on_conversations_update_callback(self.friends))
                elif resp.get("type") == "Update_Remarks" and self.on_update_remarks_callback:
                    asyncio.create_task(self.on_update_remarks_callback(resp))
                elif resp.get("type") == "messages_deleted" and self.on_conversations_update_callback:
                    await self.parsing_delete_message(resp)  # 保留原有逻辑，仅更新 friends
                elif resp.get("type") == "deleted_messages" and self.on_conversations_update_callback:
                    await self.parsing_delete_message(resp)  # 更新 friends
                    # 添加气泡移除逻辑，不显示浮动提示
                    if self.on_new_message_callback:  # 确保有 ChatWindow 实例
                        chat_window = self._get_chat_window()
                        if chat_window and chat_window.chat_components.get('chat'):
                            deleted_rowids = resp.get("deleted_rowids", [])
                            if deleted_rowids and chat_window.client.current_friend in [resp.get("from"),
                                                                                        resp.get("to")]:
                                await chat_window.chat_components['chat'].remove_bubbles_by_rowids(deleted_rowids,
                                                                                                   show_floating_label=False)
            except Exception as e:
                logging.error(f"读取推送消息失败: {e}")
                if not self.is_running:
                    break
                await asyncio.sleep(1)

    async def parsing_new_message_or_media(self, resp: dict):
        """解析并处理新消息或媒体通知，直接更新 self.friends"""
        sender = resp.get("from", "")
        if not sender:
            return

        # 查找并更新对应的好友项
        for friend in self.friends:
            if friend.get("username") == sender:
                if resp.get("type") == "new_media":
                    if "thumbnail_path" in resp:
                        thumbnail_path = resp["thumbnail_path"]
                        file_id = os.path.basename(thumbnail_path)
                        save_path = os.path.join(self.thumbnail_dir, file_id)
                        if not os.path.exists(save_path):
                            await self.download_media(file_id, save_path)
                        resp["thumbnail_local_path"] = save_path
                    friend["conversations"] = {
                        "sender": resp.get("from"),
                        "content": resp.get("conversations", f"[{resp.get('file_type', '文件')}]"),
                        "last_update_time": resp.get("write_time", "")
                    }
                else:  # 新消息
                    friend["conversations"] = {
                        "sender": resp.get("from"),
                        "content": resp.get("message", ""),
                        "last_update_time": resp.get("write_time", "")
                    }
                break
        # 判断是否需要增加未读消息计数
        should_increment_unread = True
        if sender == self.current_friend and self.on_new_message_callback:
            chat_window = self._get_chat_window()
            if chat_window and chat_window.isVisible() and not chat_window.isMinimized():
                scroll = chat_window.chat_components.get('scroll')
                if scroll:
                    sb = scroll.verticalScrollBar()
                    if sb.maximum() - sb.value() <= 5:
                        should_increment_unread = False
        if should_increment_unread:
            self.unread_messages[sender] = self.unread_messages.get(sender, 0) + 1
        # 触发对话更新回调
        if self.on_conversations_update_callback:
            asyncio.create_task(self.on_conversations_update_callback(self.friends, affected_users=[sender]))
        # 根据消息类型触发特定回调
        if resp.get("type") == "new_message" and self.on_new_message_callback:
            asyncio.create_task(self.on_new_message_callback(resp))
        elif resp.get("type") == "new_media" and self.on_new_media_callback:
            asyncio.create_task(self.on_new_media_callback(resp))

    def _get_chat_window(self):
        """辅助方法：获取 ChatWindow 实例"""
        if hasattr(self.on_new_message_callback, '__self__'):
            return self.on_new_message_callback.__self__
        return None

    def clear_unread_messages(self, friend: str):
        if friend in self.unread_messages:
            self.unread_messages[friend] = 0

    async def get_user_info(self) -> dict:
        req = {
            "type": "get_user_info",
            "username": self.username,
            "request_id": str(uuid.uuid4())
        }
        resp = await self.send_request(req)
        if resp.get("status") == "success" and "avatar_id" in resp:
            avatar_id = resp["avatar_id"]
            save_path = os.path.join(self.avatar_dir, avatar_id)
            if not os.path.exists(save_path):
                await self.download_media(avatar_id, save_path)
            resp["avatar_local_path"] = save_path
        return resp

    async def _send_file_chunks(self, req: dict, file_path: str, progress_callback=None,
                                chunk_size=1024 * 1024) -> dict:
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
                if progress_callback:
                    progress = (total_sent / file_size) * 100
                    await progress_callback("upload", progress, os.path.basename(file_path))
        return {"status": "success"}

    async def send_request(self, req: dict) -> dict:
        try:
            async with self.send_lock:
                ciphertext = self._encrypt(req)
                msg = self._pack_message(ciphertext)
                self.client_socket.send(msg)
            fut = asyncio.get_event_loop().create_future()
            self.pending_requests[req.get("request_id")] = fut
            return await fut
        except Exception as e:
            return {"status": "error", "message": str(e)}

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
        parsed_resp = await self.parse_response(resp)
        for entry in parsed_resp["data"]:
            if "thumbnail_path" in entry:
                thumbnail_path = entry["thumbnail_path"]
                file_id = os.path.basename(thumbnail_path)
                save_path = os.path.join(self.thumbnail_dir, file_id)
                if not os.path.exists(save_path):
                    await self.download_media(file_id, save_path)
                entry["thumbnail_local_path"] = save_path
        return parsed_resp

    async def send_message(self, to_user: str, message: str, reply_to: int = None) -> dict:
        req = {
            "type": "send_message",
            "from": self.username,
            "to": to_user,
            "message": message,
            "request_id": str(uuid.uuid4())
        }
        if reply_to is not None:
            req["reply_to"] = reply_to
        resp = await self.send_request(req)
        if resp.get("status") == "success":
            for friend in self.friends:
                if friend.get("username") == to_user:
                    friend["conversations"] = {"sender": self.username, "content": resp.get("conversations", message), "last_update_time": resp.get("write_time", "")}
                    break
            asyncio.create_task(self.on_conversations_update_callback(self.friends))
        return resp

    async def send_media(self, to_user: str, file_path: str, file_type: str, reply_to: Optional[int] = None,
                         message: str = "", progress_callback=None) -> dict:
        try:
            original_file_name = os.path.basename(file_path)
            request_id = str(uuid.uuid4())
            req = {
                "type": "send_media",
                "from": self.username,
                "to": to_user,
                "file_name": original_file_name,
                "file_type": file_type,
                "request_id": request_id,
                "message": message
            }
            if reply_to is not None:
                req["reply_to"] = reply_to

            await self._send_file_chunks(req, file_path, progress_callback)
            final_req = req.copy()
            final_req["file_data"] = ""
            response = await self.send_request(final_req)
            if response.get("status") == "success":
                if "text_message" in response:
                    response["message"] = response["text_message"]
                for friend in self.friends:
                    if friend.get("username") == to_user:
                        friend["conversations"] = {"sender": self.username, "content": response.get("conversations", f"[{file_type}]"), "last_update_time": response.get("write_time", "")}
                        break
                asyncio.create_task(self.on_conversations_update_callback(self.friends))
            return response
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def send_multiple_media(self, to_user: str, file_paths: List[str], progress_callback=None,
                                  message: str = "", reply_to: Optional[int] = None) -> List[dict]:
        tasks = []
        for file_path in file_paths:
            file_type = self._detect_file_type(file_path)
            task = asyncio.create_task(
                self.send_media(to_user, file_path, file_type, reply_to, message, progress_callback))
            tasks.append(task)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [result if not isinstance(result, Exception) else {"status": "error", "message": str(result)} for result
                in results]

    def _detect_file_type(self, file_path: str) -> str:
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.ico'}
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
        ext = os.path.splitext(file_path)[1].lower()
        if ext in image_extensions:
            return 'image'
        elif ext in video_extensions:
            return 'video'
        else:
            return 'file'

    async def parsing_delete_message(self, resp):
        from_user = resp.get("from")
        to_user = resp.get("to")
        conversations = resp.get("conversations", "")
        write_time = resp.get("write_time", "")
        affected_users = []
        for friend in self.friends:
            if friend.get("username") == from_user:
                friend["conversations"] = {"sender": from_user, "content": conversations, "last_update_time": write_time} if conversations else None
                affected_users.append(from_user)
            elif friend.get("username") == to_user:
                friend["conversations"] = {"sender": to_user, "content": conversations, "last_update_time": write_time} if conversations else None
                affected_users.append(to_user)
        if affected_users:
            asyncio.create_task(self.on_conversations_update_callback(self.friends, affected_users=affected_users))

    async def delete_messages(self, rowids: int | List[int]) -> dict:
        if not self.is_authenticated:
            return {"status": "error", "message": "未登录，无法删除消息"}

        req = {
            "type": "delete_messages",
            "username": self.username,
            "request_id": str(uuid.uuid4())
        }
        if isinstance(rowids, int):
            req["rowid"] = rowids
        elif isinstance(rowids, list):
            if not rowids:
                return {"status": "error", "message": "消息ID列表不能为空"}
            req["rowids"] = rowids
        else:
            return {"status": "error", "message": "rowids 参数必须是整数或整数列表"}

        resp = await self.send_request(req)
        if resp.get("status") == "success" and self.current_friend:
            # 保留对 self.friends 的更新
            for friend in self.friends:
                if friend.get("username") == self.current_friend:
                    friend["conversations"] = {
                        "sender": self.username,
                        "content": resp.get("conversations", ""),
                        "last_update_time": resp.get("write_time", "")
                    } if resp.get("conversations") else None
                    break
            # 不触发回调，交给调用方处理
        return resp

    async def upload_avatar(self, avatar: QPixmap) -> dict:
        buffer = QBuffer()
        buffer.open(QBuffer.WriteOnly)
        avatar.save(buffer, "JPEG")
        file_data = buffer.data()
        buffer.close()
        file_data_b64 = base64.b64encode(file_data).decode('utf-8')

        req = {
            "type": "upload_avatar",
            "username": self.username,
            "file_data": file_data_b64,
            "request_id": str(uuid.uuid4())
        }
        resp = await self.send_request(req)
        if resp.get("status") == "success" and "avatar_id" in resp:
            avatar_id = resp["avatar_id"]
            save_path = os.path.join(self.avatar_dir, avatar_id)
            if not os.path.exists(save_path):
                await self.download_media(avatar_id, save_path)
            resp["avatar_local_path"] = save_path
        return resp

    async def update_name(self, new_name: str) -> dict:
        if not self.is_authenticated:
            return {"status": "error", "message": "未登录，无法更改昵称"}
        req = {
            "type": "update_name",
            "username": self.username,
            "new_name": new_name,
            "request_id": str(uuid.uuid4())
        }
        resp = await self.send_request(req)
        return resp

    async def update_sign(self, new_sign: str) -> dict:
        if not self.is_authenticated:
            return {"status": "error", "message": "未登录，无法更改签名"}
        req = {
            "type": "update_sign",
            "username": self.username,
            "sign": new_sign,
            "request_id": str(uuid.uuid4())
        }
        resp = await self.send_request(req)
        return resp

    async def download_media(self, file_id: str, save_path: str, progress_callback: Optional[Callable] = None) -> dict:
        received_size = 0
        offset = 0
        try:
            with open(save_path, "wb") as f:
                while True:
                    req = {
                        "type": "download_media",
                        "file_id": file_id,
                        "offset": offset,
                        "request_id": str(uuid.uuid4())
                    }
                    resp = await self.send_request(req)
                    if resp.get("status") != "success":
                        return resp
                    total_size = resp.get("file_size", 0)
                    file_data_b64 = resp.get("file_data", "")
                    if file_data_b64:
                        file_data = base64.b64decode(file_data_b64)
                        f.write(file_data)
                        received_size += len(file_data)
                        offset += len(file_data)
                        if progress_callback:
                            progress = (received_size / total_size) * 100 if total_size else 0
                            await progress_callback("download", progress, os.path.basename(save_path))
                    if resp.get("is_complete", False):
                        break
            if total_size and received_size != total_size:
                return {"status": "error", "message": f"下载不完整: 收到 {received_size} / {total_size} 字节"}
            return {"status": "success", "message": "下载成功", "save_path": save_path}
        except Exception as e:
            if os.path.exists(save_path):
                os.remove(save_path)
            return {"status": "error", "message": f"下载失败: {str(e)}"}

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
        history = resp.get("chat_history", [])
        parsed, errors = [], []
        for entry in history:
            try:
                parsed_entry = {
                    "rowid": entry.get("rowid"),
                    "write_time": entry.get("write_time"),
                    "sender_username": entry.get("username"),
                    "message": entry.get("message", ""),
                    "is_current_user": (entry.get("username") == self.username),
                    "reply_to": entry.get("reply_to"),
                    "reply_preview": entry.get("reply_preview")
                }
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
        self.is_running = False  # 先停止 reader
        if self.reader_task and not self.reader_task.done():
            try:
                self.reader_task.cancel()
                await asyncio.wait([self.reader_task], timeout=1.0)  # 等待 reader 退出
            except Exception as e:
                logging.error(f"取消 reader 任务失败: {e}")

        if self.client_socket:
            try:
                req = {"type": "exit", "username": self.username, "request_id": str(uuid.uuid4())}
                await self.send_request(req)
            except Exception as e:
                logging.error(f"发送退出请求失败: {e}")
            finally:
                try:
                    self.client_socket.close()
                except Exception as e:
                    logging.error(f"关闭 socket 失败: {e}")
                self.client_socket = None
        self.is_authenticated = False
        self.username = None
        logging.info("客户端连接已关闭")