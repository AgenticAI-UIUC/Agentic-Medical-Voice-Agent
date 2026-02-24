from fastapi import APIRouter

from app.api.routes.vapi_tools.schedule_appointment import router as schedule_router
from app.api.routes.vapi_tools.triage_decision import router as triage_router
from app.api.routes.vapi_tools.slots import router as  slots_router


router = APIRouter(prefix="/vapi/tools", tags=["vapi-tools"])

router.include_router(schedule_router)
router.include_router(slots_router)
router.include_router(triage_router)
