"""
OpenAI SDK-based provider — handles OpenAI, OpenRouter, Groq, and Google Gemini.
All four expose an OpenAI-compatible REST interface.
"""

from __future__ import annotations

from openai import OpenAI

from ai_assistant.providers.base import AIProvider, AIResponse

# Cost per 1 000 tokens (input, output) in USD.
# OpenRouter prices vary by model; the entries below cover direct-API pricing.
_PRICING: dict[str, tuple[float, float]] = {
	# OpenAI
	"gpt-4o":               (0.005,    0.015),
	"gpt-4o-mini":          (0.000150, 0.000600),
	"gpt-4-turbo":          (0.010,    0.030),
	"gpt-3.5-turbo":        (0.0005,   0.0015),
	"o1-mini":              (0.003,    0.012),
	"o1-preview":           (0.015,    0.060),
	# Google Gemini
	"gemini-2.0-flash":     (0.000075, 0.000300),
	"gemini-2.0-flash-lite":(0.000038, 0.000150),
	"gemini-1.5-flash":     (0.000075, 0.000300),
	"gemini-1.5-pro":       (0.00125,  0.005),
	# Groq (per-1K tokens — very cheap)
	"llama-3.3-70b-versatile": (0.00059, 0.00079),
	"llama-3.1-70b-versatile": (0.00059, 0.00079),
	"llama-3.1-8b-instant":    (0.00005, 0.00008),
	"mixtral-8x7b-32768":      (0.00024, 0.00024),
	"gemma2-9b-it":            (0.00020, 0.00020),
}
_DEFAULT_PRICING = (0.001, 0.002)

# Providers that do NOT support json_object response format (fall back to prompt-only)
_NO_JSON_MODE_PROVIDERS: set[str] = set()  # all current providers support it (with retry)


class OpenAICompatibleProvider(AIProvider):
	def __init__(
		self,
		api_key: str,
		model: str,
		base_url: str | None = None,
		provider_tag: str = "openai",
		extra_headers: dict | None = None,
	):
		client_kwargs: dict = {"api_key": api_key}
		if base_url:
			client_kwargs["base_url"] = base_url
		if extra_headers:
			client_kwargs["default_headers"] = extra_headers

		self._client = OpenAI(**client_kwargs)
		self.model = model
		self.provider_tag = provider_tag
		self._use_json_mode = provider_tag not in _NO_JSON_MODE_PROVIDERS

	def chat(
		self,
		messages: list[dict],
		system_prompt: str,
		tools_schema: list[dict] | None = None,
	) -> AIResponse:
		full_messages = [{"role": "system", "content": system_prompt}, *messages]

		call_kwargs: dict = {
			"model": self.model,
			"messages": full_messages,
			"temperature": 0,
			"max_tokens": 2048,
		}

		if self._use_json_mode:
			call_kwargs["response_format"] = {"type": "json_object"}

		try:
			response = self._client.chat.completions.create(**call_kwargs)
		except Exception:
			# Retry without json_mode if the provider rejected it
			call_kwargs.pop("response_format", None)
			response = self._client.chat.completions.create(**call_kwargs)

		choice = response.choices[0]
		usage = response.usage
		tokens_prompt = usage.prompt_tokens if usage else 0
		tokens_completion = usage.completion_tokens if usage else 0
		tokens_total = usage.total_tokens if usage else 0

		return AIResponse(
			raw_text=choice.message.content or "",
			tokens_prompt=tokens_prompt,
			tokens_completion=tokens_completion,
			tokens_total=tokens_total,
			estimated_cost_usd=self.estimate_cost(tokens_prompt, tokens_completion),
			model=getattr(response, "model", self.model),
		)

	def estimate_cost(self, tokens_prompt: int, tokens_completion: int) -> float:
		# Best-match pricing key (models may have date suffixes)
		price_in, price_out = _DEFAULT_PRICING
		for key, pricing in _PRICING.items():
			if self.model.startswith(key):
				price_in, price_out = pricing
				break
		return round((tokens_prompt * price_in + tokens_completion * price_out) / 1000, 8)
