from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.console import Console
from rich import box
from datetime import datetime
from typing import Dict, Any, List

class MonitorDashboard:
    def __init__(self, title="A-Share Quantitative Monitor"):
        self.console = Console()
        self.title = title
        self.layout = Layout()
        self.log_messages = []
        self.MAX_LOGS = 12

    def create_table(self, data_list: List[Dict[str, Any]]) -> Table:
        """Create the main monitoring table."""
        table = Table(title=f"{self.title} - {datetime.now().strftime('%H:%M:%S')}", box=box.ROUNDED)

        table.add_column("代码", style="cyan", no_wrap=True)
        table.add_column("名称", style="magenta")
        table.add_column("现价", justify="right")
        table.add_column("涨跌幅", justify="right")
        table.add_column("3分涨速", justify="right")  # New
        table.add_column("均价", justify="right")      # New
        table.add_column("委比", justify="right")      # New
        table.add_column("最高", justify="right")      # New
        table.add_column("最低", justify="right")      # New
        # table.add_column("量比", justify="right")   # Removed VolRatio as it's 1.0 currently
        table.add_column("状态", justify="center")

        for item in data_list:
            code = item.get('code', 'N/A')
            name = item.get('name', 'N/A')
            price = f"{item.get('price', 0):.2f}"
            pct = item.get('pct_chg', 0.0)
            
            speed = item.get('speed', 0.0)
            vwap = f"{item.get('avg_price', 0):.3f}"
            commit_ratio = item.get('commit_ratio', 0.0)
            high = f"{item.get('high', 0):.2f}"
            low = f"{item.get('low', 0):.2f}"
            
            status = item.get('status', '-')

            # Color coding for Change%
            if pct > 0:
                pct_str = f"[red]+{pct:.2f}%[/red]"
            elif pct < 0:
                pct_str = f"[green]{pct:.2f}%[/green]"
            else:
                pct_str = f"{pct:.2f}%"
                
            # Color coding for Speed
            if speed > 1.0:
                 speed_str = f"[red]↑{speed:.1f}%[/red]"
            elif speed < -1.0:
                 speed_str = f"[green]↓{speed:.1f}%[/green]"
            else:
                 speed_str = f"{speed:.1f}%"
            
            # Color coding for Commit Ratio
            if commit_ratio > 20:
                ratio_str = f"[red]{commit_ratio:+.2f}%[/red]"
            elif commit_ratio < -20:
                ratio_str = f"[green]{commit_ratio:+.2f}%[/green]"
            else:
                ratio_str = f"{commit_ratio:+.2f}%"
                
            # Highlight Status
            if '🚀' in status or '🌊' in status:
                 status = f"[bold yellow blink]{status}[/bold yellow blink]"
            elif 'Loading' in status:
                status = "[dim]Loading[/dim]"

            table.add_row(code, name, price, pct_str, speed_str, vwap, ratio_str, high, low, status)

        return table

    def generate_layout(self, data_list: List[Dict[str, Any]]) -> Layout:
        """
        Generate the Full Layout (Table + Log Panel).
        """
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=16)
        )
        
        # Body: Table
        self.layout["body"].update(self.create_table(data_list))
        
        # Footer: Logs
        log_text = "\n".join(self.log_messages[-self.MAX_LOGS:])
        self.layout["footer"].update(Panel(log_text, title="System Logs", border_style="blue"))
        
        return self.layout

    def add_log(self, message: str):
        """Add a log message to the footer."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_messages.append(f"[{timestamp}] {message}") 

# Global instance management helper if needed, but main.py will likely own the Live context.
