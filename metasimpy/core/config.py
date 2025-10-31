# metasimpy/core/config.py

from pydantic_settings import BaseSettings
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from pathlib import Path


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"


class LLMSettings(BaseSettings):
    ollama_base_url: str = Field(default="http://localhost:11434", description="本地 Ollama 服务的 URL (从 .env 加载 OLLAMA_BASE_URL)")

    openai_api_key: Optional[str] = Field(default=None)
    deepseek_api_key: Optional[str] = Field(default=None)
    embedding_api_key: Optional[str] = Field(default=None, description="嵌入 API 密钥 (从 .env 加载 EMBEDDING_API_KEY)")

    agent_profiles_config_path: Path = Field(default=Path("data/agent_profiles.json"), description="指向 Agent 配置文件 (json) 的路径")
    agent_persona_dir: Path = Field(default=Path("prompts/persons/"), description="存放 Agent 人设 (.txt) 文件的目录")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
        case_sensitive = False

        @classmethod
        def a_get_current_directory(cls) -> Path:
            return Path(__file__).resolve().parent.parent.parent


class LLMProfile(BaseModel):
    """定义一个可复用的 LLM (聊天) 配置模板。"""

    provider: LLMProvider
    model: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    base_url: Optional[str] = Field(default=None)
    api_key_env_var: Optional[str] = Field(default=None)


class EmbeddingProfile(BaseModel):
    """定义一个可复用的 Embedding (嵌入) 配置模板。"""

    provider: LLMProvider
    model: str
    base_url: Optional[str] = Field(default=None, description="API 请求地址 (例如 https://api.deepseek.com/v1)")
    api_key_env_var: Optional[str] = Field(default=None, description="要从 .env 加载的 API 密钥的 *变量名* (例如 'DEEPSEEK_API_KEY')")


class MemorySettings(BaseModel):
    """
    定义记忆系统（MemorySystem）的全局配置。
    """

    embedding_profile_name: str = Field(description="要使用的嵌入配置文件的名称 (在 embedding_profiles 中定义)")


class AgentProfile(BaseModel):
    """(保持不变)"""

    agent_id: str
    name: str
    persona_file: str
    start_location: str
    llm_profile_name: str

    initial_state: Optional[Dict[str, Any]] = Field(default=None, description="可选：重载 agent 的初始内部状态 (例如 'money': 50)")


class AppConfig(BaseModel):

    llm_profiles: Dict[str, LLMProfile]
    embedding_profiles: Dict[str, EmbeddingProfile] = Field(description="所有可用的 Embedding 配置文件")
    memory_settings: MemorySettings = Field(description="记忆系统的全局设置")
    agents: List[AgentProfile]
