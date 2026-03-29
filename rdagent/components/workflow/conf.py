"""
工作流层公共配置：RD 循环（假设 → 实验 → 编码 → 执行 → 反馈）的可插拔类路径。
"""

from rdagent.core.conf import ExtendedBaseSettings


class BasePropSetting(ExtendedBaseSettings):
    """
    RD Loop 的通用配置基类：用「可 import 的类全路径字符串」声明各环节实现。

    子类通过 model_config 的 env_prefix 区分环境变量命名空间（如 QLIB_FACTOR_）。
    """

    scen: str | None = None
    """场景类全路径：描述任务背景、数据、接口与实验设定（供 Prompt 拼装）。"""

    knowledge_base: str | None = None
    """知识库相关类全路径（若该场景使用 RAG / 知识管理）。"""

    knowledge_base_path: str | None = None
    """知识库文件或目录路径。"""

    hypothesis_gen: str | None = None
    """假设生成器类全路径：根据 Trace 等产生 Hypothesis。"""

    interactor: str | None = None
    """人机交互组件类全路径（可选）。"""

    hypothesis2experiment: str | None = None
    """假设到实验转换器类全路径：Hypothesis → Experiment。"""

    coder: str | None = None
    """编码 / 开发者类全路径：根据 Experiment 生成或修改代码。"""

    runner: str | None = None
    """执行器类全路径：在目标环境运行实验。"""

    summarizer: str | None = None
    """反馈总结类全路径：Experiment 结果 → HypothesisFeedback。"""

    evolving_n: int = 10
    """演化轮次默认值（具体是否作为硬停止由 RDLoop 使用方式决定）。"""
