import os
import socket
import subprocess
import time
import webbrowser

PORT = 5000
_last_heartbeat: float = time.time()
_HEARTBEAT_TIMEOUT = 45


def update_heartbeat() -> None:
    global _last_heartbeat
    _last_heartbeat = time.time()


def get_last_heartbeat() -> float:
    return _last_heartbeat


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


_NO_WINDOW = subprocess.CREATE_NO_WINDOW


def _kill_port(port: int) -> None:
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL,
            creationflags=_NO_WINDOW,
        )
        for line in out.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                pid = line.split()[-1]
                subprocess.call(
                    ["taskkill", "/PID", pid, "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=_NO_WINDOW,
                )
                print(f"[server] 已關閉舊的 Server (PID {pid})")
                time.sleep(1)
                break
    except Exception:
        pass


def _open_browser() -> None:
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{PORT}")


def _heartbeat_monitor() -> None:
    while True:
        time.sleep(15)
        if time.time() - get_last_heartbeat() > _HEARTBEAT_TIMEOUT:
            print("\n[server] No browser heartbeat — shutting down.")
            os._exit(0)
