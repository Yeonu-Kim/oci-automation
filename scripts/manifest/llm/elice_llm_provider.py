from openai import OpenAI

from .base_llm_provider import BaseLLMProvider


class EliceLLMProvider(BaseLLMProvider):
    def __init__(self, base_url: str, api_key: str) -> None:
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def generate(self, system_prompt: str, user_content: str) -> str:
        response = self._client.chat.completions.create(
            model="anthropic/claude-sonnet-4-5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=8192,
            temperature=0.1,
        )
        return response.choices[0].message.content
