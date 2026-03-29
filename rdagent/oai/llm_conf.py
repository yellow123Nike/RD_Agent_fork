"""
大语言模型与 Embedding 相关配置（LLMSettings）。

通过环境变量覆盖默认值；与 LiteLLM / 旧版 DeprecBackend 等后端共用字段。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from rdagent.core.conf import ExtendedBaseSettings


class LLMSettings(ExtendedBaseSettings):
    """LLM 聊天、Embedding、缓存、Azure/GCR 等统一配置。"""

    backend: str = "rdagent.oai.backend.LiteLLMAPIBackend"
    """APIBackend 实现类的全路径，默认 LiteLLM。"""

    chat_model: str = "gpt-4-turbo"
    """聊天补全使用的模型名（LiteLLM 需带提供商前缀时按文档配置）。"""

    embedding_model: str = "text-embedding-3-small"
    """Embedding 模型名。"""

    reasoning_effort: Literal["low", "medium", "high"] | None = None
    """部分推理模型支持的 reasoning 强度（如 o 系列）。"""

    enable_response_schema: bool = True
    """是否对聊天启用结构化 response_schema；不支持该能力的模型会自动忽略。"""

    reasoning_think_rm: bool = False
    """为 True 时从模型回复中去除 </think> 包裹的思考片段，避免干扰主输出。"""

    log_llm_chat_content: bool = True
    """是否在日志中打印完整聊天内容（调试方便，生产可关）。"""

    use_azure: bool = Field(default=False, deprecated=True)
    """已弃用：请用 chat_use_azure / embedding_use_azure。"""

    chat_use_azure: bool = False
    """聊天是否走 Azure OpenAI。"""

    embedding_use_azure: bool = False
    """Embedding 是否走 Azure OpenAI。"""

    chat_use_azure_token_provider: bool = False
    """聊天是否使用 Azure AD Token Provider 而非静态 API Key。"""

    embedding_use_azure_token_provider: bool = False
    """Embedding 是否使用 Azure AD Token Provider。"""

    managed_identity_client_id: str | None = None
    """托管身份客户端 ID（与 Azure 认证配合）。"""

    max_retry: int = 10
    """调用失败时的最大重试次数。"""

    retry_wait_seconds: int = 1
    """重试间隔秒数。"""

    dump_chat_cache: bool = False
    """是否把聊天缓存写入持久化存储。"""

    use_chat_cache: bool = False
    """是否启用聊天结果缓存。"""

    dump_embedding_cache: bool = False
    """是否把 embedding 缓存写入持久化。"""

    use_embedding_cache: bool = False
    """是否启用 embedding 缓存。"""

    prompt_cache_path: str = str(Path.cwd() / "prompt_cache.db")
    """Prompt 缓存 SQLite 路径。"""

    max_past_message_include: int = 10
    """构造上下文时最多包含的历史消息条数。"""

    timeout_fail_limit: int = 10
    """超时类失败累计容忍次数相关上限（见后端实现）。"""

    violation_fail_limit: int = 1
    """策略/安全类违规失败容忍次数。"""

    use_auto_chat_cache_seed_gen: bool = False
    """为 True 时在未显式传 seed 的情况下自动生成缓存种子，使同题不同轮可得到不同默认 seed。"""

    init_chat_cache_seed: int = 42
    """聊天缓存默认随机种子初值。"""

    openai_api_key: str = ""
    """通用 OpenAI 兼容 API Key（聊天与未单独配置时的回退）。"""

    openai_api_base: str = ""
    """通用 OpenAI 兼容 Base URL。"""

    chat_openai_api_key: str | None = None
    """仅聊天使用的 API Key；None 时回退 openai_api_key。"""

    chat_openai_base_url: str | None = None
    """仅聊天使用的 Base URL。"""

    chat_azure_api_base: str = ""
    """Azure 聊天终结点。"""

    chat_azure_api_version: str = ""
    """Azure API 版本。"""

    chat_max_tokens: int | None = None
    """聊天最大生成 token；None 表示由模型默认。"""

    chat_temperature: float = 0.5
    """采样温度。"""

    chat_stream: bool = True
    """是否流式输出聊天结果。"""

    chat_seed: int | None = None
    """可复现采样时的随机种子。"""

    chat_frequency_penalty: float = 0.0
    """频率惩罚。"""

    chat_presence_penalty: float = 0.0
    """存在惩罚。"""

    chat_token_limit: int = 100000
    """建议的聊天上下文 token 上限（用于截断等，随模型能力可调）。"""

    default_system_prompt: str = "You are an AI assistant who helps to answer user's questions."
    """默认系统提示内容。"""

    system_prompt_role: str = "system"
    """系统提示使用的消息角色名（如 o1 等模型不支持 system 时可改为 user）。"""

    embedding_openai_api_key: str = ""
    """专用 Embedding API Key；空则回退 openai_api_key。"""

    embedding_openai_base_url: str = ""
    """专用 Embedding Base URL。"""

    litellm_proxy_api_key: str = ""
    """与 .env.example 中 LITELLM_PROXY_API_KEY 对应：独立 Embedding 服务密钥。"""

    litellm_proxy_api_base: str = ""
    """与 LITELLM_PROXY_API_BASE 对应：独立 Embedding 服务地址。"""

    embedding_azure_api_base: str = ""
    """Embedding 的 Azure 终结点。"""

    embedding_azure_api_version: str = ""
    """Embedding 的 Azure API 版本。"""

    embedding_max_str_num: int = 50
    """单次 embedding 请求最多拼接的字符串段数（批处理上限）。"""

    embedding_max_length: int = 8192
    """单段文本用于 embedding 的最大长度相关配置（与截断逻辑配合）。"""

    use_llama2: bool = False
    """是否启用离线 Llama2 路径。"""

    llama2_ckpt_dir: str = "Llama-2-7b-chat"
    """Llama2 权重目录。"""

    llama2_tokenizer_path: str = "Llama-2-7b-chat/tokenizer.model"
    """Llama2 分词器路径。"""

    llams2_max_batch_size: int = 8
    """Llama2 批大小（字段名沿用历史拼写 llams2）。"""

    use_gcr_endpoint: bool = False
    """是否使用 GCR 等托管推理端点。"""

    gcr_endpoint_type: str = "llama2_70b"
    """GCR 端点类型：llama2_70b、llama3_70b、phi2、phi3_4k、phi3_128k 等。"""

    llama2_70b_endpoint: str = ""
    llama2_70b_endpoint_key: str = ""
    llama2_70b_endpoint_deployment: str = ""

    llama3_70b_endpoint: str = ""
    llama3_70b_endpoint_key: str = ""
    llama3_70b_endpoint_deployment: str = ""

    phi2_endpoint: str = ""
    phi2_endpoint_key: str = ""
    phi2_endpoint_deployment: str = ""

    phi3_4k_endpoint: str = ""
    phi3_4k_endpoint_key: str = ""
    phi3_4k_endpoint_deployment: str = ""

    phi3_128k_endpoint: str = ""
    phi3_128k_endpoint_key: str = ""
    phi3_128k_endpoint_deployment: str = ""

    gcr_endpoint_temperature: float = 0.7
    gcr_endpoint_top_p: float = 0.9
    gcr_endpoint_do_sample: bool = False
    gcr_endpoint_max_token: int = 100

    chat_use_azure_deepseek: bool = False
    """是否通过 Azure 上的 DeepSeek 部署聊天。"""

    chat_azure_deepseek_endpoint: str = ""
    chat_azure_deepseek_key: str = ""

    chat_model_map: dict[str, dict[str, str]] = {}
    """按日志 tag 等映射到不同 chat_model / 温度等，用于多场景细粒度覆盖。"""


LLM_SETTINGS = LLMSettings()
