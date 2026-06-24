"""Registry for reusable AI workflow automation templates."""

from __future__ import annotations

from copy import deepcopy


WORKFLOW_REGISTRY = [
	{
		"workflow_id": "collection_recovery",
		"name": "Collection Recovery",
		"description": "Coordinate follow-up, assignment, reminders, and notifications for collection risks.",
		"icon": "credit-card",
		"supported_modules": ["Accounts", "Selling"],
		"supported_doctypes": ["Sales Invoice", "Customer", "*"],
		"estimated_duration": "15 min",
		"safe_workflow": True,
		"requires_approval": True,
		"steps": [
			{"step_id": "create_task", "action_id": "create_task", "label": "Create recovery task"},
			{"step_id": "assign_user", "action_id": "assign_user", "label": "Assign owner", "condition": "assigned_user_exists"},
			{"step_id": "reminder", "action_id": "reminder", "label": "Create reminder"},
			{"step_id": "notify_user", "action_id": "notify_user", "label": "Notify owner", "condition": "assigned_user_exists"},
		],
	},
	{
		"workflow_id": "quotation_follow_up",
		"name": "Quotation Follow-up",
		"description": "Create follow-up activity and timeline notes for pending quotations.",
		"icon": "file-text",
		"supported_modules": ["Selling"],
		"supported_doctypes": ["Quotation", "*"],
		"estimated_duration": "10 min",
		"safe_workflow": True,
		"requires_approval": True,
		"steps": [
			{"step_id": "follow_up", "action_id": "follow_up", "label": "Create follow-up task"},
			{"step_id": "add_comment", "action_id": "add_comment", "label": "Add document comment", "condition": "linked_document_exists"},
			{"step_id": "draft_email", "action_id": "draft_email", "label": "Draft follow-up email"},
		],
	},
	{
		"workflow_id": "customer_follow_up",
		"name": "Customer Follow-up",
		"description": "Assign and schedule customer follow-up.",
		"icon": "users",
		"supported_modules": ["CRM", "Selling"],
		"supported_doctypes": ["Customer", "*"],
		"estimated_duration": "12 min",
		"safe_workflow": True,
		"requires_approval": True,
		"steps": [
			{"step_id": "create_task", "action_id": "create_task", "label": "Create customer task"},
			{"step_id": "assign_user", "action_id": "assign_user", "label": "Assign user", "condition": "assigned_user_exists"},
			{"step_id": "activity_timeline", "action_id": "activity_timeline", "label": "Add timeline entry", "condition": "linked_document_exists"},
		],
	},
	{
		"workflow_id": "workshop_reminder",
		"name": "Workshop Reminder",
		"description": "Create operational reminders for workshop-related actions.",
		"icon": "tool",
		"supported_modules": ["Manufacturing", "Stock"],
		"supported_doctypes": ["Work Order", "Project", "*"],
		"estimated_duration": "8 min",
		"safe_workflow": True,
		"requires_approval": True,
		"steps": [
			{"step_id": "reminder", "action_id": "reminder", "label": "Create reminder"},
			{"step_id": "calendar_event", "action_id": "calendar_event", "label": "Create calendar event"},
		],
	},
	{
		"workflow_id": "inventory_review",
		"name": "Inventory Review",
		"description": "Create review tasks and comments for inventory issues.",
		"icon": "box",
		"supported_modules": ["Stock"],
		"supported_doctypes": ["Item", "Warehouse", "*"],
		"estimated_duration": "12 min",
		"safe_workflow": True,
		"requires_approval": True,
		"steps": [
			{"step_id": "create_task", "action_id": "create_task", "label": "Create inventory review task"},
			{"step_id": "add_comment", "action_id": "add_comment", "label": "Add stock note", "condition": "linked_document_exists"},
			{"step_id": "notify_user", "action_id": "notify_user", "label": "Notify reviewer", "condition": "assigned_user_exists"},
		],
	},
	{
		"workflow_id": "purchase_follow_up",
		"name": "Purchase Follow-up",
		"description": "Coordinate safe follow-up for purchasing actions.",
		"icon": "shopping-cart",
		"supported_modules": ["Buying"],
		"supported_doctypes": ["Supplier", "Purchase Order", "*"],
		"estimated_duration": "10 min",
		"safe_workflow": True,
		"requires_approval": True,
		"steps": [
			{"step_id": "follow_up", "action_id": "follow_up", "label": "Create purchase follow-up"},
			{"step_id": "reminder", "action_id": "reminder", "label": "Create reminder"},
		],
	},
	{
		"workflow_id": "sales_opportunity",
		"name": "Sales Opportunity",
		"description": "Create sales opportunity follow-up tasks and notifications.",
		"icon": "trending-up",
		"supported_modules": ["CRM", "Selling"],
		"supported_doctypes": ["Opportunity", "Lead", "Customer", "*"],
		"estimated_duration": "12 min",
		"safe_workflow": True,
		"requires_approval": True,
		"steps": [
			{"step_id": "create_task", "action_id": "create_task", "label": "Create sales task"},
			{"step_id": "draft_email", "action_id": "draft_email", "label": "Draft outreach email"},
			{"step_id": "notify_user", "action_id": "notify_user", "label": "Notify salesperson", "condition": "assigned_user_exists"},
		],
	},
	{
		"workflow_id": "lead_qualification",
		"name": "Lead Qualification",
		"description": "Prepare qualification follow-up for leads.",
		"icon": "user-plus",
		"supported_modules": ["CRM"],
		"supported_doctypes": ["Lead", "*"],
		"estimated_duration": "10 min",
		"safe_workflow": True,
		"requires_approval": True,
		"steps": [
			{"step_id": "follow_up", "action_id": "follow_up", "label": "Create qualification task"},
			{"step_id": "calendar_event", "action_id": "calendar_event", "label": "Schedule qualification event"},
		],
	},
	{
		"workflow_id": "reminder_workflow",
		"name": "Reminder Workflow",
		"description": "Create a reminder and optional assignment.",
		"icon": "clock",
		"supported_modules": ["All"],
		"supported_doctypes": ["*"],
		"estimated_duration": "5 min",
		"safe_workflow": True,
		"requires_approval": True,
		"steps": [
			{"step_id": "reminder", "action_id": "reminder", "label": "Create reminder"},
			{"step_id": "assign_user", "action_id": "assign_user", "label": "Assign reminder", "condition": "assigned_user_exists"},
		],
	},
	{
		"workflow_id": "notification_workflow",
		"name": "Notification Workflow",
		"description": "Notify a selected user and create an audit note when linked.",
		"icon": "bell",
		"supported_modules": ["All"],
		"supported_doctypes": ["*"],
		"estimated_duration": "5 min",
		"safe_workflow": True,
		"requires_approval": True,
		"steps": [
			{"step_id": "notify_user", "action_id": "notify_user", "label": "Notify user", "condition": "assigned_user_exists"},
			{"step_id": "activity_timeline", "action_id": "activity_timeline", "label": "Add timeline note", "condition": "linked_document_exists"},
		],
	},
]


def get_workflow_registry() -> list[dict]:
	return deepcopy(WORKFLOW_REGISTRY)


def get_workflow(workflow_id: str) -> dict | None:
	for workflow in WORKFLOW_REGISTRY:
		if workflow.get("workflow_id") == workflow_id:
			return deepcopy(workflow)
	return None
