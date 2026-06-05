# 多任务并行计时 — 设计文档

- 状态：待实现
- 日期：2026-06-04
- 相关文件：`src/desktop_timer/app.py`、`src/desktop_timer/task_history.py`、`tests/test_task_history.py`

## 背景

当前桌面计时器是单任务串行：同一时刻只能有一个任务在跑表，结束后才能开下一个。但日常工作经常是几件事并行交错（写稿、客户对接、等编译），单任务模式无法记录这种重叠时段。

## 目标

让用户能同时挂多个任务并行计时，常态 2–3 个。每个任务独立暂停、终止。任务结束后进入小票区记录；**同名任务自动合并为一条小票，耗时累加**。

## 非目标

- 不引入数据持久化（沿用 AGENTS.md「第一版不写入外部文件」的边界，关闭程序后所有进行中和小票记录丢失）。
- 不引入任务的「优先级」「分类」「标签」等元数据。
- 不改变现有的 dock / undock 拖拽手势和透明背景渲染机制。
- 不写 tkinter UI 层的自动化测试（沿用现状，UI 层只做手测）。

## 数据模型

### 新增：`RunningTask`（在 `task_history.py`）

单个进行中任务的状态机，从 `TimerApp` 中剥离出来：

```
class RunningTask:
    name: str                          # strip 过的任务名
    started_at: datetime               # 首次启动时刻
    state: "running" | "paused"
    elapsed_before_run: float          # 当前段以前的累计秒数
    run_started_monotonic: float | None  # 当前 running 段起点（paused 时为 None）

    pause() -> None                    # running → paused，累加 elapsed_before_run
    resume() -> None                   # paused → running，重置 run_started_monotonic
    elapsed_seconds() -> float         # 总秒数（running 时含当前段）
```

### 扩展：`CompletedTask`

新增 `merge_count` 字段，默认 1：

```
@dataclass(frozen=True)
class CompletedTask:
    started_at: datetime
    finished_at: datetime
    duration: timedelta
    name: str
    merge_count: int = 1
```

frozen 改成 `True` 仍保留（不可变语义对历史记录是合理的）。合并时不修改旧实例，而是构造新实例替换列表中那一项。

### 新增：`merge_into_completed(completed, finished)`

放在 `task_history.py`，纯函数 + 一处 mutation：

```
def merge_into_completed(
    completed: list[CompletedTask],
    finished: CompletedTask,
) -> None:
    """把 finished 合并进 completed 列表（in-place）。

    若 completed 中已有同名（strip 后）条目：累加 duration、started_at 取最早、
    finished_at 取最新、merge_count += 1，并把这条移到列表第一位。
    若没有同名条目：把 finished insert(0, …)。
    """
```

## TimerApp 状态字段变更

### 删除（单任务字段）

`state`、`started_at`、`current_task`、`elapsed_before_run`、`run_started_monotonic`、`tick_job`、`_flash_red`、`timer_var`。

### 新增

- `self.running: list[RunningTask]`：按启动顺序追加（最早启动在上）。
- `self.tick_job: str | None`：保留（语义改为「只要有 running 任务就保持调度」）。

### 保留

- `self.completed_tasks: list[CompletedTask]`（沿用原字段名，避免不必要的连带改动）。
- `self.tasks_expanded`、`self.docked`、`self.docked_side`、`self.last_normal_pos`。
- `self.task_var: tk.StringVar`（输入框 binding）。

## UI 几何

### 主条总高度

```
height = BAR_HEIGHT(42)                             # 顶部输入栏
       + len(running) * TASK_ROW_HEIGHT(28)         # 进行中任务行
       + (展开时) RECEIPT_HEADER + rows*ROW + FOOT  # 小票区
```

主条宽度保持 360。

### 顶部输入栏（y ∈ [0, 42]）

```
× (cx=16, CY=21)        关闭程序
─ (cx=34, CY=21)        最小化
[Entry y_center=21, x=50..286, width≈236]   # 输入新任务名
▶ (cx=302, CY=21)        启动按钮（绿色圆点 + 三角）
▾N (cx=332, CY=21)       展开/收起小票（N = len(completed)）
```

**变化要点**：
- 删除原来位于 `(78, CY)` 的顶部时钟（每个任务行已有独立时钟，不再冗余）。
- 输入框由原 130 宽扩到 ~236 宽（约 50 至 286）。
- 输入框 **始终可编辑**（不再随状态 disabled）。

