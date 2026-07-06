import logging
import json
from typing import Dict, Any
try:
    from .data_feeder import StockRealtimeData
except ImportError:
    from data_feeder import StockRealtimeData
# Import OpenAI client
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)

class KimiAdvisor:
    """
    AI Advisor based on Kimi LLM (Moonshot AI).
    Analyzes market data and provides trading advice/insights.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = None
        if OpenAI:
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.moonshot.cn/v1",
            )
        else:
            logger.warning("OpenAI package not installed. Kimi AI features will be limited to local Mock output.")

    def analyze_alert(self, data: StockRealtimeData, alert_type: str, indicators: Dict[str, Any]):
        """
        Analyze a specific alert trigger and generate a Kimi Prompt.
        And call the API if configured.
        """
        prompt_content = self._construct_prompt(data, alert_type, indicators)
        
        # Print Local Log First
        print("\n" + "="*60)
        print(f"🚨 [AI 预警] {alert_type} :: {data.name} ({data.symbol})")
        print("-" * 60)
        print(f"触发逻辑: {indicators.get('logic_desc', '')}")
        print(f"当前价格: {data.snapshot.get('最新价')} | 3分钟涨速: {indicators.get('speed_3min', 0):.2f}%")
        print(f"量比数据: {indicators.get('vol_ratio', 0)} | 主力净流入: {indicators.get('net_inflow', 0)} 万")
        print("="*60 + "\n")
        
        # Call Kimi API
        response_text = None
        if not self.client:
             return "⚠️ 错误: 未安装 openai 库，请执行 pip install openai"
             
        if not self.api_key or "sk-" not in self.api_key:
             return "⚠️ 错误: API Key 未配置或无效"

        response_text = self._call_kimi_api(prompt_content)
        return response_text

    def _call_kimi_api(self, prompt: str):
        """Call Kimi k2.5 API"""
        print("⏳ 正在请求 Kimi (kimi-k2.5) 进行分析...")
        try:
            completion = self.client.chat.completions.create(
                model="kimi-k2.5",  # Explicitly using kimi-k2.5
                messages=[
                    {"role": "system", "content": "你是资深A股交易员，请简短输出分析结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
            )
            response = completion.choices[0].message.content
            print("\n🤖 [Kimi 分析结果]:")
            print(response)
            print("-" * 60 + "\n")
            return response
        except Exception as e:
            logger.error(f"Kimi API 调用失败: {e}")
            print(f"❌ Kimi API Error: {e}")
            return f"❌ API 调用失败: {str(e)}"

    def _construct_prompt(self, data: StockRealtimeData, alert_type: str, indicators: Dict[str, Any]) -> str:
        """
        Construct the "Senior Trader" prompt.
        """
        price = data.snapshot.get('最新价', 0)
        pct_chg = data.snapshot.get('涨跌幅', 0)
        
        prompt = f"""
# Role
资深 A 股交易员 & 风险控制专家

# Context
股票代码: {data.symbol} ({data.name})
触发类型: {alert_type}
触发时间: N/A (Realtime)

# Real-time Data
1. 价格动态: 
   - 当前价: {price}
   - 今日涨跌幅: {pct_chg}% (相对于昨日收盘价)
   - 3分钟涨速: {indicators.get('speed_3min', 0):.2f}% (FROM LOCAL DB)
   
2. 资金博弈:
   - 动态量比: {indicators.get('vol_ratio', 0)} (FROM LOCAL DB: 1min delta / 30min avg)
   - 盘口委比: {data.snapshot.get('委比', 0):+.2f}% (正值代表买盘强，负值代表抛压重)
   - 日内均价: {data.snapshot.get('均价', 0):.2f} (当前乖离: {((price - data.snapshot.get('均价', 0))/data.snapshot.get('均价', 1)*100) if data.snapshot.get('均价', 0) > 0 else 0:+.2f}%)
   - 主力净流入: N/A (数据暂缺，请重点关注量价配合)
   - 盘口特征: {indicators.get('order_book_feature', 'N/A')}

3. 历史时空背景:
   - 市场情绪(监控池): {data.snapshot.get('market_sentiment', 0):+.2f}%
   - 短期形态(15分): {data.snapshot.get('price_trend', 'N/A')}
   - 中期趋势(5日): {data.snapshot.get('daily_trend', 'N/A')}

# Task
请分析上述数据，判断当前异动的原因：
A. 主力真金白银拉升，建议跟进（买入）。
B. 主力诱多/拉高出货，建议观望或卖出（风险）。
C. 市场恐慌错杀，建议抄底（反转）。
D. 杂音波动，忽略。

请输出结论 (A/B/C/D) 并给出 50 字以内的简述。
"""
        return prompt
