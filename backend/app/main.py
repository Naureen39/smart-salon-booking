from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import admin_analytics, appointments, auth, conversation, faq, locations, services, staff_profiles
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="GlowDesk API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(services.router, prefix="/api/v1")
app.include_router(locations.router, prefix="/api/v1")
app.include_router(staff_profiles.router, prefix="/api/v1")
app.include_router(appointments.router, prefix="/api/v1")
app.include_router(faq.router, prefix="/api/v1")
app.include_router(conversation.router, prefix="/api/v1")
app.include_router(admin_analytics.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
