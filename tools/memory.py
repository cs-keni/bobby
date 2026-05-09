from core.tool_result import ToolResult
from tools.registry import register_tool


@register_tool(
    name="remember_fact",
    description=(
        "Save a fact about the user to Bobby's long-term memory. "
        "Use this whenever the user tells you something worth remembering — "
        "their name, preferences, habits, important dates, account details, or "
        "anything they explicitly ask Bobby to remember. "
        "Use a short, descriptive key (e.g. 'user_name', 'preferred_browser')."
    ),
    parameters={
        "key": {
            "type": "string",
            "description": "Short identifier for the fact (e.g. 'user_name', 'favorite_playlist')",
            "required": True,
        },
        "value": {
            "type": "string",
            "description": "The value to store",
            "required": True,
        },
        "description": {
            "type": "string",
            "description": "Optional human-readable description of why this is stored",
            "required": False,
        },
    },
)
def remember_fact(key: str, value: str, description: str = "") -> ToolResult:
    from memory.db import save_fact
    save_fact(key, value, description)
    return ToolResult(success=True, message=f"Got it, I'll remember that {key} is {value}.")


@register_tool(
    name="recall_facts",
    description=(
        "Retrieve facts Bobby has stored about the user. "
        "Use this when the user asks 'what do you know about me?', "
        "'what have I told you?', or wants to see stored memories. "
        "Pass an optional query to filter results."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "Optional search term to filter memories by key or value",
            "required": False,
        },
    },
)
def recall_facts(query: str = "") -> ToolResult:
    from memory.db import list_facts
    facts = list_facts(query)
    if not facts:
        msg = "Nothing stored yet." if not query else "No matching memories."
        return ToolResult(success=True, message=msg)
    lines = [f"• [{f['key']}]: {f['value']}" for f in facts]
    return ToolResult(success=True, message="\n".join(lines))


@register_tool(
    name="forget_fact",
    description=(
        "Delete a stored memory by key. "
        "Use when the user says 'forget that', 'delete the memory about X', "
        "or explicitly asks to remove a stored fact."
    ),
    parameters={
        "key": {
            "type": "string",
            "description": "The key of the fact to remove",
            "required": True,
        },
    },
)
def forget_fact(key: str) -> ToolResult:
    from memory.db import delete_fact
    deleted = delete_fact(key)
    if deleted:
        return ToolResult(success=True, message=f"Forgot {key}.")
    return ToolResult(success=False, message=f"No memory with key {key}.")
