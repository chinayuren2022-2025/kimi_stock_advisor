"""
PyQt6 GUI 入口：6 Tab 界面，QTimer + QThread 驱动 engine.MonitorEngine。
启动: python gui.py  或  ./start.sh
配置持久化: ~/.quant_local_config.json (settings.py)
"""
import sys
import os
import logging
from datetime import datetime

# 必须在创建 QApplication 前 import config（清代理副作用）
try:
    from . import config
except ImportError:
    import config

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QLabel,
    QListWidget, QLineEdit, QFormLayout, QPlainTextEdit, QTextEdit,
    QSpinBox, QDoubleSpinBox, QMessageBox, QSplitter, QComboBox,
    QGroupBox, QGridLayout
)
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QTextCursor

try:
    from .engine import MonitorEngine, is_trading_time
    from . import ai_provider
    from . import settings
    from . import notification
except ImportError:
    from engine import MonitorEngine, is_trading_time
    import ai_provider
    import settings
    import notification

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('quant_monitor.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


# =========================================================================
# 工作线程：跑 engine.cycle()，避免 AI API 阻塞 UI
# =========================================================================
class MonitorWorker(QThread):
    cycle_done = pyqtSignal(list, list, str)   # rows, alerts, status
    log = pyqtSignal(str)

    def __init__(self, engine: MonitorEngine):
        super().__init__()
        self.engine = engine

    def run(self):
        try:
            rows, alerts, status = self.engine.cycle()
            self.cycle_done.emit(rows, alerts, status)
        except Exception as e:
            logger.error(f"Worker cycle failed: {e}")
            self.cycle_done.emit([], [], f'error:{e}')


# =========================================================================
# Tab 1: 实时行情
# =========================================================================
class MarketTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 顶部控制栏
        bar = QHBoxLayout()
        self.status_label = QLabel("⏹ 未启动")
        self.sentiment_label = QLabel("市场情绪: --")

        # AI Provider 快捷切换区
        self.provider_label = QLabel("AI:")
        self.provider_combo = QComboBox()
        for key, name in ai_provider.get_provider_list():
            self.provider_combo.addItem(f"{name} ({key})", key)

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("模型 (留空用预设)")
        self.model_input.setMaximumWidth(160)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("API Key (留空走已保存配置)")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setMaximumWidth(200)

        self.btn_apply_provider = QPushButton("快捷切换")
        self.btn_start = QPushButton("▶ 启动监控")
        self.btn_stop = QPushButton("■ 停止")
        self.btn_stop.setEnabled(False)

        bar.addWidget(self.status_label)
        bar.addWidget(self.sentiment_label)
        bar.addStretch()
        bar.addWidget(self.provider_label)
        bar.addWidget(self.provider_combo)
        bar.addWidget(self.model_input)
        bar.addWidget(self.key_input)
        bar.addWidget(self.btn_apply_provider)
        bar.addWidget(self.btn_start)
        bar.addWidget(self.btn_stop)
        layout.addLayout(bar)

        # 行情表
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            ["代码", "名称", "现价", "涨跌幅", "3分涨速", "量比", "委比", "最高", "最低", "状态"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def update_rows(self, rows):
        self.rows = rows
        self.table.setRowCount(len(rows))
        sentiment = 0.0
        valid = 0
        for r, item in enumerate(rows):
            code = item.get('code', '')
            name = item.get('name', 'N/A')
            price = item.get('price', 0)
            pct = item.get('pct_chg', 0)
            speed = item.get('speed', 0)
            vol_ratio = item.get('vol_ratio', 1.0)
            commit = item.get('commit_ratio', 0)
            high = item.get('high', 0)
            low = item.get('low', 0)
            status = item.get('status', '-')

            if pct != 0:
                sentiment += pct
                valid += 1

            cells = [
                code, name,
                f"{price:.2f}" if isinstance(price, (int, float)) else str(price),
                f"{pct:+.2f}%",
                f"{speed:+.2f}%",
                f"{vol_ratio:.2f}",
                f"{commit:+.2f}%",
                f"{high:.2f}",
                f"{low:.2f}",
                status,
            ]
            for c, text in enumerate(cells):
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c == 3:
                    if pct > 0:
                        cell.setForeground(QColor("#d32f2f"))
                    elif pct < 0:
                        cell.setForeground(QColor("#388e3c"))
                elif c == 4:
                    if speed > 1.0:
                        cell.setForeground(QColor("#d32f2f"))
                    elif speed < -1.0:
                        cell.setForeground(QColor("#388e3c"))
                if '🚀' in status or '🌊' in status:
                    cell.setBackground(QColor("#fff9c4"))
                self.table.setItem(r, c, cell)

        if valid > 0:
            self.sentiment_label.setText(f"市场情绪: {sentiment/valid:+.2f}%")
        else:
            self.sentiment_label.setText("市场情绪: --")

    def fill_provider_bar(self, cfg: dict):
        """从配置填充顶部快捷栏（启动时调用）。"""
        provider = cfg.get('ai_provider', 'kimi')
        idx = self.provider_combo.findData(provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        model = cfg.get('ai_model', '')
        if model and model != 'ep-xxx':
            self.model_input.setText(model)
        key = cfg.get('ai_api_key', '')
        if key:
            self.key_input.setText(key)


# =========================================================================
# Tab 2: AI 预警
# =========================================================================
class AlertsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._show_detail)
        splitter.addWidget(self.list)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("选中左侧预警以查看 AI 分析结果")
        splitter.addWidget(self.detail)

        splitter.setSizes([300, 500])
        layout.addWidget(splitter)
        self.records = []

    def add_alert(self, alert: dict):
        ts = alert.get('time', '')
        name = alert.get('name', '')
        atype = alert.get('type', '')
        self.records.append(alert)
        self.list.insertItem(0, f"[{ts}] {name} {atype}")
        self.list.setCurrentRow(0)

    def _show_detail(self, row):
        if row < 0 or row >= len(self.records):
            return
        idx = len(self.records) - 1 - row
        if idx < 0 or idx >= len(self.records):
            return
        a = self.records[idx]
        ind = a.get('indicators', {})
        text = (
            f"<b>时间:</b> {a.get('time','')}<br>"
            f"<b>股票:</b> {a.get('name','')} ({a.get('symbol','')})<br>"
            f"<b>类型:</b> {a.get('type','')}<br>"
            f"<b>触发逻辑:</b> {ind.get('logic_desc','')}<br>"
            f"<b>涨速:</b> {ind.get('speed_3min',0):.2f}% | "
            f"<b>量比:</b> {ind.get('vol_ratio',0)}<br>"
            f"<b>飞书推送:</b> {'✅ 已推送' if a.get('pushed') else '❌ 未推送'}<br>"
            f"<hr><pre>{a.get('ai_response','无响应')}</pre>"
        )
        self.detail.setHtml(text)


# =========================================================================
# Tab 3: 股票池配置
# =========================================================================
class StockPoolTab(QWidget):
    pool_changed = pyqtSignal(list)

    def __init__(self, engine: MonitorEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("监控股票池 (6 位代码，如 600519 / 000001 / 513180)"))

        self.list = QListWidget()
        layout.addWidget(self.list)

        edit_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入股票代码后回车或点添加")
        self.input.returnPressed.connect(self._add)
        btn_add = QPushButton("添加")
        btn_add.clicked.connect(self._add)
        btn_del = QPushButton("删除选中")
        btn_del.clicked.connect(self._del)
        edit_row.addWidget(self.input)
        edit_row.addWidget(btn_add)
        edit_row.addWidget(btn_del)
        layout.addLayout(edit_row)

        btn_apply = QPushButton("应用 (写入运行时引擎)")
        btn_apply.clicked.connect(self._apply)
        layout.addWidget(btn_apply)

    def _load(self):
        self.list.clear()
        for code in self.engine.stock_pool:
            self.list.addItem(code)

    def reload_from_engine(self):
        self._load()

    def _add(self):
        code = self.input.text().strip()
        if not code:
            return
        if code in [self.list.item(i).text() for i in range(self.list.count())]:
            return
        self.list.addItem(code)
        self.input.clear()

    def _del(self):
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))

    def _apply(self):
        pool = [self.list.item(i).text().strip() for i in range(self.list.count())]
        self.engine.set_stock_pool(pool)
        self.pool_changed.emit(pool)
        QMessageBox.information(self, "已应用", f"股票池已更新为 {len(pool)} 只")


