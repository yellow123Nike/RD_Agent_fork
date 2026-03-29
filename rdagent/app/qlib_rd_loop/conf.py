"""
Qlib 量化 R&D 循环的 Pydantic 配置：因子 / 模型 / 研报因子 / 联合量化 四套 PropSetting 与全局单例。
"""

from typing import Optional

from pydantic_settings import SettingsConfigDict

from rdagent.components.workflow.conf import BasePropSetting


class ModelBasePropSetting(BasePropSetting):
    """
    量化预测模型自动研发（fin_model）的专用配置。

    环境变量前缀 QLIB_MODEL_*；组件为单条「模型」假设—实验—编码—执行—反馈链。
    """

    model_config = SettingsConfigDict(env_prefix="QLIB_MODEL_", protected_namespaces=())

    scen: str = "rdagent.scenarios.qlib.experiment.model_experiment.QlibModelScenario"
    """模型任务场景类（全路径）：背景、输出格式、Qlib 模型接口与训练/验证/测试时间段。"""

    hypothesis_gen: str = "rdagent.scenarios.qlib.proposal.model_proposal.QlibModelHypothesisGen"
    """模型假设生成器（全路径）：结合 SOTA 反馈等生成下一轮模型假设。"""

    hypothesis2experiment: str = "rdagent.scenarios.qlib.proposal.model_proposal.QlibModelHypothesis2Experiment"
    """模型假设到实验转换器（全路径）：得到 QlibModelExperiment。"""

    coder: str = "rdagent.scenarios.qlib.developer.model_coder.QlibModelCoSTEER"
    """模型代码生成 / 开发者（全路径）。"""

    runner: str = "rdagent.scenarios.qlib.developer.model_runner.QlibModelRunner"
    """模型实验执行器（全路径）：Qlib 训练与回测。"""

    summarizer: str = "rdagent.scenarios.qlib.developer.feedback.QlibModelExperiment2Feedback"
    """模型实验反馈生成器（全路径）。"""

    evolving_n: int = 10
    """演化轮次默认上限。"""

    train_start: str = "2008-01-01"
    """训练段开始日期。"""

    train_end: str = "2014-12-31"
    """训练段结束日期。"""

    valid_start: str = "2015-01-01"
    """验证段开始日期。"""

    valid_end: str = "2016-12-31"
    """验证段结束日期。"""

    test_start: str = "2017-01-01"
    """测试 / 回测段开始日期。"""

    test_end: Optional[str] = "2020-08-01"
    """测试 / 回测段结束日期。"""


class FactorBasePropSetting(BasePropSetting):
    """
    量化因子自动研发（fin_factor）的专用配置。

    通过环境变量前缀 QLIB_FACTOR_* 覆盖默认值；RD 循环会按此处类路径实例化
    场景、假设生成、实验转换、编码、执行与反馈等组件。
    """

    model_config = SettingsConfigDict(env_prefix="QLIB_FACTOR_", protected_namespaces=())

    # 1) override base settings
    scen: str = "rdagent.scenarios.qlib.experiment.factor_experiment.QlibFactorScenario"
    """因子任务的场景类（全路径）：提供背景、数据说明、Qlib 因子接口与实验设定等 Prompt 上下文。"""

    hypothesis_gen: str = "rdagent.scenarios.qlib.proposal.factor_proposal.QlibFactorHypothesisGen"
    """假设生成器类（全路径）：根据历史 Trace 与 plan 调用 LLM 生成下一轮因子假设。"""

    hypothesis2experiment: str = "rdagent.scenarios.qlib.proposal.factor_proposal.QlibFactorHypothesis2Experiment"
    """假设到实验转换器类（全路径）：把 Hypothesis 转为 QlibFactorExperiment（子任务、工作区等）。"""

    coder: str = "rdagent.scenarios.qlib.developer.factor_coder.QlibFactorCoSTEER"
    """因子编码器 / 开发者类（全路径）：根据实验规格生成或修改因子代码（CoSTEER 流程）。"""

    runner: str = "rdagent.scenarios.qlib.developer.factor_runner.QlibFactorRunner"
    """因子执行器类（全路径）：在 Qlib/Docker 环境中运行因子实验并产出结果。"""

    summarizer: str = "rdagent.scenarios.qlib.developer.feedback.QlibFactorExperiment2Feedback"
    """实验反馈生成器类（全路径）：将运行结果总结为 HypothesisFeedback，供下一轮假设使用。"""

    evolving_n: int = 10
    """演化轮次相关默认上限（与循环停止条件等配合，具体以 RDLoop 使用为准）。"""

    train_start: str = "2008-01-01"
    """训练段开始日期（字符串），会写入场景中的实验设定描述。"""

    train_end: str = "2014-12-31"
    """训练段结束日期。"""

    valid_start: str = "2015-01-01"
    """验证段开始日期。"""

    valid_end: str = "2016-12-31"
    """验证段结束日期。"""

    test_start: str = "2017-01-01"
    """测试 / 回测段开始日期。"""

    test_end: Optional[str] = "2020-08-01"
    """测试 / 回测段结束日期。"""


