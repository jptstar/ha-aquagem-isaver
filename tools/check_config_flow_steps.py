"""Static guard for Home Assistant config-flow form dispatch.

Every literal ``step_id`` returned by ``async_show_form`` must have a public
``async_step_<step_id>`` handler on the same flow class. Home Assistant sends
subsequent form submissions directly to that method, so a private helper alone
is not sufficient.
"""

from __future__ import annotations

import ast
from pathlib import Path
import sys


CONFIG_FLOW = Path("custom_components/aquagem_isaver/config_flow.py")


def _flow_class(node: ast.ClassDef) -> bool:
    """Return whether the class is a ConfigFlow or OptionsFlow subclass."""
    for base in node.bases:
        if isinstance(base, ast.Attribute) and base.attr in {"ConfigFlow", "OptionsFlow"}:
            return True
        if isinstance(base, ast.Name) and base.id in {"ConfigFlow", "OptionsFlow"}:
            return True
    return False


def main() -> int:
    """Validate literal async_show_form step dispatch targets."""
    tree = ast.parse(CONFIG_FLOW.read_text(encoding="utf-8"), filename=str(CONFIG_FLOW))
    failures: list[str] = []

    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef) and _flow_class(node)):
        handlers = {
            node.name
            for node in cls.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("async_step_")
        }

        for node in ast.walk(cls):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != "async_show_form":
                continue

            step_id: str | None = None
            for keyword in node.keywords:
                if keyword.arg == "step_id" and isinstance(keyword.value, ast.Constant):
                    if isinstance(keyword.value.value, str):
                        step_id = keyword.value.value
                        break

            if step_id is None:
                continue

            expected = f"async_step_{step_id}"
            if expected not in handlers:
                failures.append(
                    f"{cls.name}: step_id={step_id!r} requires public handler {expected}"
                )

    if failures:
        print("Config-flow step dispatch validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Config-flow step dispatch validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
