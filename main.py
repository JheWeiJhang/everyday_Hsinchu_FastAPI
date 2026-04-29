import sys
import os

# Windowed exe: stdout/stderr are None — redirect to log file.
_log = None
if getattr(sys, "frozen", False) and sys.stdout is None:
    _log_path = os.path.join(os.path.dirname(sys.executable), "app.log")
    _log = open(_log_path, "w", encoding="utf-8", buffering=1)
    sys.stdout = _log
    sys.stderr = _log

import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
import lifecycle
from routes.pages import router as pages_router
from routes.api import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if lifecycle._port_in_use(lifecycle.PORT):
        lifecycle._kill_port(lifecycle.PORT)
    print("=" * 50)
    print(f"  新竹每日大小事  →  http://127.0.0.1:{lifecycle.PORT}")
    print("  關閉瀏覽器頁面後伺服器將自動結束")
    print("=" * 50)
    threading.Thread(target=lifecycle._open_browser, daemon=True).start()
    threading.Thread(target=lifecycle._heartbeat_monitor, daemon=True).start()
    yield


app = FastAPI(title="新竹每日大小事", lifespan=lifespan)
app.include_router(pages_router)
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    if getattr(sys, "frozen", False):
        if "--server" in sys.argv:
            # ── 子 process：在自己的主執行緒跑 uvicorn（asyncio 完全正常）──
            uvicorn.run(
                app, host="127.0.0.1", port=lifecycle.PORT,
                reload=False, log_config=None,
            )
        else:
            # ── 主 process：spawn 子 process 跑 server，自己顯示 splash ──
            import subprocess
            import time as _time

            # 先 kill 任何殘留的舊 server，避免 splash 偵測到舊 server 就立刻關閉
            if lifecycle._port_in_use(lifecycle.PORT):
                lifecycle._kill_port(lifecycle.PORT)
                _time.sleep(1.5)  # 等 OS 釋放 port

            server_proc = subprocess.Popen(
                [sys.executable, "--server"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            from splash import show_splash
            show_splash(lifecycle.PORT)  # 阻塞直到 server ready 且 splash 關閉
            exit_code = server_proc.wait()  # 等 server 結束（瀏覽器關閉後 45 秒）

            # 正常結束（exit 0）→ 刪除 log；非正常（crash）→ 保留 log 供除錯
            if exit_code == 0 and _log is not None:
                log_path = os.path.join(os.path.dirname(sys.executable), "app.log")
                try:
                    _log.flush()
                    _log.close()
                except Exception:
                    pass
                try:
                    os.remove(log_path)
                except OSError:
                    pass
    else:
        uvicorn.run(
            app, host="127.0.0.1", port=lifecycle.PORT,
            reload=False, log_config=None,
        )
