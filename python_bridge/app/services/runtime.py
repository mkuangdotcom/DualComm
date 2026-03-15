from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.base import AgentRuntime
from app.services.runtime_factory import get_runtime_backend


class BridgeRuntime:
    """
    Thin facade used by the FastAPI route layer.

    The HTTP layer should depend only on this class. Concrete runtime behavior
    is selected by the runtime factory, which allows the backend to switch
    between mock, LangChain, LlamaIndex, or future adapters without changing
    the route code.
    """

    def __init__(self, adapter: Optional[AgentRuntime] = None) -> None:
        self._adapter = adapter or get_runtime_backend()

    async def handle_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._adapter.handle_message(payload)
