from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_claude_content(self) -> str:
        """Format for returning to Claude as tool result content."""
        if self.success:
            return self.message if not self.data else f"{self.message}\n{self.data}"
        return f"Error: {self.message}"
