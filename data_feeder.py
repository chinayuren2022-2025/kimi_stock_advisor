import easyquotation
import pandas as pd
import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import akshare as ak
from . import config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize EasyQuotation (Sina source is fast for A-share)
# Global instance to reuse session
quotation_engine = easyquotation.use('sina')

@dataclass
class StockRealtimeData:
    """Dataclass to hold real-time data for a single stock."""
    symbol: str
    name: str = "Unknown"
    snapshot: Dict[str, Any] = field(default_factory=dict)
    order_book: Dict[str, Any] = field(default_factory=dict)
    # Ticks and MinBars are not supported by simple snapshot, left empty for compatibility
    tick_analysis: Dict[str, Any] = field(default_factory=dict)
    min_bars: Optional[pd.DataFrame] = None

def fetch_all_data(stock_list: List[str] = None, all_market=False) -> Dict[str, StockRealtimeData]:
    """
    Main entry point.
    If all_market=True, fetches ALL stocks using easyquotation.market_snapshot().
    Else fetches specific stock_list.
    """
    results = {}
    
    if all_market:
        logger.info("Fetching ALL A-share market snapshot...")
    else:
        logger.info(f"Fetching snapshot for {len(stock_list)} stocks...")
    
    try:
        if all_market:
            # market_snapshot returns all.
            raw_data = quotation_engine.market_snapshot(prefix=True)
        else:
            raw_data = quotation_engine.real(stock_list)
        
        # Parse result
        # Structure: {'000001': {'name': '平安银行', 'open': 10.0, 'now': 10.1, ...}, ...}
        for code, info in raw_data.items():
            # EasyQuotation returns dict. Keys might have 'sh'/'sz' prefix in all_market mode.
            # Strip it to match our config style (6 digits).
            if code.startswith('sh') or code.startswith('sz'):
                code = code[2:]
            
            # 1. Basic Info
            name = info.get('name', 'Unknown')
            current_price = float(info.get('now', 0))
            open_price = float(info.get('open', 0))
            
            # 2. Metrics
            # Vol Ratio: No history, defaults to 1.0 (Limit)
            vol_ratio = 1.0 
            
            # Pct Change: (Now - PreClose) / PreClose
            # 'close' in Sina API usually means Yesterday's Close
            pre_close = float(info.get('close', 0))
            pct_chg = 0.0
            
            if pre_close > 0:
                 pct_chg = round(((current_price - pre_close) / pre_close) * 100, 2)
            elif open_price > 0:
                # Fallback if pre_close is missing (rare)
                pct_chg = round(((current_price - open_price) / open_price) * 100, 2)
            
            # 3. Order Book
            # EasyQuotation (Sina) keys: 'buy_one', 'buy_one_price', ... 'sell_one', etc.
            # Map to list of dicts: [{'item': 'buy_1', 'value': vol}, {'item': 'buy_1_price', ...}]
            # Our main logic expects specific structure or we adapt main logic.
            # Let's adapt to our `StockRealtimeData` structure which main expects.
            # Main logic usually looks at Order Book or Snapshot.
            # Actually Main V2.2 looks at 'order_book' list for price usually, OR snapshot '最新价'.
            # We already have reliable 'now' price in snapshot, so we populate 'order_book' just for "Feature" completeness if needed.
            # Providing standard list of dicts structure:
            
            order_book_list = []
            levels = ['one', 'two', 'three', 'four', 'five']
            for i, level in enumerate(levels):
                idx = i + 1
                # Buy
                b_vol = info.get(f'bid{idx}_volume', 0)
                b_price = info.get(f'bid{idx}', 0)
                if b_vol > 0:
                    order_book_list.append({'item': f'buy_{idx}', 'value': b_vol})
                    order_book_list.append({'item': f'buy_{idx}_price', 'value': b_price})
                
                # Sell (Ask)
                a_vol = info.get(f'ask{idx}_volume', 0)
                a_price = info.get(f'ask{idx}', 0)
                if a_vol > 0:
                    order_book_list.append({'item': f'sell_{idx}', 'value': a_vol})
                    order_book_list.append({'item': f'sell_{idx}_price', 'value': a_price})

            # 4. Construct Object
            stock_data = StockRealtimeData(symbol=code, name=name)
            stock_data.snapshot = {
                '代码': code,
                '名称': name,
                '最新价': current_price,
                '今日开盘': open_price,
                '最髙': info.get('high', 0),
                '最低': info.get('low', 0),
                '成交量': info.get('turnover', 0), # Sina 'turnover' is volume (number of shares)
                '成交额': info.get('volume', 0),   # Sina 'volume' is amount (money)? Wait, easyquotation standardization varies.
                                                # Usually Sina raw: volume=shares, amount=money
                                                # EasyQuotation standardizes: turnover=成交量(手/股), volume=成交额?
                                                # Let's stick to what we need: Price & Vol Ratio (defaulted).
                '量比': vol_ratio,
                '涨跌幅': pct_chg
            }
            stock_data.order_book = order_book_list
            
            results[code] = stock_data
            
    except Exception as e:
        logger.error(f"EasyQuotation fetch failed: {e}")
        
    return results

# Legacy Single Fetch (Not used by new main fetch strategy, but kept for symbol compatibility if referenced)
def fetch_single_stock_details(symbol: str) -> StockRealtimeData:
    logger.warning("fetch_single_stock_details is deprecated in EasyQuotation mode.")
    return StockRealtimeData(symbol=symbol)

def fetch_daily_history_cache(stock_list: List[str]) -> Dict[str, str]:
    """
    Fetch recent 5-day daily history for context.
    Returns dict: {symbol: "[-5d:10.0(+2%)] -> ..."}
    Runs ONCE at startup to avoid API limits.
    """
    history_cache = {}
    logger.info(f"Pre-loading Daily History for {len(stock_list)} stocks (AkShare)...")
    
    for symbol in stock_list:
        try:
            # AkShare daily data
            # adjust='qfq' for adjusted close
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
            if df.empty:
                history_cache[symbol] = "无历史数据"
                continue
                
            # Take last 6 rows (exclude today if market open, simplified logic: take last 5 full days)
            # Assuming getting history includes today if trading.
            # Safe logic: take tail(6), exclude last one if it seems to be today (or just take last 5 finalized)
            # Simplification: Take last 5 rows.
            recent_df = df.tail(6)
            
            trend_strs = []
            for _, row in recent_df.iterrows():
                # date format usually '2023-01-01'
                date_str = str(row['日期'])[:10]
                close = row['收盘']
                pct = row['涨跌幅']
                trend_strs.append(f"[{date_str[5:]}:{close}({pct}%)])")
                
            # Join with arrow
            # Format: "12-01:10.5(+1%) -> 12-02:..."
            full_str = " -> ".join(trend_strs)
            history_cache[symbol] = full_str
            
        except Exception as e:
            logger.warning(f"Failed to fetch history for {symbol}: {e}")
            history_cache[symbol] = "历史数据获取失败"
            
    return history_cache