### 任务行（每行 28px，y_base = 42 + i*28）

```
y_center = y_base + 14
●  (cx=12, y_center)              # 小圆点（running=AMBER, paused=GREEN）
任务名 (x=24..180, y_center, anchor=w, 过长 ... 截断)
计时   (x=200..270, y_center, anchor=e, Consolas bold)
‖ / ▶  (cx=294, y_center)         # 暂停 / 继续切换
✓      (cx=322, y_center)         # 终止该任务
```

### 小票区

沿用现有齿边纸张样式。合并条目末尾追加 ` ×N`（仅当 merge_count ≥ 2 时显示）。

### dock 模式（缩成圆球）

- 圆球边框颜色：
  - 任意 `RunningTask.state == "running"` → AMBER
  - 全部 paused → GREEN
  - `running` 列表为空 → ACCENT
- 圆球内右下角小数字 = `len(self.running)`，等于 0 时不画。
- dock 期间任务继续跑，tick 不停。

## 核心交互

### 启动新任务

- 输入框非空 + 回车 / 点 ▶：
  1. `name = self.task_var.get().strip()`
  2. 若 `name == ""`：什么都不做（不弹窗，原 messagebox 体验在多任务下过于打扰）。
  3. 构造 `RunningTask(name, started_at=datetime.now(), state="running", elapsed_before_run=0.0, run_started_monotonic=time.monotonic())`。
  4. `self.running.append(task)`。
  5. `self.task_var.set("")` 清空输入框。
  6. `_apply_geometry()` + `_draw_scene()`。
  7. `_ensure_tick_scheduled()`。
- **同名并行允许**：如果已经有同名任务在跑，再次启动一条同名的，会形成两条独立的 RunningTask 并行。终止时各自走「合并到小票」路径，最终归并到同一条小票（merge_count 累加）。

### 暂停 / 继续单任务

- 点行内 `‖`：`task.pause()` → 重绘。若 `running` 中已无任意 running，可让 tick 自然在下一帧退出（看 tick 守卫）。
- 点行内 `▶`：`task.resume()` → 重绘 → `_ensure_tick_scheduled()`。

### 终止单任务

- 点行内 `✓`：
  1. 计算最终 `duration = timedelta(seconds=task.elapsed_seconds())`。
  2. 构造 `finished = CompletedTask(task.started_at, datetime.now(), duration, task.name, merge_count=1)`。
  3. `merge_into_completed(self.completed_tasks, finished)`。
  4. `self.running.remove(task)`。
  5. `_apply_geometry()` + `_draw_scene()`。
  6. 若 `not self.running`：让下一次 tick 自然退出。

### tick 调度

```
def _ensure_tick_scheduled(self):
    if self.tick_job is None and any(t.state == "running" for t in self.running):
        self.tick_job = self.root.after(250, self._on_tick)

def _on_tick(self):
    self.tick_job = None
    if not any(t.state == "running" for t in self.running):
        return                       # 没有 running 任务，停止调度
    self._draw_scene()               # 整体重绘（性能足够）
    self._ensure_tick_scheduled()
```

### 关闭程序

沿用现状：点 × → `root.destroy`。进行中和小票都不持久化。

## 文件改动清单

```
AGENTS.md                              [改]  目录约定新增 docs/
docs/2026-06-04-multi-task-parallel-design.md  [新建]  本文档

src/desktop_timer/task_history.py      [扩展]
  + class RunningTask
  ~ CompletedTask 新增 merge_count: int = 1
  + def merge_into_completed(completed, finished) -> None

src/desktop_timer/app.py               [大改]
  删除：单任务字段（见上节）；
        _on_btn_click、_on_btn_dblclick、_do_finish、_draw_action_button、
        _draw_timer、_update_timer_text、reset_current_task、
        pause_task、resume_task、finish_task（单任务版）、
        _schedule_tick、_cancel_tick（被新 tick 函数取代）
  新增：self.running、_draw_running_rows(y_base)、
        _ensure_tick_scheduled、_on_tick、
        _toggle_task_pause(task)、_finish_task(task)
  重写：_compute_height、_apply_geometry、_draw_scene、_draw_orb、
        _build_ui（输入框扩宽、删 timer_var）、start_task（创建 RunningTask）

tests/test_task_history.py             [扩展]
  + RunningTask 单元测试（pause / resume / elapsed 累加）
  + merge_into_completed 单元测试（空列表 / 同名合并 / 排序 / 启动时间最早 /
    finished_at 最新 / merge_count 累加）
```

