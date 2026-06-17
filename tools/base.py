from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    """
    Abstract Base Class for J.A.R.V.I.S. tools.
    All registered tools must inherit from this class and define metadata and async execution logic.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """
        The name of the tool (e.g. 'system_stats').
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Description of what the tool does, used by the LLM to decide when to call it.
        """
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """
        JSON schema defining the input parameters for the tool.
        """
        pass

    @abstractmethod
    async def run(self, **kwargs) -> str:
        """
        Asynchronously execute the tool's logic. Must return a string response.
        """
        pass
