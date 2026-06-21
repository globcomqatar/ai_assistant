import frappe
from frappe.model.document import Document


class AIToolPermission(Document):
    def on_update(self):
        _invalidate()

    def after_delete(self):
        _invalidate()


def _invalidate():
    from ai_assistant.api.permission_manager import invalidate_cache
    invalidate_cache()
