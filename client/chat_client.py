#!/usr/bin/env python3
# chat_client.py
import logging
import os
import socket
import json
import time
import uuid
import asyncio
import base64
from typing import List, Optional, Callable

from PyQt5.QtCore import QBuffer, QObject, pyqtSignal
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


class ChatClient(QObject):
    # 定义所有信号
    friend_list_updated = pyqtSignal(list)           # 好友列表更新
    conversations_updated = pyqtSignal(list, list, list, bool)  # 对话更新，参数：friends, affected_users, deleted_rowids
    new_message_received = pyqtSignal(dict)          # 新消息接收
    new_media_received = pyqtSignal(dict)            # 新媒体接收
    remarks_updated = pyqtSignal(dict)               # 备注更新

    def __init__(self, host='26.102.137.22', port=13235):
        super().__init__()
        self.config = {
            'host': host,
            'port': port,
            'retries': 5,
            'delay': 2
        }
        self.is_running = True
        self.reader_task = None
        self.register_task = None
        self.register_active = False
        self.register_requests = {}
        self.lock = asyncio.Lock()
        self.friends = []
        self.unread_messages = {}

        # 从 config.json 加载缓存路径
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding='utf-8') as f:
                config = json.load(f)
            self.cache_root = config.get("cache_path", os.path.join(os.path.dirname(__file__), "Chat_DATA"))
        else:
            self.cache_root = os.path.join(os.path.dirname(__file__), "Chat_DATA")

        self.avatar_dir = os.path.join(self.cache_root, "avatars")
        self.thumbnail_dir = os.path.join(self.cache_root, "thumbnails")
        os.makedirs(self.avatar_dir, exist_ok=True)
        os.makedirs(self.thumbnail_dir, exist_ok=True)

        self.chat_window = None
        # 直接初始化变量，不调用 _connect
        self.is_authenticated = False
        self.username = self.current_friend = None
        self.client_socket = None
        self.send_lock = asyncio.Lock()
        self.pending_requests = {}
        self.reply_to_id = None

    async def start(self):
        if self.register_active and self.register_task:
            self.register_active = False
            self.register_task.cancel()
            try:
                await self.register_task
            except asyncio.CancelledError:
                return
        self.reader_task = asyncio.create_task(self.start_reader())

    def _init_connection(self):
        if self.client_socket is None:  # 避免重复连接
            self._connect()

    def _connect(self):
        for attempt in range(self.config['retries']):
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.config['host'], self.config['port']))
                return
            except socket.error as e:
                logging.warning(f"连接尝试 {attempt + 1}/{self.config['retries']} 失败: {e}")
                if attempt < self.config['retries'] - 1:
                    time.sleep(self.config['delay'])
        raise ConnectionError("无法连接到服务器")

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
            self.friend_list_updated.emit(self.friends)
        return resp

    async def start_reader(self):
        while self.is_running:
            try:
                header = await self._recv_async(4)
                if len(header) < 4:
                    continue
                length = int.from_bytes(header, 'big')
                encrypted_payload = await self._recv_async(length)
                resp = self._decrypt(encrypted_payload)

                # 未登录状态下的消息过滤
                if not self.is_authenticated and resp.get("type") not in ["user_register", "exit"]:
                    continue  # 丢弃非注册或退出相关的消息

                # 处理退出消息
                if resp.get("type") == "exit":
                    self.is_running = False
                    req_id = resp.get("request_id")
                    if req_id in self.pending_requests:
                        self.pending_requests.pop(req_id).set_result(resp)
                    break

                # 处理请求响应
                req_id = resp.get("request_id")
                if req_id in self.pending_requests:
                    self.pending_requests.pop(req_id).set_result(resp)
                # 处理推送消息（仅在登录后有效）
                elif resp.get("type") in ["new_message", "new_media"]:
                    await self.parsing_new_message_or_media(resp)
                elif resp.get("type") == "friend_list_update":
                    self.friends = resp.get("friends", [])
                    self.friend_list_updated.emit(self.friends)
                elif resp.get("type") == "friend_update":
                    friend = resp.get("friend", {})
                    friend_id = friend.get("username")
                    if friend_id:
                        for i, f in enumerate(self.friends):
                            if f.get("username") == friend_id:
                                self.friends[i] = friend
                                break
                        else:
                            self.friends.append(friend)
                        self.friend_list_updated.emit(self.friends)
                elif resp.get("type") == "deleted_messages":
                    await self.parsing_delete_message(resp)
                elif resp.get("type") == "Update_Remarks":
                    self.remarks_updated.emit(resp)

            except Exception as e:
                logging.error(f"读取推送消息失败: {e}")
                if not self.is_running:
                    break
                await asyncio.sleep(1)

    async def register_reader(self):
        self.register_active = True
        try:
            while self.register_active:
                header = await self._recv_async(4)
                if len(header) < 4:
                    continue
                length = int.from_bytes(header, 'big')
                encrypted_payload = await self._recv_async(length)
                resp = self._decrypt(encrypted_payload)

                if resp.get("type") == "user_register":
                    req_id = resp.get("request_id")
                    if req_id in self.register_requests:
                        self.register_requests.pop(req_id).set_result(resp)
                else:
                    return
        except Exception as e:
            logging.error(f"注册监听失败: {e}")
            for fut in self.register_requests.values():
                if not fut.done():
                    fut.set_exception(e)
        finally:
            self.register_active = False
            self.register_task = None

    # 修改后的 register 方法
    async def register(self, subtype: str, session_id: str = None, captcha_input: str = None,
                       password: str = None, avatar: QPixmap = None, nickname: str = None, sign: str = None) -> dict:
        """处理用户注册请求"""
        req = {
            "type": "user_register",
            "subtype": subtype,
            "request_id": str(uuid.uuid4())
        }
        if session_id:
            req["session_id"] = session_id

        # 检查并异步初始化 socket
        if not self.client_socket:
            try:
                # 使用 asyncio.to_thread 异步执行同步的 _connect 方法
                await asyncio.to_thread(self._connect)
            except ConnectionError as e:
                logging.error(f"连接服务器失败")
                return {"status": "error", "message": "无法连接到服务器，请检查网络后重试"}
            except Exception as e:
                logging.error(f"异步连接服务器时发生未知错误: {str(e)}")
                return {"status": "error", "message": "连接服务器时发生错误，请稍后重试"}

        if not self.register_active:
            self.register_task = asyncio.create_task(self.register_reader())

        # 发送请求
        try:
            async with self.send_lock:
                ciphertext = self._encrypt(req)
                msg = self._pack_message(ciphertext)
                self.client_socket.send(msg)
        except AttributeError:  # 如果 self.client_socket 仍为 None
            return {"status": "error", "message": "客户端未正确初始化，请重试"}
        except Exception as e:
            logging.error(f"发送注册请求失败")
            return {"status": "error", "message": "发送请求失败"}

        # 等待响应
        fut = asyncio.get_event_loop().create_future()
        self.register_requests[req["request_id"]] = fut
        resp = await fut

        # 处理响应（保持原有逻辑）
        if subtype == "register_1":
            if resp.get("status") == "success":
                return {
                    "status": "success",
                    "username": resp.get("username"),
                    "captcha_image": resp.get("captcha_image"),
                    "session_id": resp.get("session_id")
                }
            return resp
        elif subtype == "register_2":
            if not captcha_input:
                return {"status": "error", "message": "请输入验证码"}
            req["captcha_input"] = captcha_input
            async with self.send_lock:
                ciphertext = self._encrypt(req)
                msg = self._pack_message(ciphertext)
                try:
                    self.client_socket.send(msg)
                except Exception as e:
                    return {"status": "error", "message": f"发送请求失败: {str(e)}"}
                fut = asyncio.get_event_loop().create_future()
                self.register_requests[req["request_id"]] = fut
                return await fut
        elif subtype == "register_3":
            if not password:
                return {"status": "error", "message": "密码不能为空"}
            req["password"] = password
            if avatar:
                buffer = QBuffer()
                buffer.open(QBuffer.WriteOnly)
                avatar.save(buffer, "JPEG")
                file_data = buffer.data()
                buffer.close()
                req["avatar_data"] = base64.b64encode(file_data).decode('utf-8')
            req["nickname"] = nickname or ""
            req["sign"] = sign or ""
            async with self.send_lock:
                ciphertext = self._encrypt(req)
                msg = self._pack_message(ciphertext)
                try:
                    self.client_socket.send(msg)
                except Exception as e:
                    return {"status": "error", "message": f"发送请求失败: {str(e)}"}
                fut = asyncio.get_event_loop().create_future()
                self.register_requests[req["request_id"]] = fut
                resp = await fut
                if resp.get("status") == "success":
                    self.register_active = False
                    if self.register_task:
                        self.register_task.cancel()
                return resp
        elif subtype == "register_4":
            if not session_id:
                return {"status": "error", "message": "会话ID缺失"}
            async with self.send_lock:
                ciphertext = self._encrypt(req)
                msg = self._pack_message(ciphertext)
                try:
                    self.client_socket.send(msg)
                except Exception as e:
                    return {"status": "error", "message": f"发送请求失败: {str(e)}"}
                fut = asyncio.get_event_loop().create_future()
                self.register_requests[req["request_id"]] = fut
                resp = await fut
                if resp.get("status") == "success":
                    return {
                        "status": "success",
                        "captcha_image": resp.get("captcha_image"),
                        "session_id": resp.get("session_id")
                    }
                return resp
        return {"status": "error", "message": "未知的子类型"}

    async def parsing_new_message_or_media(self, resp: dict):
        sender = resp.get("from", "")
        if not sender:
            return

        for friend in self.friends:
            if friend.get("username") == sender:
                if resp.get("type") == "new_media":
                    file_id = resp.get("file_id")
                    file_type = resp.get("file_type")
                    thumbnail_data = resp.get("thumbnail_data")
                    save_path = os.path.join(self.thumbnail_dir, f"{file_id}")
                    if thumbnail_data and not os.path.exists(save_path):
                        try:
                            thumbnail_bytes = base64.b64decode(thumbnail_data)
                            with open(save_path, "wb") as f:
                                f.write(thumbnail_bytes)
                            logging.debug(f"保存缩略图: file_id={file_id}, save_path={save_path}")
                        except Exception as e:
                            logging.error(f"保存缩略图失败: file_id={file_id}, error={e}")
                    resp["thumbnail_local_path"] = save_path
                    friend["conversations"] = {
                        "sender": resp.get("from"),
                        "content": resp.get("conversations", f"[{resp.get('file_type', '文件')}]"),
                        "last_update_time": resp.get("write_time", "")
                    }
                else:
                    friend["conversations"] = {
                        "sender": resp.get("from"),
                        "content": resp.get("message", ""),
                        "last_update_time": resp.get("write_time", "")
                    }
                break

        should_increment_unread = True
        if sender == self.current_friend:
            chat_window = self._get_chat_window()
            if chat_window and chat_window.isVisible() and not chat_window.isMinimized():
                scroll = chat_window.chat_components.get('scroll')
                if scroll:
                    sb = scroll.verticalScrollBar()
                    if sb.maximum() - sb.value() <= 5:
                        should_increment_unread = False
        if should_increment_unread:
            self.unread_messages[sender] = self.unread_messages.get(sender, 0) + 1

        # 发射对话更新信号
        self.conversations_updated.emit(self.friends, [sender], [], False)

        # 根据消息类型发射特定信号
        if resp.get("type") == "new_message":
            self.new_message_received.emit(resp)
        elif resp.get("type") == "new_media":
            logging.debug(f"发射新媒体信号: {resp}")
            self.new_media_received.emit(resp)

    def _get_chat_window(self):
        """辅助方法：获取 ChatWindow 实例"""
        return getattr(self, 'chat_window', None)

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
                await self.download_media(avatar_id, save_path, "avatar")  # 指定为 avatar 类型
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

        # 处理缩略图下载
        for entry in parsed_resp["data"]:
            if "file_id" in entry and entry.get("attachment_type") in ["image", "video"]:
                file_id = entry["file_id"]
                save_path = os.path.join(self.thumbnail_dir, f"{file_id}_thumbnail")
                if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:  # 检查文件是否存在且有效
                    result = await self.download_media(file_id, save_path, "thumbnail")
                    if result.get("status") != "success":
                        logging.error(f"缩略图下载失败: {result.get('message')}")
                entry["thumbnail_local_path"] = save_path  # 始终设置本地路径
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
                    friend["conversations"] = {
                        "sender": self.username,
                        "content": resp.get("conversations", message),
                        "last_update_time": resp.get("write_time", "")
                    }
                    break
            self.conversations_updated.emit(self.friends, [to_user], [], False)
        return resp

    async def send_media(self, to_user: str, file_path: str, file_type: str, reply_to: Optional[int] = None,
                         message: str = "", progress_callback: Optional[Callable] = None) -> dict:
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
                        friend["conversations"] = {
                            "sender": self.username,
                            "content": response.get("conversations", f"[{file_type}]"),
                            "last_update_time": response.get("write_time", "")
                        }
                        break
                self.conversations_updated.emit(self.friends, [to_user], [], False)
            return response
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def send_multiple_media(self, to_user: str, file_paths: List[str], progress_callback: Optional[Callable] = None,
                                  message: str = "", reply_to: Optional[int] = None) -> List[dict]:
        tasks = []
        for file_path in file_paths:
            file_type = self._detect_file_type(file_path)
            task = asyncio.create_task(
                self.send_media(to_user, file_path, file_type, reply_to, message, progress_callback))
            tasks.append(task)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        processed_results = [result if not isinstance(result, Exception) else {"status": "error", "message": str(result)} for result in results]
        return processed_results

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
        if resp.get("type") == "messages_deleted":
            user1 = self.username
            user2 = self.current_friend
        else:
            user2 = resp.get("from")
            user1 = resp.get("to")
        conversations = resp.get("conversations", "")
        write_time = resp.get("write_time", "")
        show_floating_label = resp.get("show_floating_label", False)  # 获取新字段，默认 False

        new_conversation = {"sender": user1, "content": conversations, "last_update_time": write_time} if conversations else None
        for friend in self.friends:
            if friend.get("username") in (user1, user2):
                friend["conversations"] = new_conversation

        deleted_rowids = resp.get("deleted_rowids", [])
        if not isinstance(deleted_rowids, list):
            deleted_rowids = [deleted_rowids]

        affected_users = [user2] if user2 else []
        # 传递 show_floating_label 给信号
        self.conversations_updated.emit(self.friends, affected_users, deleted_rowids, show_floating_label)

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
        asyncio.create_task(self.parsing_delete_message(resp))
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
                await self.download_media(avatar_id, save_path, "avatar")
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

    async def download_media(self, file_id: str, save_path: str, download_type: str = "default", progress_callback=None):
        received_size = 0
        offset = 0
        try:
            with open(save_path, "wb") as f:
                while True:
                    req = {
                        "type": "download_media",
                        "file_id": file_id,
                        "offset": offset,
                        "download_type": download_type,
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
            logging.error(f"下载失败: file_id={file_id}, error={str(e)}")
            return {"status": "error", "message": f"下载失败: {str(e)}"}

    async def add_friend(self, friend_username: str) -> dict:  # 返回类型改为 dict
        req = {
            "type": "add_friend",
            "username": self.username,
            "friend": friend_username,
            "request_id": str(uuid.uuid4())
        }
        resp = await self.send_request(req)
        return resp

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

    async def logout(self) -> dict:
        req = {
            "type": "exit",
            "username": self.username,
            "request_id": str(uuid.uuid4())
        }
        return await self.send_request(req)

    async def close_connection(self):
        self.is_running = False
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

        # 取消 reader_task
        if self.reader_task and not self.reader_task.done():
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                raise

        self.is_authenticated = False
        self.username = None