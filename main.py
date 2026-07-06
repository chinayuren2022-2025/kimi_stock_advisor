"""
TUI 入口：Rich Live 仪表盘，调用 engine.MonitorEngine。
保留作为无头/调试模式，GUI 入口见 gui.py。
"""
import sys
import logging
import time

try:
    from . import config
    from .engine import MonitorEngine, is_trading_time
    from .dashboard import MonitorDashboard
    from .paths import log_path as _LOG_PATH
    from rich.live import Live
except ImportError:
    import config
    from engine import MonitorEngine, is_trading_time
    from dashboard import MonitorDashboard
    from paths import log_path as _LOG_PATH
    from rich.live import Live

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_LOG_PATH, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def monitor_forever():
    engine = MonitorEngine()
    dashboard = MonitorDashboard()

    # 启动日志
    logger.info(f"启动量化监控系统 (扫描间隔: {config.MONITOR_INTERVAL}秒)...")
    logger.info(f"监控股票池: {engine.stock_pool}")

    # 初始化 DB + 日线历史（首次较慢）
    engine.init(log_cb=dashboard.add_log)

    display_data = [{'code': c, 'name': 'Loading...', 'price': 0, 'pct_chg': 0,
                     'status': 'Loading...'} for c in engine.stock_pool]

    with Live(dashboard.generate_layout(display_data), refresh_per_second=1, screen=True) as live:
        try:
            while True:
                dashboard.add_log("--- Scanning Market ---")

                rows, alerts, status = engine.cycle()

                if status == 'fetch_failed':
                    dashboard.add_log("[Error] Fetch failed, retry in 5s")
                    live.update(dashboard.generate_layout(display_data))
                    time.sleep(5)
                    continue

                dashboard.add_log(f"Fetched {len(rows)} stocks (Pool Only).")

                if not is_trading_time():
                    dashboard.add_log("⏸️ 非交易时间，暂停存储 (节省空间)...")

                # 渲染预警日志
                for a in alerts:
                    dashboard.add_log(f"🔥 Trigger: {a['type']} on {a['name']}")
                    if a.get('ai_response'):
                        dashboard.add_log(f"✅ AI 分析完成")
                        for line in a['ai_response'].split('\n'):
                            if line.strip():
                                dashboard.add_log(f"[AI] {line.strip()}")
                        if a.get('pushed'):
                            dashboard.add_log("📨 已触发飞书推送")
                    else:
                        dashboard.add_log("⚠️ AI 未返回有效内容")

                display_data = rows
                live.update(dashboard.generate_layout(display_data))

                # 非交易时间降频
                if is_trading_time():
                    time.sleep(config.MONITOR_INTERVAL)
                else:
                    time.sleep(60)

        except KeyboardInterrupt:
            logger.info("用户停止了监控程序。")


if __name__ == "__main__":
    monitor_forever()