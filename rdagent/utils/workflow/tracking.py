"""
工作流执行指标上报：在启用 MLflow 时将 loop/step、时间、API 失败与计时器状态写入实验跟踪。

未安装 MLflow 或配置关闭时，方法为空操作。
"""

import datetime
from typing import TYPE_CHECKING

import pytz

from rdagent.core.conf import RD_AGENT_SETTINGS
from rdagent.log.timer import RD_Agent_TIMER_wrapper

if TYPE_CHECKING:
    from rdagent.utils.workflow.loop import LoopBase

from rdagent.log import rdagent_logger as logger

mlflow = None

if RD_AGENT_SETTINGS.enable_mlflow:
    try:
        import mlflow  # type: ignore[assignment]
    except ImportError:
        logger.warning("MLflow is enabled in settings but could not be imported.")
        RD_AGENT_SETTINGS.enable_mlflow = False


class WorkflowTracker:
    """
    绑定 LoopBase 实例，在关键步骤把当前 loop/step 与时间等写入 MLflow metric。

    `RD_AGENT_SETTINGS.enable_mlflow` 为 False 时不执行任何网络调用。
    """

    def __init__(self, loop_base: "LoopBase"):
        """loop_base：被追踪的工作流对象。"""
        self.loop_base = loop_base

    @staticmethod
    def is_enabled() -> bool:
        """是否启用了 MLflow 跟踪。"""
        return RD_AGENT_SETTINGS.enable_mlflow

    @staticmethod
    def _datetime_to_float(dt: datetime.datetime) -> float:
        """将 datetime 压成可 log 的标量（年/月/日/时/分/秒拼接式编码）。"""
        return dt.second + dt.minute * 1e2 + dt.hour * 1e4 + dt.day * 1e6 + dt.month * 1e8 + dt.year * 1e10

    def log_workflow_state(self) -> None:
        """从 loop_base 读取进度与计时器、API 失败计数并写入 MLflow。"""
        if not RD_AGENT_SETTINGS.enable_mlflow or mlflow is None:
            return

        try:
            mlflow.log_metric("loop_index", self.loop_base.loop_idx)
            mlflow.log_metric("step_index", self.loop_base.step_idx[self.loop_base.loop_idx])

            current_local_datetime = datetime.datetime.now(pytz.timezone("Asia/Shanghai"))
            float_like_datetime = self._datetime_to_float(current_local_datetime)
            mlflow.log_metric("current_datetime", float_like_datetime)

            mlflow.log_metric("api_fail_count", RD_Agent_TIMER_wrapper.api_fail_count)
            latest_api_fail_time = RD_Agent_TIMER_wrapper.latest_api_fail_time
            if latest_api_fail_time is not None:
                float_like_datetime = self._datetime_to_float(latest_api_fail_time)
                mlflow.log_metric("lastest_api_fail_time", float_like_datetime)

            if self.loop_base.timer.started:
                remain_time = self.loop_base.timer.remain_time()
                assert remain_time is not None
                mlflow.log_metric("remain_time", remain_time.total_seconds())
                mlflow.log_metric(
                    "remain_percent",
                    remain_time / self.loop_base.timer.all_duration * 100,
                )

        except Exception as e:
            logger.warning(f"Error in log_workflow_state: {e}")