class FactorFromReportPropSetting(FactorBasePropSetting):
    """
    从研报 PDF 抽取因子并继续因子研发（fin_factor_report）的专用配置。

    在 FactorBasePropSetting 上替换场景类，并增加研报列表路径、每轮因子数量与处理篇数上限。
    """

    scen: str = "rdagent.scenarios.qlib.experiment.factor_from_report_experiment.QlibFactorFromReportScenario"
    """研报因子场景类（全路径）：在通用因子场景基础上强化「来自研报」的表述与约束。"""

    report_result_json_file_path: str = "git_ignore_folder/report_list.json"
    """未指定 report_folder 时，从此 JSON 读取待处理研报路径列表（与 FactorReportLoop 逻辑一致）。"""

    max_factors_per_exp: int = 6
    """单次实验中最多实现 / 截断的因子子任务数量（控制每轮复杂度）。"""

    report_limit: int = 20
    """最多处理的研报篇数上限（与循环内 loop_n 等共同限制总工作量）。"""


class QuantBasePropSetting(BasePropSetting):
    """
    因子 + 模型联合量化研发（fin_quant）的专用配置。

    环境变量前缀 QLIB_QUANT_*；含两套 hypothesis2experiment/coder/runner/summarizer，
    由 quant_hypothesis_gen 在因子与模型动作间选择。
    """

    model_config = SettingsConfigDict(env_prefix="QLIB_QUANT_", protected_namespaces=())

    scen: str = "rdagent.scenarios.qlib.experiment.quant_experiment.QlibQuantScenario"
    """联合量化场景类（全路径）：同时描述因子与模型两条分支的上下文。"""

    quant_hypothesis_gen: str = "rdagent.scenarios.qlib.proposal.quant_proposal.QlibQuantHypothesisGen"
    """量化动作假设生成器（全路径）：输出下一步做因子还是做模型等。"""

    model_hypothesis2experiment: str = "rdagent.scenarios.qlib.proposal.model_proposal.QlibModelHypothesis2Experiment"
    """模型分支：假设到实验转换器（全路径）。"""

    model_coder: str = "rdagent.scenarios.qlib.developer.model_coder.QlibModelCoSTEER"
    """模型分支：编码器（全路径）。"""

    model_runner: str = "rdagent.scenarios.qlib.developer.model_runner.QlibModelRunner"
    """模型分支：执行器（全路径）。"""

    model_summarizer: str = "rdagent.scenarios.qlib.developer.feedback.QlibModelExperiment2Feedback"
    """模型分支：反馈生成器（全路径）。"""

    factor_hypothesis2experiment: str = (
        "rdagent.scenarios.qlib.proposal.factor_proposal.QlibFactorHypothesis2Experiment"
    )
    """因子分支：假设到实验转换器（全路径）。"""

    factor_coder: str = "rdagent.scenarios.qlib.developer.factor_coder.QlibFactorCoSTEER"
    """因子分支：编码器（全路径）。"""

    factor_runner: str = "rdagent.scenarios.qlib.developer.factor_runner.QlibFactorRunner"
    """因子分支：执行器（全路径）。"""

    factor_summarizer: str = "rdagent.scenarios.qlib.developer.feedback.QlibFactorExperiment2Feedback"
    """因子分支：反馈生成器（全路径）。"""

    evolving_n: int = 10
    """演化轮次默认上限。"""

    action_selection: str = "bandit"
    """下一步动作选择策略：bandit（多臂赌博机）/ llm / random 等，由实现解析。"""

    train_start: str = "2008-01-01"
    """训练段开始日期。"""

    train_end: str = "2014-12-31"
    """训练段结束日期。"""

    valid_start: str = "2015-01-01"
    """验证段开始日期。"""

    valid_end: str = "2016-12-31"
    """验证段结束日期。"""

    test_start: str = "2017-01-01"
    """测试 / 回测段开始日期。"""

    test_end: Optional[str] = "2020-08-01"
    """测试 / 回测段结束日期。"""


# 因子自动研发（rdagent fin_factor）使用的全局默认配置实例
FACTOR_PROP_SETTING = FactorBasePropSetting()
# 研报驱动因子（rdagent fin_factor_report）使用的全局默认配置实例
FACTOR_FROM_REPORT_PROP_SETTING = FactorFromReportPropSetting()
# 模型自动研发（rdagent fin_model）
MODEL_PROP_SETTING = ModelBasePropSetting()
# 因子+模型联合（rdagent fin_quant）
QUANT_PROP_SETTING = QuantBasePropSetting()
