import sys
import os
import logging
import time
from collections import deque
from typing import Dict, Any

from . import config
from .data_feeder import fetch_all_data, StockRealtimeData
from .kimi_advisor import KimiAdvisor
from . import notification

# Setup logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('quant_monitor.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# STATE MANAGER
# Store recent price history for speed calculation
# {symbol: deque([price1, price2, ...], maxlen=config.HISTORY_LEN)}
price_history_cache: Dict[str, deque] = {}

def update_state(symbol: str, current_price: float):
    """Update price history state for a symbol."""
    if current_price <= 0:
        return
        
    if symbol not in price_history_cache:
        price_history_cache[symbol] = deque(maxlen=config.HISTORY_LEN)
    
    
    # Simple Smoothing: If we have history, average with last price to avoid single-tick spikes
    if price_history_cache[symbol]:
        last_price = price_history_cache[symbol][-1]
        # Weighted avg: 70% current, 30% last
        smoothed_price = current_price * 0.7 + last_price * 0.3
        price_history_cache[symbol].append(smoothed_price)
    else:
        price_history_cache[symbol].append(current_price)

def calc_speed_3min(symbol: str) -> float:
    """Calculate Approx 3-min speed based on history deque."""
    history = price_history_cache.get(symbol)
    if not history or len(history) < 2:
        return 0.0
    
    # Simple change: (Latest - Oldest) / Oldest
    # Assuming each tick is ~30-60s interval (set in config)
    oldest = history[0]
    latest = history[-1]
    
    if oldest == 0: return 0.0
    
    return ((latest - oldest) / oldest) * 100

def check_triggers(data: StockRealtimeData) -> Dict[str, Any]:
    """
    Check for Rocket, High Dive, and Undercurrent patterns.
    Returns None if no trigger, or a dict {alert_type, indicators}.
    """
    if not data.snapshot:
        return None
        
    symbol = data.symbol
    current_price = float(data.snapshot.get('最新价', 0))
    if current_price <= 0:
        return None
        
    vol_ratio = float(data.snapshot.get('量比', 0) or 0) # Handle None
    
    # 1. Update State
    update_state(symbol, current_price)
    
    # 2. Calculate Indicators
    # Prefer DB enriched speed if available, else legacy calc
    speed = data.snapshot.get('speed_3min_db', 0.0)
    if speed == 0.0:
         speed = calc_speed_3min(symbol)
    
    # Net Inflow (Mock or Real)
    # Using '成交额' as proxy if net inflow not available directly in snapshot
    # Real logic needs 'stock_zh_a_tick_tx_js' analysis result
    net_inflow = data.tick_analysis.get('net_vol', 0) if data.tick_analysis else 0
    # Convert hands to money roughly (Price * Vol * 100 / 10000 = Wan)
    net_inflow_wan = (net_inflow * 100 * current_price) / 10000 if net_inflow else 0

    indicators = {
        'speed_3min': speed,
        'vol_ratio': vol_ratio,
        'net_inflow': net_inflow_wan,
        'logic_desc': ''
    }
    
    # 3. Model Detection
    
    # [Model 1] Rocket Launch 🚀
    # Now using DB-calculated VolRatio, so we can respect the threshold again!
    if speed > config.RISE_SPEED_THRESHOLD and vol_ratio > config.VOL_RATIO_THRESHOLD:
        indicators['logic_desc'] = f"3分钟涨速 {speed:.2f}% > {config.RISE_SPEED_THRESHOLD}% 且 量比 {vol_ratio} > {config.VOL_RATIO_THRESHOLD}"
        return {'type': '🚀 火箭发射', 'indicators': indicators}
        
    # [Model 2] High Dive 🌊
    if speed < config.DROP_SPEED_THRESHOLD:
        indicators['logic_desc'] = f"3分钟跌幅 {speed:.2f}% < {config.DROP_SPEED_THRESHOLD}%"
        return {'type': '🌊 高台跳水', 'indicators': indicators}
        
    # [Model 3] Undercurrent (Hidden Accumulation) ⚓
    # DISABLED: Depends on net_inflow which is currently 0 (missing data source).
    # if abs(speed) < 1.0 and net_inflow_wan > config.NET_INFLOW_THRESHOLD:
    #     indicators['logic_desc'] = f"价格波动极小 但主力净流入 {net_inflow_wan:.0f}万 > {config.NET_INFLOW_THRESHOLD}万"
    #     return {'type': '⚓ 暗流涌动', 'indicators': indicators}
        
    return None

