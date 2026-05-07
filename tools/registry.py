"""
Tool registry — every action Bobby can take lives here.
Each tool is a typed Python function registered via @register_tool.
Claude receives the schema; dispatch_tool executes the call.
"""

from typing import Any, Callable

from core.logging import get_logger
from core.tool_result import ToolResult

log = get_logger(__name__)

_tools: dict[str, dict] = {}
_handlers: dict[str, Callable] = {}


def register_tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
):
    """Decorator that registers a function as a Bobby tool."""
    def decorator(fn: Callable) -> Callable:
        # Strip "required" from individual property dicts — it belongs only at the
        # top-level schema array, not inside each property definition (JSON Schema draft 2020-12).
        clean_properties = {
            k: {key: val for key, val in v.items() if key != "required"}
            for k, v in parameters.items()
        }
        _tools[name] = {
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": clean_properties,
                "required": [k for k, v in parameters.items() if v.get("required", False)],
            },
        }
        _handlers[name] = fn
        return fn
    return decorator


def get_tools() -> list[dict[str, Any]]:
    """Return all registered tools in Anthropic tool-use format."""
    # Import tool modules to trigger registration
    import tools.os_control  # noqa: F401
    return list(_tools.values())


def dispatch_tool(name: str, inputs: dict[str, Any]) -> ToolResult:
    """Call the handler for a tool by name."""
    handler = _handlers.get(name)
    if not handler:
        return ToolResult(success=False, message=f"Unknown tool: {name}")
    try:
        return handler(**inputs)
    except Exception as e:
        log.error(f"Tool {name} raised: {e}", exc_info=True)
        return ToolResult(success=False, message=f"Tool {name} failed: {e}")
