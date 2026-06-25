"""
AI Context Manager

Builds and manages the standardized AIContext object passed to every AI Engine.
Every request that flows through the AI Kernel gets one context that carries
all the information an engine needs — identity, navigation state, conversation,
provider selection, permissions, and feature flags.

Phase 3 will extend this with persistent memory hooks and cross-session context.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass
class AIContext:
    """
    Standardized context object passed to every AI Engine.

    Immutable by convention — use the with_* helpers on AIContextManager
    to create modified copies rather than mutating fields directly.
    """

    # ── Identity ───────────────────────────────────────────────────────────────
    user: str = ""
    roles: list[str] = field(default_factory=list)
    company: str = ""
    language: str = "en"
    timezone: str = "UTC"

    # ── Navigation ────────────────────────────────────────────────────────────
    module: str = ""
    doctype: str = ""
    document: str = ""
    filters: dict[str, Any] = field(default_factory=dict)

    # ── Conversation ──────────────────────────────────────────────────────────
    conversation: list[dict[str, Any]] = field(default_factory=list)

    # ── Provider ──────────────────────────────────────────────────────────────
    provider: str = ""
    model: str = ""

    # ── Authorization ─────────────────────────────────────────────────────────
    permissions: dict[str, Any] = field(default_factory=dict)
    feature_flags: dict[str, bool] = field(default_factory=dict)

    # ── Phase 3: persistent memory (hook registry, not yet implemented) ───────
    memory_hooks: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation (excludes memory_hooks)."""
        return {
            "user": self.user,
            "roles": self.roles,
            "company": self.company,
            "language": self.language,
            "timezone": self.timezone,
            "module": self.module,
            "doctype": self.doctype,
            "document": self.document,
            "filters": self.filters,
            "provider": self.provider,
            "model": self.model,
            "feature_flags": self.feature_flags,
        }


class AIContextManager:
    """Builds, validates, and transforms AIContext objects."""

    def build(
        self,
        *,
        user: str = "",
        roles: list[str] | None = None,
        company: str = "",
        language: str = "en",
        timezone: str = "UTC",
        module: str = "",
        doctype: str = "",
        document: str = "",
        filters: dict[str, Any] | None = None,
        conversation: list[dict[str, Any]] | None = None,
        provider: str = "",
        model: str = "",
        permissions: dict[str, Any] | None = None,
        feature_flags: dict[str, bool] | None = None,
    ) -> AIContext:
        """Build an AIContext from individual keyword arguments."""
        return AIContext(
            user=user,
            roles=roles or [],
            company=company,
            language=language,
            timezone=timezone,
            module=module,
            doctype=doctype,
            document=document,
            filters=filters or {},
            conversation=conversation or [],
            provider=provider,
            model=model,
            permissions=permissions or {},
            feature_flags=feature_flags or {},
        )

    def from_request(self, request: dict[str, Any]) -> AIContext:
        """Build AIContext from a raw request dictionary (e.g. from a Frappe API call)."""
        return self.build(
            user=request.get("user", ""),
            roles=request.get("roles") or [],
            company=request.get("company", ""),
            language=request.get("language", "en"),
            timezone=request.get("timezone", "UTC"),
            module=request.get("module", ""),
            doctype=request.get("doctype", ""),
            document=request.get("document", ""),
            filters=request.get("filters") or {},
            conversation=request.get("conversation") or [],
            provider=request.get("provider", ""),
            model=request.get("model", ""),
            permissions=request.get("permissions") or {},
            feature_flags=request.get("feature_flags") or {},
        )

    def from_frappe_session(self) -> AIContext:
        """Build context from the current Frappe session (requires live Frappe context)."""
        import frappe
        return self.build(
            user=frappe.session.user,
            roles=frappe.get_roles(frappe.session.user),
            company=frappe.defaults.get_user_default("Company") or "",
            language=frappe.local.lang or "en",
            timezone=frappe.utils.get_time_zone() or "UTC",
        )

    def with_conversation(self, ctx: AIContext, messages: list[dict[str, Any]]) -> AIContext:
        """Return a new context with messages appended to the conversation."""
        return replace(ctx, conversation=list(ctx.conversation) + list(messages))

    def with_flags(self, ctx: AIContext, flags: dict[str, bool]) -> AIContext:
        """Return a new context with feature flags merged (overrides existing keys)."""
        return replace(ctx, feature_flags={**ctx.feature_flags, **flags})

    def with_provider(self, ctx: AIContext, provider: str, model: str = "") -> AIContext:
        """Return a new context with a specific provider/model selected."""
        return replace(ctx, provider=provider, model=model)


# Module-level singleton
context_manager = AIContextManager()
