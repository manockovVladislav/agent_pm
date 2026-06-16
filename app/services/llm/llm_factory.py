from app.config import KOBOLD_CPP_URL, LLM_BACKEND, QWEN_MODEL_PATH
from app.services.llm.base import LLMService


def _normalize_backend(backend: str | None) -> str:
    return str(backend or "").strip().lower().replace("-", "_")


def _get_backend(backend: str | None = None) -> str:
    return backend or LLM_BACKEND


def create_llm_service(backend: str | None = None) -> LLMService:
    """
    Создает LLM-адаптер по имени backend.

    Поддерживаемые значения:
    - qwen
    - kobold_cpp
    - cobolt_cpp
    """

    backend = _normalize_backend(_get_backend(backend))

    if backend == "qwen":
        from app.services.llm.qwen_llm_service import QwenLLMService

        return QwenLLMService(model_path=QWEN_MODEL_PATH)

    if backend in {"kobold", "koboldcpp", "kobold_cpp", "cobolt", "coboltcpp", "cobolt_cpp"}:
        from app.services.llm.kobold_cpp_llm_service import KoboldCppLLMService

        return KoboldCppLLMService(api_url=KOBOLD_CPP_URL)

    raise ValueError(f"Неизвестный LLM_BACKEND: {backend}")
