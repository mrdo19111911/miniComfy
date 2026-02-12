"""Tests for plugin lifecycle: 2-tier loading, activate/deactivate/delete, hooks, executor error handling."""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipestudio.plugin_api import _NODE_REGISTRY, _EXECUTORS
from pipestudio.models import WorkflowNode, WorkflowEdge, WorkflowDefinition, NodeUnavailableError
from pipestudio.executor import WorkflowExecutor

PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "..", "plugins")


def _fresh_load():
    """Clear registry and reload all plugins."""
    _NODE_REGISTRY.clear()
    _EXECUTORS.clear()
    from pipestudio.plugin_loader import load_plugins
    return load_plugins(PLUGINS_DIR)


# ------------------------------------------------------------------
# NodeUnavailableError
# ------------------------------------------------------------------

def test_node_unavailable_error_has_fields():
    """NodeUnavailableError stores node_id, node_type, and reason."""
    err = NodeUnavailableError(
        node_id="abc123",
        node_type="my_node",
        reason="inactive",
    )
    assert err.node_id == "abc123"
    assert err.node_type == "my_node"
    assert err.reason == "inactive"
    assert "my_node" in str(err)


def test_node_unavailable_error_is_exception():
    """NodeUnavailableError can be raised and caught."""
    try:
        raise NodeUnavailableError(
            node_id="n1", node_type="missing_node", reason="not_installed"
        )
    except NodeUnavailableError as e:
        assert e.reason == "not_installed"
    except Exception:
        assert False, "Should be caught as NodeUnavailableError"


# ------------------------------------------------------------------
# unregister_node
# ------------------------------------------------------------------

def test_unregister_node_removes_from_registry():
    """unregister_node removes node from both _NODE_REGISTRY and _EXECUTORS."""
    from pipestudio.plugin_api import unregister_node
    _fresh_load()
    assert "tsp_generate_points" in _NODE_REGISTRY
    assert "tsp_generate_points" in _EXECUTORS

    unregister_node("tsp_generate_points")

    assert "tsp_generate_points" not in _NODE_REGISTRY
    assert "tsp_generate_points" not in _EXECUTORS


def test_unregister_node_nonexistent_is_silent():
    """unregister_node on a non-existent type does not raise."""
    from pipestudio.plugin_api import unregister_node
    _fresh_load()
    # Should not raise
    unregister_node("does_not_exist_xyz")


# ------------------------------------------------------------------
# 2-tier plugin loading
# ------------------------------------------------------------------

def test_core_plugin_loads_loop_nodes():
    """core/ project folder loads loop_group, loop_start, loop_end, loop_node."""
    manifests = _fresh_load()
    core = [m for m in manifests if m.get("name") == "core"]
    assert len(core) == 1
    assert core[0]["_loaded"] is True

    for node_type in ("loop_group", "loop_start", "loop_end", "loop_node"):
        assert node_type in _NODE_REGISTRY, f"{node_type} not loaded from core/"


def test_tsp_plugin_loads():
    """tsp/ loads correctly alongside core/."""
    manifests = _fresh_load()
    tsp = [m for m in manifests if m.get("name") == "tsp"]
    assert len(tsp) == 1
    assert tsp[0]["_loaded"] is True
    assert "tsp_generate_points" in _NODE_REGISTRY


# ------------------------------------------------------------------
# Complex plugin (folder with __init__.py)
# ------------------------------------------------------------------

def test_folder_plugin_with_init_py():
    """A plugin as a folder with __init__.py loads correctly."""
    tmp_dir = tempfile.mkdtemp()
    try:
        # Create project folder
        project_dir = os.path.join(tmp_dir, "test_project")
        os.makedirs(os.path.join(project_dir, "nodes", "complex_node"))

        # Project manifest
        with open(os.path.join(project_dir, "manifest.json"), "w") as f:
            json.dump({
                "name": "test_project",
                "version": "1.0.0",
                "description": "Test",
                "categories": {"TEST": {"color": "#000", "label": "Test"}}
            }, f)

        # Complex node: folder with __init__.py
        init_code = '''
NODE_INFO = {
    "type": "complex_test_node",
    "label": "Complex Test",
    "category": "TEST",
    "ports_in": [{"name": "input", "type": "NUMBER", "default": 0}],
    "ports_out": [{"name": "output", "type": "NUMBER"}],
}

def run(input=0):
    return 42
'''
        with open(os.path.join(project_dir, "nodes", "complex_node", "__init__.py"), "w") as f:
            f.write(init_code)

        _NODE_REGISTRY.clear()
        _EXECUTORS.clear()
        from pipestudio.plugin_loader import load_plugins
        load_plugins(tmp_dir)

        assert "complex_test_node" in _NODE_REGISTRY
        assert "complex_test_node" in _EXECUTORS
        result = _EXECUTORS["complex_test_node"]({})
        assert result["output"] == 42
    finally:
        shutil.rmtree(tmp_dir)


