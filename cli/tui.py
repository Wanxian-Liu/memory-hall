"""
记忆殿堂v2.0 - TUI组件库
提供表格渲染、进度条、颜色输出、分页显示等组件
"""

import sys
import shutil
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

# ============== 颜色输出 ==============

class Colors:
    """ANSI颜色码"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # 前景色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # 亮色
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    # 背景色
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


def colorize(text: str, fg: str = "", bg: str = "", bold: bool = False, dim: bool = False) -> str:
    """给文本添加颜色
    
    Args:
        text: 要着色的文本
        fg: 前景色 (如 Colors.RED)
        bg: 背景色
        bold: 是否加粗
        dim: 是否变暗
    
    Returns:
        着色后的文本
    """
    codes = []
    if bold:
        codes.append(Colors.BOLD)
    if dim:
        codes.append(Colors.DIM)
    if fg:
        codes.append(fg)
    if bg:
        codes.append(bg)
    
    if codes:
        return "".join(codes) + text + Colors.RESET
    return text


def has_color_support() -> bool:
    """检测终端是否支持颜色"""
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


# ============== 表格渲染 ==============

@dataclass
class Column:
    """表格列定义"""
    header: str
    key: str
    width: Optional[int] = None
    align: str = "left"  # left, center, right
    color: str = ""


class Table:
    """终端表格渲染器"""
    
    def __init__(self, columns: List[Column], title: str = ""):
        self.columns = columns
        self.title = title
        self.rows: List[Dict[str, Any]] = []
        self._col_widths: Dict[str, int] = {}
    
    def add_row(self, row: Dict[str, Any]):
        """添加一行数据"""
        self.rows.append(row)
    
    def render(self, color: bool = True) -> str:
        """渲染表格并返回字符串"""
        if not color or not has_color_support():
            return self._render_plain()
        return self._render_colorful()
    
    def _calculate_widths(self) -> Dict[str, int]:
        """计算每列宽度"""
        widths = {}
        for col in self.columns:
            content_width = len(col.header)
            for row in self.rows:
                val = str(row.get(col.key, ""))
                content_width = max(content_width, len(val))
            if col.width:
                widths[col.key] = min(col.width, content_width)
            else:
                widths[col.key] = content_width
        self._col_widths = widths
        return widths
    
    def _render_plain(self) -> str:
        """渲染纯文本表格"""
        widths = self._calculate_widths()
        lines = []
        
        # 表头
        header_cells = []
        for col in self.columns:
            cell = col.header.ljust(widths[col.key])
            header_cells.append(cell)
        lines.append(" | ".join(header_cells))
        
        # 分隔线
        sep_cells = []
        for col in self.columns:
            sep_cells.append("-" * widths[col.key])
        lines.append("-+-".join(sep_cells))
        
        # 数据行
        for row in self.rows:
            row_cells = []
            for col in self.columns:
                val = str(row.get(col.key, ""))
                if col.align == "right":
                    cell = val.rjust(widths[col.key])
                elif col.align == "center":
                    cell = val.center(widths[col.key])
                else:
                    cell = val.ljust(widths[col.key])
                row_cells.append(cell)
            lines.append(" | ".join(row_cells))
        
        return "\n".join(lines)
    
    def _render_colorful(self) -> str:
        """渲染彩色表格"""
        widths = self._calculate_widths()
        lines = []
        
        # 标题
        if self.title:
            total_width = sum(widths.values()) + len(widths) * 3 - 1
            title_line = colorize(f" {self.title} ", fg=Colors.BG_BLUE, bold=True)
            lines.append(title_line.center(total_width + 4))
        
        # 表头
        header_cells = []
        for col in self.columns:
            cell = col.header.ljust(widths[col.key])
            header_cells.append(colorize(cell, fg=Colors.CYAN, bold=True))
        lines.append(" │ ".join(header_cells))
        
        # 分隔线
        sep_cells = []
        for col in self.columns:
            sep_cells.append(colorize("─" * widths[col.key], fg=Colors.DIM))
        lines.append("─┼─".join(sep_cells))
        
        # 数据行
        for i, row in enumerate(self.rows):
            row_cells = []
            for col in self.columns:
                val = str(row.get(col.key, ""))
                if col.align == "right":
                    cell = val.rjust(widths[col.key])
                elif col.align == "center":
                    cell = val.center(widths[col.key])
                else:
                    cell = val.ljust(widths[col.key])
                # 交替行颜色
                if i % 2 == 0:
                    row_cells.append(colorize(cell, fg=Colors.WHITE))
                else:
                    row_cells.append(colorize(cell, fg=Colors.BRIGHT_BLACK))
            lines.append(" │ ".join(row_cells))
        
        return "\n".join(lines)
    
    def print(self):
        """直接打印表格"""
        print(self.render())


# ============== 进度条 ==============

class ProgressBar:
    """终端进度条"""
    
    def __init__(
        self,
        total: int,
        prefix: str = "",
        width: int = 40,
        show_percent: bool = True,
        show_count: bool = True,
        color: str = Colors.GREEN
    ):
        self.total = total
        self.prefix = prefix
        self.width = width
        self.show_percent = show_percent
        self.show_count = show_count
        self.color = color
        self.current = 0
        self._displayed = False
    
    def update(self, current: Optional[int] = None, increment: int = 1):
        """更新进度
        
        Args:
            current: 直接设置当前值
            increment: 增量（当current=None时使用）
        """
        if current is not None:
            self.current = current
        else:
            self.current += increment
        
        self.current = min(self.current, self.total)
        self._render()
    
    def _render(self):
        """渲染进度条"""
        # 计算进度
        if self.total == 0:
            percent = 100
            filled = self.width
        else:
            percent = int(100 * self.current / self.total)
            filled = int(self.width * self.current / self.total)
        
        empty = self.width - filled
        
        # 构建显示字符串
        parts = []
        
        if self.prefix:
            parts.append(self.prefix)
        
        # 进度条主体
        bar = (
            colorize("█" * filled, fg=self.color) +
            colorize("░" * empty, fg=Colors.DIM)
        )
        parts.append(f"[{bar}]")
        
        # 百分比
        if self.show_percent:
            parts.append(f"{percent}%")
        
        # 计数
        if self.show_count:
            parts.append(f"{self.current}/{self.total}")
        
        # 输出
        line = " ".join(parts)
        sys.stdout.write("\r" + line)
        sys.stdout.flush()
        self._displayed = True
    
    def finish(self, message: str = "完成!"):
        """完成进度条"""
        self.current = self.total
        self._render()
        suffix = colorize(f" {message}", fg=Colors.GREEN, bold=True)
        print(suffix)


class Spinner:
    """旋转加载动画"""
    
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    def __init__(self, message: str = "加载中"):
        self.message = message
        self.current = 0
        self._running = False
    
    def update(self):
        """更新一帧"""
        frame = self.FRAMES[self.current % len(self.FRAMES)]
        sys.stdout.write(f"\r{frame} {self.message}...")
        sys.stdout.flush()
        self.current += 1
    
    def start(self):
        """开始旋转"""
        import threading
        self._running = True
        
        def spin():
            while self._running:
                self.update()
                import time
                time.sleep(0.1)
        
        self._thread = threading.Thread(target=spin, daemon=True)
        self._thread.start()
    
    def stop(self, message: str = "完成"):
        """停止旋转"""
        self._running = False
        print(f"\r{colorize('✓', fg=Colors.GREEN, bold=True)} {message}")


# ============== 分页显示 ==============

class Pager:
    """终端分页器"""
    
    def __init__(
        self,
        items: List[Any],
        page_size: int = 20,
        formatter: Optional[Callable[[Any], str]] = None
    ):
        self.items = items
        self.page_size = page_size
        self.formatter = formatter or (lambda x: str(x))
        self.total_pages = max(1, (len(items) + page_size - 1) // page_size)
        self.current_page = 0
    
    def get_page(self, page: int) -> List[str]:
        """获取指定页的内容"""
        if page < 0:
            page = 0
        if page >= self.total_pages:
            page = self.total_pages - 1
        
        start = page * self.page_size
        end = min(start + self.page_size, len(self.items))
        
        return [self.formatter(item) for item in self.items[start:end]]
    
    def display_page(self, page: int):
        """显示指定页"""
        self.current_page = page
        lines = self.get_page(page)
        
        # 清屏并显示
        self._clear()
        
        # 页眉
        header = colorize(
            f" 第 {page + 1}/{self.total_pages} 页 ",
            fg=Colors.CYAN, bold=True
        )
        print(header)
        print()
        
        # 内容
        for line in lines:
            print(line)
        
        print()
        self._print_nav(page)
    
    def _print_nav(self, page: int):
        """打印导航"""
        nav_parts = []
        
        # 首页
        if page > 0:
            nav_parts.append(colorize("[H]首页", fg=Colors.GREEN))
        
        # 上一页
        if page > 0:
            nav_parts.append(colorize("[P]上一页", fg=Colors.YELLOW))
        
        # 下一页
        if page < self.total_pages - 1:
            nav_parts.append(colorize("[N]下一页", fg=Colors.YELLOW))
        
        # 末页
        if page < self.total_pages - 1:
            nav_parts.append(colorize("[L]末页", fg=Colors.GREEN))
        
        # 退出
        nav_parts.append(colorize("[Q]退出", fg=Colors.RED))
        
        print("  ".join(nav_parts))
    
    def _clear(self):
        """清屏"""
        print("\033[2J\033[H", end="")
    
    def browse(self):
        """交互式浏览"""
        import tty
        import termios
        
        page = 0
        self.display_page(page)
        
        try:
            while True:
                key = self._get_key()
                
                if key.lower() == 'q':
                    break
                elif key.lower() == 'h':
                    page = 0
                elif key.lower() == 'l':
                    page = self.total_pages - 1
                elif key.lower() == 'p' or key == '\x1b[A':  # 上箭头
                    page = max(0, page - 1)
                elif key.lower() == 'n' or key == '\x1b[B':  # 下箭头
                    page = min(self.total_pages - 1, page + 1)
                elif key == '\x03':  # Ctrl+C
                    break
                
                self.display_page(page)
                
        finally:
            self._clear()
            print(f"共 {len(self.items)} 条记录")
    
    def _get_key(self) -> str:
        """获取单个按键"""
        import tty
        import termios
        import sys
        
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        
        return ch


# ============== 便捷函数 ==============

def print_header(text: str, color: str = Colors.CYAN):
    """打印加粗标题"""
    line = "=" * (shutil.get_terminal_size().columns - 2)
    print(colorize(line, fg=color, dim=True))
    print(colorize(f" {text} ", fg=color, bold=True))
    print(colorize(line, fg=color, dim=True))


def print_success(text: str):
    """打印成功消息"""
    print(colorize(f"✓ {text}", fg=Colors.GREEN))


def print_error(text: str):
    """打印错误消息"""
    print(colorize(f"✗ {text}", fg=Colors.RED, bold=True))


def print_warning(text: str):
    """打印警告消息"""
    print(colorize(f"⚠ {text}", fg=Colors.YELLOW))


def print_info(text: str):
    """打印信息消息"""
    print(colorize(f"ℹ {text}", fg=Colors.BLUE))


def confirm(prompt: str, default: bool = False) -> bool:
    """确认提示
    
    Args:
        prompt: 提示文本
        default: 默认值
    
    Returns:
        用户选择
    """
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        response = input(colorize(prompt + suffix, fg=Colors.CYAN)).strip().lower()
        
        if not response:
            return default
        
        if response in ('y', 'yes'):
            return True
        elif response in ('n', 'no'):
            return False
        
        print("请输入 y 或 n")


def input_with_default(prompt: str, default: str) -> str:
    """带默认值的输入"""
    response = input(colorize(f"{prompt} [{default}]: ", fg=Colors.CYAN)).strip()
    return response or default


# ============== 任务列表视图 ==============

class TaskListView:
    """任务列表视图 - 用于TUI显示任务列表"""
    
    STATUS_COLORS = {
        "pending": Colors.YELLOW,
        "running": Colors.CYAN,
        "completed": Colors.GREEN,
        "failed": Colors.RED,
        "cancelled": Colors.BRIGHT_BLACK,
        "timeout": Colors.MAGENTA,
        "circuit_open": Colors.BRIGHT_RED,
    }
    
    def __init__(self, tasks: List[Dict[str, Any]], title: str = "任务列表"):
        self.tasks = tasks
        self.title = title
    
    def render(self, color: bool = True) -> str:
        """渲染任务列表"""
        if not self.tasks:
            return colorize("没有任务", fg=Colors.DIM) if color else "没有任务"
        
        lines = []
        
        # 标题
        if color:
            lines.append(colorize(f"\n {self.title} ", fg=Colors.BG_BLUE, bold=True))
        else:
            lines.append(f"\n{self.title}")
        
        # 表头
        header = f"  {'ID':<8} {'名称':<20} {'状态':<12} {'阶段':<12} {'更新时间':<20}"
        lines.append(colorize(header, fg=Colors.CYAN, bold=True) if color else header)
        lines.append(colorize("─" * 76, fg=Colors.DIM) if color else "─" * 76)
        
        # 任务行
        for i, task in enumerate(self.tasks):
            task_id = task.get("task_id", "")[:8]
            name = task.get("name", "")[:18]
            status = task.get("status", "unknown")
            phase = task.get("phase", "unknown")
            
            # 格式化时间
            import time
            updated = task.get("updated_at", 0)
            if updated:
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(updated))
            else:
                time_str = "-"
            
            # 状态颜色
            status_color = self.STATUS_COLORS.get(status, Colors.WHITE)
            
            row = f"  {task_id:<8} {name:<20} "
            if color:
                row += colorize(f"{status:<12}", fg=status_color, bold=True)
                row += f" {phase:<12} {time_str}"
                if i % 2 == 0:
                    row = colorize(row, fg=Colors.WHITE)
                else:
                    row = colorize(row, fg=Colors.BRIGHT_BLACK)
            else:
                row += f"{status:<12} {phase:<12} {time_str}"
            
            lines.append(row)
        
        # 底部统计
        total = len(self.tasks)
        by_status = {}
        for t in self.tasks:
            s = t.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
        
        stats_parts = [f"总计: {total}"]
        for s, count in by_status.items():
            stats_parts.append(f"{s}: {count}")
        
        stats_line = " | ".join(stats_parts)
        lines.append(colorize("─" * 76, fg=Colors.DIM) if color else "─" * 76)
        lines.append(colorize(stats_line, fg=Colors.DIM) if color else stats_line)
        
        return "\n".join(lines)
    
    def print(self):
        """直接打印任务列表"""
        print(self.render())


# ============== 导出 ==============

__all__ = [
    'Colors', 'colorize', 'has_color_support',
    'Column', 'Table',
    'ProgressBar', 'Spinner',
    'Pager',
    'print_header', 'print_success', 'print_error', 'print_warning', 'print_info',
    'confirm', 'input_with_default',
    'TaskListView'
]
