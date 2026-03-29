"""
RD-Agent 核心配置模块。

提供 ExtendedBaseSettings（合并父类环境变量源）与全局 RDAgentSettings。
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)


class ExtendedBaseSettings(BaseSettings):
    """
    在 Pydantic Settings 默认行为上，额外把「继承链上各父类」的 EnvSettingsSource 并入。

    这样子类可带独立 env_prefix（如 LITELLM_），同时仍读取无前缀的 LLM_* / 父类字段。
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # 1) 自当前类向上遍历 ExtendedBaseSettings 子类链
        def base_iter(settings_cls: type[ExtendedBaseSettings]) -> list[type[ExtendedBaseSettings]]:
            bases = []
            for cl in settings_cls.__bases__:
                if issubclass(cl, ExtendedBaseSettings) and cl is not ExtendedBaseSettings:
                    bases.append(cl)
                    bases.extend(base_iter(cl))
            return bases

        # 2) 为每个父类构建 EnvSettingsSource，使带 env_prefix 的父类字段也能从环境变量加载
        parent_env_settings = [
            EnvSettingsSource(
                base_cls,
                case_sensitive=base_cls.model_config.get("case_sensitive"),
                env_prefix=base_cls.model_config.get("env_prefix"),
                env_nested_delimiter=base_cls.model_config.get("env_nested_delimiter"),
            )
            for base_cls in base_iter(cast("type[ExtendedBaseSettings]", settings_cls))
        ]
        return init_settings, env_settings, *parent_env_settings, dotenv_settings, file_secret_settings


class RDAgentSettings(ExtendedBaseSettings):
    """
    RD-Agent 全局杂项配置（工作区、并行、缓存、Azure 文档智能等）。

    字段可通过环境变量覆盖（Pydantic Settings 默认大写蛇形命名，如 WORKSPACE_PATH）。
    """

    azure_document_intelligence_key: str = ""
    """Azure Document Intelligence（文档智能）服务的 API 密钥。"""

    azure_document_intelligence_endpoint: str = ""
    """Azure Document Intelligence 服务端点 URL。"""

    max_input_duplicate_factor_group: int = 300
    """因子去重 / 分组流程中，输入侧参与判重的因子组数量上限。"""

    max_output_duplicate_factor_group: int = 20
    """因子去重后保留的输出因子组数量上限。"""

    max_kmeans_group_number: int = 40
    """因子聚类（如 KMeans）时允许的最大簇数。"""

    workspace_path: Path = Path.cwd() / "git_ignore_folder" / "RD-Agent_workspace"
    """Agent 工作区根目录：实验代码、中间产物等默认存放位置。"""

    workspace_ckp_size_limit: int = 0
    """工作区检查点（zip）内文件总大小上限（字节级语义以调用方为准）。
    0 或负数表示不限制。"""

    workspace_ckp_white_list_names: list[str] | None = None
    """打工作区检查点时仅包含的文件名白名单；None 表示不按白名单过滤。"""

    multi_proc_n: int = 1
    """多进程相关默认并行度（具体使用场景见各模块）。"""

    cache_with_pickle: bool = True
    """是否启用基于 pickle 的函数结果缓存。"""

    pickle_cache_folder_path_str: str = str(
        Path.cwd() / "pickle_cache/",
    )
    """pickle 缓存文件存放目录路径（字符串形式）。"""

    use_file_lock: bool = True
    """相同参数重复调用时是否使用文件锁，避免并发重复执行。"""

    stdout_context_len: int = 400
    """日志 / 上下文中截断标准输出时的最大保留长度。"""

    stdout_line_len: int = 10000
    """单行 stdout 在展示或记录时的最大长度。"""

    enable_mlflow: bool = False
    """是否启用 MLflow 实验跟踪集成。"""

    initial_fator_library_size: int = 20
    """初始因子库规模（字段名沿用历史拼写 fator）。"""

    step_semaphore: int | dict[str, int] = 1
    """工作流各步骤并发信号量：可为全局整数，或按步骤名配置，如 {"coding": 3, "running": 2}。"""

    def get_max_parallel(self) -> int:
        """根据 step_semaphore 推算允许的最大并行 loop 数。"""
        if isinstance(self.step_semaphore, int):
            return self.step_semaphore
        return max(self.step_semaphore.values())

    subproc_step: bool = False
    """调试开关：为 True 时倾向在子进程中执行步骤（与并行逻辑配合）。"""

    def is_force_subproc(self) -> bool:
        """是否应强制使用子进程执行步骤（高并行或 subproc_step 为真时为 True）。"""
        return self.subproc_step or self.get_max_parallel() > 1

    app_tpl: str | None = None
    """应用级模板覆盖路径，例如 finetune 场景下的 "app/fintune/tpl"；None 使用默认模板。"""


# 全局单例：各模块通过 RD_AGENT_SETTINGS 读取上述配置
RD_AGENT_SETTINGS = RDAgentSettings()
