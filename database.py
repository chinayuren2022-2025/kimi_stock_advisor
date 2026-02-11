import sqlite3
import logging
import akshare as ak
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
import os

logger = logging.getLogger(__name__)

DB_FILE = "quant_data.db"

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    """Initialize database tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Stock Meta Table (All Stocks)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_meta (
            code TEXT PRIMARY KEY,
            name TEXT
        )
    ''')
    
    # 2. Market Snapshot Table (TimeSeries)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            code TEXT,
            price REAL,
            change_pct REAL,
            volume REAL,
            FOREIGN KEY(code) REFERENCES stock_meta(code)
        )
    ''')
    
    # 3. Performance Index (Composite)
    # Critical for get_stock_history_stats to be fast with millions of rows
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_code_timestamp 
        ON market_snapshot (code, timestamp DESC)
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized (with Index).")

def init_all_stock_meta():
    """
    Populate stock_meta with ALL A-share stocks.
    Checks if empty first to avoid repeated heavy fetching.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if we already have data
    cursor.execute("SELECT count(*) FROM stock_meta")
    count = cursor.fetchone()[0]
    
    if count > 1000:
        logger.info(f"Stock meta already populated ({count} stocks). Skipping fetch.")
        conn.close()
        return

    logger.info("Fetching ALL A-share stock list (this may take a moment)...")
    try:
        # Use AkShare to get list
        df = ak.stock_info_a_code_name()
        # df columns: code, name
        
        data_to_insert = []
        for _, row in df.iterrows():
            data_to_insert.append((row['code'], row['name']))
            
        cursor.executemany("INSERT OR IGNORE INTO stock_meta (code, name) VALUES (?, ?)", data_to_insert)
        conn.commit()
        logger.info(f"Successfully populated {len(data_to_insert)} stocks into meta table.")
        
    except Exception as e:
        logger.error(f"Failed to populate stock meta: {e}")
        
    conn.close()

def save_snapshots(data_list: List[Dict[str, Any]]):
    """
    Save a batch of snapshots to DB.
    """
    if not data_list:
        return

    conn = get_connection()
    cursor = conn.cursor()
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    insert_sql = "INSERT INTO market_snapshot (timestamp, code, price, change_pct, volume) VALUES (?, ?, ?, ?, ?)"
    rows = []
    
    for item in data_list:
        rows.append((
            now_str,
            item.get('code'),
            item.get('price'),
            item.get('change_pct'),
            item.get('volume')
        ))
        
    try:
        conn.execute("BEGIN TRANSACTION")
        cursor.executemany(insert_sql, rows)
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving snapshots to DB: {e}")
        
    conn.close()

def get_stock_history_stats(symbol: str, minutes=30) -> Dict[str, Any]:
    """
    Reverse engineer metrics from local DB history.
    Calculates:
    - speed_3min: Price change over last 3 mins.
    - vol_ratio: (Latest 1-min Vol) / (Avg 1-min Vol of past 30 mins).
    """
    conn = get_connection()
    # Fetch recent history
    # We need enough buffer. 30 mins.
    # We fetch last N records.
    # Better: Fetch by Time.
    
    query = f"""
        SELECT timestamp, price, volume 
        FROM market_snapshot 
        WHERE code = ? 
        ORDER BY timestamp DESC 
        LIMIT {minutes * 10}  
    """
    # Assuming 6 snapshots per min (10s interval), 30*6 = 180 records.
    # Safely fetch 300 to be sure.
    
    try:
        df = pd.read_sql_query(query, conn, params=(symbol,))
        conn.close()
        
        if df.empty or len(df) < 5:
            return {'speed_3min': 0.0, 'vol_ratio': 1.0, 'trend_desc': 'Insufficient Data'}
            
        # Ensure proper types
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp') # Ascending
        
        # 1. Calc 3-min Speed
        # Find record closets to 3 mins ago
        now_time = df.iloc[-1]['timestamp']
        target_time = now_time - pd.Timedelta(minutes=3)
        
        # Find index closest to target_time
        # simple search
        idx_3min = df['timestamp'].searchsorted(target_time)
        # Handle if target is before start
        if idx_3min < 0: idx_3min = 0
        if idx_3min >= len(df): idx_3min = len(df) - 1
            
        price_now = df.iloc[-1]['price']
        price_3min = df.iloc[idx_3min]['price']
        
        speed_3min = 0.0
        if price_3min > 0:
            speed_3min = ((price_now - price_3min) / price_3min) * 100
            
        # 2. Calc Vol Ratio
        # Need to resample to 1-min to get delta volume (since raw volume is cumulative for the day)
        # Note: If 'volume' is cumulative:
        # Vol_1min = Record_End_Min - Record_Start_Min
        # Let's resample using pandas
        
        df_resampled = df.set_index('timestamp').resample('1min').last()
        # Calculate Delta of Cumulative Volume
        df_resampled['vol_delta'] = df_resampled['volume'].diff()
        
        # Now we have minute-by-minute volume
        valid_vols = df_resampled['vol_delta'].dropna()
        
        vol_ratio = 1.0
        if len(valid_vols) >= 2:
            latest_vol = valid_vols.iloc[-1]
            past_vols = valid_vols.iloc[:-1]
            
            # Use last 30 mins (or available)
            avg_vol = past_vols.tail(30).mean()
            
            if avg_vol > 0:
                vol_ratio = latest_vol / avg_vol
                
        # 3. Trend Desc
        trend_desc = "震荡"
        if speed_3min > 1.0: trend_desc = "快速上行"
        elif speed_3min < -1.0: trend_desc = "快速下行"
        elif 0.5 < speed_3min <= 1.0: trend_desc = "稳步推升"
        elif -1.0 <= speed_3min < -0.5: trend_desc = "阴跌"
        
        return {
            'speed_3min': round(speed_3min, 2),
            'vol_ratio': round(vol_ratio, 2),
            'trend_desc': trend_desc
        }
        
    except Exception as e:
        logger.error(f"Error calculating stats for {symbol}: {e}")
        conn.close()
        return {'speed_3min': 0.0, 'vol_ratio': 1.0, 'trend_desc': 'Error'}


def get_price_trend(symbol: str, limit_mins=15) -> str:
    """
    Get intraday price trend string for AI context.
    Format: "10:00(10.5) -> 10:01(10.6)..."
    """
    conn = get_connection()
    try:
        # Fetch last N records approx covering limit_mins
        query = f"""
            SELECT timestamp, price 
            FROM market_snapshot 
            WHERE code = ? 
            ORDER BY timestamp DESC 
            LIMIT {limit_mins * 6 + 10}
        """
        df = pd.read_sql_query(query, conn, params=(symbol,))
        
        if df.empty:
            return "无日内数据"
            
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Resample to 1min closing price
        df_1min = df.set_index('timestamp').resample('1min')['price'].last().dropna()
        
        # Take last limit_mins points
        recent_1min = df_1min.tail(limit_mins)
        
        trend_parts = []
        for time_idx, price in recent_1min.items():
            time_str = time_idx.strftime("%H:%M")
            trend_parts.append(f"{time_str}({price})")
            
        return " -> ".join(trend_parts)
        
    except Exception as e:
        logger.error(f"Error getting price trend for {symbol}: {e}")
        return "趋势数据错误"
    finally:
        conn.close()
