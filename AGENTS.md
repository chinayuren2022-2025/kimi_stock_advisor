# AGENTS.md

A 股实时量化监控系统：Easyquotation 行情 → SQLite 派生指标 → Kimi (Moonshot) 分析 → 飞书推送。Python 3.10+。

## 运行

```bash
pip install easyquotation akshare rich openai requests pandas
export KIMI_API_KEY1="sk-..."        # 注意：config.py 读 KIMI_API_KEY1，不是 KIMI_API_KEY（readme 写错了）
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
export FEISHU_SECRET=""             # 可选
python main.py                      # 入口，直接在仓库根目录运行
```

- 仓库根目录即包根：`__init__.py` 存在，模块既支持 `python -m quant_local.main`（需父目录名为 `quant_local`），也支持 `python main.py`。当前下载文件夹名为 `kimi_stock_advisor-main`，直接 `python main.py` 即可；`python -m quant_local.main` 需把目录重命名为 `quant_local` 或从父目录运行。
- 交易时间外自动跳过 DB 存储，循环降为 60s；启动会预拉全 A 股 meta 表（首次较慢）。

## 测试

```bash
python -m unittest test_feed_all_data        # 唯一单测，mock easyquotation/akshare
python verify_data_feeder.py                  # 手动联调，需真实网络（会打实盘行情源）
```

测试通过 `sys.modules['easyquotation'] = MagicMock()` 屏蔽外部依赖，不要装真库到测试环境，否则 mock 失效逻辑会被绕过。

## 关键架构事实

- `config.py` 在 import 时强制 `os.environ.pop` 清掉 `http_proxy/https_proxy`：在有系统代理但 VPN 关闭时会触发 `RemoteDisconnected`。改网络相关 bug 前注意这点。
- `data_feeder.py` 顶部 `quotation_engine = easyquotation.use('sina')` 是模块级全局，import 即建连；`verify_data_feeder.py` 依赖它能从 `quant_local` 包路径导入。
- Sina 字段语义反直觉：`turnover`=成交量(股)，`volume`=成交额(元)。`feed_all_data` 里据此算 VWAP，改字段映射时别按字面意思。
- 涨速/量比的真值来自 `database.get_stock_history_stats`（本地 DB 回溯），不是 `data_feeder` 快照里的初值（量比默认 1.0）。`main.py` 会在 `check_triggers` 前把 DB 值注入 `snapshot['speed_3min_db']` / `snapshot['量比']`。
- Model 3「暗流涌动」在 `main.py` 已注释禁用，依赖净流入数据源（当前恒为 0）。
- `quant_data.db`（~1.8MB，随运行增长）和 `quant_monitor.log` 是运行产物，已加 `.gitignore`。

## 约定

- 所有模块用 `try: from . import x / except ImportError: import x` 兼容包内/直接运行两种模式，新增模块沿用此模式。
- API Key 走环境变量，零硬编码；`config.py` 的 `KIMI_API_KEY = os.getenv("KIMI_API_KEY1", "")`（变量名带 `1`）。
- Kimi 模型 ID 硬编码为 `kimi-k2.5`（`kimi_advisor.py`），更新模型需改源码。
- 代码注释与日志中英混用，沿用即可。