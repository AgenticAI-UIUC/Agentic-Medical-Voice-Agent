from fastapi import APIRouter

from app.api.vapi_tools.identify_patient import router as identify_router
from app.api.vapi_tools.triage import router as triage_router
from app.api.vapi_tools.find_slots import router as slots_router
from app.api.vapi_tools.book import router as book_router
from app.api.vapi_tools.reschedule import router as reschedule_router
from app.api.vapi_tools.cancel import router as cancel_router

router = APIRouter(prefix="/vapi/tools", tags=["vapi-tools"])

router.include_router(identify_router)
router.include_router(triage_router)
router.include_router(slots_router)
router.include_router(book_router)
router.include_router(reschedule_router)
router.include_router(cancel_router)
