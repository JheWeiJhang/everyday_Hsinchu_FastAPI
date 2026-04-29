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
    uvicorn.run("main:app", host="127.0.0.1", port=lifecycle.PORT, reload=False)
