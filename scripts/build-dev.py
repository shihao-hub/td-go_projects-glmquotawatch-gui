# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
# 编译开发版 glmquotawatch-gui-dev.exe（注入 dev 模式、独立单例、独立数据目录）
# 产物：bin/glmquotawatch-gui-dev.exe
# 环境：Dev 单例互斥锁、数据目录指向 %APPDATA%\language_projects\glmquotawatch-gui\dev，
#       禁止开机自启（拦截保护）
# 用法：uv run scripts/build-dev.py [--skip-frontend] [--show-console]
#       默认 -H windowsgui 隐藏控制台黑框；需要调试日志时传 --show-console

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = PROJECT_ROOT / "bin"

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run(cmd: list[str], cwd: Path) -> None:
    # Windows 下 npm 等实为 .cmd，CreateProcess 不解析 PATHEXT，须用 which 取完整路径
    executable = shutil.which(cmd[0])
    if executable is None:
        raise RuntimeError(f"未找到命令：{cmd[0]}（请确认已安装并在 PATH 上）")
    r = subprocess.run([executable, *cmd[1:]], cwd=str(cwd))
    if r.returncode != 0:
        raise RuntimeError(f"命令失败（exit {r.returncode}）：{' '.join(cmd)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="编译开发版 glmquotawatch-gui-dev.exe（dev 标签 + 独立单例与数据目录）")
    parser.add_argument("--skip-frontend", action="store_true", help="跳过前端构建（复用现有 dist）")
    parser.add_argument("--show-console", action="store_true", help="保留控制台窗口（调试日志用，默认 -H windowsgui）")
    args = parser.parse_args()

    try:
        print("=== [1/3] 检查并构建前端资源 ===")
        if not args.skip_frontend:
            frontend = PROJECT_ROOT / "frontend"
            dist = frontend / "dist"
            if dist.exists():
                import shutil
                shutil.rmtree(dist, ignore_errors=True)
            print("正在编译前端 (vite build --mode production)...")
            run(["npm", "run", "build"], frontend)
        else:
            print("跳过前端构建 (--skip-frontend)")

        BIN_DIR.mkdir(parents=True, exist_ok=True)

        print("=== [2/3] 生成 Windows 资源 (.syso) ===")
        run(
            [
                "wails3", "generate", "syso", "-arch", "amd64",
                "-icon", "windows/icon-dev.ico",
                "-manifest", "windows/wails.exe.manifest",
                "-info", "windows/info.json",
                "-out", "../wails_windows_amd64.syso",
            ],
            PROJECT_ROOT / "build",
        )

        out_exe = BIN_DIR / "glmquotawatch-gui-dev.exe"
        print(f"=== [3/3] 编译开发版可执行文件 -> {out_exe} ===")

        version = "0.1.0-dev"
        gui_flag = "" if args.show_console else "-H windowsgui"
        ldflags = f"{gui_flag} -X glmquotawatch-gui/internal/cli.Version={version}".strip()

        run(
            [
                "go", "build", "-tags", "dev", "-buildvcs=false",
                "-gcflags=all=-l", "-ldflags", ldflags,
                "-o", str(out_exe), ".",
            ],
            PROJECT_ROOT,
        )

        stat = out_exe.stat()
        print(f"✓ 开发版构建成功: {out_exe}")
        print(f"  Name: {out_exe.name}  Length: {stat.st_size}  LastWriteTime: "
              f"{datetime.fromtimestamp(stat.st_mtime).strftime('%Y/%m/%d %H:%M:%S')}")
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        # 清理临时生成的 syso 资源（防止误入后续普通 go build）
        for syso in PROJECT_ROOT.glob("*.syso"):
            syso.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
