"""统一的子进程执行包装。

要点：
1. 实时把 stdout / stderr 写入日志文件，便于排查。
2. 失败时抛出 RuntimeError，错误信息包含命令、返回码、最后 30 行日志。
3. 提供命令存在性检测，便于在缺工具时及早报错或回退到 mock。
"""
from __future__ import annotations

import collections
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional


_DEFAULT_TAIL_LINES = 30


class CommandError(RuntimeError):
    def __init__(self, cmd: list[str], returncode: int, tail: list[str]):
        self.cmd = cmd
        self.returncode = returncode
        self.tail = tail
        msg = (
            f"Command failed (code={returncode}): {' '.join(cmd)}\n"
            + "----- last log -----\n"
            + "\n".join(tail)
        )
        super().__init__(msg)


def command_exists(name: str) -> bool:
    """检查可执行命令是否在 PATH 中。"""
    return shutil.which(name) is not None


def run_command(
    cmd: list[str],
    cwd: Optional[str | Path] = None,
    env: Optional[dict] = None,
    timeout: Optional[int] = None,
    log_path: Optional[str | Path] = None,
    on_log: Optional[Callable[[str], None]] = None,
) -> subprocess.CompletedProcess:
    """运行外部命令，实时输出到日志，失败抛错。

    on_log: 每接收到一行 stdout/stderr 时回调，可用于推送到 JobStore。
    """
    if log_path is not None:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    log_handle = open(log_path, "a", encoding="utf-8") if log_path else None
    tail: collections.deque[str] = collections.deque(maxlen=_DEFAULT_TAIL_LINES)

    try:
        if log_handle:
            log_handle.write(f"$ {' '.join(str(c) for c in cmd)}\n")
            log_handle.flush()

        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                line = line.rstrip("\n")
                tail.append(line)
                if log_handle:
                    log_handle.write(line + "\n")
                    log_handle.flush()
                if on_log:
                    try:
                        on_log(line)
                    except Exception:
                        pass
            returncode = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise CommandError(cmd, -1, list(tail) + ["TIMEOUT"])

        if returncode != 0:
            raise CommandError(cmd, returncode, list(tail))

        return subprocess.CompletedProcess(cmd, returncode, "\n".join(tail), "")
    finally:
        if log_handle:
            log_handle.close()
