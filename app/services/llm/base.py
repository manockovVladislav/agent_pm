from typing import Protocol


class LLMService(Protocol):
    def generate(self, prompt: str, max_new_tokens: int = 1200) -> str:
        ...
