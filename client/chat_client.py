#!/usr/bin/env python3
import socket, json, time, uuid, asyncio
from datetime import datetime, timedelta

class ChatClient:
    def __init__(self, host='192.168.110.103', port=10000):
        self.config = {
            'host': host,
            'port': port,
            'retries': 5,
            'delay': 2
        }
        self._init_connection()

    def _init_connection(self):
        """初始化连接相关属性"""
        self.is_authenticated = False
        self.username = self.current_friend = None
        self.client_socket = None
        self.send_lock = asyncio.Lock()
        self.pending_requests = {}
        self.on_new_message_callback = None
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

    def _sync_send_recv(self, req: dict) -> dict:
        try:
            data = json.dumps(req, ensure_ascii=False).encode('utf-8')
            self.client_socket.send(len(data).to_bytes(4, 'big') + data)
            header = self.client_socket.recv(4)
            if len(header) < 4:
                raise Exception("响应头不完整")
            length = int.from_bytes(header, 'big')
            return json.loads(self.client_socket.recv(length).decode('utf-8'))
        except Exception as e:
            print(f"发送/接收异常: {e}")
            return {"status": "error", "message": str(e)}

    async def authenticate(self, username, password) -> str:
        req = {"type": "authenticate", "username": username, "password": password, "request_id": str(uuid.uuid4())}
        resp = await asyncio.to_thread(self._sync_send_recv, req)
        if resp.get("status") == "success":
            self.username, self.is_authenticated = username, True
            return "认证成功"
        return resp.get("message", "账号或密码错误")

    async def start_reader(self):
        while True:
            try:
                h = await self._recv_async(4)
                if len(h) < 4:
                    continue
                l = int.from_bytes(h, 'big')
                payload = await self._recv_async(l)
                try:
                    resp = json.loads(payload.decode('utf-8'))
                except Exception as decode_err:
                    print(f"后台读取任务异常: {decode_err}")
                    continue
                req_id = resp.get("request_id")
                if req_id in self.pending_requests:
                    self.pending_requests.pop(req_id).set_result(resp)
                elif resp.get("type") == "new_message" and self.on_new_message_callback:
                    asyncio.create_task(self.on_new_message_callback(resp))
                else:
                    print("未匹配的响应:", resp)
            except Exception as e:
                print("后台读取任务异常:", e)
                await asyncio.sleep(1)

    async def get_chat_history(self, friend: str) -> dict:
        req = {"type": "get_chat_history", "username": self.username, "friend": friend, "request_id": str(uuid.uuid4())}
        resp = await self.send_request(req)
        return await self.parse_response(resp, friend)

    async def send_message(self, from_user: str, to_user: str, message: str) -> dict:
        req = {"type": "send_message", "from": from_user, "to": to_user, "message": message, "request_id": str(uuid.uuid4())}
        return await self.send_request(req)

    async def request_friend_list(self) -> list:
        req = {"type": "get_friends", "username": self.username, "request_id": str(uuid.uuid4())}
        resp = await self.send_request(req)
        print("好友列表响应:", resp)
        return resp.get("friends", []) if resp else []

    async def add_friend(self, friend_username: str) -> str:
        req = {"type": "add_friend", "username": self.username, "friend": friend_username, "request_id": str(uuid.uuid4())}
        resp = await self.send_request(req)
        return resp.get("message", "添加好友失败")

    async def send_request(self, req: dict) -> dict:
        try:
            async with self.send_lock:
                data = json.dumps(req, ensure_ascii=False).encode('utf-8')
                self.client_socket.send(len(data).to_bytes(4, 'big') + data)
            fut = asyncio.get_running_loop().create_future()
            self.pending_requests[req.get("request_id")] = fut
            return await fut
        except Exception as e:
            print("发送请求异常:", e)
            return None

    async def _recv_async(self, length: int) -> bytes:
        data = b""
        while len(data) < length:
            chunk = await asyncio.to_thread(self.client_socket.recv, length - len(data))
            if not chunk:
                raise Exception("接收数据异常")
            data += chunk
        return data

    async def parse_response(self, resp: dict, friend: str) -> dict:
        history = resp.get("chat_history", [])
        parsed = []
        errors = []
        for entry in history:
            try:
                wt, sender, msg = entry.get("write_time"), entry.get("username"), entry.get("message")
                if not (wt and sender and msg):
                    raise Exception("缺少字段")
                ts = datetime.strptime(wt, "%Y-%m-%d %H:%M:%S")
                formatted = ts.strftime("%H:%M") if (datetime.now() - ts) < timedelta(days=1) else ts.strftime("%m.%d %H:%M")
                is_current = (sender == self.username)
                parsed.append({"write_time": formatted, "sender_username": sender, "message": msg, "is_current_user": is_current})
            except Exception as ex:
                errors.append({"entry": entry, "error": str(ex)})
        res = {"type": "chat_history", "data": parsed, "request_id": resp.get("request_id")}
        if errors:
            res["errors"] = errors
        return res

    async def close_connection(self):
        try:
            req = {"type": "exit", "username": self.username, "request_id": str(uuid.uuid4())}
            await self.send_request(req)
        except Exception as e:
            print("发送退出请求异常:", e)
        try:
            self.client_socket.close()
            print("连接已关闭")
        except Exception as e:
            print("关闭 socket 异常:", e)
