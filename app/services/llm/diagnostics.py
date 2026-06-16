from app.services.llm.llm_factory import create_llm_service


def ping_llm(
    backend: str | None = None,
    prompt: str = "Ответь одним словом: ping",
) -> dict:
    try:
        llm = create_llm_service(backend=backend)
        text = llm.generate(prompt, max_new_tokens=16)
    except Exception as error:
        return {
            "status": "error",
            "error": str(error),
        }

    return {
        "status": "ok",
        "text": text,
    }
