from frappe.model.document import Document

class AIAgent(Document):
    def on_update(self):
        from ai_assistant.api.agent_manager import invalidate_agent_cache
        invalidate_agent_cache(self.agent_code)

    def after_delete(self):
        from ai_assistant.api.agent_manager import invalidate_agent_cache
        invalidate_agent_cache(self.agent_code)
