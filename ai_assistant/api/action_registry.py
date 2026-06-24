"""Registry for safe AI Action Framework actions."""

from __future__ import annotations

from copy import deepcopy


ACTION_REGISTRY = [
	{
		"action_id": "create_task",
		"label": "Create Task",
		"icon": "check-square",
		"description": "Create an ERPNext Task from an AI recommendation.",
		"handler": "create_task",
		"safe_action": True,
		"requires_approval": False,
		"required_permission": {"doctype": "Task", "ptype": "create"},
		"supported_doctypes": ["*"],
		"primary": True,
	},
	{
		"action_id": "follow_up",
		"label": "Follow-up",
		"icon": "corner-up-right",
		"description": "Create a follow-up Task.",
		"handler": "follow_up",
		"safe_action": True,
		"requires_approval": False,
		"required_permission": {"doctype": "Task", "ptype": "create"},
		"supported_doctypes": ["*"],
	},
	{
		"action_id": "assign_user",
		"label": "Assign",
		"icon": "user-check",
		"description": "Create a safe ToDo assignment for a selected user.",
		"handler": "assign_user",
		"safe_action": True,
		"requires_approval": False,
		"required_permission": {"doctype": "ToDo", "ptype": "create"},
		"supported_doctypes": ["*"],
		"requires_user": True,
	},
	{
		"action_id": "open_document",
		"label": "Open Document",
		"icon": "external-link",
		"description": "Open a linked ERPNext document when the recommendation has one.",
		"handler": "open_document",
		"safe_action": True,
		"requires_approval": False,
		"required_permission": {"ptype": "read"},
		"supported_doctypes": ["*"],
		"requires_document": True,
	},
	{
		"action_id": "draft_email",
		"label": "Draft Email",
		"icon": "mail",
		"description": "Prepare an email draft without sending it.",
		"handler": "draft_email",
		"safe_action": True,
		"requires_approval": False,
		"required_permission": None,
		"supported_doctypes": ["*"],
	},
	{
		"action_id": "calendar_event",
		"label": "Calendar Event",
		"icon": "calendar",
		"description": "Create a private calendar event for the recommendation.",
		"handler": "calendar_event",
		"safe_action": True,
		"requires_approval": False,
		"required_permission": {"doctype": "Event", "ptype": "create"},
		"supported_doctypes": ["*"],
	},
	{
		"action_id": "notify_user",
		"label": "Notify User",
		"icon": "bell",
		"description": "Create a safe in-app notification for a selected user.",
		"handler": "notify_user",
		"safe_action": True,
		"requires_approval": False,
		"required_permission": {"doctype": "Notification Log", "ptype": "create"},
		"supported_doctypes": ["*"],
		"requires_user": True,
	},
	{
		"action_id": "add_comment",
		"label": "Add Comment",
		"icon": "message-square",
		"description": "Add a comment to a linked ERPNext document.",
		"handler": "add_comment",
		"safe_action": True,
		"requires_approval": False,
		"required_permission": {"doctype": "Comment", "ptype": "create"},
		"supported_doctypes": ["*"],
		"requires_document": True,
	},
	{
		"action_id": "reminder",
		"label": "Reminder",
		"icon": "clock",
		"description": "Create a reminder ToDo for the current user.",
		"handler": "reminder",
		"safe_action": True,
		"requires_approval": False,
		"required_permission": {"doctype": "ToDo", "ptype": "create"},
		"supported_doctypes": ["*"],
	},
	{
		"action_id": "activity_timeline",
		"label": "Activity Timeline Entry",
		"icon": "activity",
		"description": "Record a safe timeline note on a linked ERPNext document.",
		"handler": "activity_timeline",
		"safe_action": True,
		"requires_approval": False,
		"required_permission": {"doctype": "Comment", "ptype": "create"},
		"supported_doctypes": ["*"],
		"requires_document": True,
	},
]


def get_action_registry() -> list[dict]:
	return deepcopy(ACTION_REGISTRY)


def get_action(action_id: str) -> dict | None:
	for action in ACTION_REGISTRY:
		if action.get("action_id") == action_id:
			return deepcopy(action)
	return None
