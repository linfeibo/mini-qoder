# -*- coding: utf-8 -*-
"""Mini Qoder：一个类似 Qoder 的命令行 AI 编程智能体（纯 Python 标准库）

用法：
  1. 在 config.json 中填入你的 API-KEY（默认使用阿里云百炼 OpenAI 兼容接口）
  2. python3 agent.py
  3. 直接用自然语言下达开发任务，例如："帮我写一个贪吃蛇游戏"

命令：/exit 退出  /clear 清空上下文  /tools 查看工具列表
"""
import json
import os
import ssl
import sys
import urllib.request
import urllib.error

import tools

# SSL 上下文：macOS Python 证书问题处理（开发环境）
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

def _config_path():
    """定位 config.json。

    - 源码运行：与本文件同目录。
    - PyInstaller 打包后：可执行文件所在目录（便于用户就地填写密钥，
      而不是被解压到临时目录里找不到）。
    """
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "config.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


CONFIG_PATH = _config_path()

SYSTEM_PROMPT = """你是一个专业的 AI 编程智能体，工作在用户的代码工作区中。
你可以通过工具来：查看目录、读取文件、搜索代码、创建/修改文件、执行命令。

工作准则：
1. 接到开发任务时，先规划步骤，再动手，逐个步骤完成并验证。
2. 修改已有文件前，先用 read_file 了解现状，不要凭空猜测。
3. 使用 edit_file 时，old_text 必须与文件内容完全一致（含缩进）。
4. 完成任务后用 run_command 做必要的验证（如语法检查、运行测试）。
5. 回复使用中文，简洁说明你做了什么、结果如何。
6. 最多连续调用 20 次工具，避免死循环。"""

MAX_TOOL_ROUNDS = 20


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not cfg.get("api_key") or cfg["api_key"].startswith("在此填入"):
        print("❌ 请先在 config.json 中填入你的 api_key")
        sys.exit(1)
    return cfg


def chat(cfg, messages, tool_schemas):
    """调用 OpenAI 兼容的 chat completions 接口"""
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "tools": tool_schemas,
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + cfg["api_key"],
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180, context=SSL_CTX) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError("API 请求失败 [%d]：%s" % (e.code, body))
    except urllib.error.URLError as e:
        raise RuntimeError("网络错误：%s" % e.reason)


def agent_step(cfg, messages, tool_schemas, callback=None):
    """执行一轮智能体推理：可能包含多次工具调用，直到产出最终回复。
    callback: 可选函数，签名 callback(event)，事件类型：
        {"type":"tool_call", "name":str, "args":dict}
        {"type":"tool_result", "name":str, "result":str}
    """
    for _ in range(MAX_TOOL_ROUNDS):
        resp = chat(cfg, messages, tool_schemas)
        msg = resp["choices"][0]["message"]
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            content = msg.get("content") or ""
            messages.append({"role": "assistant", "content": content})
            return content

        # 记录助手的工具调用消息
        messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if callback:
                callback({"type": "tool_call", "name": name, "args": args})
            else:
                print("\n  🔧 调用工具 %s(%s)" % (
                    name, json.dumps(args, ensure_ascii=False)[:200]))
            result = tools.dispatch(name, args)
            if callback:
                callback({"type": "tool_result", "name": name, "result": result})
            else:
                print("  ✅ 结果：%s" % result[:200].replace("\n", " ⏎ "))
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })
    return "（已达到单轮工具调用上限，任务可能未完成）"


def main():
    cfg = load_config()
    # 切换到用户配置的工作区
    ws = os.path.abspath(cfg.get("workspace") or ".")
    tools.WORKSPACE = ws
    os.chdir(ws)

    tool_schemas = [
        {"type": "function", "function": t["schema"]} for t in tools.TOOLS.values()
    ]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("=" * 56)
    print("  Mini Qoder · AI 编程智能体")
    print("  模型：%s | 工作区：%s" % (cfg["model"], ws))
    print("  命令：/exit 退出  /clear 清空上下文  /tools 查看工具")
    print("=" * 56)

    while True:
        try:
            user_input = input("\n你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input == "/exit":
            print("再见！")
            break
        if user_input == "/clear":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("已清空上下文。")
            continue
        if user_input == "/tools":
            for name, t in tools.TOOLS.items():
                print("  - %s：%s" % (name, t["schema"]["description"]))
            continue

        messages.append({"role": "user", "content": user_input})
        try:
            reply = agent_step(cfg, messages, tool_schemas)
            print("\n智能体 > %s" % reply)
        except RuntimeError as e:
            print("\n❌ %s" % e)
            messages.pop()  # 移除失败的用户消息，便于重试


if __name__ == "__main__":
    main()
