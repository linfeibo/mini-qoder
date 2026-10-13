# -*- coding: utf-8 -*-
"""工具层：智能体可调用的所有工具实现（纯标准库）"""
import os
import re
import subprocess

WORKSPACE = os.getcwd()
MAX_OUTPUT = 8000

# 危险命令关键词，命中后需用户二次确认
DANGEROUS_PATTERN = re.compile(
    r"\b(rm|sudo|mkfs|dd|shutdown|reboot|kill|pkill|drop|truncate|format)\b|>\s*/|&&\s*rm"
)

# 跳过的目录与二进制后缀
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".idea"}
BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".tar",
               ".so", ".dylib", ".exe", ".class", ".jar", ".woff", ".woff2", ".mp4"}


def _resolve(path):
    """将相对路径解析到工作区内"""
    p = os.path.abspath(os.path.join(WORKSPACE, path))
    return p


def _clip(text):
    if len(text) > MAX_OUTPUT:
        return text[:MAX_OUTPUT] + "\n...[输出过长已截断，共%d字符]" % len(text)
    return text


def read_file(path, start_line=None, end_line=None):
    p = _resolve(path)
    if not os.path.isfile(p):
        return "错误：文件不存在 %s" % p
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return "错误：读取失败 %s" % e
    s = max(int(start_line or 1), 1)
    e = min(int(end_line or len(lines)), len(lines))
    body = "".join("%5d→ %s" % (i, lines[i - 1]) for i in range(s, e + 1))
    return "文件 %s 共%d行，当前显示 %d-%d 行：\n%s" % (path, len(lines), s, e, _clip(body))


def write_file(path, content):
    p = _resolve(path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return "已写入 %s（%d字符）" % (path, len(content))


def edit_file(path, old_text, new_text):
    p = _resolve(path)
    if not os.path.isfile(p):
        return "错误：文件不存在 %s" % p
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        src = f.read()
    n = src.count(old_text)
    if n == 0:
        return "错误：未找到要替换的文本，请确认 old_text 与文件内容完全一致"
    if n > 1:
        return "错误：找到%d处相同文本，请提供更多上下文使其唯一" % n
    with open(p, "w", encoding="utf-8") as f:
        f.write(src.replace(old_text, new_text))
    return "已在 %s 完成一处替换" % path


def list_dir(path="."):
    p = _resolve(path)
    if not os.path.isdir(p):
        return "错误：目录不存在 %s" % p
    out = []
    for name in sorted(os.listdir(p)):
        full = os.path.join(p, name)
        out.append(("[目录] " if os.path.isdir(full) else "       ") + name)
    return "\n".join(out) if out else "（空目录）"


def search_code(pattern, path="."):
    """正则搜索文件内容，返回 文件:行号:内容"""
    p = _resolve(path)
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return "错误：正则无效 %s" % e
    hits, scanned = [], 0
    targets = []
    if os.path.isfile(p):
        targets = [p]
    else:
        for r, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if os.path.splitext(f)[1].lower() not in BINARY_EXTS:
                    targets.append(os.path.join(r, f))
    for fp in targets:
        scanned += 1
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if rx.search(line):
                        hits.append("%s:%d: %s" % (os.path.relpath(fp, WORKSPACE), i, line.strip()))
                        if len(hits) >= 100:
                            return _clip("\n".join(hits)) + "\n...[已达100条上限]"
        except Exception:
            continue
    return ("共扫描%d个文件，匹配%d条：\n" % (scanned, len(hits))) + _clip("\n".join(hits)) if hits \
        else "扫描%d个文件，未找到匹配" % scanned


def run_command(command):
    if DANGEROUS_PATTERN.search(command):
        ans = input("\n⚠️  检测到潜在危险命令：%s\n是否执行？(y/N): " % command).strip().lower()
        if ans != "y":
            return "用户拒绝执行该命令"
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=120, cwd=WORKSPACE,
        )
    except subprocess.TimeoutExpired:
        return "错误：命令执行超时(120s)"
    out = "$ %s\n[退出码 %d]\n%s%s" % (command, proc.returncode, proc.stdout, proc.stderr)
    return _clip(out)


# 工具注册表：名称 -> (实现函数, OpenAI function schema)
TOOLS = {
    "read_file": {
        "fn": read_file,
        "schema": {
            "name": "read_file",
            "description": "读取文件内容，可指定行号范围",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "start_line": {"type": "integer", "description": "起始行(可选)"},
                    "end_line": {"type": "integer", "description": "结束行(可选)"},
                },
                "required": ["path"],
            },
        },
    },
    "write_file": {
        "fn": write_file,
        "schema": {
            "name": "write_file",
            "description": "创建或覆盖写入文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "完整文件内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    "edit_file": {
        "fn": edit_file,
        "schema": {
            "name": "edit_file",
            "description": "精确替换文件中的一段文本，old_text必须与文件内容完全一致且唯一",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "old_text": {"type": "string", "description": "要被替换的原文"},
                    "new_text": {"type": "string", "description": "替换后的新文本"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    "list_dir": {
        "fn": list_dir,
        "schema": {
            "name": "list_dir",
            "description": "列出目录下的文件和子目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径，默认当前目录"},
                },
            },
        },
    },
    "search_code": {
        "fn": search_code,
        "schema": {
            "name": "search_code",
            "description": "用正则在代码文件中搜索内容，返回文件:行号:内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "正则表达式"},
                    "path": {"type": "string", "description": "搜索的文件或目录"},
                },
                "required": ["pattern"],
            },
        },
    },
    "run_command": {
        "fn": run_command,
        "schema": {
            "name": "run_command",
            "description": "在工作区目录中执行shell命令",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"},
                },
                "required": ["command"],
            },
        },
    },
}


def dispatch(name, args):
    """按名称调用工具，统一捕获异常"""
    tool = TOOLS.get(name)
    if not tool:
        return "错误：未知工具 %s" % name
    try:
        return str(tool["fn"](**args))
    except Exception as e:
        return "工具执行出错：%s" % e
