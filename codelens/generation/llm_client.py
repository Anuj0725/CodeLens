import logging
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from codelens.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Async LLM client supporting Gemini, OpenAI, and Anthropic.
    Reads config from settings by default.
    """

    # Google's OpenAI-compatible endpoint
    _GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.provider = provider or settings.llm_provider
        self.model = model or settings.llm_model

        if self.provider == "gemini":
            key = api_key or settings.gemini_api_key
            self._openai = AsyncOpenAI(api_key=key, base_url=self._GEMINI_BASE_URL)
        elif self.provider == "openai":
            key = api_key or settings.openai_api_key
            self._openai = AsyncOpenAI(api_key=key)
        elif self.provider == "anthropic":
            key = api_key or settings.anthropic_api_key
            self._anthropic = AsyncAnthropic(api_key=key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """
        Send a prompt to the LLM and return the response text.
        
        Args:
            prompt: The user message / query with context
            system_prompt: Optional system instruction
            
        Returns:
            The LLM's response text
        """
        try:
            if self.provider in ("openai", "gemini"):
                return await self._generate_openai(prompt, system_prompt)
            else:
                return await self._generate_anthropic(prompt, system_prompt)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    async def _generate_openai(self, prompt: str, system_prompt: str | None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self._openai.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.1,
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""

    async def _generate_anthropic(self, prompt: str, system_prompt: str | None) -> str:
        kwargs = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await self._anthropic.messages.create(**kwargs)
        return response.content[0].text or ""
