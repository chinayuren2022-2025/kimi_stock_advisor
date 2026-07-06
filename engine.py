"""
监控核心引擎：从 main.py 抽出，供 TUI / GUI 共用。
负责 fetch -> enrich -> detect -> analyze -> notify 一个周期。
"""
import logging
import time
from datetime import datetime
from collections import deque
from typing import Dict, Any, List, Tuple, Optional

try:
    from . import config
    from .data_feeder import feed_all_data, StockRealtimeData, fetch_daily_history_cache
    from .kimi_advisor import KimiAdvisor
    from . import notification
    from . import database
except ImportError:
    import config
    from data_feeder import feed_all_data, StockRealtimeData, fetch_daily_history_cache
    from kimi_advisor import KimiAdvisor
    import notification
    import database

logger = logging.getLogger(__name__)


def is_trading_time() -> bool:
    """
    判断当前是否在 A 股交易时段内。
    09:30 - 11:30 / 13:00 - 15:00（避开 09:25 集合竞价空快照噪声）
    """
    now = datetime.now()
    current_time = now.time()
    morning_start = datetime.strptime("09:30", "%H:%M").time()
    morning_end = datetime.strptime("11:30", "%H:%M").time()
    afternoon_start = datetime.strptime("13:00", "%H:%M").time()
    afternoon_end = datetime.strptime("15:00", "%H:%M").time()
    return (morning_start <= current_time <= morning_end) or \
           (afternoon_start <= current_time <= afternoon_end)


