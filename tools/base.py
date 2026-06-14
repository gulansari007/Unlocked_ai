from abc import ABC, abstractmethod
from typing import Any, Dict, List
from enum import Enum

class ExecutionMode(str, Enum):
    """
    Operating execution modes for the agent framework.
    """
    PLAN = "PLAN"    # Read-only sandboxed repo access
    BUILD = "BUILD"  # Mutation & bash command execution permitted

class BaseTool(ABC):
    """
    Abstract base class for all tools in Unlocked AI.
    All parameters are defined in standard JSON Schema format.
    """
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        required_mode: ExecutionMode = ExecutionMode.PLAN
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.required_mode = required_mode

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """
        Execute tool and return output string.
        """
        pass

class ToolRegistry:
    """
    Manager registry holding tools.
    Enforces mode-based safety gates preventing mutation tools from executing in PLAN mode.
    """
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get_tools_for_mode(self, mode: ExecutionMode) -> List[BaseTool]:
        """
        Return tools allowed for the given execution mode.
        PLAN mode only returns read-only tools.
        BUILD mode returns all tools.
        """
        if mode == ExecutionMode.PLAN:
            return [t for t in self._tools.values() if t.required_mode == ExecutionMode.PLAN]
        return list(self._tools.values())

    def get_tool(self, name: str, mode: ExecutionMode) -> BaseTool:
        """
        Retrieve a tool by name, raising PermissionError if the tool requires BUILD
        privileges but the current operating mode is PLAN.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        
        tool = self._tools[name]
        if mode == ExecutionMode.PLAN and tool.required_mode == ExecutionMode.BUILD:
            raise PermissionError(
                f"Security Gate violation: Tool '{name}' requires BUILD mode. Current mode is PLAN."
            )
        return tool

    @property
    def all_tools(self) -> List[BaseTool]:
        return list(self._tools.values())
