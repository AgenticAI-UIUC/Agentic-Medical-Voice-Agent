from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.vapi_tools import router as vapi_tools_router
from app.api.vapi_webhook import router as vapi_webhook_router
from app.config import settings



@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting {settings.PROJECT_NAME} ({settings.ENVIRONMENT})")
    yield
    print("Shutting down")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.is_local else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_HOST] if not settings.is_local else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers under /api/v1
app.include_router(vapi_webhook_router, prefix=settings.API_V1_STR)
app.include_router(vapi_tools_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)

@app.get("/health")
def health():
    return {"status": "ok"}