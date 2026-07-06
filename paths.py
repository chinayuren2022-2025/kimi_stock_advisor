"""
运行时数据路径解析。
PyInstaller frozen 时写到 ~/Library/Application Support/kimi_stock_advisor/（macOS 规范）；
开发时写到仓库根目录。
"""
import os
import sys

APP_NAME = "kimi_stock_advisor"

# 是否在 PyInstaller frozen 环境中
is_frozen = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def _ensure_dir(path: str) -> str:
    """目录不存在则创建。"""
    os.makedirs(path, exist_ok=True)
    return path


if is_frozen:
    # 打包后：~/Library/Application Support/kimi_stock_advisor/
    data_dir = os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
    _ensure_dir(data_dir)
else:
    # 开发时：仓库根目录
    data_dir = os.path.dirname(os.path.abspath(__file__))

db_path = os.path.join(data_dir, "quant_data.db")
log_path = os.path.join(data_dir, "quant_monitor.log")