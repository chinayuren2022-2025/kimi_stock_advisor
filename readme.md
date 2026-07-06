# kimi_stock_advisor

**A 股实时量化监控终端 · 多 LLM 智能分析 · 飞书秒级推送**

> ⚠️ **免责声明**：本项目仅供技术研究与辅助参考，不构成任何投资建议。股市有风险，入市需谨慎。

---

## 简介

一个轻量级、高敏感度的 A 股实时监控系统。核心理念：**小而美 + AI 赋能**。

系统利用 EasyQuotation（新浪源）获取 3-10 秒级实时行情，通过本地 SQLite 数据库自行计算「3 分钟涨速」和「动态量比」等深度指标。一旦捕捉到「火箭发射」或「高台跳水」等异动信号，立即唤醒 AI 交易员（支持 Kimi / DeepSeek / 通义千问 / 智谱 GLM / 豆包 / 自定义，运行时热切换）进行盘面分析，并将结论通过飞书机器人实时推送到你的手机。

提供 **PyQt6 桌面 GUI** 与 **Rich 终端 TUI** 双入口，一键脚本启动。

## 核心特性

- **极速行情** — 基于 EasyQuotation（新浪源）3-10 秒/次扫描，支持 A 股与 ETF
- **多 LLM AI 交易员** — 6 家 provider 热切换，不仅看价格，还能结合日内分时形态（15 分钟轨迹）与中期趋势（5 日 K 线）给出买卖逻辑
- **本地数据清洗** — 内置 SQLite 引擎，实时存储快照，本地反向合成「真·3 分钟涨速」与「量比」，比收费软件更灵敏
- **飞书卡片推送** — 触发后通过飞书机器人发送富文本卡片，支持 Markdown 渲染 AI 分析报告
- **双入口界面** — PyQt6 桌面 GUI（实时行情表 / AI 预警面板 / 股票池配置 / 阈值调节 / 推送日志）+ Rich CLI 仪表盘
- **一键启动** — `start.sh` / `start.bat` 自动建 venv、装依赖、检查环境变量、拉起 GUI
- **隐私安全** — 所有 API Key 走环境变量，代码零硬编码

## 快速开始

### 1. 克隆与依赖

```bash
git clone git@github.com:chinayuren2022-2025/kimi_stock_advisor.git
cd kimi_stock_advisor
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# macOS / Linux
export QUANT_AI_PROVIDER="kimi"          # kimi|deepseek|qwen|glm|doubao|custom
export KIMI_API_KEY1="sk-..."            # 对应 provider 的 key，详见下方表格
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
export FEISHU_SECRET=""                 # 可选，飞书签名校验密钥（默认空串=不签名）

# Windows (PowerShell)
$env:QUANT_AI_PROVIDER="kimi"
$env:KIMI_API_KEY1="sk-..."
$env:FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

### 3. 启动

```bash
./start.sh                # 推荐：一键建 venv + 装依赖 + 起 GUI（macOS/Linux）
start.bat                 # Windows
python gui.py             # 直接起 GUI（已装好依赖）
python main.py            # 直接起 TUI（Rich Live 终端模式，无头/调试）
```

启动后前 3 分钟数据在积累中，随后指标开始跳动。

### 4. 配置股票池

在 GUI 的「股票池」标签页直接增删，或在 `config.py` 修改 `STOCK_POOL` 列表：

```python
STOCK_POOL = [
    '600519', # 贵州茅台
    '513180', # 恒生科技ETF
    '300059', # 东方财富
]
```

阈值可在 GUI「参数」标签页实时调节，或改 `config.py` 中的 `RISE_SPEED_THRESHOLD` 等。

## AI Provider 切换

6 家全部走 OpenAI 兼容接口，`openai` SDK 一套代码通吃。GUI 顶部下拉框可运行时热切换，无需重启。

| Provider | `QUANT_AI_PROVIDER` | key 环境变量 | 默认 model |
|---|---|---|---|
| Kimi (Moonshot) | `kimi` | `KIMI_API_KEY1` | `kimi-k2.5` |
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| 通义千问 | `qwen` | `QWEN_API_KEY` | `qwen-plus` |
| 智谱 GLM | `glm` | `GLM_API_KEY` | `glm-4-flash` |
| 豆包 | `doubao` | `DOUBAO_API_KEY` | `ep-xxx`（需改 endpoint id） |
| 自定义 | `custom` | `AI_API_KEY` | 由 `AI_MODEL` env 指定 |

**env 覆盖**：`AI_MODEL` 覆盖默认 model，`AI_BASE_URL` 覆盖 base_url（custom 必填）。

**key 校验规则**（按 provider 不同）：kimi/deepseek/qwen 要求 `sk-` 前缀；glm 要求含 `.`（id.secret 格式）；doubao/custom 非空即可。

## 架构流程

```
EasyQuotation(新浪) ──fetch──▶ SQLite 快照
                                │
                          DB 回溯计算
                                ▼
                     涨速 / 量比 / 分时趋势
                                │
                          策略引擎检测
                                ▼
                    🚀火箭发射 / 🌊高台跳水
                                │
                      AI 交易员分析 (多 LLM)
                                ▼
                       飞书 Webhook 推送
```

1. **Fetch** — 启动时预加载 AkShare 日线；运行时高频拉取 EasyQuotation 实时快照
2. **Store** — Tick 数据存入本地 `quant_data.db`（非交易时间跳过）
3. **Enrich** — 从 DB 回溯计算衍生指标（涨速、量比、分时趋势串）
4. **Detect** — 策略引擎匹配模式（如：涨速 > 1.0% 且 量比 > 1.5）
5. **Analyze** — 触发后组装 Prompt → 请求 AI（Kimi/DeepSeek/...）
6. **Notify** — AI 返回结论 → 飞书 Webhook 推送

## 策略说明

内置两套核心策略（可在 `config.py` 或 GUI 参数页调整）：

| 策略 | 触发条件（默认） | 逻辑 |
|---|---|---|
| **🚀 火箭发射** | 3 分钟涨速 > 1.0% **且** 量比 > 1.5 | 捕捉主力资金点火拉升的瞬间，结合量能确认真伪 |
| **🌊 高台跳水** | 3 分钟跌速 < -1.0% | 预警盘中急杀，提示止盈或止损风险 |

系统自动计算「市场情绪」（监控池平均涨跌幅），作为 AI 判断的宏观参考。

## 目录结构

```
kimi_stock_advisor/
├── gui.py              # PyQt6 GUI 入口（5 标签页）
├── main.py             # Rich TUI 入口（薄包装层）
├── engine.py           # 监控核心：MonitorEngine，TUI/GUI 共用
├── ai_provider.py      # 多 LLM provider 预设与解析
├── kimi_advisor.py     # AI 顾问（通用 AIAdvisor 类）
├── data_feeder.py      # 行情获取（EasyQuotation + AkShare）
├── database.py         # SQLite 存储与指标计算
├── notification.py     # 飞书消息推送
├── dashboard.py        # Rich 终端 UI 组件
├── config.py           # 配置（股票池、阈值、env 读取）
├── test_feed_all_data.py  # 单元测试
├── start.sh / start.bat   # 一键启动脚本
└── requirements.txt
```

## 测试

```bash
python -m unittest test_feed_all_data
```

测试通过 mock 屏蔽 easyquotation/akshare 外部依赖，无需真实网络。

## 贡献

欢迎提交 Issue 或 Pull Request！如果有更好的 prompt 策略或新的数据源接口，请随时分享。