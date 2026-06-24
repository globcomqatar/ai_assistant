"""AI Workflow Automation engine.

The engine orchestrates registered actions only; business behavior remains in
action handlers behind the Approval Framework.
"""

from __future__ import annotations

from time import perf_counter

import frappe
from frappe import _

from ai_assistant.api.action_handlers import related_document, response, text
from ai_assistant.api.approval_service import execute_approved_action
from ai_assistant.api.workflow_templates import populate_steps, workflow_payload


STEP_PENDING = "Pending"
STEP_RUNNING = "Running"
STEP_COMPLETED = "Completed"
STEP_SKIPPED = "Skipped"
STEP_FAILED = "Failed"
STEP_CANCELLED = "Cancelled"

WORKFLOW_PENDING = "Pending Approval"
WORKFLOW_RUNNING = "Running"
WORKFLOW_COMPLETED = "Completed"
WORKFLOW_FAILED = "Failed"
WORKFLOW_CANCELLED = "Cancelled"


def require_authenticated() -> None:
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to use the Workflow Center."), frappe.PermissionError)


def workflow_log(event: str, workflow: dict, steps: list[dict], result: dict | None = None,
	execution_time: float = 0, error: str | None = None) -> None:
	entry = {
		"timestamp": frappe.utils.now(),
		"user": frappe.session.user,
		"event": event,
		"workflow": workflow.get("workflow_id"),
		"workflow_name": workflow.get("name"),
		"steps": [{
			"order": step.get("order"),
			"step_id": step.get("step_id"),
			"action_id": step.get("action_id"),
			"status": step.get("status"),
		} for step in steps],
		"result": result,
		"execution_time": round(execution_time, 4),
		"error": error,
	}
	try:
		frappe.logger("ai_assistant.workflow_engine").info(entry)
	except Exception:
		pass


def condition_passes(condition: str, payload: dict) -> bool:
	condition = condition or "always"
	if condition == "always":
		return True
	if condition == "assigned_user_exists":
		return bool(payload.get("user") or payload.get("assigned_user") or payload.get("assigned_to") or payload.get("owner"))
	if condition == "linked_document_exists":
		doctype, name = related_document(payload)
		return bool(doctype and name and frappe.db.exists("DocType", doctype) and frappe.db.exists(doctype, name))
	return False


def build_workflow_plan(workflow_id=None, recommendation_payload=None) -> dict:
	require_authenticated()
	workflow, payload = workflow_payload(workflow_id, recommendation_payload)
	if not workflow.get("safe_workflow"):
		frappe.throw(_("Workflow is not marked safe for automation."), frappe.PermissionError)
	steps = populate_steps(workflow, payload)
	plan = {
		"success": True,
		"ok": True,
		"workflow_id": workflow.get("workflow_id"),
		"workflow_name": workflow.get("name"),
		"description": workflow.get("description"),
		"business_impact": text(payload.get("business_impact") or payload.get("impact") or payload.get("expected_impact"), 1000),
		"confidence": payload.get("confidence") or payload.get("confidence_score"),
		"estimated_duration": payload.get("estimated_duration") or workflow.get("estimated_duration"),
		"progress": 0,
		"status": WORKFLOW_PENDING,
		"requires_approval": True,
		"safe_workflow": True,
		"steps": steps,
		"payload": payload,
	}
	workflow_log("plan", workflow, steps, plan)
	return plan


def execute_workflow(workflow_id=None, recommendation_payload=None, approved: bool = False,
	user: str | None = None, skip_steps=None, retry_from_step: str | None = None) -> dict:
	require_authenticated()
	start = perf_counter()
	plan = build_workflow_plan(workflow_id, recommendation_payload)
	workflow = {
		"workflow_id": plan.get("workflow_id"),
		"name": plan.get("workflow_name"),
	}
	steps = plan.get("steps") or []
	skip_steps = set(skip_steps or [])
	if not approved:
		plan.update({
			"success": False,
			"ok": False,
			"message": _("Workflow approval is required before execution."),
			"approval_required": True,
		})
		return plan

	results = []
	created_documents = []
	execution_log = []
	started = retry_from_step is None
	failed = None
	for step in steps:
		if not started and step.get("step_id") != retry_from_step:
			step["status"] = STEP_SKIPPED
			continue
		started = True
		if step.get("step_id") in skip_steps:
			step["status"] = STEP_SKIPPED
			execution_log.append({"step_id": step.get("step_id"), "status": STEP_SKIPPED, "message": _("Skipped by user.")})
			continue
		if not condition_passes(step.get("condition"), step.get("payload") or {}):
			step["status"] = STEP_SKIPPED
			execution_log.append({"step_id": step.get("step_id"), "status": STEP_SKIPPED, "message": _("Condition not met.")})
			continue

		step["status"] = STEP_RUNNING
		result = execute_approved_action(step.get("action_id"), step.get("payload"), user=user)
		results.append(result)
		if result.get("created_document"):
			created_documents.append(result.get("created_document"))
		if not result.get("success"):
			step["status"] = STEP_FAILED
			failed = {"step": step, "result": result}
			execution_log.append({"step_id": step.get("step_id"), "status": STEP_FAILED, "result": result})
			break
		step["status"] = STEP_COMPLETED
		execution_log.append({"step_id": step.get("step_id"), "status": STEP_COMPLETED, "result": result})

	if failed:
		status = WORKFLOW_FAILED
		success = False
		message = _("Workflow stopped after a failed step. Retry or skip the failed step to continue.")
	else:
		status = WORKFLOW_COMPLETED
		success = True
		message = _("Workflow completed successfully.")

	execution_time = perf_counter() - start
	completed = len([step for step in steps if step.get("status") == STEP_COMPLETED])
	resolved = len([step for step in steps if step.get("status") in {STEP_COMPLETED, STEP_SKIPPED}])
	failed_count = len([step for step in steps if step.get("status") == STEP_FAILED])
	result = response(plan.get("workflow_id"), message, success=success, execution_time=execution_time, extra={
		"workflow_id": plan.get("workflow_id"),
		"workflow_name": plan.get("workflow_name"),
		"status": status,
		"progress": int((resolved / len(steps)) * 100) if steps else 0,
		"steps": steps,
		"completed_steps": completed,
		"failed_steps": failed_count,
		"business_impact": plan.get("business_impact"),
		"created_documents": created_documents,
		"execution_log": execution_log,
		"allow_retry": bool(failed),
		"allow_skip": bool(failed),
		"failed_step": failed.get("step") if failed else None,
		"results": results,
	})
	workflow_log("execute", workflow, steps, result, execution_time=execution_time, error=failed.get("result", {}).get("message") if failed else None)
	return result
