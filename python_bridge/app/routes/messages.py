from fastapi import APIRouter, Header, HTTPException

from app.schemas.messages import AgentRequest, AgentResponse
from app.services.runtime import BridgeRuntime
from app.settings import get_settings


router = APIRouter(prefix="/messages", tags=["messages"])

_runtime = BridgeRuntime()
_settings = get_settings()


@router.post("", response_model=AgentResponse)
async def handle_message(
    request: AgentRequest,
    x_agent_api_key: str | None = Header(default=None),
) -> AgentResponse:
    if not _settings.validate_api_key(x_agent_api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing agent API key",
        )

    try:
        return AgentResponse.model_validate(
            await _runtime.handle_message(request.model_dump())
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process inbound message: {exc}",
        ) from exc
