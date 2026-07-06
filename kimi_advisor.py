"""
AI Advisor (多 Provider 支持)。
基于 openai SDK 调用任意 OpenAI 兼容接口 (Kimi/DeepSeek/Qwen/GLM/豆包/自定义)。
保留文件名 kimi_advisor.py 与 KimiAdvisor 别名，避免破坏 import 链。
"""
import logging
from typing import Dict, Any
try:
    from .data_feeder import StockRealtimeData
except ImportError:
    from data_feeder import StockRealtimeData
try:
    from . import ai_provider
except ImportError:
    import ai_provider
# Import OpenAI client
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


class AIAdvisor:
    """
    多 Provider AI 顾问。所有 provider 走 OpenAI 兼容接口。
    """
    def __init__(self,
                 provider: str = None,
                 api_key: str = None,
                 model: str = None,
                 base_url: str = None):
        # 解析配置：显式参数 > env > 预设
        self.provider, self.base_url, self.model, self.api_key = ai_provider.resolve(
            provider=provider,
            api_key_override=api_key,
            model_override=model,
            base_url_override=base_url,
        )
        self.client = None
        if OpenAI and self.api_key and self.base_url:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            logger.warning("OpenAI 包未安装或 base_url/api_key 缺失，AI 功能将降级。")

    def reconfigure(self, provider: str = None, api_key: str = None,
                    model: str = None, base_url: str = None):
        """运行时切换 provider（GUI 调用），重建 client。"""
        self.provider, self.base_url, self.model, self.api_key = ai_provider.resolve(
            provider=provider,
            api_key_override=api_key,
            model_override=model,
            base_url_override=base_url,
        )
        if OpenAI and self.api_key and self.base_url:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.client = None

    def analyze_alert(self, data: StockRealtimeData, alert_type: str, indicators: Dict[str, Any]):
        """
        分析预警触发，生成 prompt 并调用 LLM。
        """
        prompt_content = self._construct_prompt(data, alert_type, indicators)

        # Local Log
        print("\n" + "=" * 60)
        print(f"🚨 [AI 预警] {alert_type} :: {data.name} ({data.symbol})")
        print("-" * 60)
        print(f"触发逻辑: {indicators.get('logic_desc', '')}")
        print(f"当前价格: {data.snapshot.get('最新价')} | 3分钟涨速: {indicators.get('speed_3min', 0):.2f}%")
        print(f"量比数据: {indicators.get('vol_ratio', 0)}")
        print("=" * 60 + "\n")

        if not self.client:
            return "⚠️ 错误: 未安装 openai 库或 base_url/api_key 缺失"

        if not ai_provider.validate_key(self.provider, self.api_key):
            return f"⚠️ 错误: {self.provider} 的 API Key 未配置或格式无效"

        return self._call_llm_api(prompt_content)

    def _call_llm_api(self, prompt: str):
        """调用 LLM (OpenAI 兼容接口)"""
        print(f"⏳ 正在请求 {self.provider} ({self.model}) 进行分析...")
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是资深A股交易员，请简短输出分析结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
            )
            response = completion.choices[0].message.content
            print(f"\n🤖 [{self.provider} 分析结果]:")
            print(response)
            print("-" * 60 + "\n")
            return response
        except Exception as e:
            logger.error(f"{self.provider} API 调用失败: {e}")
            print(f"❌ {self.provider} API Error: {e}")
            return f"❌ API 调用失败: {str(e)}"

    def _construct_prompt(self, data: StockRealtimeData, alert_type: str, indicators: Dict[str, Any]) -> str:
        """
        构造"资深交易员" prompt。各 provider 通用。
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


# 兼容别名：旧代码 import KimiAdvisor 仍可用
KimiAdvisor = AIAdvisor