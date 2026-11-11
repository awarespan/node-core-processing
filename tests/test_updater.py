"""
Unit tests for AWARESPAN Updater and Version State.
"""

import tempfile
from pathlib import Path
from node_manager.updater.version_state import VersionStateManager
from node_manager.service_manager import ServiceManager
from node_manager.updater.update_checker import UpdateChecker


def test_version_state_manager():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = str(Path(tmp_dir) / "state.json")
        mgr = VersionStateManager(state_file_override=state_file)
        state = mgr.get_state()
        assert state.status == "IDLE"

        mgr.record_check(target_commit="abcdef12", has_update=True)
        assert mgr.get_state().target_commit == "abcdef12"

        mgr.start_update(target_commit="abcdef12", rollback_commit="12345678")
        assert mgr.get_state().status == "UPDATING"

        mgr.finish_update(success=True, new_commit="abcdef12", affected_services=["awarespan-node.service"])
        assert mgr.get_state().status == "SUCCESS"
        assert mgr.get_state().current_commit == "abcdef12"
        assert len(mgr.get_state().history) == 1


def test_service_manager_affected_services():
    sm = ServiceManager()
    # Changes in node_runtime should affect awarespan-node.service
    aff = sm.determine_affected_services(["node_runtime/main.py"])
    assert "awarespan-node.service" in aff
    assert "awarespan-power-monitor.service" not in aff

    # Changes in shared should affect both node and power monitor
    aff = sm.determine_affected_services(["shared/config/settings.py"])
    assert "awarespan-node.service" in aff
    assert "awarespan-power-monitor.service" in aff

    # Changes in docs should not restart services
    aff = sm.determine_affected_services(["README.md", "docs/index.html"])
    assert len(aff) == 0


def test_health_checker_runtime_endpoint():
    from node_manager.health_check import HealthChecker
    hc = HealthChecker()
    # If not running on this dummy port, check returns False gracefully without crash
    res = hc.check_runtime_endpoint(timeout_sec=0.1)
    assert isinstance(res, bool)
    assert hc.check_event_queue() is True