class MonitorEngine:
    """
    封装监控状态与单周期逻辑。TUI/GUI 按间隔调用 cycle()。
    线程安全说明：SQLite 连接在 database.py 内每次新建，可在工作线程调用。
    """

    def __init__(self,
                 stock_pool: Optional[List[str]] = None,
                 thresholds: Optional[Dict[str, float]] = None,
                 api_key: Optional[str] = None):
        # 运行时可变配置（GUI 改值时直接 set）
        self.stock_pool: List[str] = list(stock_pool if stock_pool is not None else config.STOCK_POOL)
        self.thresholds: Dict[str, float] = thresholds or {
            'rise_speed': config.RISE_SPEED_THRESHOLD,
            'vol_ratio': config.VOL_RATIO_THRESHOLD,
            'drop_speed': config.DROP_SPEED_THRESHOLD,
        }
        self.advisor = KimiAdvisor(api_key or config.KIMI_API_KEY)

        # 内存历史缓存（legacy 回退路径，DB 速度为 0 时兜底）
        self.price_history_cache: Dict[str, deque] = {}
        self.daily_history_cache: Dict[str, str] = {}
        self._initialized = False

    # ---- 运行时配置 setters（GUI 调用）----
    def set_stock_pool(self, pool: List[str]):
        self.stock_pool = list(pool)

    def set_thresholds(self, thresholds: Dict[str, float]):
        self.thresholds.update(thresholds)

    # ---- 初始化（只跑一次）----
    def init(self, log_cb=None):
        """初始化 DB 与日线历史缓存。log_cb(msg) 可选用于 UI 日志。"""
        if self._initialized:
            return
        database.init_db()
        if log_cb:
            log_cb("Checking Stock Metadata (Populating if empty, please wait)...")
        database.init_all_stock_meta()
        try:
            self.daily_history_cache = fetch_daily_history_cache(self.stock_pool)
        except Exception as e:
            logger.error(f"Daily history init failed: {e}")
            self.daily_history_cache = {}
        self._initialized = True

    # ---- 单周期 ----
    def cycle(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
        """
        执行一次完整监控周期。
        返回:
            rows:    表格显示数据 list[dict]
            alerts:  触发的预警 list[dict]，含 ai_response / pushed 字段
            status:  'ok' / 'fetch_failed' / 'no_trading'
        """
        if not self._initialized:
            self.init()

        try:
            data_map = feed_all_data(stock_list=self.stock_pool, all_market=False)
        except Exception as e:
            logger.error(f"Fetch failed: {e}")
            return [], [], 'fetch_failed'

        # 仅交易时段写 DB
        if is_trading_time():
            db_payload = [{
                'code': sym,
                'price': d.snapshot.get('最新价', 0),
                'change_pct': d.snapshot.get('涨跌幅', 0),
                'volume': d.snapshot.get('成交量', 0),
            } for sym, d in data_map.items()]
            try:
                database.save_snapshots(db_payload)
            except Exception as e:
                logger.error(f"DB save failed: {e}")

        # 市场情绪
        sentiment_vals = [d.snapshot.get('涨跌幅', 0) for d in data_map.values()
                          if d.snapshot.get('涨跌幅', 0) != 0]
        market_sentiment = round(sum(sentiment_vals) / len(sentiment_vals), 2) if sentiment_vals else 0.0

        rows: List[Dict[str, Any]] = []
        alerts: List[Dict[str, Any]] = []

        for symbol in self.stock_pool:
            if symbol not in data_map:
                rows.append({'code': symbol, 'name': 'N/A', 'status': 'Offline'})
                continue

            data = data_map[symbol]

            # DB 富化（涨速/量比真值）
            try:
                history_stats = database.get_stock_history_stats(symbol)
                data.snapshot['量比'] = history_stats.get('vol_ratio', 1.0)
                data.snapshot['speed_3min_db'] = history_stats.get('speed_3min', 0.0)
                data.snapshot['trend_desc'] = history_stats.get('trend_desc', '')
                data.snapshot['daily_trend'] = self.daily_history_cache.get(symbol, "N/A")
                data.snapshot['price_trend'] = database.get_price_trend(symbol)
            except Exception as e:
                logger.error(f"DB Enrich Error {symbol}: {e}")

            data.snapshot['market_sentiment'] = market_sentiment

            trigger = self._check_triggers(data)

            status_str = "Normal"
            if trigger:
                alert_type = trigger['type']
                indicators = trigger['indicators']
                status_str = alert_type

                alert_record = {
                    'time': datetime.now().strftime("%H:%M:%S"),
                    'symbol': symbol,
                    'name': data.name,
                    'type': alert_type,
                    'indicators': indicators,
                    'ai_response': None,
                    'pushed': False,
                }

                # Kimi 分析（阻塞，GUI 应在工作线程调用 cycle）
                try:
                    ai_response = self.advisor.analyze_alert(data, alert_type, indicators)
                    alert_record['ai_response'] = ai_response
                    if ai_response:
                        push_title = f"🚨 预警: {data.name} 触发 {alert_type}"
                        notification.send_feishu(push_title, ai_response)
                        alert_record['pushed'] = True
                except Exception as e:
                    logger.error(f"AI/Notify Error {symbol}: {e}")
                    alert_record['ai_response'] = f"❌ {e}"

                alerts.append(alert_record)

            rows.append({
                'code': symbol,
                'name': data.name,
                'price': data.snapshot.get('最新价', 0),
                'pct_chg': data.snapshot.get('涨跌幅', 0),
                'speed': data.snapshot.get('speed_3min_db', 0.0),
                'avg_price': data.snapshot.get('均价', 0),
                'commit_ratio': data.snapshot.get('委比', 0),
                'high': data.snapshot.get('最高', 0),
                'low': data.snapshot.get('最低', 0),
                'vol_ratio': data.snapshot.get('量比', 1.0),
                'status': status_str,
                'sentiment': market_sentiment,
            })

        return rows, alerts, 'ok'

    # ---- 触发检测（从 main.py 移植，保持等价）----
    def _update_state(self, symbol: str, current_price: float):
        if current_price <= 0:
            return
        if symbol not in self.price_history_cache:
            self.price_history_cache[symbol] = deque(maxlen=config.HISTORY_LEN)
        if self.price_history_cache[symbol]:
            last_price = self.price_history_cache[symbol][-1]
            smoothed_price = current_price * 0.7 + last_price * 0.3
            self.price_history_cache[symbol].append(smoothed_price)
        else:
            self.price_history_cache[symbol].append(current_price)

    def _calc_speed_3min(self, symbol: str) -> float:
        history = self.price_history_cache.get(symbol)
        if not history or len(history) < 2:
            return 0.0
        oldest = history[0]
        latest = history[-1]
        if oldest == 0:
            return 0.0
        return ((latest - oldest) / oldest) * 100

    def _check_triggers(self, data: StockRealtimeData) -> Optional[Dict[str, Any]]:
        if not data.snapshot:
            return None
        symbol = data.symbol
        current_price = float(data.snapshot.get('最新价', 0))
        if current_price <= 0:
            return None
        vol_ratio = float(data.snapshot.get('量比', 0) or 0)

        self._update_state(symbol, current_price)

        speed = data.snapshot.get('speed_3min_db', 0.0)
        if speed == 0.0:
            speed = self._calc_speed_3min(symbol)

        indicators = {
            'speed_3min': speed,
            'vol_ratio': vol_ratio,
            'logic_desc': '',
        }

        # Model 1: Rocket Launch
        if speed > self.thresholds['rise_speed'] and vol_ratio > self.thresholds['vol_ratio']:
            indicators['logic_desc'] = (
                f"3分钟涨速 {speed:.2f}% > {self.thresholds['rise_speed']}% 且 "
                f"量比 {vol_ratio} > {self.thresholds['vol_ratio']}"
            )
            return {'type': '🚀 火箭发射', 'indicators': indicators}

        # Model 2: High Dive
        if speed < self.thresholds['drop_speed']:
            indicators['logic_desc'] = (
                f"3分钟跌幅 {speed:.2f}% < {self.thresholds['drop_speed']}%"
            )
            return {'type': '🌊 高台跳水', 'indicators': indicators}

        # Model 3: Undercurrent — DISABLED (net inflow data source missing)

        return None