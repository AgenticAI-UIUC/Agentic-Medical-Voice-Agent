from fastapi import APIRouter

from app.api.routes import login, private, users, utils
from app.core.config import settings
from app.api.routes import vapi, vapi_tools
from app.api.routes import doctors

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(vapi.router)
api_router.include_router(vapi_tools.router)
api_router.include_router(doctors.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
