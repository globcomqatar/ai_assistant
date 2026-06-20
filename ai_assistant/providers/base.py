from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AIResponse:
	raw_text: str
	tokens_prompt: int
	tokens_completion: int
	tokens_total: int
	estimated_cost_usd: float
	model: str


class AIProvider(ABC):
	"""Abstract base class for all AI provider integrations."""

	@abstractmethod
	def chat(
		self,
		messages: list[dict],
		system_prompt: str,
		tools_schema: list[dict] | None = None,
	) -> AIResponse:
		"""Send messages to the AI and return a structured response."""
		...

	@abstractmethod
	def estimate_cost(self, tokens_prompt: int, tokens_completion: int) -> float:
		"""Estimate USD cost for given token counts."""
		...
