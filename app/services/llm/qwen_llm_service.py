import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


class QwenLLMService:
    def __init__(
        self,
        model_path: str,
        torch_dtype=torch.float16,
    ):
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            local_files_only=True,
        )

        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch_dtype,
            device_map="auto",
            trust_remote_code=True,
            local_files_only=True,
        )

        self.model.eval()

    def generate(self, prompt: str, max_new_tokens: int = 1200) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты агент для подготовки event log в process mining. "
                    "Не выдумывай факты. Если данных не хватает, скажи об этом."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
        ).to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )

        generated_ids = outputs[0][inputs["input_ids"].shape[-1]:]

        answer = self.tokenizer.decode(
            generated_ids,
            skip_special_tokens=True,
        )

        return answer.strip()
