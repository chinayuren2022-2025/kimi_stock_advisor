# AGENTS.md

> 用户文档见 `readme.md`。本文件面向 AI 编程助手，记录代码层面易错事实。

A 股实时量化监控系统：Easyquotation 行情 → SQLite 派生指标 → 多 LLM 分析 → 飞书推送。Python 3.10+。双入口：PyQt6 GUI（`gui.py`）与 Rich TUI（`main.py`），共用 `engine.MonitorEngine`。支持 6 个 AI provider 切换（Kimi/DeepSeek/Qwen/GLM/豆包/自定义）。

## 运行

```bash
pip install -r requirements.txt          # 首次：easyquotation akshare rich openai requests pandas PyQt6
export QUANT_AI_PROVIDER="kimi"          # kimi|deepseek|qwen|glm|doubao|custom（默认 kimi）
export KIMI_API_KEY1="sk-..."            # 对应 provider 的 key 变量，详见下表
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
export FEISHU_SECRET=""                   # 可选；默认空串=不签名。旧版默认是空格会导致飞书校验失败
./start.sh                                # 推荐：一键建 venv + 装依赖 + 起 GUI（Windows 用 start.bat）
python gui.py                             # 直接起 GUI
python main.py                            # 直接起 TUI（Rich Live），无头/调试模式
```

### AI Provider 切换

| Provider | `QUANT_AI_PROVIDER` | key 环境变量 | 默认 model |
|---|---|---|---|
| Kimi (Moonshot) | `kimi` | `KIMI_API_KEY1` | `kimi-k2.5` |
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| 通义千问 | `qwen` | `QWEN_API_KEY` | `qwen-plus` |
| 智谱 GLM | `glm` | `GLM_API_KEY` | `glm-4-flash` |
| 豆包 | `doubao` | `DOUBAO_API_KEY` | `ep-xxx`（需改 endpoint id） |
| 自定义 | `custom` | `AI_API_KEY` | 由 `AI_MODEL` env 指定 |

- 6 家全部走 OpenAI 兼容接口，`openai` SDK 一套代码通吃，`ai_provider.py` 是唯一 provider 配置源。
- GUI 顶部下拉框可运行时切换 provider，无需重启；model 与 key 可在 GUI 临时覆盖（留空走 env）。
- env 覆盖：`AI_MODEL` 覆盖默认 model，`AI_BASE_URL` 覆盖 base_url（custom 必填）。
- key 校验按 provider 不同：kimi/deepseek/qwen 要求 `sk-` 前缀；glm 要求含 `.`（id.secret）；doubao/custom 非空即可。旧版只认 `sk-` 前缀会误判智谱/豆包无效。

- 仓库根目录即包根：`__init__.py` 存在，模块既支持 `python -m quant_local.main`（需父目录名为 `quant_local`），也支持直接 `python xxx.py`。当前下载文件夹名为 `kimi_stock_advisor-main`，直接运行即可；`python -m quant_local.xxx` 需把目录重命名为 `quant_local` 或从父目录运行。
- 交易时间外自动跳过 DB 存储，GUI QTimer 与 TUI 循环均降为 60s；启动会预拉全 A 股 meta 表（首次较慢）。
- 监控核心在 `engine.MonitorEngine`：`init()` 建库 + 预拉日线，`cycle()` 跑一个 fetch→enrich→detect→analyze→notify 周期，返回 `(rows, alerts, status)`。TUI 和 GUI 都只是它的视图层。

## 测试

```bash
python -m unittest test_feed_all_data     # 唯一单测，mock easyquotation/akshare
```

测试通过 `sys.modules['easyquotation'] = MagicMock()` 屏蔽外部依赖，不要装真库到测试环境，否则 mock 失效逻辑会被绕过。

## 关键架构事实

- `config.py` 在 import 时强制 `os.environ.pop` 清掉 `http_proxy/https_proxy`：在有系统代理但 VPN 关闭时会触发 `RemoteDisconnected`。改网络相关 bug 前注意这点。GUI import 链同样受影响。
- `data_feeder.py` 顶部 `quotation_engine = easyquotation.use('sina')` 是模块级全局，import 即建连；GUI/TUI 任一启动都会建连。
- Sina 字段语义反直觉：`turnover`=成交量(股)，`volume`=成交额(元)。`feed_all_data` 里据此算 VWAP，改字段映射时别按字面意思。
- 涨速/量比的真值来自 `database.get_stock_history_stats`（本地 DB 回溯），不是 `data_feeder` 快照里的初值（量比默认 1.0）。`engine.MonitorEngine.cycle()` 会在触发检测前把 DB 值注入 `snapshot['speed_3min_db']` / `snapshot['量比']`。
- Model 3「暗流涌动」在 `engine.py` 已注释禁用，依赖净流入数据源（当前恒为 0）。
- Kimi 模型 ID 硬编码为 `kimi-k2.5`（`ai_provider.py` 预设），`temperature=0.4`；更新模型/温度需改源码。
- `kimi_advisor.py` 实为通用 `AIAdvisor` 类，保留文件名与 `KimiAdvisor` 别名以兼容旧 import。`ai_provider.py` 是 provider 配置唯一来源。
- GUI 用 QThread 跑 `engine.cycle()` 避免 Kimi API 阻塞 UI；SQLite 连接在 `database.py` 内每次新建，不跨线程共享，符合线程安全。
- `quant_data.db`（~1.8MB，随运行增长）和 `quant_monitor.log` 是运行产物，已加 `.gitignore`；`.venv/` 同已忽略。

## 约定

- 所有模块用 `try: from . import x / except ImportError: import x` 兼容包内/直接运行两种模式，新增模块沿用此模式。
- API Key 走环境变量，零硬编码；`config.py` 的 `KIMI_API_KEY = os.getenv("KIMI_API_KEY1", "")`（变量名带 `1`）。
- `FEISHU_SECRET` 默认必须是空串 `""`，不能是空格——空格会让 `notification.py` 误判已配置签名密钥，导致飞书校验失败。
- 代码注释与日志中英混用，沿用即可。