def monitor_forever():
    # 0. Initialize Database
    try:
        from . import database
        from .dashboard import MonitorDashboard
        from rich.live import Live
    except ImportError as e:
        logger.error(f"Missing dependencies: {e}")
        return

    logger.info("Initializing Database...")
    database.init_db()
    
    # Check if we need to populate stock meta (RUN ONCE check)
    # This might take time, so warn user
    logger.info("Checking Stock Metadata (Populating if empty, please wait)...")
    database.init_all_stock_meta()
    
    logger.info(f"启动量化监控系统 (扫描间隔: {config.MONITOR_INTERVAL}秒)...")
    logger.info(f"监控股票池: {config.STOCK_POOL}")
    
    advisor = KimiAdvisor(api_key=config.KIMI_API_KEY)
    dashboard = MonitorDashboard()
    
    display_data = []
    for code in config.STOCK_POOL:
        display_data.append({'code': code, 'name': 'Loading...', 'price': 0, 'pct_chg': 0, 'status': 'Loading...'})

    # 0.2 Pre-load Daily History (Context)
    # This runs ONCE.
    try:
        daily_history_cache = data_feeder.fetch_daily_history_cache(config.STOCK_POOL)
    except Exception as e:
        logger.error(f"Daily history init failed: {e}")
        daily_history_cache = {}

    # Start Rich Live Loop
    with Live(dashboard.generate_layout(display_data), refresh_per_second=1, screen=True) as live:
        try:
            while True:
                dashboard.add_log("--- Scanning Market ---")
                
                # 1. Fetch
                try:
                    # Fetch ONLY Monitored Pool (Optimization)
                    # Previous "All Market" fetch was causing DB bloat and slowness (~5000 rows/10s).
                    data_map = fetch_all_data(stock_list=config.STOCK_POOL, all_market=False)
                    dashboard.add_log(f"Fetched {len(data_map)} stocks (Pool Only).")
                    
                except Exception as e:
                    dashboard.add_log(f"[Error] Fetch failed: {e}")
                    time.sleep(5)
                    continue

                # 2. Save to DB
                # Convert to list of dicts for DB
                db_payload = []
                for symbol, data in data_map.items():
                    db_payload.append({
                        'code': symbol,
                        'price': data.snapshot.get('最新价', 0),
                        'change_pct': data.snapshot.get('涨跌幅', 0),
                        'volume': data.snapshot.get('成交量', 0)
                    })
                database.save_snapshots(db_payload)
                
                # 2.1 Calculate Market Sentiment (Pool Average)
                sentiment = 0.0
                valid_count = 0
                for d in data_map.values():
                    p = d.snapshot.get('涨跌幅', 0)
                    if p != 0:
                        sentiment += p
                        valid_count += 1
                market_sentiment = round(sentiment / valid_count, 2) if valid_count > 0 else 0.0

                # 3. Analyze & Trigger & Update Display
                new_display_data = []
                
                for symbol in config.STOCK_POOL:
                    if symbol not in data_map:
                        new_display_data.append({'code': symbol, 'name': 'N/A', 'status': 'Offline'})
                        continue
                        
                    data = data_map[symbol]
                    
                    # 2.1 [ENRICHMENT] Reverse Engineer History from DB
                    # Speed & Vol Ratio are now calculated from DB history, not just memory
                    try:
                        history_stats = database.get_stock_history_stats(symbol)
                        # Inject into data.snapshot
                        data.snapshot['量比'] = history_stats.get('vol_ratio', 1.0)
                        # We can also put speed here for check_triggers to use
                        data.snapshot['speed_3min_db'] = history_stats.get('speed_3min', 0.0)
                        data.snapshot['speed_3min_db'] = history_stats.get('speed_3min', 0.0)
                        data.snapshot['trend_desc'] = history_stats.get('trend_desc', '')
                        
                        # [Context Injection]
                        # 1. Daily Trend (from startup cache)
                        data.snapshot['daily_trend'] = daily_history_cache.get(symbol, "N/A")
                        
                        # 2. Intraday Trend (from DB)
                        # Slightly expensive query, but checking pool size (e.g. 20 stocks) * 10s is fine.
                        # Optimization: Only fetch if trigger candidates? Or just fetch.
                        # Main loop is 10s. 20 queries is fine for SQLite.
                        data.snapshot['price_trend'] = database.get_price_trend(symbol)
                        
                    except Exception as e:
                         dashboard.add_log(f"DB Enrich Error {symbol}: {e}")

                    # Update State (History) for Speed Calc (Legacy memory cache, keeping it as backup or for smoothing)
                    # check_triggers internal logic handles update_state, so we skip explicit call here
                    # update_state(data.symbol, float(data.snapshot.get('最新价', 0)))
                    
                    # Check Triggers
                    # Pass market sentiment possibly? trigger doesn't use it yet but we put it in snapshot for AI?
                    data.snapshot['market_sentiment'] = market_sentiment
                    trigger = check_triggers(data)
                    
                    status_str = "Normal"
                    if trigger:
                        alert_type = trigger['type']
                        indicators = trigger['indicators']
                        status_str = f"{alert_type}"
                        
                        # Call AI (Async or non-blocking ideally, here it blocks)
                        dashboard.add_log(f"🔥 Trigger: {alert_type} on {data.name}")
                        try:
                            # 这一步会暂停几秒钟等待 AI 思考，属正常现象
                            dashboard.add_log(f"🤖 正在请求 AI 分析 {data.name}...")
                            ai_response = advisor.analyze_alert(data, alert_type, indicators)
                            
                            if ai_response:
                                dashboard.add_log(f"✅ AI 分析完成:")
                                # Add response line by line to dashboard
                                for line in ai_response.split('\n'):
                                    if line.strip():
                                        dashboard.add_log(f"[AI] {line.strip()}")
                                
                                # [新增] 发送飞书推送
                                push_title = f"🚨 预警: {data.name} 触发 {alert_type}"
                                notification.send_feishu(push_title, ai_response)
                                dashboard.add_log("📨 已触发飞书推送")

                            else:
                                dashboard.add_log(f"⚠️ AI 未返回有效内容")
                                
                        except Exception as e:
                            logger.error(f"AI Error: {e}")
                            dashboard.add_log(f"❌ AI 响应失败: {e}") 
                    # Use DB calculated speed for display if available, else legacy (which is 0.0 usually now without update_state called explicitly?)
                    # Wait, check_triggers calls update_state internally. 
                    # But we want the DB speed as it persists across restarts!
                    display_speed = data.snapshot.get('speed_3min_db', 0.0)
                    
                    new_display_data.append({
                        'code': symbol,
                        'name': data.name,
                        'price': data.snapshot.get('最新价', 0),
                        'pct_chg': data.snapshot.get('涨跌幅', 0),
                        'speed': display_speed,
                        'high': data.snapshot.get('最高', 0),
                        'low': data.snapshot.get('最低', 0),
                        'vol_ratio': data.snapshot.get('量比', 1.0),
                        'status': status_str
                    })
                    
                display_data = new_display_data
                live.update(dashboard.generate_layout(display_data))
            
                # 4. Sleep
                time.sleep(config.MONITOR_INTERVAL)
            
        except KeyboardInterrupt:
            logger.info("用户停止了监控程序。")


if __name__ == "__main__":
    monitor_forever()
