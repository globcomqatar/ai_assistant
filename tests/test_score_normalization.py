import importlib
import sys
import types
import unittest


def import_chat_module():
	frappe = types.ModuleType("frappe")
	frappe._ = lambda text, *args, **kwargs: text
	frappe.log_error = lambda *args, **kwargs: None
	frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn)

	router = types.ModuleType("ai_assistant.api.router")
	router.route = lambda *args, **kwargs: None
	router._extract_json = lambda value: value

	executor = types.ModuleType("ai_assistant.api.executor")
	executor.execute_actions = lambda *args, **kwargs: None

	security = types.ModuleType("ai_assistant.api.security")
	security.is_system_manager = lambda *args, **kwargs: False
	security.require_management_access = lambda *args, **kwargs: None

	sys.modules.setdefault("frappe", frappe)
	sys.modules.setdefault("ai_assistant.api.router", router)
	sys.modules.setdefault("ai_assistant.api.executor", executor)
	sys.modules.setdefault("ai_assistant.api.security", security)

	return importlib.import_module("ai_assistant.api.chat")


class ScoreNormalizationTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.chat = import_chat_module()

	def test_normalize_score_scales_common_model_formats(self):
		cases = [
			(0.8, 80),
			(8, 80),
			(80, 80),
			(120, 100),
			("invalid", 0),
		]
		for raw, expected in cases:
			with self.subTest(raw=raw):
				self.assertEqual(self.chat.normalize_score(raw), expected)

	def test_risk_and_opportunity_scores_use_normalized_values(self):
		risks = self.chat._normalize_risks([{"title": "Risk", "risk_score": 8}])
		opportunities = self.chat._normalize_opportunities([{"title": "Opportunity", "opportunity_score": 0.6}])

		self.assertEqual(risks[0]["risk_score"], 80)
		self.assertEqual(opportunities[0]["opportunity_score"], 60)


if __name__ == "__main__":
	unittest.main()
