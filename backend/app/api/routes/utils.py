from fastapi import APIRouter, HTTPException, status

from app import crud
from app.api.deps import CurrentUser
from app.core.config import settings

router = APIRouter(prefix="/utils", tags=["utils"])


@router.get("/health-check")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/debug-seed")
def debug_seed() -> dict[str, int]:
    if not settings.is_local:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return {
        "users": len(crud.list_all_users()),
    }


@router.get("/whoami")
def who_am_i(current_user: CurrentUser) -> dict[str, str]:
    return {"email": current_user.email}
