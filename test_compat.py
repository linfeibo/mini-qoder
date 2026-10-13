# -*- coding: utf-8 -*-
"""跨平台兼容性测试（纯标准库，零依赖）

本地运行：
    python3 test_compat.py      # macOS / Linux
    python test_compat.py       # Windows

CI：由 .github/workflows/ci.yml 在 Windows / Linux / macOS 矩阵中调用。

测试内容：
  1. 全项目语法编译检查（跨平台、跨 Python 版本）
  2. 核心模块导入检查
  3. 工具层逻辑测试（读写/编辑/搜索/命令，中文内容验证编码）
  4. Web 服务冒烟测试（HTTP 200/400/404，不需要 API Key）
  5. GUI 构建测试（tkinter，无图形环境自动跳过）
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# Windows 控制台默认可能不是 UTF-8，避免中文输出报错
for _stream in (sys.stdout, sys.stderr):
    try:
        if _stream.encoding and _stream.encoding.lower().replace("-", "") != "utf8":
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# web.py 使用固定端口
WEB_PORT = 8081
WEB_FILES = ["web.py", "agent.py", "tools.py", "index.html"]


def platform_banner():
    print("=" * 60)
    print("  平台：%s %s (%s)" % (platform.system(), platform.release(), platform.machine()))
    print("  Python：%s" % platform.python_version())
    print("  解释器：%s" % sys.executable)
    print("=" * 60)


class TestSyntax(unittest.TestCase):
    """全项目 .py 文件语法编译检查"""

    def test_compile_all(self):
        import py_compile
        for name in sorted(os.listdir(ROOT)):
            if name.endswith(".py"):
                py_compile.compile(os.path.join(ROOT, name), doraise=True)


class TestImports(unittest.TestCase):
    """核心模块导入检查"""

    def test_import_core(self):
        import tools
        import agent  # noqa: F401
        self.assertTrue(callable(tools.dispatch))

    def test_import_tkinter(self):
        try:
            import tkinter  # noqa: F401
        except ImportError as e:
            self.skipTest("tkinter 不可用：%s" % e)


class TestTools(unittest.TestCase):
    """工具层逻辑跨平台测试（在临时工作区中进行，不触碰项目文件）"""

    def setUp(self):
        import tools
        self.tools = tools
        self.tmp = tempfile.mkdtemp(prefix="mq_test_")
        self.old_ws = tools.WORKSPACE
        tools.WORKSPACE = self.tmp

    def tearDown(self):
        self.tools.WORKSPACE = self.old_ws
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_read_chinese(self):
        """中文文件名 + 中文内容（验证 UTF-8 编码跨平台一致）"""
        r = self.tools.write_file("子目录/中文.txt", "你好，世界\n第二行")
        self.assertIn("已写入", r)
        r = self.tools.read_file("子目录/中文.txt")
        self.assertIn("你好，世界", r)
        self.assertIn("第二行", r)

    def test_edit_file(self):
        self.tools.write_file("a.py", "x = 1\n")
        r = self.tools.edit_file("a.py", "x = 1", "x = 2")
        self.assertIn("完成", r)
        self.assertIn("x = 2", self.tools.read_file("a.py"))

    def test_edit_file_not_found(self):
        self.tools.write_file("a.py", "x = 1\n")
        r = self.tools.edit_file("a.py", "不存在的文本", "y")
        self.assertIn("错误", r)

    def test_list_and_search(self):
        self.tools.write_file("src/main.py", "print('兼容性')\n")
        self.assertIn("main.py", self.tools.list_dir("src"))
        r = self.tools.search_code("兼容性", ".")
        self.assertIn("main.py", r)

    def test_run_command(self):
        """shell 执行（Windows 走 cmd，Unix 走 sh）"""
        r = self.tools.run_command("echo hello")
        self.assertIn("hello", r)
        self.assertIn("[退出码 0]", r)

    def test_dispatch(self):
        r = self.tools.dispatch("list_dir", {"path": "."})
        self.assertNotIn("错误：未知工具", r)


class TestWebSmoke(unittest.TestCase):
    """Web 服务冒烟测试（临时副本 + 假密钥，不触碰真实配置、不调用 API）"""

    proc = None
    workdir = None
    base = None

    @classmethod
    def setUpClass(cls):
        cls.workdir = tempfile.mkdtemp(prefix="mq_web_")
        for name in WEB_FILES:
            shutil.copy(os.path.join(ROOT, name), cls.workdir)
        fake_cfg = {
            "api_key": "ci-dummy-key",
            "base_url": "http://127.0.0.1:1/v1",
            "model": "dummy",
            "workspace": ".",
        }
        with open(os.path.join(cls.workdir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(fake_cfg, f)

        cls.proc = subprocess.Popen(
            [sys.executable, "web.py"],
            cwd=cls.workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        cls.base = "http://127.0.0.1:%d" % WEB_PORT

        # 最多等待 15 秒，直到服务就绪
        for _ in range(50):
            if cls.proc.poll() is not None:
                out = cls.proc.stdout.read().decode("utf-8", "replace")
                raise RuntimeError("web.py 启动失败：\n" + out)
            try:
                with urllib.request.urlopen(cls.base + "/", timeout=1) as r:
                    if r.status == 200:
                        return
            except Exception:
                time.sleep(0.3)
        raise RuntimeError("等待 web.py 就绪超时（端口 %d 可能被占用）" % WEB_PORT)

    @classmethod
    def tearDownClass(cls):
        if cls.proc and cls.proc.poll() is None:
            cls.proc.kill()
            cls.proc.wait(timeout=5)
        if cls.workdir:
            shutil.rmtree(cls.workdir, ignore_errors=True)

    def test_index_200(self):
        with urllib.request.urlopen(self.base + "/") as r:
            body = r.read().decode("utf-8", "replace")
        self.assertEqual(r.status, 200)
        self.assertIn("html", body.lower())

    def test_404(self):
        try:
            urllib.request.urlopen(self.base + "/no-such-page")
            self.fail("预期返回 404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_chat_empty_400(self):
        """空消息应被拒绝，此路径不需要 API Key"""
        req = urllib.request.Request(
            self.base + "/chat",
            data=json.dumps({"message": "  "}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
            self.fail("预期返回 400")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)


class TestGUI(unittest.TestCase):
    """GUI 构建测试（无图形环境自动跳过，Linux CI 用 xvfb 提供虚拟显示）"""

    def test_build_calculator(self):
        try:
            import tkinter as tk
        except ImportError as e:
            self.skipTest("tkinter 不可用：%s" % e)
        try:
            root = tk.Tk()
        except tk.TclError as e:
            self.skipTest("无图形环境：%s" % e)
        try:
            from calculator import Calculator
            Calculator(root)
            root.update()
        finally:
            root.destroy()


if __name__ == "__main__":
    platform_banner()
    unittest.main(verbosity=2)
