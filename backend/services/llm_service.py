from backend.core.config import settings
from backend.core.logging import logger


def get_llm():
    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        logger.info("llm.provider", provider="anthropic", model=settings.anthropic_model)
        return ChatAnthropic(
            model=settings.anthropic_model,
            anthropic_api_key=settings.anthropic_api_key,
            temperature=0,
        )
    elif settings.llm_provider == "groq":
        from langchain_groq import ChatGroq
        logger.info("llm.provider", provider="groq", model=settings.groq_model)
        return ChatGroq(
            model=settings.groq_model,
            groq_api_key=settings.groq_api_key,
            temperature=0,
        )
    else:
        from langchain_ollama import ChatOllama
        logger.info("llm.provider", provider="ollama", model=settings.ollama_model)
        return ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0,
        )


llm = get_llm()