# ------------------------------------------------------------------
# Manifest merge
# ------------------------------------------------------------------

def test_manifest_merge_child_overrides_parent():
    """Child plugin's manifest.json overrides parent's fields."""
    tmp_dir = tempfile.mkdtemp()
    try:
        project_dir = os.path.join(tmp_dir, "merge_test")
        os.makedirs(os.path.join(project_dir, "nodes", "override_node"))

        # Parent manifest
        with open(os.path.join(project_dir, "manifest.json"), "w") as f:
            json.dump({
                "name": "merge_test",
                "version": "1.0.0",
                "description": "Parent desc",
                "categories": {"CAT_A": {"color": "#111", "label": "A"}}
            }, f)

        # Child manifest (overrides version, adds category)
        with open(os.path.join(project_dir, "nodes", "override_node", "manifest.json"), "w") as f:
            json.dump({
                "version": "2.0.0",
                "categories": {"CAT_B": {"color": "#222", "label": "B"}}
            }, f)

        # Child __init__.py
        init_code = '''
NODE_INFO = {
    "type": "override_test_node",
    "label": "Override Test",
    "category": "CAT_B",
    "ports_in": [],
    "ports_out": [{"name": "out", "type": "NUMBER"}],
}

def run():
    return 1
'''
        with open(os.path.join(project_dir, "nodes", "override_node", "__init__.py"), "w") as f:
            f.write(init_code)

        _NODE_REGISTRY.clear()
        _EXECUTORS.clear()
        from pipestudio.plugin_loader import load_plugins
        load_plugins(tmp_dir)

        assert "override_test_node" in _NODE_REGISTRY
    finally:
        shutil.rmtree(tmp_dir)


# ------------------------------------------------------------------
# plugins_state.json --- activate / deactivate
# ------------------------------------------------------------------

def test_deactivate_plugin_skips_loading():
    """Plugin marked inactive in plugins_state.json is not loaded."""
    tmp_dir = tempfile.mkdtemp()
    try:
        project_dir = os.path.join(tmp_dir, "state_test")
        os.makedirs(os.path.join(project_dir, "nodes"))

        with open(os.path.join(project_dir, "manifest.json"), "w") as f:
            json.dump({
                "name": "state_test", "version": "1.0.0",
                "description": "Test", "categories": {}
            }, f)

        node_code = '''
NODE_INFO = {
    "type": "state_test_node",
    "label": "State Test",
    "category": "TEST",
    "ports_in": [],
    "ports_out": [{"name": "out", "type": "NUMBER"}],
}

def run():
    return 1
'''
        with open(os.path.join(project_dir, "nodes", "state_test_node.py"), "w") as f:
            f.write(node_code)

        # Mark it inactive
        with open(os.path.join(tmp_dir, "plugins_state.json"), "w") as f:
            json.dump({"state_test/state_test_node": "inactive"}, f)

        _NODE_REGISTRY.clear()
        _EXECUTORS.clear()
        from pipestudio.plugin_loader import load_plugins
        load_plugins(tmp_dir)

        assert "state_test_node" not in _NODE_REGISTRY
        assert "state_test_node" not in _EXECUTORS
    finally:
        shutil.rmtree(tmp_dir)


def test_activate_plugin_loads_it():
    """Plugin marked active (or not listed) in plugins_state.json is loaded."""
    tmp_dir = tempfile.mkdtemp()
    try:
        project_dir = os.path.join(tmp_dir, "active_test")
        os.makedirs(os.path.join(project_dir, "nodes"))

        with open(os.path.join(project_dir, "manifest.json"), "w") as f:
            json.dump({
                "name": "active_test", "version": "1.0.0",
                "description": "Test", "categories": {}
            }, f)

        node_code = '''
NODE_INFO = {
    "type": "active_test_node",
    "label": "Active Test",
    "category": "TEST",
    "ports_in": [],
    "ports_out": [{"name": "out", "type": "NUMBER"}],
}

def run():
    return 99
'''
        with open(os.path.join(project_dir, "nodes", "active_test_node.py"), "w") as f:
            f.write(node_code)

        # No plugins_state.json -> default active
        _NODE_REGISTRY.clear()
        _EXECUTORS.clear()
        from pipestudio.plugin_loader import load_plugins
        load_plugins(tmp_dir)

        assert "active_test_node" in _NODE_REGISTRY
        assert _EXECUTORS["active_test_node"]({})["out"] == 99
    finally:
        shutil.rmtree(tmp_dir)


