from loguru import logger
from langchain_community.chat_models import ChatOllama, ChatOpenAI
from langchain_core.language_models import BaseLanguageModel
from langchain_core.embeddings import Embeddings as BaseEmbeddings
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_ollama import OllamaEmbeddings

from .config import AgentProfile, LLMSettings, LLMProvider, LLMProfile, EmbeddingProfile


def create_llm_instance(
    agent_profile: AgentProfile,
    llm_profile_config: LLMProfile,
    global_settings: LLMSettings,
) -> BaseLanguageModel:
    """为 Agent 创建并返回一个 LangChain LLM 实例"""
    logger.info(f"为 Agent '{agent_profile.name}' (ID: {agent_profile.agent_id}) 创建 LLM 实例...")

    provider = llm_profile_config.provider
    model = llm_profile_config.model
    temperature = llm_profile_config.temperature

    logger.debug(f"  Provider: {provider.value}, Model: {model}, Temp: {temperature}")

    if provider == LLMProvider.OLLAMA:
        return ChatOllama(
            model=model,
            base_url=global_settings.ollama_base_url,
            temperature=temperature,
        )

    elif provider == LLMProvider.OPENAI_COMPATIBLE:
        api_key_str = None
        key_env_var_name = llm_profile_config.api_key_env_var

        if not key_env_var_name:
            logger.error(f"Agent '{agent_profile.name}' 使用 openai_compatible，但未在 llm_profiles 中配置 'api_key_env_var'")
            raise ValueError(f"配置 {agent_profile.llm_profile_name} 缺少 api_key_env_var")
        try:
            api_key_str = getattr(global_settings, key_env_var_name.lower())
        except AttributeError:
            logger.error(f"在 .env (LLMSettings) 中找不到名为 '{key_env_var_name}' (或 {key_env_var_name.lower()}) 的 API 密钥")
            raise
        if not api_key_str:
            raise ValueError(f"在 .env 中找到了 {key_env_var_name}，但其值为空。")
        base_url = llm_profile_config.base_url

        if not base_url:
            logger.warning(f"Agent '{agent_profile.name}' 未在 JSON 中提供 base_url，将使用 LangChain 的 OpenAI 默认地址。")

        logger.info(f"  > 正在连接到 OpenAI 兼容端点: {base_url or '默认'}")
        return ChatOpenAI(
            model=model,
            api_key=api_key_str,
            base_url=base_url,
            temperature=temperature,
        )
    else:
        logger.error(f"不支持的 LLM 供应商: {provider}")
        raise NotImplementedError(f"未实现 {provider} 的 LLM 工厂")


def create_embedding_function(embedding_profile: EmbeddingProfile, global_settings: LLMSettings) -> BaseEmbeddings:
    """为 MemorySystem 创建一个嵌入函数实例"""
    provider = embedding_profile.provider
    model = embedding_profile.model

    logger.info(f"正在为 MemorySystem 创建嵌入函数 (Provider: {provider.value}, Model: {model})")

    if provider == LLMProvider.OLLAMA:
        return OllamaEmbeddings(model=model, base_url=global_settings.ollama_base_url)
    elif provider == LLMProvider.OPENAI_COMPATIBLE:
        api_key_str = None
        key_env_var_name = embedding_profile.api_key_env_var

        if not key_env_var_name:
            raise ValueError(f"嵌入配置 {embedding_profile.model} 缺少 'api_key_env_var'")

        try:
            api_key_str = getattr(global_settings, key_env_var_name.lower())
        except AttributeError:
            raise ValueError(f"在 .env (LLMSettings) 中找不到嵌入密钥 '{key_env_var_name}'")

        if not api_key_str:
            raise ValueError(f"在 .env 中找到了 {key_env_var_name}，但其值为空。")

        base_url = embedding_profile.base_url
        logger.info(f"  > 正在连接到 OpenAI 兼容的嵌入端点: {base_url or '默认'}")
        return OpenAIEmbeddings(model=model, api_key=api_key_str, base_url=base_url)

    else:
        raise NotImplementedError(f"未实现 {provider} 的嵌入函数")
