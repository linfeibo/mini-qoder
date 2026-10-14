# -*- coding: utf-8 -*-
"""用 PyInstaller 把 Mini Qoder 打包成单文件可执行程序（跨平台）。

用法：
    pip install pyinstaller        # 首次需安装打包工具
    python build.py                # macOS / Linux
    python build.py                # Windows

产物：
    dist/mini-qoder        （macOS / Linux）
    dist/mini-qoder.exe    （Windows）

运行成品时，需要把 config.json 放在可执行文件同目录（含真实 api_key）。
index.html 会被打进包内，无需额外携带。

注意：打包本身需要安装 pyinstaller，但它是「构建期」依赖，
      不会被 test_compat.py 之类的运行期兼容性测试导入。
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(ROOT, "web.py")
APP_NAME = "mini-qoder"


def build_command():
    # PyInstaller 的 --add-data 分隔符：Windows 用 ';'，其它平台用 ':'
    sep = os.pathsep
    add_data = "%s%s." % (os.path.join(ROOT, "index.html"), sep)
    return [
        sys.executable, "-m", "PyInstaller",
        "--onefile",              # 打成单个可执行文件
        "--console",              # 保留控制台（Web 服务会打印启动信息）
        "--name", APP_NAME,
        "--add-data", add_data,   # 把 index.html 打进包
        "--distpath", os.path.join(ROOT, "dist"),
        "--workpath", os.path.join(ROOT, "build"),
        "--specpath", ROOT,
        "--noconfirm",
        ENTRY,
    ]


def main():
    cmd = build_command()
    print("执行打包命令：\n  " + " ".join(cmd) + "\n")
    subprocess.check_call(cmd)
    exe = APP_NAME + (".exe" if os.name == "nt" else "")
    out = os.path.join(ROOT, "dist", exe)
    print("\n✅ 打包完成：%s" % out)
    print("   运行前请把 config.json 放到：%s" % os.path.dirname(out))


if __name__ == "__main__":
    main()
