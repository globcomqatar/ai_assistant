"""
providers/__init__.py — factory that reads AI Settings and returns the right provider.
"""

from __future__ import annotations

import frappe

from ai_assistant.providers.base import AIProvider

# OpenRouter base URL
_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
# Google Gemini OpenAI-compatible endpoint
_GOOGLE_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
# Groq OpenAI-compatible endpoint
_GROQ_BASE = "https://api.groq.com/openai/v1"


def get_provider() -> AIProvider:
	"""
	Read AI Settings and instantiate the correct AI provider.
	Raises frappe.ValidationError if settings are incomplete.
	"""
	settings = frappe.get_single("AI Settings")

	if not settings.enabled:
		frappe.throw(frappe._("AI Assistant is disabled. Enable it in AI Settings."))

	provider_name: str = settings.provider or "OpenRouter"
	api_key: str = settings.get_active_api_key()
	model: str = settings.get_active_model()

	if not api_key:
		frappe.throw(frappe._(
			"No API key configured for {0}. Set it in AI Settings."
		).format(provider_name))

	if not model:
		frappe.throw(frappe._("No model selected for {0}.").format(provider_name))

	return _build_provider(provider_name, api_key, model)


def _build_provider(provider_name: str, api_key: str, model: str) -> AIProvider:
	from ai_assistant.providers.openai_compatible import OpenAICompatibleProvider
	from ai_assistant.providers.anthropic_provider import AnthropicProvider

	if provider_name == "OpenAI":
		return OpenAICompatibleProvider(
			api_key=api_key,
			model=model,
			provider_tag="openai",
		)

	if provider_name == "OpenRouter":
		return OpenAICompatibleProvider(
			api_key=api_key,
			model=model,
			base_url=_OPENROUTER_BASE,
			provider_tag="openrouter",
			extra_headers={
				"HTTP-Referer": "https://erpnext.com",
				"X-Title": "ERPNext AI Assistant",
			},
		)

	if provider_name == "Groq":
		return OpenAICompatibleProvider(
			api_key=api_key,
			model=model,
			base_url=_GROQ_BASE,
			provider_tag="groq",
		)

	if provider_name == "Google Gemini":
		return OpenAICompatibleProvider(
			api_key=api_key,
			model=model,
			base_url=_GOOGLE_BASE,
			provider_tag="google",
		)

	if provider_name == "Claude (Anthropic)":
		return AnthropicProvider(api_key=api_key, model=model)

	frappe.throw(frappe._("Unknown AI provider: {0}").format(provider_name))
