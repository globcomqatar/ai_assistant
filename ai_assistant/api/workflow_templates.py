"""Workflow template helpers for AI recommendations."""

from __future__ import annotations

from ai_assistant.api.action_handlers import parse_payload, text
from ai_assistant.api.workflow_registry import get_workflow, get_workflow_registry


KEYWORD_WORKFLOWS = [
	("collection_recovery", ("collection", "overdue", "invoice", "receivable", "payment")),
	("quotation_follow_up", ("quotation", "quote")),
	("customer_follow_up", ("customer",)),
	("workshop_reminder", ("workshop", "work order", "maintenance")),
	("inventory_review", ("inventory", "stock", "warehouse", "item")),
	("purchase_follow_up", ("purchase", "supplier", "buying")),
	("sales_opportunity", ("opportunity", "sales pipeline", "deal")),
	("lead_qualification", ("lead", "qualification")),
	("notification_workflow", ("notify", "notification")),
	("reminder_workflow", ("reminder", "due")),
]


def infer_workflow_id(payload: dict) -> str:
	explicit = text(payload.get("workflow_id"), 120)
	if explicit and get_workflow(explicit):
		return explicit
	haystack = " ".join(str(payload.get(key) or "") for key in (
		"title", "action", "description", "business_impact", "doctype", "related_doctype"
	)).lower()
	for workflow_id, keywords in KEYWORD_WORKFLOWS:
		if any(keyword in haystack for keyword in keywords):
			return workflow_id
	return "reminder_workflow"


def workflow_payload(workflow_id: str | None, recommendation_payload=None) -> tuple[dict, dict]:
	payload = parse_payload(recommendation_payload)
	if payload.get("assigned_user") and not payload.get("user"):
		payload["user"] = payload.get("assigned_user")
	workflow = get_workflow(workflow_id or infer_workflow_id(payload))
	if not workflow:
		workflow = get_workflow("reminder_workflow") or get_workflow_registry()[0]
	return workflow, payload


def populate_steps(workflow: dict, payload: dict) -> list[dict]:
	steps = []
	custom_steps = payload.get("steps") if isinstance(payload.get("steps"), list) else []
	source_steps = custom_steps or workflow.get("steps") or []
	for index, step in enumerate(source_steps, start=1):
		action_id = step.get("action_id") or step.get("action") or "create_task"
		step_payload = {
			**payload,
			**(step.get("payload") if isinstance(step.get("payload"), dict) else {}),
			"workflow_id": workflow.get("workflow_id"),
			"workflow_step_id": step.get("step_id") or f"step_{index}",
			"title": step.get("title") or payload.get("title") or payload.get("action") or step.get("label"),
			"description": step.get("description") or payload.get("description") or payload.get("suggested_next_step"),
		}
		steps.append({
			"step_id": step.get("step_id") or f"step_{index}",
			"order": index,
			"label": step.get("label") or action_id.replace("_", " ").title(),
			"action_id": action_id,
			"condition": step.get("condition") or "always",
			"status": "Pending",
			"payload": step_payload,
		})
	return steps
