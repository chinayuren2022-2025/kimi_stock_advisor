import os

# -----------------------------------------------------------------------------
# Network Patch (Fix ProxyError)
# -----------------------------------------------------------------------------
# Force disable proxies to avoid 'RemoteDisconnected' if VPN is off but system proxy is on
import os
"""os.environ['no_proxy'] = '*'""" 
# Also clear any existing env vars just in case
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)

# -----------------------------------------------------------------------------
# Stock Pool
# -----------------------------------------------------------------------------
# Default monitoring list
STOCK_POOL = [
    '513180', # 恒生科技ETF
    '601988', # 中国银行
    '600172', # 黄河旋风
    '300316', # 晶盛机电
    '002985', # 北摩高科
    '002149', # 西部材料
    '600406', # 国电南瑞 
    '601138', # 工业富联 
    '000400', # 许继电气
    '002131', # 利欧股份
    '518680', # 金ETF
]

# -----------------------------------------------------------------------------
# API Keys & Services
# -----------------------------------------------------------------------------
# Kimi AI API Key (Get from environment variable for security)
KIMI_API_KEY = os.getenv("KIMI_API_KEY1", "")

# -----------------------------------------------------------------------------
# Notification Services
# -----------------------------------------------------------------------------
# Feishu Webhook (Get from Group Settings -> Bots -> Add Robot -> Custom Robot)
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "") # 填入 Webhook 地址
FEISHU_SECRET = os.getenv("FEISHU_SECRET", " ") # 选填: 签名校验密钥

# -----------------------------------------------------------------------------
# System Config
# -----------------------------------------------------------------------------
# Data Fetching
DATA_FETCH_CONFIG = {
    "max_workers": 1,  # Concurrency for threading
    "retries": 3,      # API retry attempts
    "retry_delay": 2   # Seconds
}

# Mock Data Flag (Set to True if network is unstable)
USE_MOCK_DATA = False 

# -----------------------------------------------------------------------------
# Monitoring Models & Thresholds
# -----------------------------------------------------------------------------
HISTORY_LEN = 19       # Keep last 19 snapshots (3 mins @ 10s interval)
MONITOR_INTERVAL = 10    # Check every 10 seconds

# Model 1: Rocket Launch (Opportunity)
RISE_SPEED_THRESHOLD = 0.4    # 3-min rise > 2%
VOL_RATIO_THRESHOLD = 1.0    # Volume Ratio > 2.5
NET_INFLOW_THRESHOLD = 50   # Net inflow > 1000 wan (10 million)

# Model 2: High Dive (Risk)
DROP_SPEED_THRESHOLD = -0.4   # 3-min drop < -2%
ASK_BID_RATIO_LIMIT = 1.0     # Ask vol / Bid vol > 5x (Wall of Ask)
BREAK_SUPPORT_LINE = -0.5     # Drop below daily -3%

# Model 3: Undercurrent (Accumulation)
# (Logic: Small price change + Huge inflow)