def test_activate_deactivate_functions():
    """activate_plugin and deactivate_plugin update state file and registry."""
    from pipestudio.plugin_loader import activate_plugin, deactivate_plugin
    tmp_dir = tempfile.mkdtemp()
    try:
        project_dir = os.path.join(tmp_dir, "toggle_test")
        os.makedirs(os.path.join(project_dir, "nodes"))

        with open(os.path.join(project_dir, "manifest.json"), "w") as f:
            json.dump({
                "name": "toggle_test", "version": "1.0.0",
                "description": "Test", "categories": {}
            }, f)

        node_code = '''
NODE_INFO = {
    "type": "toggle_node",
    "label": "Toggle",
    "category": "TEST",
    "ports_in": [],
    "ports_out": [{"name": "out", "type": "NUMBER"}],
}

def run():
    return 7
'''
        with open(os.path.join(project_dir, "nodes", "toggle_node.py"), "w") as f:
            f.write(node_code)

        # Initial load
        _NODE_REGISTRY.clear()
        _EXECUTORS.clear()
        from pipestudio.plugin_loader import load_plugins
        load_plugins(tmp_dir)
        assert "toggle_node" in _NODE_REGISTRY

        # Deactivate
        deactivate_plugin(tmp_dir, "toggle_test/toggle_node")
        assert "toggle_node" not in _NODE_REGISTRY
        assert "toggle_node" not in _EXECUTORS

        # State file updated
        with open(os.path.join(tmp_dir, "plugins_state.json")) as f:
            state = json.load(f)
        assert state["toggle_test/toggle_node"] == "inactive"

        # Activate
        activate_plugin(tmp_dir, "toggle_test/toggle_node")
        assert "toggle_node" in _NODE_REGISTRY
        assert "toggle_node" in _EXECUTORS
    finally:
        shutil.rmtree(tmp_dir)


def test_delete_requires_inactive():
    """delete_plugin raises error if plugin is still active."""
    from pipestudio.plugin_loader import delete_plugin
    tmp_dir = tempfile.mkdtemp()
    try:
        project_dir = os.path.join(tmp_dir, "del_test")
        os.makedirs(os.path.join(project_dir, "nodes"))

        with open(os.path.join(project_dir, "manifest.json"), "w") as f:
            json.dump({
                "name": "del_test", "version": "1.0.0",
                "description": "Test", "categories": {}
            }, f)

        node_code = '''
NODE_INFO = {
    "type": "del_test_node",
    "label": "Del Test",
    "category": "TEST",
    "ports_in": [],
    "ports_out": [{"name": "out", "type": "NUMBER"}],
}

def run():
    return 1
'''
        with open(os.path.join(project_dir, "nodes", "del_test_node.py"), "w") as f:
            f.write(node_code)

        _NODE_REGISTRY.clear()
        _EXECUTORS.clear()
        from pipestudio.plugin_loader import load_plugins
        load_plugins(tmp_dir)

        # Try delete while active --- should raise
        try:
            delete_plugin(tmp_dir, "del_test/del_test_node")
            assert False, "Should have raised an error"
        except ValueError as e:
            assert "inactive" in str(e).lower() or "deactivate" in str(e).lower()
    finally:
        shutil.rmtree(tmp_dir)


def test_delete_inactive_plugin_removes_file():
    """delete_plugin removes file from disk when plugin is inactive."""
    from pipestudio.plugin_loader import deactivate_plugin, delete_plugin
    tmp_dir = tempfile.mkdtemp()
    try:
        project_dir = os.path.join(tmp_dir, "rm_test")
        os.makedirs(os.path.join(project_dir, "nodes"))

        with open(os.path.join(project_dir, "manifest.json"), "w") as f:
            json.dump({
                "name": "rm_test", "version": "1.0.0",
                "description": "Test", "categories": {}
            }, f)

        node_file = os.path.join(project_dir, "nodes", "rm_node.py")
        node_code = '''
NODE_INFO = {
    "type": "rm_node",
    "label": "RM",
    "category": "TEST",
    "ports_in": [],
    "ports_out": [{"name": "out", "type": "NUMBER"}],
}

def run():
    return 1
'''
        with open(node_file, "w") as f:
            f.write(node_code)

        _NODE_REGISTRY.clear()
        _EXECUTORS.clear()
        from pipestudio.plugin_loader import load_plugins
        load_plugins(tmp_dir)

        deactivate_plugin(tmp_dir, "rm_test/rm_node")
        delete_plugin(tmp_dir, "rm_test/rm_node")

        assert not os.path.exists(node_file)
    finally:
        shutil.rmtree(tmp_dir)


