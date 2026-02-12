"""Plugin lifecycle hook runner.

Loads and executes optional hooks.py from plugin directories.
Supported hooks: on_activate, on_deactivate, on_uninstall.
"""
import importlib.util
import os
import sys


def run_hook(plugin_dir: str, hook_name: str) -> None:
    """Run a named hook function from plugin_dir/hooks.py.

    Silent if hooks.py doesn't exist or the function isn't defined.
    Catches and logs exceptions from hooks to prevent crashing the server.
    """
    hooks_path = os.path.join(plugin_dir, "hooks.py")
    if not os.path.exists(hooks_path):
        return

    try:
        module_name = f"_pipestudio_hooks_{os.path.basename(plugin_dir)}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        spec = importlib.util.spec_from_file_location(module_name, hooks_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        fn = getattr(module, hook_name, None)
        if fn is not None and callable(fn):
            fn()
    except Exception as e:
        print(f"  Hook '{hook_name}' in {plugin_dir} failed: {e}")
