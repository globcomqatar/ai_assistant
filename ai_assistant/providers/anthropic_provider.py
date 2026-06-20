"""
Anthropic (Claude) provider — uses the official anthropic Python SDK.

JSON output is enforced via:
  1. Strong system-prompt instruction.
  2. Assistant pre-fill technique: we start the assistant turn with "{" so
     Claude is forced to continue a JSON object.
"""

from __future__ import annotations

from ai_assistant.providers.base import AIProvider, AIResponse

# Cost per 1 000 tokens (input, output) in USD
_PRICING: dict[str, tuple[float, float]] = {
	"claude-opus-4-8":              (0.015,   0.075),
	"claude-sonnet-4-6":            (0.003,   0.015),
	"claude-3-5-sonnet-20241022":   (0.003,   0.015),
	"claude-3-5-haiku-20241022":    (0.0008,  0.004),
	"claude-3-opus-20240229":       (0.015,   0.075),
	"claude-3-haiku-20240307":      (0.00025, 0.00125),
}
_DEFAULT_PRICING = (0.003, 0.015)


class AnthropicProvider(AIProvider):
	def __init__(self, api_key: str, model: str):
		# Lazy import so `anthropic` is only required when Claude is actually used
		from anthropic import Anthropic
		self._client = Anthropic(api_key=api_key)
		self.model = model

	def chat(
		self,
		messages: list[dict],
		system_prompt: str,
		tools_schema: list[dict] | None = None,
	) -> AIResponse:
		# Anthropic separates system from conversation messages
		# Pre-fill the assistant turn with "{" to force JSON output
		anthropic_messages = [
			*messages,
			{"role": "assistant", "content": "{"},
		]

		response = self._client.messages.create(
			model=self.model,
			max_tokens=2048,
			system=system_prompt + "\n\nIMPORTANT: Your response must start with '{' and be valid JSON only.",
			messages=anthropic_messages,
		)

		# The model continues from "{" — prepend it back
		raw = "{" + (response.content[0].text if response.content else "")

		usage = response.usage
		tokens_prompt = usage.input_tokens if usage else 0
		tokens_completion = usage.output_tokens if usage else 0

		return AIResponse(
			raw_text=raw,
			tokens_prompt=tokens_prompt,
			tokens_completion=tokens_completion,
			tokens_total=tokens_prompt + tokens_completion,
			estimated_cost_usd=self.estimate_cost(tokens_prompt, tokens_completion),
			model=self.model,
		)

	def estimate_cost(self, tokens_prompt: int, tokens_completion: int) -> float:
		price_in, price_out = _DEFAULT_PRICING
		for key, pricing in _PRICING.items():
			if self.model.startswith(key):
				price_in, price_out = pricing
				break
		return round((tokens_prompt * price_in + tokens_completion * price_out) / 1000, 8)
