import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password

# Maps provider name → (api_key_field, model_field)
_PROVIDER_FIELDS: dict[str, tuple[str, str]] = {
	"OpenRouter":         ("openrouter_api_key", "openrouter_model"),
	"OpenAI":             ("openai_api_key",      "openai_model"),
	"Claude (Anthropic)": ("anthropic_api_key",   "claude_model"),
	"Groq":               ("groq_api_key",         "groq_model"),
	"Google Gemini":      ("google_api_key",        "google_model"),
}


class AISettings(Document):
	def validate(self):
		if self.enabled:
			fields = _PROVIDER_FIELDS.get(self.provider)
			if not fields:
				frappe.throw(_("Unknown provider '{0}'.").format(self.provider))

			key_field, model_field = fields
			# During save the form populates self with the typed value; if it's
			# still empty the user hasn't entered a key yet.
			if not (self.get(key_field) or self._stored_api_key(key_field)):
				frappe.throw(_(
					"API Key for {0} is required. Enter it in the '{0}' section."
				).format(self.provider))

			if not self.get(model_field):
				frappe.throw(_("Please select a model for {0}.").format(self.provider))

		if self.max_monthly_budget and self.max_monthly_budget < 0:
			frappe.throw(_("Max Monthly Budget cannot be negative."))

	# ── Public helpers called by providers/__init__.py ──────────────────────────

	def get_active_api_key(self) -> str:
		"""
		Return the decrypted API key for the active provider.

		We bypass Document.get_password() because for Single DocTypes loaded via
		frappe.get_single(), Password fields are NOT populated in the document
		object — they live in __Auth, not tabSingles.  get_password() guards on
		self.get(fieldname) which is always falsy here, causing a silent exception.
		"""
		key_field, _ = self._provider_fields()
		return self._stored_api_key(key_field) if key_field else ""

	def get_active_model(self) -> str:
		"""Return the model name for the active provider."""
		_, model_field = self._provider_fields()
		return self.get(model_field) or "" if model_field else ""

	def get_voice_api_key(self) -> str:
		"""Return the decrypted API key for the configured voice provider."""
		return self._stored_api_key("voice_api_key")

	# ── Private ─────────────────────────────────────────────────────────────────

	def _provider_fields(self) -> tuple[str | None, str | None]:
		"""Return (key_field, model_field) for the active provider."""
		fields = _PROVIDER_FIELDS.get(self.provider or "")
		return fields if fields else (None, None)

	def _stored_api_key(self, key_field: str) -> str:
		"""Read decrypted password directly from __Auth, never from self.*."""
		try:
			return get_decrypted_password(
				"AI Settings", "AI Settings", key_field, raise_exception=False
			) or ""
		except Exception:
			return ""
