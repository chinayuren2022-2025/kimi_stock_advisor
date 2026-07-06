"""
PyQt6 GUI 入口：5 Tab 界面，QTimer + QThread 驱动 engine.MonitorEngine。
启动: python gui.py  或  ./start.sh
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
    QSpinBox, QDoubleSpinBox, QMessageBox, QSplitter, QComboBox
)
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QTextCursor

try:
    from .engine import MonitorEngine, is_trading_time
    from . import ai_provider
except ImportError:
    from engine import MonitorEngine, is_trading_time
    import ai_provider

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
# 工作线程：跑 engine.cycle()，避免 Kimi API 阻塞 UI
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

        # AI Provider 切换区
        self.provider_label = QLabel("AI:")
        self.provider_combo = QComboBox()
        for key, name in ai_provider.get_provider_list():
            self.provider_combo.addItem(f"{name} ({key})", key)
        # 默认选当前 provider
        cur_provider = ai_provider.resolve()[0]
        idx = self.provider_combo.findData(cur_provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("模型 (留空用预设默认)")
        cur_model = ai_provider.resolve()[2]
        if cur_model and cur_model != 'ep-xxx':
            self.model_input.setText(cur_model)
        self.model_input.setMaximumWidth(160)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("API Key (留空走 env)")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setMaximumWidth(200)

        self.btn_apply_provider = QPushButton("应用 Provider")
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
                # 着色
                if c == 3:  # 涨跌幅
                    if pct > 0:
                        cell.setForeground(QColor("#d32f2f"))
                    elif pct < 0:
                        cell.setForeground(QColor("#388e3c"))
                elif c == 4:  # 涨速
                    if speed > 1.0:
                        cell.setForeground(QColor("#d32f2f"))
                    elif speed < -1.0:
                        cell.setForeground(QColor("#388e3c"))
                # 预警行高亮
                if '🚀' in status or '🌊' in status:
                    cell.setBackground(QColor("#fff9c4"))
                self.table.setItem(r, c, cell)

        if valid > 0:
            self.sentiment_label.setText(f"市场情绪: {sentiment/valid:+.2f}%")
        else:
            self.sentiment_label.setText("市场情绪: --")


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

        # 左: 触发列表
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._show_detail)
        splitter.addWidget(self.list)

        # 右: AI 分析结果
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("选中左侧预警以查看 Kimi 分析结果")
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
        # list 是倒序显示，records 是正序追加
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
    pool_changed = pyqtSignal(list)   # 应用时发出

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
# Tab 4: 参数
# =========================================================================
class ParamsTab(QWidget):
    thresholds_changed = pyqtSignal(dict)

    def __init__(self, engine: MonitorEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._build_ui()

    def _build_ui(self):
        layout = QFormLayout(self)
        t = self.engine.thresholds

        self.spin_rise = QDoubleSpinBox()
        self.spin_rise.setRange(-10, 10)
        self.spin_rise.setSingleStep(0.1)
        self.spin_rise.setDecimals(2)
        self.spin_rise.setValue(t.get('rise_speed', config.RISE_SPEED_THRESHOLD))
        layout.addRow("火箭发射 涨速阈值 (%)", self.spin_rise)

        self.spin_vol = QDoubleSpinBox()
        self.spin_vol.setRange(0, 100)
        self.spin_vol.setSingleStep(0.1)
        self.spin_vol.setDecimals(2)
        self.spin_vol.setValue(t.get('vol_ratio', config.VOL_RATIO_THRESHOLD))
        layout.addRow("火箭发射 量比阈值", self.spin_vol)

        self.spin_drop = QDoubleSpinBox()
        self.spin_drop.setRange(-10, 10)
        self.spin_drop.setSingleStep(0.1)
        self.spin_drop.setDecimals(2)
        self.spin_drop.setValue(t.get('drop_speed', config.DROP_SPEED_THRESHOLD))
        layout.addRow("高台跳水 跌速阈值 (%)", self.spin_drop)

        btn_apply = QPushButton("应用阈值")
        btn_apply.clicked.connect(self._apply)
        layout.addRow(btn_apply)

    def _apply(self):
        new = {
            'rise_speed': self.spin_rise.value(),
            'vol_ratio': self.spin_vol.value(),
            'drop_speed': self.spin_drop.value(),
        }
        self.engine.set_thresholds(new)
        self.thresholds_changed.emit(new)
        QMessageBox.information(self, "已应用", "阈值已更新，下一周期生效")


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

    def _build_ui(self):
        tabs = QTabWidget()
        self.market_tab = MarketTab()
        self.alerts_tab = AlertsTab()
        self.pool_tab = StockPoolTab(self.engine)
        self.params_tab = ParamsTab(self.engine)
        self.pushlog_tab = PushLogTab()

        tabs.addTab(self.market_tab, "实时行情")
        tabs.addTab(self.alerts_tab, "AI 预警")
        tabs.addTab(self.pool_tab, "股票池")
        tabs.addTab(self.params_tab, "参数")
        tabs.addTab(self.pushlog_tab, "推送日志")
        self.setCentralWidget(tabs)

    def _wire_signals(self):
        self.market_tab.btn_start.clicked.connect(self.start)
        self.market_tab.btn_stop.clicked.connect(self.stop)
        self.market_tab.btn_apply_provider.clicked.connect(self.apply_provider)
        self.pool_tab.pool_changed.connect(
            lambda pool: self.pushlog_tab.append(f"股票池更新: {len(pool)} 只")
        )
        self.params_tab.thresholds_changed.connect(
            lambda d: self.pushlog_tab.append(f"阈值更新: {d}")
        )

    def apply_provider(self):
        """应用 GUI 选择的 provider/model/key 到 engine。"""
        provider = self.market_tab.provider_combo.currentData()
        model = self.market_tab.model_input.text().strip() or None
        key = self.market_tab.key_input.text().strip() or None
        self.engine.set_provider(provider=provider, api_key=key, model=model)
        p, base_url, m, _ = ai_provider.resolve(provider=provider,
                                                 api_key_override=key,
                                                 model_override=model)
        self.pushlog_tab.append(
            f"AI Provider 切换 -> {p} | model={m} | base_url={base_url}"
        )

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
        self._tick()  # 立即跑一次
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
        # 交易时间 10s，非交易时间 60s
        interval = 10000 if is_trading_time() else 60000
        self.timer.start(interval)

    def _tick(self):
        if self.worker and self.worker.isRunning():
            return  # 上一周期还没跑完，跳过
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
        self._schedule_next()  # 重新调度（间隔可能因交易时段变化）

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