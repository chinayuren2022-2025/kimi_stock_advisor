import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock module dependencies before importing data_feeder
sys.modules['easyquotation'] = MagicMock()
sys.modules['akshare'] = MagicMock()

try:
    from quant_local.data_feeder import feed_all_data, StockRealtimeData
except ImportError:
    from data_feeder import feed_all_data, StockRealtimeData

class TestFeedAllData(unittest.TestCase):
    @patch('data_feeder.quotation_engine')
    def test_feed_all_data_parsing(self, mock_engine):
        # Mock data based on user provided sample
        # quotation.real('162411') 
        # {'162411': {'name': '华宝油气', 'open': 0.799, 'close': 0.788, 'now': 0.788, 'high': 0.8, 'low': 0.788, 'buy': 0.788, 'sell': 0.789, 'turnover': 214672645, 'volume': 170266195.863, 'bid1_volume': 254536, 'bid1': 0.788, 'bid2_volume': 618100, 'bid2': 0.787, 'bid3_volume': 124700, 'bid3': 0.786, 'bid4_volume': 53500, 'bid4': 0.785, 'bid5_volume': 159600, 'bid5': 0.784, 'ask1_volume': 468133, 'ask1': 0.789, 'ask2_volume': 231053, 'ask2': 0.79, 'ask3_volume': 1004046, 'ask3': 0.791, 'ask4_volume': 1039696, 'ask4': 0.792, 'ask5_volume': 810439, 'ask5': 0.793, 'date': '2026-02-09', 'time': '15:00:00'}}
        
        mock_response = {
            '162411': {
                'name': '华宝油气', 
                'open': 0.799, 
                'close': 0.788, 
                'now': 0.788, 
                'high': 0.8, 
                'low': 0.788, 
                'buy': 0.788, 
                'sell': 0.789, 
                'turnover': 214672645, 
                'volume': 170266195.863, 
                'bid1_volume': 254536, 'bid1': 0.788, 
                'bid2_volume': 618100, 'bid2': 0.787, 
                'ask1_volume': 468133, 'ask1': 0.789, 
                'date': '2026-02-09', 
                'time': '15:00:00'
            }
        }
        mock_engine.real.return_value = mock_response
        
        # Run function
        results = feed_all_data(stock_list=['162411'])
        
        # Verify results
        self.assertIn('162411', results)
        data = results['162411']
        self.assertIsInstance(data, StockRealtimeData)
        
        # Check Snapshot Fields
        snapshot = data.snapshot
        self.assertEqual(snapshot['代码'], '162411')
        self.assertEqual(snapshot['名称'], '华宝油气')
        self.assertEqual(snapshot['最新价'], 0.788)
        self.assertEqual(snapshot['成交量'], 214672645) # Turnover -> Volume (shares)
        self.assertEqual(snapshot['成交额'], 170266195.863) # Volume -> Amount (money)
        self.assertEqual(snapshot['昨收'], 0.788)
        self.assertEqual(snapshot['date'], '2026-02-09')
        self.assertEqual(snapshot['time'], '15:00:00')
        
        # Check Order Book
        # Should have bid1, bid2, ask1
        obs = data.order_book
        # We expect parsed list of dicts
        # buy_1
        self.assertTrue(any(item['item'] == 'buy_1' and item['value'] == 254536 for item in obs))
        self.assertTrue(any(item['item'] == 'buy_1_price' and item['value'] == 0.788 for item in obs))
        # buy_2
        self.assertTrue(any(item['item'] == 'buy_2' and item['value'] == 618100 for item in obs))
        # sell_1
        self.assertTrue(any(item['item'] == 'sell_1' and item['value'] == 468133 for item in obs))

        # Check New Indicators
        # Commit Ratio: (Total Bid - Total Ask) / (Total Bid + Total Ask)
        # Bid Vol: 254536 + 618100 + 0 + 0 + 0 = 872636
        # Ask Vol: 468133 + 0 + 0 + 0 + 0 = 468133 (Mock data only has ask1 provided in dict partially but let's check input)
        # Input has: ask1_volume=468133, ask2=231053... wait. 
        # The mock_response in test_feed_all_data had incomplete data compared to user prompt sample?
        # Let's check the mock_response definition in test file.
        # It had: 'bid1_volume': 254536, 'bid2_volume': 618100, 'ask1_volume': 468133.
        # So Bid=872636, Ask=468133.
        # Ratio = (872636 - 468133) / (872636 + 468133) = 404503 / 1340769 = 0.30169 -> 30.17%
        
        self.assertIn('委比', snapshot)
        self.assertEqual(snapshot['委比'], 30.17)
        
        # VWAP
        # Turnover (Vol) = 214672645
        # Volume (Amt) = 170266195.863
        # VWAP = Amt / Vol = 170266195.863 / 214672645 = 0.79314... -> 0.793
        self.assertIn('均价', snapshot)
        self.assertEqual(snapshot['均价'], 0.793)

    @patch('data_feeder.quotation_engine')
    def test_prefix_handling(self, mock_engine):
        # Mock data with prefix in key
        mock_response = {
            'sh000001': {
                'name': '平安银行', 
                'now': 10.0,
                'close': 9.9
            }
        }
        mock_engine.real.return_value = mock_response
        
        results = feed_all_data(stock_list=['sh000001'])
        
        # Should strip prefix
        self.assertIn('000001', results)
        self.assertEqual(results['000001'].snapshot['代码'], '000001')

if __name__ == '__main__':
    unittest.main()
