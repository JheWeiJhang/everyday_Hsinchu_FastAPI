import sys
import os


def resource_path(relative: str) -> str:
    """唯讀資源（如 templates）：frozen 時指向 MEIPASS 解壓目錄，否則指向原始碼目錄。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def data_path(relative: str) -> str:
    """可寫資料（如 cache）：永遠指向 exe 旁邊的目錄，確保資料持久化。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)
