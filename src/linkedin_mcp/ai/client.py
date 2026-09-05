"""
Multi-provider LLM client supporting Google Gemini and local Ollama.
"""

import logging
from typing import Optional, Dict, Any
import httpx

from linkedin_mcp.ai.settings import load_settings

logger = logging.getLogger("linkedin-mcp.ai.client")


class LLMClient:
    """Unified LLM inference client for Gemini and local Ollama."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.settings = settings or load_settings()

    async def generate(
        self,
        prompt: str,
        system_instruction: str = "",
        temperature: float = 0.7,
    ) -> str:
        """Generate a response using the configured LLM provider."""
        # Reload latest settings in case user updated API key via UI
        self.settings = load_settings()
        provider = self.settings.get("llm_provider", "gemini").lower()

        if provider == "gemini":
            return await self._generate_gemini(prompt, system_instruction, temperature)
        elif provider == "ollama":
            return await self._generate_ollama(prompt, system_instruction, temperature)
        else:
            return f"❌ Unknown LLM provider: '{provider}'. Please select 'gemini' or 'ollama' in Settings."

    async def _generate_gemini(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float,
    ) -> str:
        api_key = (self.settings.get("gemini_api_key") or "").strip()
        if not api_key:
            return (
                "⚠️ **Gemini API Key Needed**\n\n"
                "Please configure your **Google Gemini API Key** in the **Settings** tab above "
                "or add `GEMINI_API_KEY=your_key` to your `.env` file.\n\n"
                "👉 Get your free API key at [Google AI Studio](https://aistudio.google.com/)."
            )

        model_name = self.settings.get("gemini_model", "gemini-1.5-flash")

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)

            config = types.GenerateContentConfig(
                temperature=temperature,
            )
            if system_instruction:
                config.system_instruction = system_instruction

            response = await client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            return response.text or "*(No response received from Gemini)*"

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Gemini generation error: {err_msg}", exc_info=True)
            if "API_KEY_INVALID" in err_msg or "400" in err_msg and "API key" in err_msg:
                return (
                    "❌ **Invalid Gemini API Key**\n\n"
                    "The provided Gemini API key was rejected by Google. "
                    "Please verify your key in the **Settings** tab."
                )
            return f"❌ **Gemini Error:** {err_msg}"

    async def _generate_ollama(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float,
    ) -> str:
        ollama_url = self.settings.get("ollama_url", "http://localhost:11434").rstrip("/")
        model = self.settings.get("ollama_model", "llama3.1")

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature},
                }
                if system_instruction:
                    payload["system"] = system_instruction

                resp = await client.post(f"{ollama_url}/api/generate", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("response", "")
                else:
                    return f"❌ Ollama HTTP {resp.status_code}: {resp.text}"
        except httpx.ConnectError:
            return (
                f"❌ **Could not connect to Ollama** at `{ollama_url}`.\n\n"
                "Please make sure Ollama is running locally (`ollama serve` or open Ollama app) "
                f"and that model `{model}` is pulled (`ollama pull {model}`)."
            )
        except Exception as e:
            return f"❌ **Ollama Error:** {str(e)}"
