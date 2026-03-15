from fastapi import FastAPI

from app.routes.messages import router as messages_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Messaging Python Agent Bridge",
        version="0.1.0",
        description=(
            "Python agent runtime for normalized Telegram/WhatsApp bridge payloads. "
            "Receives normalized inbound messages and returns outbound actions."
        ),
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(messages_router, prefix="")

    return app


app = create_app()
