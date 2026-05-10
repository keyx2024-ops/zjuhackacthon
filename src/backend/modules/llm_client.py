"""
统一的 LLM 客户端封装

- 支持任意 OpenAI 兼容端点（pincc.ai / 官方 OpenAI / vLLM 等）
- 统一 system + user prompt 调用接口
- 返回 (text, usage_dict) 元组，兼容现有调用
- 未配置 api key / base url 时 client 为 None，上层走 mock 分支
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from config import settings


logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI 兼容 LLM 客户端"""

    def __init__(self):
        self._client = None
        self._model = settings.model_name

        if settings.provider_auth_token and settings.provider_base_url:
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    base_url=settings.provider_base_url.rstrip("/") + "/v1",
                    api_key=settings.provider_auth_token,
                    timeout=settings.llm_timeout,
                )
                logger.info(
                    f"LLM client initialized: base_url={settings.provider_base_url}, "
                    f"model={self._model}"
                )
            except ImportError:
                logger.error("openai SDK not installed; run: pip install openai")
                self._client = None
        else:
            logger.warning("LLM client not configured (PROVIDER_BASE_URL / PROVIDER_AUTH_TOKEN missing)")

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def model(self) -> str:
        return self._model

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> Tuple[str, dict]:
        """
        发起一次聊天补全请求

        Returns:
            (content_text, {"input_tokens": int, "output_tokens": int})
        """
        if not self._client:
            raise RuntimeError("LLM client is not configured")

        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = response.choices[0].message.content or ""
        usage = {}
        if response.usage is not None:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }
        return text, usage


llm_client = LLMClient()
