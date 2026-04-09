from types import SimpleNamespace
from unittest.mock import patch

from app.services.scenario_run_service import ScenarioRunService


def test_runtime_selection_prefers_temporal_when_enabled():
    scenario = SimpleNamespace(labels={"runtime_type": "temporal"})
    with patch("app.services.scenario_run_service.settings.TEMPORAL_ENABLED", True), patch(
        "app.services.scenario_run_service.settings.SCENARIO_RUNTIME_DEFAULT",
        "local",
    ):
        runtime = ScenarioRunService.get_runtime_for_scenario(scenario)

    assert runtime.runtime_type == "temporal"


def test_runtime_selection_falls_back_to_local_when_temporal_disabled():
    scenario = SimpleNamespace(labels={"runtime_type": "temporal"})
    with patch("app.services.scenario_run_service.settings.TEMPORAL_ENABLED", False), patch(
        "app.services.scenario_run_service.settings.SCENARIO_RUNTIME_DEFAULT",
        "temporal",
    ):
        runtime = ScenarioRunService.get_runtime_for_scenario(scenario)

    assert runtime.runtime_type == "local"


def test_runtime_selection_uses_default_backend():
    scenario = SimpleNamespace(labels={})
    with patch("app.services.scenario_run_service.settings.TEMPORAL_ENABLED", True), patch(
        "app.services.scenario_run_service.settings.SCENARIO_RUNTIME_DEFAULT",
        "temporal",
    ):
        runtime = ScenarioRunService.get_runtime_for_scenario(scenario)

    assert runtime.runtime_type == "temporal"
