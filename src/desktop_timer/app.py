from __future__ import annotations

import sys
import time
import tkinter as tk
from datetime import datetime, timedelta

from .task_history import (
    CompletedTask,
    RunningTask,
    format_task_row,
    merge_into_completed,
)

TRANSPARENT = "#ff00ff"
BG_DARK = "#1c1a24"
BG_SURFACE = "#262430"
TEXT_PRIMARY = "#ede9e3"
TEXT_MUTED = "#7a7585"
ACCENT = "#f0a050"
GREEN = "#3dd68c"
RED = "#ef5350"
AMBER = "#f0c040"
BORDER = "#35323f"

RECEIPT_PAPER = "#f5f0e8"
RECEIPT_TEXT = "#2c2420"
RECEIPT_LINE = "#e0d8cc"
RECEIPT_MUTED = "#8a7e74"

BAR_WIDTH = 240
BAR_HEIGHT = 42
BAR_RADIUS = 10
CY = BAR_HEIGHT // 2

TASK_ROW_HEIGHT = 28

RECEIPT_TOP_OFFSET = 2
RECEIPT_HEADER_HEIGHT = 32
RECEIPT_ROW_HEIGHT = 20
RECEIPT_FOOTER = 10

ORB_SIZE = 56
DOCK_THRESHOLD = 12
CLICK_TOLERANCE = 5


class TimerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("桌面计时器")
        self.root.minsize(ORB_SIZE, ORB_SIZE)
        self.root.configure(bg=TRANSPARENT)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self._enable_transparency()

        self.running: list[RunningTask] = []
        self.completed_tasks: list[CompletedTask] = []
        self.tasks_expanded = False
        self.docked = False
        self.docked_side: str | None = None
        self.last_normal_pos: tuple[int, int] = (120, 90)
        self.drag_start_x = 0
        self.drag_start_y = 0
        self._press_root_x = 0
        self._press_root_y = 0
        self.tick_job: str | None = None

        self.task_var = tk.StringVar()

        self._build_ui()
        self._apply_geometry()
        self._draw_scene()
        self.root.after(50, self._enable_taskbar_visibility)
        self.root.bind("<Map>", self._on_window_map)

    def _enable_transparency(self) -> None:
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            self.root.configure(bg=BG_DARK)

    def _build_ui(self) -> None:
        self.canvas = tk.Canvas(
            self.root, width=BAR_WIDTH, height=BAR_HEIGHT,
            bg=TRANSPARENT, highlightthickness=0, bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag_window)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_release)

        self.task_entry = tk.Entry(
            self.canvas, textvariable=self.task_var,
            bd=0, relief="flat", bg=BG_SURFACE, fg=TEXT_PRIMARY,
            insertbackground=ACCENT, font=("Microsoft YaHei UI", 9), justify="center",
        )
        self.task_entry.bind("<Return>", lambda _e: self.start_task())
        self.entry_window = self.canvas.create_window(
            106, CY, window=self.task_entry, width=75, height=20,
        )

    # ── geometry ─────────────────────────────────────────

    def _compute_height(self) -> int:
        if self.docked:
            return ORB_SIZE
        total = BAR_HEIGHT + len(self.running) * TASK_ROW_HEIGHT
        if self.tasks_expanded:
            rows = len(self.completed_tasks) if self.completed_tasks else 1
            receipt_h = RECEIPT_HEADER_HEIGHT + rows * RECEIPT_ROW_HEIGHT + RECEIPT_FOOTER
            total += RECEIPT_TOP_OFFSET + receipt_h + 6
        return total

    def _apply_geometry(self) -> None:
        if self.docked:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            y = max(60, min(sh - ORB_SIZE - 60, self.last_normal_pos[1] + 40))
            x = 0 if self.docked_side == "left" else sw - ORB_SIZE
            self.root.geometry(f"{ORB_SIZE}x{ORB_SIZE}+{x}+{y}")
            self.canvas.config(width=ORB_SIZE, height=ORB_SIZE)
            return
        height = self._compute_height()
        x, y = self.last_normal_pos
        self.root.geometry(f"{BAR_WIDTH}x{height}+{x}+{y}")
        self.canvas.config(width=BAR_WIDTH, height=height)

    # ── drawing ──────────────────────────────────────────

    def _draw_scene(self) -> None:
        self.canvas.delete("drawn")
        if self.docked:
            self.canvas.itemconfigure(self.entry_window, state="hidden")
            self._draw_orb()
            return
        self.canvas.itemconfigure(self.entry_window, state="normal")
        self._draw_top_bar()
        self._draw_running_rows()
        if self.tasks_expanded:
            self._draw_receipt()
        self.canvas.tag_raise(self.entry_window)

    def _round_rect(self, x1: int, y1: int, x2: int, y2: int, r: int, **kw: object) -> int:
        pts = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def _draw_top_bar(self) -> None:
        self._round_rect(3, 3, BAR_WIDTH - 3, BAR_HEIGHT - 3, BAR_RADIUS,
                         fill=BG_DARK, outline=BORDER, width=1, tags="drawn")
        self._round_rect(52, 8, 160, BAR_HEIGHT - 8, 11,
                         fill=BG_SURFACE, outline=BORDER, width=1, tags="drawn")
        self._draw_top_controls()
        self._draw_task_toggle()

    def _draw_top_controls(self) -> None:
        c = self.canvas
        r = 6
        for cx, color, cmd in [(16, RED, self.root.destroy), (34, AMBER, self.minimize_window)]:
            dot = c.create_oval(cx - r, CY - r, cx + r, CY + r, fill=color, outline="", tags="drawn")
            c.tag_bind(dot, "<Button-1>", lambda _e, fn=cmd: fn())
            c.tag_bind(dot, "<Enter>", lambda _e: c.configure(cursor="hand2"))
            c.tag_bind(dot, "<Leave>", lambda _e: c.configure(cursor=""))

    def _draw_task_toggle(self) -> None:
        c = self.canvas
        count = len(self.completed_tasks)
        arrow = "▾" if self.tasks_expanded else "▸"
        label = f"{arrow}{count}"
        label_color = TEXT_PRIMARY if count or self.tasks_expanded else TEXT_MUTED
        text = c.create_text(
            200, CY, text=label, fill=label_color,
            font=("Consolas", 10, "bold"), tags="drawn",
        )
        hot = c.create_rectangle(178, 3, BAR_WIDTH - 3, BAR_HEIGHT - 3,
                                 fill="", outline="", tags="drawn")
        for it in (hot, text):
            c.tag_bind(it, "<Button-1>", self._toggle_tasks)
            c.tag_bind(it, "<Enter>", lambda _e: c.configure(cursor="hand2"))
            c.tag_bind(it, "<Leave>", lambda _e: c.configure(cursor=""))

    def _draw_running_rows(self) -> None:
        c = self.canvas
        for i, task in enumerate(self.running):
            y_base = BAR_HEIGHT + i * TASK_ROW_HEIGHT
            y_center = y_base + TASK_ROW_HEIGHT // 2

            self._round_rect(3, y_base + 2, BAR_WIDTH - 3, y_base + TASK_ROW_HEIGHT - 2, 8,
                             fill=BG_DARK, outline=BORDER, width=1, tags="drawn")

            dot_color = AMBER if task.state == "running" else GREEN
            c.create_oval(12 - 4, y_center - 4, 12 + 4, y_center + 4,
                          fill=dot_color, outline="", tags="drawn")

            name = task.name if len(task.name) <= 8 else task.name[:7] + "…"
            c.create_text(22, y_center, text=name, anchor="w",
                          fill=TEXT_PRIMARY, font=("Microsoft YaHei UI", 9), tags="drawn")

            elapsed = int(task.elapsed_seconds())
            hours, rem = divmod(elapsed, 3600)
            mins, secs = divmod(rem, 60)
            time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
            c.create_text(176, y_center, text=time_str, anchor="e",
                          fill=ACCENT, font=("Consolas", 10, "bold"), tags="drawn")

            self._draw_row_pause(task, 196, y_center)
            self._draw_row_done(task, 220, y_center)

    def _draw_row_pause(self, task: RunningTask, cx: int, cy: int) -> None:
        c = self.canvas
        r = 9
        items: list[int] = []
        items.append(c.create_oval(cx - r, cy - r, cx + r, cy + r,
                                   fill=BG_SURFACE, outline=BORDER, tags="drawn"))
        if task.state == "running":
            bw, bh, g = 2, 7, 2
            items.append(c.create_rectangle(cx - g - bw, cy - bh // 2, cx - g, cy + bh // 2,
                                            fill=TEXT_PRIMARY, outline="", tags="drawn"))
            items.append(c.create_rectangle(cx + g, cy - bh // 2, cx + g + bw, cy + bh // 2,
                                            fill=TEXT_PRIMARY, outline="", tags="drawn"))
        else:
            items.append(c.create_polygon(cx - 3, cy - 5, cx + 5, cy, cx - 3, cy + 5,
                                          fill=TEXT_PRIMARY, outline="", tags="drawn"))
        for it in items:
            c.tag_bind(it, "<Button-1>", lambda _e, t=task: self._toggle_task_pause(t))
            c.tag_bind(it, "<Enter>", lambda _e: c.configure(cursor="hand2"))
            c.tag_bind(it, "<Leave>", lambda _e: c.configure(cursor=""))

    def _draw_row_done(self, task: RunningTask, cx: int, cy: int) -> None:
        c = self.canvas
        r = 9
        items: list[int] = []
        items.append(c.create_oval(cx - r, cy - r, cx + r, cy + r,
                                   fill=GREEN, outline="", tags="drawn"))
        items.append(c.create_line(cx - 4, cy, cx - 1, cy + 3, cx + 5, cy - 4,
                                   fill=BG_DARK, width=2, tags="drawn"))
        for it in items:
            c.tag_bind(it, "<Button-1>", lambda _e, t=task: self._finish_task(t))
            c.tag_bind(it, "<Enter>", lambda _e: c.configure(cursor="hand2"))
            c.tag_bind(it, "<Leave>", lambda _e: c.configure(cursor=""))

    def _draw_receipt(self) -> None:
        c = self.canvas
        top = BAR_HEIGHT + len(self.running) * TASK_ROW_HEIGHT + RECEIPT_TOP_OFFSET
        left, right = 20, BAR_WIDTH - 20
        rows = len(self.completed_tasks) if self.completed_tasks else 1
        receipt_h = RECEIPT_HEADER_HEIGHT + rows * RECEIPT_ROW_HEIGHT + RECEIPT_FOOTER
        bottom = top + receipt_h
        tooth = 8

        pts: list[int] = [left, top, right, top, right, bottom - 4]
        x = right
        while x >= left:
            pts.extend([x, bottom + (4 if ((right - x) // tooth) % 2 else 0)])
            x -= tooth
        pts.extend([left, bottom - 4, left, top])
        c.create_polygon(pts, fill=RECEIPT_PAPER, outline=RECEIPT_LINE, width=1, tags="drawn")

        c.create_oval(left + 10, top + 8, left + 18, top + 16, fill=ACCENT, outline="", tags="drawn")
        c.create_text(left + 22, top + 12, text="TASK RECORD", fill=RECEIPT_TEXT,
                      font=("Consolas", 8, "bold"), anchor="w", tags="drawn")
        c.create_line(left + 10, top + 24, right - 10, top + 24,
                      fill=RECEIPT_LINE, dash=(3, 3), tags="drawn")

        if self.completed_tasks:
            ccx, ccy = right - 12, top + 12
            clr = c.create_oval(ccx - 6, ccy - 6, ccx + 6, ccy + 6, fill=RED, outline="", tags="drawn")
            xmark = c.create_text(ccx, ccy, text="×", fill=RECEIPT_PAPER,
                                  font=("Arial", 8, "bold"), tags="drawn")
            for it in (clr, xmark):
                c.tag_bind(it, "<Button-1>", lambda _e: self.clear_history())
                c.tag_bind(it, "<Enter>", lambda _e: c.configure(cursor="hand2"))
                c.tag_bind(it, "<Leave>", lambda _e: c.configure(cursor=""))

        if not self.completed_tasks:
            c.create_text((left + right) // 2, top + RECEIPT_HEADER_HEIGHT + 10,
                          text="终止后吐出小票", fill=RECEIPT_MUTED,
                          font=("Microsoft YaHei UI", 8), tags="drawn")
            return

        row_y = top + RECEIPT_HEADER_HEIGHT + 4
        for task in self.completed_tasks:
            started, duration, name = format_task_row(task)
            name = name if len(name) <= 6 else f"{name[:5]}…"
            if task.merge_count >= 2:
                name = f"{name} ×{task.merge_count}"
            c.create_text(left + 10, row_y, text=f"{started} {duration}", anchor="w",
                          fill=RECEIPT_TEXT, font=("Consolas", 9, "bold"), tags="drawn")
            c.create_text(right - 10, row_y, text=name, anchor="e",
                          fill=RECEIPT_MUTED, font=("Microsoft YaHei UI", 8), tags="drawn")
            c.create_line(left + 10, row_y + 10, right - 10, row_y + 10,
                          fill=RECEIPT_LINE, tags="drawn")
            row_y += RECEIPT_ROW_HEIGHT

    def _draw_orb(self) -> None:
        c = self.canvas
        cx, cy = ORB_SIZE // 2, ORB_SIZE // 2
        r = ORB_SIZE // 2 - 6

        if any(t.state == "running" for t in self.running):
            border = AMBER
        elif self.running:
            border = GREEN
        else:
            border = ACCENT

        items: list[int] = []
        items.append(c.create_oval(cx - r, cy - r, cx + r, cy + r,
                                   fill=BG_DARK, outline=border, width=2, tags="drawn"))

        ear = 4
        items.append(c.create_oval(cx - r + 2, cy - r - 3, cx - r + 2 + ear * 2, cy - r - 3 + ear * 2,
                                   fill=BG_DARK, outline=border, width=2, tags="drawn"))
        items.append(c.create_oval(cx + r - 2 - ear * 2, cy - r - 3, cx + r - 2, cy - r - 3 + ear * 2,
                                   fill=BG_DARK, outline=border, width=2, tags="drawn"))

        items.append(c.create_oval(cx - 1, cy - r + 4, cx + 1, cy - r + 6,
                                   fill=border, outline="", tags="drawn"))
        items.append(c.create_line(cx, cy, cx, cy - r + 8, fill=border, width=2, tags="drawn"))
        items.append(c.create_line(cx, cy, cx + r - 8, cy + 1, fill=border, width=2, tags="drawn"))

        n = len(self.running)
        if n > 0:
            bcx, bcy = ORB_SIZE - 10, ORB_SIZE - 10
            br = 7
            c.create_oval(bcx - br, bcy - br, bcx + br, bcy + br,
                          fill=ACCENT, outline=BG_DARK, width=1, tags="drawn")
            c.create_text(bcx, bcy, text=str(n), fill=BG_DARK,
                          font=("Consolas", 8, "bold"), tags="drawn")

        for it in items:
            c.tag_bind(it, "<Enter>", lambda _e: c.configure(cursor="hand2"))
            c.tag_bind(it, "<Leave>", lambda _e: c.configure(cursor=""))

    # ── interactions ─────────────────────────────────────

    def _toggle_tasks(self, _event: tk.Event | None = None) -> None:
        self.tasks_expanded = not self.tasks_expanded
        self._apply_geometry()
        self._draw_scene()

    def start_task(self) -> None:
        name = self.task_var.get().strip()
        if not name:
            return
        task = RunningTask(
            name=name,
            started_at=datetime.now(),
            state="running",
            elapsed_before_run=0.0,
            run_started_monotonic=time.monotonic(),
        )
        self.running.append(task)
        self.task_var.set("")
        self._apply_geometry()
        self._draw_scene()
        self._ensure_tick_scheduled()

    def _toggle_task_pause(self, task: RunningTask) -> None:
        if task.state == "running":
            task.pause()
        else:
            task.resume()
        self._draw_scene()
        self._ensure_tick_scheduled()

    def _finish_task(self, task: RunningTask) -> None:
        finished = CompletedTask(
            started_at=task.started_at,
            finished_at=datetime.now(),
            duration=timedelta(seconds=task.elapsed_seconds()),
            name=task.name,
            merge_count=1,
        )
        merge_into_completed(self.completed_tasks, finished)
        if task in self.running:
            self.running.remove(task)
        self._apply_geometry()
        self._draw_scene()

    def clear_history(self) -> None:
        self.completed_tasks.clear()
        self._apply_geometry()
        self._draw_scene()

    def minimize_window(self) -> None:
        # 非 Windows：直接 iconify
        if sys.platform != "win32":
            self.root.iconify()
            return
        # Windows：直接调 Win32 ShowWindow(SW_MINIMIZE)，不切 overrideredirect 避免标题栏闪烁
        try:
            import ctypes

            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            GA_ROOT = 2
            SW_MINIMIZE = 6

            hwnd = ctypes.windll.user32.GetAncestor(self.root.winfo_id(), GA_ROOT)
            if not hwnd:
                hwnd = self.root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
            if new_style != style:
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
        except Exception:
            self.root.iconify()

    def _on_window_map(self, event: tk.Event) -> None:
        if event.widget is self.root:
            self._enable_taskbar_visibility()

    def _enable_taskbar_visibility(self) -> None:
        # 给无边框窗口加 WS_EX_APPWINDOW 标志、移除 WS_EX_TOOLWINDOW，让任务栏识别它。
        if sys.platform != "win32":
            return
        try:
            import ctypes

            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            GA_ROOT = 2

            hwnd = ctypes.windll.user32.GetAncestor(self.root.winfo_id(), GA_ROOT)
            if not hwnd:
                hwnd = self.root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
            if new_style != style:
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        except Exception:
            pass

    # ── drag + dock ──────────────────────────────────────

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self._press_root_x = event.x_root
        self._press_root_y = event.y_root

    def _drag_window(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + event.x - self.drag_start_x
        y = self.root.winfo_y() + event.y - self.drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def _on_drag_release(self, event: tk.Event) -> None:
        moved = abs(event.x_root - self._press_root_x) + abs(event.y_root - self._press_root_y)
        if self.docked:
            if moved < CLICK_TOLERANCE:
                self._undock()
            else:
                self.last_normal_pos = (self.last_normal_pos[0], self.root.winfo_y())
            return
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        sw = self.root.winfo_screenwidth()
        if moved >= CLICK_TOLERANCE:
            if x <= DOCK_THRESHOLD:
                self.last_normal_pos = (max(20, DOCK_THRESHOLD + 8), y)
                self._dock("left")
                return
            if x + BAR_WIDTH >= sw - DOCK_THRESHOLD:
                self.last_normal_pos = (sw - BAR_WIDTH - DOCK_THRESHOLD - 8, y)
                self._dock("right")
                return
        self.last_normal_pos = (x, y)

    def _dock(self, side: str) -> None:
        self.docked = True
        self.docked_side = side
        self._apply_geometry()
        self._draw_scene()

    def _undock(self) -> None:
        self.docked = False
        self.docked_side = None
        self._apply_geometry()
        self._draw_scene()

    # ── tick ─────────────────────────────────────────────

    def _ensure_tick_scheduled(self) -> None:
        if self.tick_job is None and any(t.state == "running" for t in self.running):
            self.tick_job = self.root.after(250, self._on_tick)

    def _on_tick(self) -> None:
        self.tick_job = None
        if not any(t.state == "running" for t in self.running):
            return
        self._draw_scene()
        self._ensure_tick_scheduled()


def main() -> None:
    root = tk.Tk()
    TimerApp(root)
    root.mainloop()