`src/desktop_timer/obsidian_writer.py`、`src/desktop_timer/settings.py` 不改。

## 测试

### `tests/test_task_history.py` 新增覆盖

- `test_running_task_pause_accumulates_elapsed`：跑一段、暂停、检查 `elapsed_seconds()` 不再涨。
- `test_running_task_resume_continues`：暂停后 resume，时间从暂停时的值继续涨。
- `test_running_task_elapsed_includes_current_segment`：running 状态下 elapsed_seconds() 包含当前段。
- `test_merge_into_empty_completed`：空列表 → finished 直接进列表第一位。
- `test_merge_into_existing_same_name`：同名 → duration 累加，原条目位置被替换的新实例移到第一位。
- `test_merge_into_different_name`：不同名 → 新 insert(0)，旧条目保留原位（向后挪一位）。
- `test_merge_uses_earliest_started_at`：合并后 started_at 是较早那次。
- `test_merge_uses_latest_finished_at`：合并后 finished_at 是较晚那次。
- `test_merge_count_increments`：连续合并 3 次后 merge_count == 3。
- `test_merge_strips_name_for_comparison`：名字带前后空格的也能合并（`"写稿  "` 和 `"写稿"`）。

### 手动验证脚本

启动 `python -m src.desktop_timer` 后按顺序：

1. 输入「写稿子」→ 回车 → 主条下方出现第一行跑表，圆点 AMBER，时间开始跳。
2. 输入「客户对接」→ 回车 → 第二行出现，两个时间同时跳。
3. 点「写稿子」行 `‖` → 该行圆点变 GREEN、按钮变 ▶、时间停；客户对接仍跑。
4. 点「写稿子」行 ▶ → 恢复 running，继续累加。
5. 点「客户对接」行 ✓ → 该行消失，▾N 计数 +1。
6. 点 ▾N 展开 → 小票里看到「客户对接」，无 ×N。
7. 再次输入「客户对接」→ 跑几秒 → 终止 → 小票里「客户对接」变成 `客户对接 ×2`、时间累加、排到第一条。
8. 主条拖到屏幕左边 → dock 成圆球，边框 AMBER（写稿子还在跑），右下角小数字「1」。
9. 点圆球展开 → 写稿子时间仍在涨，没有丢秒。
10. 点 × 关程序 → 重新启动 → 所有记录清空（沿用不持久化）。

### 自动化命令（AGENTS.md 约定）

```
python -m unittest discover -s tests
python -m compileall src tests
```

## 风险与边界

- **输入框焦点抢夺**：输入框现在永远可编辑。如果输入框获得焦点时，点击主条空白区拖动是否会丢失焦点 / 中断输入？需在手动验证里关注。
- **任务行 click 闭包陷阱**：循环绑定每行按钮 handler 时必须 `lambda task=t: …`，否则所有按钮会都指向最后一个 task。
- **tick 退出时机**：tick 守卫必须严格——任何 `running` 任务都没有时直接 return，否则 idle 也在 250ms 重绘，浪费 CPU。
- **dock 期间任务计时不丢秒**：因为计时基于 `time.monotonic()` 而非 tick 计数，dock 期间不重绘但状态没冻结，展开时一定能看到正确累计。要在测试 9 步重点确认。

## 已显式拒绝的备选

- **方案 X（最小改造）**：把单任务字段直接改成 list/dict。拒绝原因：`TimerApp` 已经 491 行，再加并行管理会成为大泥球，且状态机和 UI 耦合度更高。
- **任务切换式语义**（同时挂多个、只跑一个）：拒绝原因：用户明确选「真并行」。
- **顶部时钟保留**：拒绝原因：每行已有独立时钟，顶部时钟必须人为定义「显示哪个」，语义牵强且和下面行重复。
- **Frame 控件堆叠渲染**：拒绝原因：与现有 Canvas 全画风格不一致，会出现拼接感。
- **暂停 / 终止 沿用「点击 + 双击」**：拒绝原因：每行独立按钮后误触风险已低，独立按钮更直观。
- **数据持久化**：超出第一版 + 多任务的范围，保持 AGENTS.md「第一版不写外部文件」的边界。
