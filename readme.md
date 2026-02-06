# 🚀 kimi_stock_advisor (A-Share)

**基于 Kimi 大模型与本地数据流的 A 股智能量化监控终端**

> ⚠️ **Disclaimer**: 本项目仅供技术研究与辅助参考，不构成任何投资建议。股市有风险，入市需谨慎。

## 📖 简介 | Introduction

**Quant Local** 是一个轻量级、高敏感度的 A 股实时监控系统。它不同于传统的量化框架，核心理念是**“小而美”与“AI 赋能”**。

系统利用 `EasyQuotation` 获取毫秒级行情，通过本地 `SQLite` 数据库实时清洗数据，自行计算“3分钟涨速”和“动态量比”等深度指标。一旦捕捉到**“火箭发射”**或**“高台跳水”**等异动信号，系统会立即唤醒 Kimi (Moonshot AI) 扮演资深交易员进行盘面分析，并将结论通过**飞书 (Feishu)** 实时推送到您的手机。

## ✨ 核心特性 | Features

* **⚡️ 极速行情**: 基于 `EasyQuotation` (新浪源) 实现 3-5秒/次的超高频扫描，支持 A 股与 ETF。
* **🧠 Kimi AI 交易员**: 集成 Moonshot Kimi 大模型，不仅看价格，还能结合**日内分时形态**（15分钟轨迹）与**中期趋势**（5日K线）给出买卖逻辑。
* **📊 本地数据清洗**: 拒绝 API 依赖！内置 `SQLite` 引擎，实时存储快照，本地反向合成“真·3分钟涨速”与“量比”，比收费软件更灵敏。
* **📱 飞书卡片推送**: 报警触发后，通过飞书机器人发送富文本卡片，支持 Markdown 渲染 AI 分析报告。
* **🖥 极客终端 UI**: 基于 `Rich` 库打造的 CLI 仪表盘，实时刷新，红绿涨跌一目了然。
* **🛡 隐私安全**: 所有 API Key 与敏感配置均通过环境变量管理，代码零硬编码。

## 🛠 架构流程 | Architecture

1. **Fetch**: 启动时预加载 AkShare 日线数据；运行时高频拉取 EasyQuotation 实时快照。
2. **Store**: 将每一笔 Tick 数据存入本地 `quant_data.db`。
3. **Enrich**: 实时从数据库回溯计算衍生指标（涨速、量比、分时趋势串）。
4. **Detect**: 策略引擎匹配模式（如：涨速 > 1.0% 且 量比 > 1.5）。
5. **Analyze**: 触发阈值 -> 组装 Prompt (包含宏观情绪、微观形态) -> 请求 Kimi AI。
6. **Notify**: AI 返回结论 -> 飞书 Webhook 推送。

## 🚀 快速开始 | Quick Start

### 1. 环境准备

确保您的环境安装了 Python 3.10+。

```bash
# 克隆仓库
git clone https://github.com/your-username/quant_local.git
cd quant_local

# 安装依赖
pip install -r requirements.txt

```

*(注：如果尚未创建 `requirements.txt`，可以使用 `pip install easyquotation akshare rich openai requests pandas`)*

### 2. 配置环境变量 (推荐)

为了保护您的 API Key，请在终端设置环境变量，或在项目根目录创建 `.env` 文件：

```bash
# macOS / Linux (.zshrc 或 .bashrc)
export KIMI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxxx-xxxx"
export FEISHU_SECRET="" # (可选) 飞书签名校验密钥

# Windows (PowerShell)
$env:KIMI_API_KEY="sk-xxxxxxxx"
...

```

### 3. 配置股票池

打开 `quant_local/config.py`，修改 `STOCK_POOL` 列表：

```python
STOCK_POOL = [
    '600519', # 贵州茅台
    '513180', # 恒生科技ETF
    '300059', # 东方财富
    # ... 添加您关注的代码
]

```

您也可以在 `config.py` 中微调策略阈值（如 `RISE_SPEED_THRESHOLD`）。

### 4. 启动监控

```bash
python -m quant_local.main

```

启动后，您将看到终端显示实时行情表格。前 3 分钟数据可能在积累中，随后指标将开始跳动。

## 🤖 策略说明 | Strategies

目前内置两套核心策略（可在 `config.py` 调整参数）：

| 策略名称 | 触发条件 (默认) | 逻辑描述 |
| --- | --- | --- |
| **🚀 火箭发射 (Rocket)** | 3分钟涨速 > 1.0% **且** 量比 > 1.5 | 捕捉主力资金点火拉升的瞬间，结合量能确认真伪。 |
| **🌊 高台跳水 (High Dive)** | 3分钟跌速 < -1.5% | 预警盘中急杀，提示止盈或止损风险。 |

*(注：系统会自动计算“市场情绪”，即监控池的平均涨跌幅，作为 AI 判断的宏观参考)*

## 📂 目录结构

```text
quant_local/
├── main.py             # 主程序入口，调度循环
├── config.py           # 配置文件 (股票池、阈值)
├── database.py         # SQLite 存储与指标计算
├── data_feeder.py      # 数据获取 (EasyQuotation + AkShare)
├── kimi_advisor.py     # AI 分析师 (Moonshot 接口)
├── dashboard.py        # Rich 终端 UI
├── notification.py     # 飞书消息推送
└── verify_data_feeder.py # 数据源测试工具

```

## 🤝 贡献 | Contributing

欢迎提交 Issue 或 Pull Request！如果您有更好的 prompt 策略或新的数据源接口，请随时分享。
