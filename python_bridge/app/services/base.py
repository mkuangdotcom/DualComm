from __future__ import annotations

from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class AgentRuntime(Protocol):
    """
    Protocol for pluggable Python agent adapters.

    Implementations should accept the normalized inbound payload emitted by the
    TypeScript/Baileys bridge and return a dictionary shaped like the bridge
    response contract, typically:

    {
        "actions": [...],
        "metadata": {...}
    }
    """

    async def handle_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a normalized inbound message payload and return outbound actions.
        """
        ...