# =========================================================================
# Tab 4: 配置中心 (AI + 飞书 + 阈值 + 持久化)
# =========================================================================
class ConfigTab(QWidget):
    config_saved = pyqtSignal(dict)   # 保存成功后发出

    def __init__(self, engine: MonitorEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._build_ui()
        self._load_from_engine()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- AI Provider 区 ----
        ai_group = QGroupBox("AI Provider")
        ai_layout = QGridLayout(ai_group)

        ai_layout.addWidget(QLabel("Provider:"), 0, 0)
        self.provider_combo = QComboBox()
        for key, name in ai_provider.get_provider_list():
            self.provider_combo.addItem(f"{name} ({key})", key)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        ai_layout.addWidget(self.provider_combo, 0, 1)

        ai_layout.addWidget(QLabel("Model:"), 1, 0)
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("留空用预设默认 model")
        ai_layout.addWidget(self.model_input, 1, 1)

        ai_layout.addWidget(QLabel("API Key:"), 2, 0)
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("sk-... 或对应 provider 的 key")
        ai_layout.addWidget(self.key_input, 2, 1)

        ai_layout.addWidget(QLabel("Base URL:"), 3, 0)
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("仅 custom 需填，其余留空用预设")
        ai_layout.addWidget(self.base_url_input, 3, 1)

        layout.addWidget(ai_group)

        # ---- 飞书推送区 ----
        feishu_group = QGroupBox("飞书推送")
        feishu_layout = QGridLayout(feishu_group)

        feishu_layout.addWidget(QLabel("Webhook URL:"), 0, 0)
        self.feishu_webhook_input = QLineEdit()
        self.feishu_webhook_input.setPlaceholderText("https://open.feishu.cn/open-apis/bot/v2/hook/xxx")
        feishu_layout.addWidget(self.feishu_webhook_input, 0, 1, 1, 2)

        feishu_layout.addWidget(QLabel("签名密钥:"), 1, 0)
        self.feishu_secret_input = QLineEdit()
        self.feishu_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.feishu_secret_input.setPlaceholderText("可选，留空=不签名")
        feishu_layout.addWidget(self.feishu_secret_input, 1, 1)

        self.btn_test_push = QPushButton("🧪 测试推送")
        self.btn_test_push.clicked.connect(self._test_push)
        feishu_layout.addWidget(self.btn_test_push, 1, 2)

        layout.addWidget(feishu_group)

        # ---- 策略阈值区 ----
        threshold_group = QGroupBox("策略阈值")
        th_layout = QFormLayout(threshold_group)

        self.spin_rise = QDoubleSpinBox()
        self.spin_rise.setRange(-10, 10)
        self.spin_rise.setSingleStep(0.1)
        self.spin_rise.setDecimals(2)
        th_layout.addRow("火箭发射 涨速阈值 (%)", self.spin_rise)

        self.spin_vol = QDoubleSpinBox()
        self.spin_vol.setRange(0, 100)
        self.spin_vol.setSingleStep(0.1)
        self.spin_vol.setDecimals(2)
        th_layout.addRow("火箭发射 量比阈值", self.spin_vol)

        self.spin_drop = QDoubleSpinBox()
        self.spin_drop.setRange(-10, 10)
        self.spin_drop.setSingleStep(0.1)
        self.spin_drop.setDecimals(2)
        th_layout.addRow("高台跳水 跌速阈值 (%)", self.spin_drop)

        layout.addWidget(threshold_group)

        # ---- 按钮区 ----
        btn_row = QHBoxLayout()
        btn_save = QPushButton("💾 保存配置 (持久化到 ~/.quant_local_config.json)")
        btn_save.clicked.connect(self._save)
        btn_reset = QPushButton("恢复默认")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_reset)
        layout.addLayout(btn_row)

        layout.addStretch()

    def _load_from_engine(self):
        """从 engine 当前生效配置填充表单。"""
        cfg = self.engine.get_config()
        # AI
        provider = cfg.get('ai_provider', 'kimi')
        idx = self.provider_combo.findData(provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        self.model_input.setText(cfg.get('ai_model', '') or '')
        self.key_input.setText(cfg.get('ai_api_key', '') or '')
        self.base_url_input.setText(cfg.get('ai_base_url', '') or '')
        self._sync_base_url_visibility(provider)
        # 飞书
        self.feishu_webhook_input.setText(cfg.get('feishu_webhook_url', '') or '')
        self.feishu_secret_input.setText(cfg.get('feishu_secret', '') or '')
        # 阈值
        t = cfg.get('thresholds', {})
        self.spin_rise.setValue(t.get('rise_speed', 1.0))
        self.spin_vol.setValue(t.get('vol_ratio', 1.5))
        self.spin_drop.setValue(t.get('drop_speed', -1.0))

    def _on_provider_changed(self, _idx):
        provider = self.provider_combo.currentData()
        self._sync_base_url_visibility(provider)

    def _sync_base_url_visibility(self, provider: str):
        """custom provider 显示 base_url 输入框，其余隐藏（用预设）。"""
        is_custom = (provider == 'custom')
        self.base_url_input.setEnabled(is_custom)
        if not is_custom:
            self.base_url_input.clear()

    def _save(self):
        """保存配置：应用到 engine + 持久化到 JSON。"""
        provider = self.provider_combo.currentData()
        model = self.model_input.text().strip() or None
        key = self.key_input.text().strip() or None
        base_url = self.base_url_input.text().strip() or None
        webhook = self.feishu_webhook_input.text().strip()
        secret = self.feishu_secret_input.text().strip()
        thresholds = {
            'rise_speed': self.spin_rise.value(),
            'vol_ratio': self.spin_vol.value(),
            'drop_speed': self.spin_drop.value(),
        }

        # 应用到 engine
        self.engine.set_provider(provider=provider, api_key=key,
                                  model=model, base_url=base_url)
        self.engine.set_feishu(webhook_url=webhook, secret=secret)
        self.engine.set_thresholds(thresholds)

        # 持久化
        cfg = self.engine.save_runtime_config()
        self.config_saved.emit(cfg)
        QMessageBox.information(self, "已保存", "配置已保存并应用，下次启动自动加载。")

    def _reset_defaults(self):
        """恢复默认值（不自动保存，需用户点保存）。"""
        defaults = settings.get_default_config()
        provider = defaults['ai_provider']
        idx = self.provider_combo.findData(provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        self.model_input.clear()
        self.key_input.clear()
        self.base_url_input.clear()
        self.feishu_webhook_input.clear()
        self.feishu_secret_input.clear()
        t = defaults['thresholds']
        self.spin_rise.setValue(t['rise_speed'])
        self.spin_vol.setValue(t['vol_ratio'])
        self.spin_drop.setValue(t['drop_speed'])
        QMessageBox.information(self, "已恢复", "已填入默认值，点「保存配置」才会持久化。")

    def _test_push(self):
        """发送一条测试卡片到飞书群。"""
        webhook = self.feishu_webhook_input.text().strip()
        secret = self.feishu_secret_input.text().strip()
        if not webhook:
            QMessageBox.warning(self, "无法测试", "请先填写飞书 Webhook URL。")
            return
        # 临时配置并发送
        notification.configure_feishu(webhook_url=webhook, secret=secret)
        ok = notification.send_feishu("🧪 测试推送", "kimi_stock_advisor 配置成功！")
        if ok:
            QMessageBox.information(self, "成功", "测试卡片已发送到飞书群，请查收。")
        else:
            QMessageBox.warning(self, "失败", "推送失败，请检查 Webhook URL / 签名密钥。")

    def reload_from_engine(self):
        self._load_from_engine()


# =========================================================================
# Tab 5: 推送日志
# =========================================================================
class PushLogTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        layout.addWidget(self.log)
        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(self.log.clear)
        layout.addWidget(btn_clear)

    def append(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {msg}")


# =========================================================================
# 主窗口
# =========================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("A 股量化监控系统 (多 LLM)")
        self.resize(1280, 760)

        self.engine = MonitorEngine()
        self.worker = None
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)

        self._build_ui()
        self._wire_signals()
        self._init_from_config()

    def _build_ui(self):
        tabs = QTabWidget()
        self.market_tab = MarketTab()
        self.alerts_tab = AlertsTab()
        self.pool_tab = StockPoolTab(self.engine)
        self.config_tab = ConfigTab(self.engine)
        self.pushlog_tab = PushLogTab()

        tabs.addTab(self.market_tab, "实时行情")
        tabs.addTab(self.alerts_tab, "AI 预警")
        tabs.addTab(self.pool_tab, "股票池")
        tabs.addTab(self.config_tab, "配置中心")
        tabs.addTab(self.pushlog_tab, "推送日志")
        self.setCentralWidget(tabs)

    def _init_from_config(self):
        """启动时从已加载的 JSON 配置填充各 Tab。"""
        cfg = self.engine.get_config()
        self.market_tab.fill_provider_bar(cfg)
        self.config_tab.reload_from_engine()
        self.pool_tab.reload_from_engine()

    def _wire_signals(self):
        self.market_tab.btn_start.clicked.connect(self.start)
        self.market_tab.btn_stop.clicked.connect(self.stop)
        self.market_tab.btn_apply_provider.clicked.connect(self.quick_switch_provider)
        self.pool_tab.pool_changed.connect(
            lambda pool: self.pushlog_tab.append(f"股票池更新: {len(pool)} 只")
        )
        self.config_tab.config_saved.connect(self._on_config_saved)

    def _on_config_saved(self, cfg: dict):
        """配置中心保存后，同步顶部快捷栏与股票池 Tab。"""
        self.market_tab.fill_provider_bar(cfg)
        self.pool_tab.reload_from_engine()
        self.pushlog_tab.append(
            f"配置已保存: provider={cfg.get('ai_provider')} | "
            f"飞书={'✅' if cfg.get('feishu_webhook_url') else '❌'}"
        )

    def quick_switch_provider(self):
        """顶部快捷切换（不写 JSON，仅运行时生效）。"""
        provider = self.market_tab.provider_combo.currentData()
        model = self.market_tab.model_input.text().strip() or None
        key = self.market_tab.key_input.text().strip() or None
        self.engine.set_provider(provider=provider, api_key=key, model=model)
        p, base_url, m, _ = ai_provider.resolve(provider=provider,
                                                 api_key_override=key,
                                                 model_override=model)
        self.pushlog_tab.append(
            f"AI Provider 快捷切换 -> {p} | model={m} | base_url={base_url}"
        )
        # 同步配置中心 Tab
        self.config_tab.reload_from_engine()

    # ---- 启动 / 停动 ----
    def start(self):
        if not self.engine._initialized:
            self.pushlog_tab.append("正在初始化 DB 与日线历史 (首次较慢)...")
            QApplication.processEvents()
            self.engine.init(log_cb=self.pushlog_tab.append)
            self.pushlog_tab.append("初始化完成")
        self.market_tab.status_label.setText("▶ 监控中")
        self.market_tab.btn_start.setEnabled(False)
        self.market_tab.btn_stop.setEnabled(True)
        self._tick()
        self._schedule_next()

    def stop(self):
        self.timer.stop()
        if self.worker and self.worker.isRunning():
            self.worker.quit()
        self.market_tab.status_label.setText("⏹ 已停止")
        self.market_tab.btn_start.setEnabled(True)
        self.market_tab.btn_stop.setEnabled(False)
        self.pushlog_tab.append("监控已停止")

    def _schedule_next(self):
        interval = 10000 if is_trading_time() else 60000
        self.timer.start(interval)

    def _tick(self):
        if self.worker and self.worker.isRunning():
            return
        self.worker = MonitorWorker(self.engine)
        self.worker.cycle_done.connect(self._on_cycle_done)
        self.worker.log.connect(self.pushlog_tab.append)
        self.worker.start()

    def _on_cycle_done(self, rows, alerts, status):
        if status == 'fetch_failed':
            self.pushlog_tab.append("[Error] Fetch failed")
        elif status.startswith('error:'):
            self.pushlog_tab.append(f"[Error] {status}")
        else:
            self.market_tab.update_rows(rows)
            if not is_trading_time():
                self.pushlog_tab.append("⏸️ 非交易时间，暂停 DB 存储")
            for a in alerts:
                self.alerts_tab.add_alert(a)
                self.pushlog_tab.append(
                    f"🔥 预警: {a['type']} on {a['name']} | "
                    f"推送: {'✅' if a.get('pushed') else '❌'}"
                )
        self._schedule_next()

    def closeEvent(self, event):
        self.timer.stop()
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(3000)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()