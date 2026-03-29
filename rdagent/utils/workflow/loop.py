"""
异步多 Loop 工作流引擎：会话落盘 / 恢复、步骤调度、并行信号量与计时。

说明：曾考虑用 Python generator 表达流程，但 generator 难以 pickle，故采用显式步骤列表 + LoopMeta 收集方法名。
"""

import asyncio
import concurrent.futures
import copy
import multiprocessing.queues
import os
import pickle
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Union, cast

import psutil
from tqdm.auto import tqdm

from rdagent.core.conf import RD_AGENT_SETTINGS
from rdagent.log import rdagent_logger as logger
from rdagent.log.conf import LOG_SETTINGS
from rdagent.log.timer import RD_Agent_TIMER_wrapper, RDAgentTimer
from rdagent.utils.workflow.tracking import WorkflowTracker


class LoopMeta(type):
    """
    元类：合并基类与当前类中「可作为工作流步骤」的公开方法名，写入 `cls.steps`（顺序即执行顺序）。

    排除 `_` 前缀、`load`/`dump` 及嵌套 class，避免把普通工具方法误认为步骤。
    """

    @staticmethod
    def _get_steps(bases: tuple[type, ...]) -> list[str]:
        """递归收集基类链上已注册的 `steps`，去重并排除 load/dump。"""
        steps = []
        for base in bases:
            for step in LoopMeta._get_steps(base.__bases__) + getattr(base, "steps", []):
                if step not in steps and step not in ["load", "dump"]:  # 避免把 load/dump 当作一步
                    steps.append(step)
        return steps

    def __new__(mcs, clsname: str, bases: tuple[type, ...], attrs: dict[str, Any]) -> Any:
        """构造类对象时汇总 `steps`：先继承基类步骤，再追加本类新增的公开可调用方法。"""
        steps = LoopMeta._get_steps(bases)  # 基类步骤
        for name, attr in attrs.items():
            if not name.startswith("_") and callable(attr) and not isinstance(attr, type):
                # 排除嵌套 class（type）
                if name not in steps and name not in ["load", "dump"]:  # 同上
                    # 子类若覆写同名步骤，不重复追加（name 已在 steps）
                    steps.append(name)
        attrs["steps"] = steps
        return super().__new__(mcs, clsname, bases, attrs)


@dataclass
class LoopTrace:
    """单次步骤执行的时间记录（用于会话截断与统计）。"""

    start: datetime  # 该步开始时间（UTC）
    end: datetime  # 该步结束时间（UTC）
    step_idx: int  # 步骤在 self.steps 中的下标
    # TODO: 可扩展更多 trace 字段


