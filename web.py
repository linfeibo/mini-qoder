# -*- coding: utf-8 -*-
"""Mini Qoder Web 服务端：纯 Python 标准库 HTTP 服务器

启动：python3 web.py
访问：http://localhost:8080
"""
import json
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

import agent
import tools

PORT = 8081
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 全局配置与会话状态
cfg = None
tool_schemas = None
sessions = {}  # session_id -> {"messages": [...]}
lock = threading.Lock()


def init_config():
    global cfg, tool_schemas
    cfg = agent.load_config()
    ws = os.path.abspath(cfg.get("workspace") or ".")
    tools.WORKSPACE = ws
    os.chdir(ws)
    tool_schemas = [
        {"type": "function", "function": t["schema"]} for t in tools.TOOLS.values()
    ]


class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 静默日志，只保留错误
        pass

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def send_html(self, path):
        with open(path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self.send_html(os.path.join(BASE_DIR, "index.html"))
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/chat":
            self.handle_chat()
        else:
            self.send_error(404)

    def handle_chat(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            user_msg = data.get("message", "").strip()
            session_id = data.get("session_id", "default")

            if not user_msg:
                self.send_json({"error": "消息为空"}, 400)
                return

            with lock:
                if session_id not in sessions:
                    sessions[session_id] = {
                        "messages": [{"role": "system", "content": agent.SYSTEM_PROMPT}]
                    }
                sess = sessions[session_id]

            # 收集工具调用事件
            events = []
            def on_event(evt):
                events.append(evt)

            sess["messages"].append({"role": "user", "content": user_msg})
            try:
                reply = agent.agent_step(cfg, sess["messages"], tool_schemas, callback=on_event)
                self.send_json({
                    "reply": reply,
                    "events": events,
                })
            except RuntimeError as e:
                sess["messages"].pop()
                self.send_json({"error": str(e)}, 500)

        except Exception as e:
            self.send_json({"error": "服务器错误：%s" % e}, 500)

    def do_OPTIONS(self):
        # CORS 预检
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main():
    init_config()
    server = HTTPServer(("0.0.0.0", PORT), WebHandler)
    print("=" * 56)
    print("  Mini Qoder · Web 界面")
    print("  模型：%s | 工作区：%s" % (cfg["model"], tools.WORKSPACE))
    print("  打开浏览器访问：http://localhost:%d" % PORT)
    print("  按 Ctrl+C 停止服务")
    print("=" * 56)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。")
        server.server_close()


if __name__ == "__main__":
    main()