# ------------------------------------------------------------------
# Hooks
# ------------------------------------------------------------------

def test_hooks_on_activate_called():
    """on_activate hook is called when plugin is activated."""
    from pipestudio.hooks import run_hook
    tmp_dir = tempfile.mkdtemp()
    try:
        plugin_dir = os.path.join(tmp_dir, "hook_plugin")
        os.makedirs(plugin_dir)

        marker_file = os.path.join(tmp_dir, "activated.marker")
        hooks_code = f'''
def on_activate():
    with open(r"{marker_file}", "w") as f:
        f.write("activated")
'''
        with open(os.path.join(plugin_dir, "hooks.py"), "w") as f:
            f.write(hooks_code)

        run_hook(plugin_dir, "on_activate")
        assert os.path.exists(marker_file)
        with open(marker_file) as f:
            assert f.read() == "activated"
    finally:
        shutil.rmtree(tmp_dir)


def test_hooks_missing_file_is_silent():
    """run_hook on a directory without hooks.py does not raise."""
    from pipestudio.hooks import run_hook
    tmp_dir = tempfile.mkdtemp()
    try:
        # No hooks.py --- should not raise
        run_hook(tmp_dir, "on_activate")
    finally:
        shutil.rmtree(tmp_dir)


def test_hooks_missing_function_is_silent():
    """run_hook with a hook name not defined in hooks.py does not raise."""
    from pipestudio.hooks import run_hook
    tmp_dir = tempfile.mkdtemp()
    try:
        hooks_code = '''
def on_activate():
    pass
'''
        with open(os.path.join(tmp_dir, "hooks.py"), "w") as f:
            f.write(hooks_code)

        # on_deactivate not defined --- should not raise
        run_hook(tmp_dir, "on_deactivate")
    finally:
        shutil.rmtree(tmp_dir)


def test_hooks_exception_does_not_crash():
    """Hooks that raise exceptions are caught and don't crash the system."""
    from pipestudio.hooks import run_hook
    tmp_dir = tempfile.mkdtemp()
    try:
        hooks_code = '''
def on_activate():
    raise RuntimeError("Intentional error in hook")
'''
        with open(os.path.join(tmp_dir, "hooks.py"), "w") as f:
            f.write(hooks_code)

        # Should not raise
        run_hook(tmp_dir, "on_activate")
    finally:
        shutil.rmtree(tmp_dir)


# ------------------------------------------------------------------
# Executor: NodeUnavailableError instead of KeyError
# ------------------------------------------------------------------

def test_executor_raises_unavailable_for_missing_node():
    """Executor raises NodeUnavailableError when node type not in registry."""
    _fresh_load()
    wf = WorkflowDefinition(
        name="test_missing",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 10}),
            WorkflowNode(id="bad", type="nonexistent_node_xyz"),
            WorkflowNode(id="dm", type="tsp_distance_matrix"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="bad", target_port="input"),
            WorkflowEdge(id="e2", source="bad", source_port="output",
                         target="dm", target_port="points"),
        ],
    )
    executor = WorkflowExecutor(wf)
    try:
        executor.execute()
        assert False, "Should have raised NodeUnavailableError"
    except NodeUnavailableError as e:
        assert e.node_id == "bad"
        assert e.node_type == "nonexistent_node_xyz"


def test_executor_runs_nodes_before_stuck_point():
    """Nodes before the unavailable node execute and keep their results."""
    _fresh_load()
    wf = WorkflowDefinition(
        name="test_partial",
        nodes=[
            WorkflowNode(id="gen", type="tsp_generate_points", params={"num_points": 10}),
            WorkflowNode(id="bad", type="nonexistent_node_xyz"),
        ],
        edges=[
            WorkflowEdge(id="e1", source="gen", source_port="points",
                         target="bad", target_port="input"),
        ],
    )
    executor = WorkflowExecutor(wf)
    try:
        executor.execute()
    except NodeUnavailableError:
        pass
    # gen should have run successfully
    assert "gen" in executor.node_outputs
    assert "points" in executor.node_outputs["gen"]