class LoopBase:
    """
    多 Loop 并行工作流基类：kickoff 与 execute 协程配合 asyncio.Queue 调度各 loop 的步骤。

    约定：最后一步（通常为 record）负责写入全局可追溯状态；`force_subproc` 为 True 时子进程与 Timer 等全局状态同步仍需谨慎。
    """

    steps: list[str]  # 步骤方法名有序列表，由 LoopMeta 生成
    loop_trace: dict[int, list[LoopTrace]]

    skip_loop_error: tuple[type[BaseException], ...] = ()  # 捕获此类异常时跳过当前 loop 的后续逻辑或跳到指定步
    skip_loop_error_stepname: str | None = None  # 跳过异常后强制从该步骤名继续（须晚于当前步）
    withdraw_loop_error: tuple[
        type[BaseException], ...
    ] = ()  # 捕获此类异常时回滚到上一 loop 的会话快照

    EXCEPTION_KEY = "_EXCEPTION"  # loop_prev_out 中存放步骤异常的键
    LOOP_IDX_KEY = "_LOOP_IDX"  # 当前 loop 下标，注入各步输入 dict
    SENTINEL = -1  # 队列结束标记，通知 execute_loop 退出

    _pbar: tqdm  # tqdm 进度条实例（惰性创建）

    class LoopTerminationError(Exception):
        """步数用尽、计时器超时等正常停止条件。"""

    class LoopResumeError(Exception):
        """需要撤销当前进度并重启所有协程时抛出（如 withdraw 后）。"""

    def __init__(self) -> None:
        # 调度状态
        self.loop_idx: int = 0  # 下一个待 kickoff 的 loop 编号
        self.step_idx: defaultdict[int, int] = defaultdict(int)  # 每个 loop 下一个待执行步骤下标
        self.queue: asyncio.Queue[Any] = asyncio.Queue()

        # 嵌套字典：loop_prev_out[li][step_name] = 该步返回值；另含 LOOP_IDX_KEY、EXCEPTION_KEY 等
        self.loop_prev_out: dict[int, dict[str, Any]] = defaultdict(dict)
        self.loop_trace = defaultdict(list[LoopTrace])  # 键为 loop 编号
        self.session_folder = Path(LOG_SETTINGS.trace_path) / "__session__"
        self.timer: RDAgentTimer = RD_Agent_TIMER_wrapper.timer
        self.tracker = WorkflowTracker(self)  # MLflow 等可选追踪

        # run() 可设置的剩余配额
        self.loop_n: Optional[int] = None  # 剩余可启动的 loop 次数（None 表示不限制）
        self.step_n: Optional[int] = None  # 剩余可向前推进的步数（全局递减）

        self.semaphores: dict[str, asyncio.Semaphore] = {}  # 按步骤名缓存信号量

    def get_unfinished_loop_cnt(self, next_loop: int) -> int:
        """统计编号小于 next_loop 且尚未跑完所有步骤的 loop 数量（用于背压/限流）。"""
        n = 0
        for li in range(next_loop):
            if self.step_idx[li] < len(self.steps):  # 该 loop 仍有未执行步骤
                n += 1
        return n

    def get_semaphore(self, step_name: str) -> asyncio.Semaphore:
        """
        返回该步骤名的 asyncio 并发许可。`RD_AGENT_SETTINGS.step_semaphore` 可为全局 int 或按步骤名的 dict。

        `feedback` 与 `record` 强制为 1：最后一步会改全局 Trace；反馈步与父节点对齐复杂，避免并行导致不一致。
        """
        if isinstance(limit := RD_AGENT_SETTINGS.step_semaphore, dict):
            limit = limit.get(step_name, 1)  # 未配置则默认 1

        if step_name in ("record", "feedback"):
            limit = 1

        if step_name not in self.semaphores:
            self.semaphores[step_name] = asyncio.Semaphore(limit)
        return self.semaphores[step_name]

    @property
    def pbar(self) -> tqdm:
        """懒创建 tqdm 进度条（按步骤总数）。"""
        if getattr(self, "_pbar", None) is None:
            self._pbar = tqdm(total=len(self.steps), desc="Workflow Progress", unit="step")
        return self._pbar

    def close_pbar(self) -> None:
        if getattr(self, "_pbar", None) is not None:
            self._pbar.close()
            del self._pbar

    def _check_exit_conditions_on_step(self, loop_id: Optional[int] = None, step_id: Optional[int] = None) -> None:
        """每成功前进一步后调用：递减 step_n 或检查计时器；不满足则抛 LoopTerminationError。"""
        # 全局剩余步数
        if self.step_n is not None:
            if self.step_n <= 0:
                raise self.LoopTerminationError("Step count reached")
            self.step_n -= 1

        # 总时长计时器
        if self.timer.started:
            if self.timer.is_timeout():
                logger.warning("Timeout, exiting the loop.")
                raise self.LoopTerminationError("Timer timeout")
            else:
                logger.info(f"Timer remaining time: {self.timer.remain_time()}")

    async def _run_step(self, li: int, force_subproc: bool = False) -> None:
        """
        执行 loop `li` 的当前一步：从 `self.steps[step_idx]` 取方法名，调用实例方法并写回 `loop_prev_out`。

        force_subproc 为 True 时用 ProcessPoolExecutor 深拷贝后执行同步函数，避免阻塞事件循环（注意与 Timer 全局状态）。
        """
        si = self.step_idx[li]
        name = self.steps[si]

        async with self.get_semaphore(name):

            logger.info(f"Start Loop {li}, Step {si}: {name}")
            self.tracker.log_workflow_state()

            with logger.tag(f"Loop_{li}.{name}"):
                start = datetime.now(timezone.utc)
                func: Callable[..., Any] = cast(Callable[..., Any], getattr(self, name))

                next_step_idx = si + 1
                step_forward = True
                # 各步可通过 prev_out[LOOP_IDX_KEY] 获知当前 loop 编号；须在调用步骤函数前写入
                self.loop_prev_out[li][self.LOOP_IDX_KEY] = li

                try:
                    if force_subproc:
                        curr_loop = asyncio.get_running_loop()
                        with concurrent.futures.ProcessPoolExecutor() as pool:
                            # 深拷贝避免子进程与主进程并发修改同一 dict 导致迭代中结构变化
                            result = await curr_loop.run_in_executor(
                                pool, copy.deepcopy(func), copy.deepcopy(self.loop_prev_out[li])
                            )
                    else:
                        if asyncio.iscoroutinefunction(func):
                            result = await func(self.loop_prev_out[li])
                        else:
                            result = func(self.loop_prev_out[li])
                    self.loop_prev_out[li][name] = result
                except Exception as e:
                    if isinstance(e, self.skip_loop_error):
                        logger.warning(f"Skip loop {li} due to {e}")
                        if self.skip_loop_error_stepname:
                            next_step_idx = self.steps.index(self.skip_loop_error_stepname)
                            if next_step_idx <= si:
                                raise RuntimeError(
                                    f"Cannot skip backwards or to same step. Current: {si} ({name}), Target: {next_step_idx} ({self.skip_loop_error_stepname})"
                                ) from e
                        else:
                            # 默认跳到 feedback，否则最后一步（一般为 record）
                            if "feedback" in self.steps:
                                next_step_idx = self.steps.index("feedback")
                            else:
                                next_step_idx = len(self.steps) - 1
                        self.loop_prev_out[li][name] = None
                        self.loop_prev_out[li][self.EXCEPTION_KEY] = e
                    elif isinstance(e, self.withdraw_loop_error):
                        logger.warning(f"Withdraw loop {li} due to {e}")
                        self.withdraw_loop(li)
                        step_forward = False

                        msg = "We have reset the loop instance, stop all the routines and resume."
                        raise self.LoopResumeError(msg) from e
                    else:
                        raise  # re-raise unhandled exceptions
                finally:
                    end = datetime.now(timezone.utc)
                    self.loop_trace[li].append(LoopTrace(start, end, step_idx=si))
                    logger.log_object(
                        {
                            "start_time": start,
                            "end_time": end,
                        },
                        tag="time_info",
                    )
                    if step_forward:
                        self.step_idx[li] = next_step_idx

                        current_step = self.step_idx[li]
                        self.pbar.n = current_step
                        next_step = self.step_idx[li] % len(self.steps)
                        self.pbar.set_postfix(
                            loop_index=li + next_step_idx // len(self.steps),
                            step_index=next_step,
                            step_name=self.steps[next_step],
                        )

                        # 成功前进一步后再 dump：保证恢复时 step_idx 与 pickle 一致；withdraw 不保存
                        if name in self.loop_prev_out[li]:
                            self.dump(self.session_folder / f"{li}" / f"{si}_{name}")

                        self._check_exit_conditions_on_step(loop_id=li, step_id=si)
                    else:
                        logger.warning(f"Step forward {si} of loop {li} is skipped.")

    async def kickoff_loop(self) -> None:
        """不断递增 loop_idx：在 loop_n 限额内为每个新 loop 先跑第 0 步（通常为实验生成），再丢进队列。"""
        while True:
            li = self.loop_idx

            if self.loop_n is not None:
                if self.loop_n <= 0:
                    for _ in range(RD_AGENT_SETTINGS.get_max_parallel()):
                        self.queue.put_nowait(self.SENTINEL)
                    break
                self.loop_n -= 1

            # 第一步一般为实验生成，可内部阻塞直到并行度允许
            if self.step_idx[li] == 0:
                await self._run_step(li)
            self.queue.put_nowait(li)  # execute_loop 侧消费并推进后续步骤
            self.loop_idx += 1
            await asyncio.sleep(0)

    async def execute_loop(self) -> None:
        """从队列取 loop 编号，顺序执行该 loop 剩余步骤；末步通常不强制子进程。"""
        while True:
            li = await self.queue.get()
            if li == self.SENTINEL:
                break
            while self.step_idx[li] < len(self.steps):
                if self.step_idx[li] == len(self.steps) - 1:
                    # 假定最后一步为 record：快且修改全局 Trace，直接同进程执行
                    await self._run_step(li)
                else:
                    await self._run_step(li, force_subproc=RD_AGENT_SETTINGS.is_force_subproc())

    async def run(self, step_n: int | None = None, loop_n: int | None = None, all_duration: str | None = None) -> None:
        """
        启动工作流：1 个 kickoff_loop + 多个 execute_loop（并行度由 RD_AGENT_SETTINGS.get_max_parallel()）。

        loop_n：剩余可 kickoff 的 loop 次数；None 表示直到异常或手动中断。
        step_n：全局剩余步数配额，每成功前进一步减一。
        all_duration：总运行时长字符串，交给 RDAgentTimer 解析。
        """
        if all_duration is not None and not self.timer.started:
            self.timer.reset(all_duration=all_duration)

        if step_n is not None:
            self.step_n = step_n
        if loop_n is not None:
            self.loop_n = loop_n

        while not self.queue.empty():
            self.queue.get_nowait()
        self.loop_idx = 0  # 每次 run 从 0 开始编号，保证 kickoff 顺序一致

        tasks: list[asyncio.Task] = []
        while True:
            try:
                tasks = [
                    asyncio.create_task(t)
                    for t in [
                        self.kickoff_loop(),
                        *[self.execute_loop() for _ in range(RD_AGENT_SETTINGS.get_max_parallel())],
                    ]
                ]
                await asyncio.gather(*tasks)
                break
            except self.LoopResumeError as e:
                logger.warning(f"Stop all the routines and resume loop: {e}")
                self.loop_idx = 0
            except self.LoopTerminationError as e:
                logger.warning(f"Reach stop criterion and stop loop: {e}")
                kill_subprocesses()  # 协程无法自动回收 ProcessPool 子进程，需手动清理
                break
            finally:
                for t in tasks:
                    t.cancel()
                self.close_pbar()

    def withdraw_loop(self, loop_idx: int) -> None:
        """从上一 loop 的会话目录加载最新 pickle，覆盖当前实例状态（用于 withdraw_loop_error）。"""
        prev_session_dir = self.session_folder / str(loop_idx - 1)
        prev_path = min(
            (p for p in prev_session_dir.glob("*_*") if p.is_file()),
            key=lambda item: int(item.name.split("_", 1)[0]),
            default=None,
        )
        if prev_path:
            loaded = type(self).load(
                prev_path,
                checkout=True,
                replace_timer=True,
            )
            logger.info(f"Load previous session from {prev_path}")
            self.__dict__ = loaded.__dict__
        else:
            logger.error(f"No previous dump found at {prev_session_dir}, cannot withdraw loop {loop_idx}")
            raise

    def dump(self, path: str | Path) -> None:
        """将当前 Loop 实例 pickle 到 path（会先刷新计时器剩余时间）。"""
        if RD_Agent_TIMER_wrapper.timer.started:
            RD_Agent_TIMER_wrapper.timer.update_remain_time()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            pickle.dump(self, f)

    def truncate_session_folder(self, li: int, si: int) -> None:
        """删除会话目录中晚于 (li, si) 的 dump：用于 checkout 后丢弃「更晚」的快照。"""
        for sf in self.session_folder.iterdir():
            if sf.is_dir() and int(sf.name) > li:
                for file in sf.iterdir():
                    file.unlink()
                sf.rmdir()

        final_loop_session_folder = self.session_folder / str(li)
        for step_session in final_loop_session_folder.glob("*_*"):
            if step_session.is_file():
                step_id = int(step_session.name.split("_", 1)[0])
                if step_id > si:
                    step_session.unlink()

    @classmethod
    def load(
        cls,
        path: str | Path,
        checkout: bool | Path | str = False,
        replace_timer: bool = True,
    ) -> "LoopBase":
        """
        从 pickle 恢复会话。

        path 可为具体 `.pkl` 文件，或目录（则在 `__session__` 下按 loop/step 序取最新文件）。
        checkout=True：在原会话根继续写并截断更晚快照与日志；checkout=Path：克隆到新目录；False：不截断。
        replace_timer：是否用会话内 timer 替换全局包装器中的 timer。
        """
        path = Path(path)
        session_folder = None
        if path.is_dir():
            if path.name != "__session__":
                session_folder = path / "__session__"
            else:
                session_folder = path

            if not session_folder.exists():
                raise FileNotFoundError(f"No session file found in {path}")

            files = sorted(session_folder.glob("*/*_*"), key=lambda f: (int(f.parent.name), int(f.name.split("_")[0])))
            path = files[-1]
            logger.info(f"Loading latest session from {path}")
        else:
            session_folder = path.parent.parent

        with path.open("rb") as f:
            session = cast(LoopBase, pickle.load(f))

        if checkout:
            if checkout is True:
                session.session_folder = session_folder
                logger.set_storages_path(session.session_folder.parent)

                max_loop = max(session.loop_trace.keys())
                session.truncate_session_folder(max_loop, len(session.loop_trace[max_loop]) - 1)
                logger.truncate_storages(session.loop_trace[max_loop][-1].end)
            else:
                checkout = Path(checkout)
                checkout.mkdir(parents=True, exist_ok=True)
                session.session_folder = checkout / "__session__"
                logger.set_storages_path(checkout)

            logger.info(f"Checkout session to {session.session_folder.parent}")

        if session.timer.started:
            if replace_timer:
                RD_Agent_TIMER_wrapper.replace_timer(session.timer)
                RD_Agent_TIMER_wrapper.timer.restart_by_remain_time()
            else:
                session.timer = RD_Agent_TIMER_wrapper.timer

        return session

    def __getstate__(self) -> dict[str, Any]:
        """pickle 时排除不可序列化的 queue、信号量、进度条与多进程 Queue。"""
        res = {}
        for k, v in self.__dict__.items():
            if k in ["queue", "semaphores", "_pbar"]:
                continue
            if isinstance(v, multiprocessing.queues.Queue):
                continue
            res[k] = v
        return res

    def __setstate__(self, state: dict[str, Any]) -> None:
        """反序列化后重建空的 asyncio 队列与信号量表。"""
        self.__dict__.update(state)
        self.queue = asyncio.Queue()
        self.semaphores = {}


def kill_subprocesses() -> None:
    """
    主进程事件循环无法自动结束 `run_in_executor` 拉起的子进程；终止工作流时需遍历子进程树 terminate/kill，
    避免僵尸任务占用资源。
    """
    current_proc = psutil.Process(os.getpid())
    for child in current_proc.children(recursive=True):
        try:
            print(f"Terminating subprocess PID {child.pid} ({child.name()})")
            child.terminate()
        except Exception as ex:
            print(f"Could not terminate subprocess {child.pid}: {ex}")
    print("Finished terminating subprocesses. Then force killing still alive subprocesses.")
    _, alive = psutil.wait_procs(current_proc.children(recursive=True), timeout=3)
    for p in alive:
        try:
            print(f"Killing still alive subprocess PID {p.pid} ({p.name()})")
            p.kill()
        except Exception as ex:
            print(f"Could not kill subprocess {p.pid}: {ex}")
    print("Finished killing subprocesses.")
