import sys
import os
import pandas as pd

# Add parent directory to path so we can import quant_local
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from quant_local.data_feeder import fetch_all_data, StockRealtimeData

def verify_data_feeder():
    test_stocks = ['600000', '000001', '300059'] # PF Bank, Ping An, East Money
    print(f"Starting verification for stocks: {test_stocks}")
    
    results = fetch_all_data(test_stocks, max_workers=3)
    
    if not results:
        print("FAIL: No results returned.")
        return
        
    for symbol in test_stocks:
        if symbol not in results:
            print(f"FAIL: Symbol {symbol} missing from results.")
            continue
            
        data = results[symbol]
        print(f"Verifying {symbol} - {data.name}...")
        
        # 1. Check Snapshot
        if not data.snapshot:
            print(f"  [X] Snapshot missing")
        else:
            price = data.snapshot.get('最新价')
            print(f"  [OK] Snapshot (Price: {price})")
            
        # 2. Check Order Book
        # order_book is a list of dicts or dict
        if not data.order_book:
            print(f"  [X] Order Book missing")
        else:
            # Check structure roughly
            print(f"  [OK] Order Book present")
            
        # 3. Check Ticks
        if not data.tick_analysis:
            print(f"  [X] Tick Analysis missing (could be market closed or no volume)")
        else:
            print(f"  [OK] Tick Analysis: {data.tick_analysis}")
            
        # 4. Check Min Bars
        if data.min_bars is None or data.min_bars.empty:
            print(f"  [X] Min Bars missing")
        else:
            rows = len(data.min_bars)
            print(f"  [OK] Min Bars (Rows: {rows})")
            
    print("\nVerification Complete.")

if __name__ == "__main__":
    verify_data_feeder()
