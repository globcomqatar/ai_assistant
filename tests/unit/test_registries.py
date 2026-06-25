"""Unit tests for registry modules — no Frappe dependency."""
import sys
import unittest


class TestActionRegistry(unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, ".")
        from ai_assistant.registries import action_registry as ar
        self.ar = ar

    def test_registry_is_non_empty(self):
        self.assertGreater(len(self.ar.ACTION_REGISTRY), 0)

    def test_every_action_has_required_fields(self):
        required = {"action_id", "label", "handler", "safe_action"}
        for action in self.ar.ACTION_REGISTRY:
            missing = required - set(action.keys())
            self.assertFalse(missing, f"Action '{action.get('action_id')}' missing: {missing}")

    def test_get_action_returns_copy(self):
        action = self.ar.get_action("create_task")
        self.assertIsNotNone(action)
        # Modifying the returned copy must not mutate the registry
        action["label"] = "MODIFIED"
        fresh = self.ar.get_action("create_task")
        self.assertNotEqual(fresh.get("label"), "MODIFIED")

    def test_get_action_unknown_returns_none(self):
        self.assertIsNone(self.ar.get_action("non_existent_action"))

    def test_get_action_registry_returns_copy(self):
        reg = self.ar.get_action_registry()
        reg.clear()
        self.assertGreater(len(self.ar.ACTION_REGISTRY), 0)

    def test_all_safe_actions_flagged(self):
        for action in self.ar.ACTION_REGISTRY:
            self.assertTrue(
                action.get("safe_action"),
                f"Action '{action.get('action_id')}' is not marked safe_action=True",
            )

    def test_known_actions_present(self):
        ids = {a["action_id"] for a in self.ar.ACTION_REGISTRY}
        expected = {"create_task", "follow_up", "assign_user", "draft_email", "open_document"}
        self.assertTrue(expected.issubset(ids))


class TestWorkflowRegistry(unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, ".")
        from ai_assistant.registries import workflow_registry as wr
        self.wr = wr

    def test_registry_is_non_empty(self):
        self.assertGreater(len(self.wr.WORKFLOW_REGISTRY), 0)

    def test_every_workflow_has_required_fields(self):
        required = {"workflow_id", "name", "steps", "safe_workflow"}
        for wf in self.wr.WORKFLOW_REGISTRY:
            missing = required - set(wf.keys())
            self.assertFalse(missing, f"Workflow '{wf.get('workflow_id')}' missing: {missing}")

    def test_every_workflow_has_at_least_one_step(self):
        for wf in self.wr.WORKFLOW_REGISTRY:
            self.assertGreater(len(wf.get("steps", [])), 0,
                               f"Workflow '{wf.get('workflow_id')}' has no steps")

    def test_get_workflow_returns_copy(self):
        wf = self.wr.get_workflow("collection_recovery")
        self.assertIsNotNone(wf)
        wf["name"] = "MODIFIED"
        fresh = self.wr.get_workflow("collection_recovery")
        self.assertNotEqual(fresh.get("name"), "MODIFIED")

    def test_get_workflow_unknown_returns_none(self):
        self.assertIsNone(self.wr.get_workflow("no_such_workflow"))


class TestPlaceholderRegistries(unittest.TestCase):

    def test_playbook_registry_has_named_entries(self):
        from ai_assistant.registries.playbook_registry import PLAYBOOK_REGISTRY, get_playbook
        self.assertGreater(len(PLAYBOOK_REGISTRY), 0)
        self.assertIsNotNone(get_playbook("collection_recovery"))
        self.assertIsNone(get_playbook("does_not_exist"))

    def test_kpi_registry_has_named_entries(self):
        from ai_assistant.registries.kpi_registry import KPI_REGISTRY, get_kpi
        self.assertGreater(len(KPI_REGISTRY), 0)
        self.assertIsNotNone(get_kpi("monthly_revenue"))
        self.assertIsNone(get_kpi("does_not_exist"))

    def test_prediction_registry_is_empty_placeholder(self):
        from ai_assistant.registries.prediction_registry import PREDICTION_REGISTRY, get_predictor
        self.assertEqual(PREDICTION_REGISTRY, [])
        self.assertIsNone(get_predictor("anything"))


if __name__ == "__main__":
    unittest.main()
