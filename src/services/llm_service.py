import httpx
import logging
import re
from tenacity import retry, stop_after_attempt, wait_exponential
from src.config.settings import settings
from typing import List, Dict, Optional

logger = logging.getLogger("healthy_rag")

class LLMService:
    def __init__(self):
        # DeepSeek Config
        self.ds_api_key = settings.DEEP_SEEK_API_KEY
        self.ds_base_url = "https://api.deepseek.com"
        self.ds_timeout = settings.DEEP_SEEK_TIMEOUT
        self.ds_chat_model = "deepseek-chat"
        self.ds_reasoner_model = settings.DEEP_SEEK_MODEL_REASONER

        # Gemini Config
        self.gemini_api_key = settings.GEMINI_API_KEY
        self.gemini_base_url = settings.GEMINI_BASE_URL
        self.gemini_model = settings.GEMINI_MODEL
        self.gemini_timeout = settings.GEMINI_TIMEOUT

        # Compatibility properties for existing code
        self.default_model = "deepseek-chat"  # Used as fallback/identifier
        self.reasoner_model = settings.DEEP_SEEK_MODEL_REASONER

    @retry(
        stop=stop_after_attempt(2), # Try Gemini twice before failing over
        wait=wait_exponential(multiplier=1, min=2, max=5)
    )
    async def _call_gemini(
        self,
        messages: List[Dict[str, str]],
        thinking_level: str = "low",
        temperature: float = 1.0,
        max_tokens: int = 4000,
    ) -> str:
        if not self.gemini_api_key:
            raise ValueError("Gemini API Key not configured")

        url = f"{self.gemini_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.gemini_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.gemini_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "extra_body": {
                "thinking_level": thinking_level
            }
        }

        import time
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=self.gemini_timeout) as client:
            logger.info(f"[TIMING] Calling Gemini API ({thinking_level} thinking, max_tokens={max_tokens}, timeout={self.gemini_timeout}s)...")
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            except httpx.TimeoutException as te:
                logger.error(f"[GEMINI] Timeout after {self.gemini_timeout}s: {te}")
                raise
            except httpx.HTTPStatusError as he:
                logger.error(f"[GEMINI] HTTP error {he.response.status_code}: {he.response.text[:500]}")
                raise
            
            result = response.json()
            if not result.get("choices") or not result["choices"][0].get("message"):
                logger.error(f"[GEMINI] Unexpected response structure: {str(result)[:500]}")
                raise ValueError(f"Gemini returned unexpected response: {str(result)[:200]}")
            content = result["choices"][0]["message"]["content"].strip()
            
            elapsed = time.time() - start_time
            logger.info(f"[TIMING] Gemini API responded in {elapsed:.2f}s")
            
            # Strip <think> tags if present (multiple strategies)
            # Strategy 1: Remove complete <think>...</think> blocks (greedy match)
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
            
            # Strategy 2: Remove unclosed <think> tags (from <think> to end of string)
            content = re.sub(r"<think>.*$", "", content, flags=re.DOTALL | re.IGNORECASE)
            
            # Strategy 3: Remove any standalone </think> tags
            content = re.sub(r"</think>", "", content, flags=re.IGNORECASE)
            
            # Strategy 4: Remove any remaining <think> tags (without content)
            content = re.sub(r"<think>", "", content, flags=re.IGNORECASE)
            
            # Clean up multiple newlines and whitespace
            content = re.sub(r"\n\s*\n\s*\n+", "\n\n", content)
            content = content.strip()
            
            # Log if thinking content was detected and removed
            if "<think>" in result["choices"][0]["message"]["content"].lower():
                logger.info("[FILTER] Removed <think> tags from response")
            
            # Some upstream gateways may return a sentinel string instead of a normal answer
            # when content is blocked by safety policy. Treat it as a failure so that
            # `chat_completion()` can fall back to DeepSeek automatically.
            if content.strip().upper() == "PROHIBITED_CONTENT":
                logger.warning("[GEMINI] Upstream returned PROHIBITED_CONTENT sentinel; fallback")
                raise ValueError("Gemini returned PROHIBITED_CONTENT sentinel")
            
            return content

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5)
    )
    async def _call_deepseek(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: Optional[float] = None,
        max_tokens: int = 4000,
    ) -> str:
        if not self.ds_api_key:
            raise ValueError("DeepSeek API Key not configured")

        url = f"{self.ds_base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.ds_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        if temperature is not None:
            payload["temperature"] = temperature

        async with httpx.AsyncClient(timeout=self.ds_timeout) as client:
            logger.info(f"Calling DeepSeek API ({model})...")
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = None,
        model: str = None, # Keeps compatibility, used to determine intent if thinking_level not explicit
        thinking_level: str = "low" # "low" for chat, "high" for report
    ) -> str:
        """
        Unified Chat Completion
        Prioritizes Gemini (with thinking_level).
        Falls back to DeepSeek if Gemini fails.
        """
        
        # Construct messages
        final_messages = []
        if system_prompt:
            final_messages.append({"role": "system", "content": system_prompt})
        final_messages.extend(messages)

        # Determine config based on usage context
        # If model was passed as 'deepseek-reasoner', it implies high reasoning (Report)
        # If model was passed as 'deepseek-chat' or None, it implies low reasoning (Chat)
        
        effective_thinking_level = thinking_level
        
        # Try Gemini First
        try:
            return await self._call_gemini(
                messages=final_messages,
                thinking_level=effective_thinking_level
            )
        except Exception as e:
            logger.error(f"Gemini API failed: {str(e)}. Falling back to DeepSeek.")
            
            # Fallback Logic
            fallback_model = self.ds_chat_model
            fallback_temp = 0.7
            
            if effective_thinking_level == "high":
                fallback_model = self.ds_reasoner_model
                fallback_temp = None # Reasoner doesn't support temperature
            
            return await self._call_deepseek(
                messages=final_messages,
                model=fallback_model,
                temperature=fallback_temp
            )

    async def gemini_completion(
        self,
        *,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        thinking_level: str = "high",
        temperature: float = 0.7,
        max_tokens: int = 8000,
    ) -> str:
        """强制使用 Gemini（不做 DeepSeek fallback）。"""
        final_messages: List[Dict[str, str]] = []
        if system_prompt:
            final_messages.append({"role": "system", "content": system_prompt})
        final_messages.extend(messages)
        return await self._call_gemini(
            messages=final_messages,
            thinking_level=thinking_level,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def deepseek_completion(
        self,
        *,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """强制使用 DeepSeek（不走 Gemini）。"""
        final_messages: List[Dict[str, str]] = []
        if system_prompt:
            final_messages.append({"role": "system", "content": system_prompt})
        final_messages.extend(messages)
        return await self._call_deepseek(
            messages=final_messages,
            model=model or self.ds_chat_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

llm_service = LLMService()
