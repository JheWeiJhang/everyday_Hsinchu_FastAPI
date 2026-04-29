import socket
import threading
import time
import tkinter as tk
from tkinter import ttk


def _wait_for_server(port: int, on_ready):
    """Poll /api/ping until FastAPI is fully ready (not just TCP-open)."""
    import urllib.request
    url = f"http://127.0.0.1:{port}/api/ping"
    for _ in range(120):  # 最多等 60 秒
        try:
            urllib.request.urlopen(url, timeout=1)
            on_ready()
            return
        except Exception:
            time.sleep(0.5)
    on_ready()  # 逾時也關閉 splash，避免卡住


def show_splash(port: int) -> None:
    """在主執行緒顯示啟動 splash，server ready 後自動關閉。"""
    root = tk.Tk()
    root.title("新竹每日大小事")
    root.resizable(False, False)
    root.overrideredirect(True)  # 無標題列，乾淨的 splash 樣式

    W, H = 420, 220
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

    # ── 外框陰影效果 ──────────────────────────────
    BG = "#1b2b4b"
    ACCENT = "#4a9eff"

    root.configure(bg=BG)

    canvas = tk.Canvas(root, width=W, height=H, bg=BG, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    # 頂部 accent 條
    canvas.create_rectangle(0, 0, W, 4, fill=ACCENT, outline="")

    # 標題
    canvas.create_text(
        W // 2, 60,
        text="新竹每日大小事",
        font=("微軟正黑體", 20, "bold"),
        fill="white",
    )
    canvas.create_text(
        W // 2, 95,
        text="Hsinchu Daily News",
        font=("微軟正黑體", 10),
        fill="#7a9cc8",
    )

    # 狀態文字（動態更新）
    status_var = tk.StringVar(value="正在啟動伺服器...")
    status_label = tk.Label(
        root, textvariable=status_var,
        font=("微軟正黑體", 9), bg=BG, fg="#aabbcc",
    )
    status_label.place(x=W // 2, y=135, anchor="center")

    # 進度條
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        "Splash.Horizontal.TProgressbar",
        troughcolor="#0d1b33",
        background=ACCENT,
        bordercolor=BG,
        lightcolor=ACCENT,
        darkcolor=ACCENT,
    )
    bar = ttk.Progressbar(
        root, style="Splash.Horizontal.TProgressbar",
        mode="indeterminate", length=340,
    )
    bar.place(x=W // 2, y=165, anchor="center")
    bar.start(12)

    # 版本 / 提示
    canvas.create_text(
        W // 2, H - 14,
        text="載入完成後將自動開啟瀏覽器",
        font=("微軟正黑體", 8),
        fill="#445566",
    )

    # 動態省略號動畫
    _dots = ["", ".", "..", "..."]
    _dot_idx = [0]

    def _animate():
        _dot_idx[0] = (_dot_idx[0] + 1) % len(_dots)
        status_var.set(f"正在啟動伺服器{_dots[_dot_idx[0]]}")
        root.after(400, _animate)

    _animate()

    def _on_ready():
        root.after(0, root.destroy)

    threading.Thread(
        target=_wait_for_server, args=(port, _on_ready), daemon=True
    ).start()

    root.mainloop()
