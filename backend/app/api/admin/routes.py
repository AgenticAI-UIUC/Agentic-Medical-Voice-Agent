from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_current_active_user, get_current_superuser
from app.supabase import get_supabase

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_active_user)],
)


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------


class DoctorCreateIn(BaseModel):
    full_name: str
    specialties: list[str] = Field(default_factory=list)
    image_url: str | None = None


class AvailabilityWindowIn(BaseModel):
    day_of_week: int = Field(ge=0, le=6)  # 0=Sun, 6=Sat
    start_time: str  # "09:00"
    end_time: str  # "12:00"
    slot_minutes: int = 60
    timezone: str = "America/Chicago"


class DoctorSetupIn(BaseModel):
    """Create a doctor with availability in one call."""

    full_name: str
    specialties: list[str] = Field(default_factory=list)
    image_url: str | None = None
    availability: list[AvailabilityWindowIn] = Field(default_factory=list)


class BlockIn(BaseModel):
    start_at: str  # ISO datetime
    end_at: str
    reason: str | None = None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _appointment_outcome(appointment: dict[str, Any] | None) -> str | None:
    if not appointment:
        return None
    status = appointment.get("status")
    if status == "CONFIRMED":
        return "Appointment booked"
    if status == "CANCELLED":
        return "Appointment cancelled"
    if status:
        return f"Appointment {str(status).lower()}"
    return None


def _shape_call(row: dict[str, Any]) -> dict[str, Any]:
    appointments = [
        item for item in _as_list(row.get("appointments")) if isinstance(item, dict)
    ]
    appointment = appointments[0] if appointments else None

    return {
        "id": row.get("id"),
        "call_id": row.get("call_id"),
        "call_status": row.get("call_status") or "unknown",
        "outcome": row.get("outcome") or _appointment_outcome(appointment),
        "ended_reason": row.get("ended_reason"),
        "summary": row.get("summary"),
        "transcript": row.get("transcript") or [],
        "created_at": row.get("created_at"),
        "started_at": row.get("started_at"),
        "ended_at": row.get("ended_at"),
        "last_event_at": row.get("last_event_at") or row.get("created_at"),
        "patient": row.get("patients"),
        "appointments": appointments,
    }


# ------------------------------------------------------------------
# Doctors
# ------------------------------------------------------------------


@router.get("/doctors")
def list_doctors(active_only: bool = Query(default=True)):
    sb = get_supabase()
    query = sb.table("doctors").select("id,full_name,image_url,is_active,created_at")
    if active_only:
        query = query.eq("is_active", True)
    res = query.order("full_name").execute()
    return getattr(res, "data", None) or []


@router.post("/doctors")
def create_doctor(
    payload: DoctorSetupIn,
    current_user: Annotated[CurrentUser, Depends(get_current_superuser)],
):
    del current_user
    sb = get_supabase()

    # 1. Create doctor
    doc_res = (
        sb.table("doctors")
        .insert(
            {
                "full_name": payload.full_name,
                "image_url": payload.image_url,
            }
        )
        .execute()
    )
    doc_data = getattr(doc_res, "data", None) or []
    if not doc_data:
        raise HTTPException(status_code=500, detail="Failed to create doctor")
    doctor = doc_data[0]
    doctor_id = doctor["id"]

    # 2. Link specialties
    for s in payload.specialties:
        s = s.strip()
        if not s:
            continue
        # Upsert specialty
        existing = sb.table("specialties").select("id").eq("name", s).limit(1).execute()
        existing_data = getattr(existing, "data", None) or []
        if existing_data:
            specialty_id = existing_data[0]["id"]
        else:
            ins = sb.table("specialties").insert({"name": s}).execute()
            ins_data = getattr(ins, "data", None) or []
            specialty_id = ins_data[0]["id"] if ins_data else None
        if specialty_id:
            sb.table("doctor_specialties").insert(
                {
                    "doctor_id": doctor_id,
                    "specialty_id": specialty_id,
                }
            ).execute()

    # 3. Set availability
    if payload.availability:
        rows = [
            {
                "doctor_id": doctor_id,
                "day_of_week": w.day_of_week,
                "start_time": w.start_time,
                "end_time": w.end_time,
                "slot_minutes": w.slot_minutes,
                "timezone": w.timezone,
            }
            for w in payload.availability
        ]
        sb.table("doctor_availability").insert(rows).execute()

    return {"doctor": doctor, "status": "created"}


@router.get("/doctors/{doctor_id}/availability")
def get_availability(doctor_id: str):
    sb = get_supabase()
    res = (
        sb.table("doctor_availability")
        .select("*")
        .eq("doctor_id", doctor_id)
        .order("day_of_week")
        .execute()
    )
    return getattr(res, "data", None) or []


@router.put("/doctors/{doctor_id}/availability")
def set_availability(
    doctor_id: str,
    windows: list[AvailabilityWindowIn],
    current_user: Annotated[CurrentUser, Depends(get_current_superuser)],
):
    del current_user
    sb = get_supabase()
    # Replace all existing availability
    sb.table("doctor_availability").delete().eq("doctor_id", doctor_id).execute()
    if windows:
        rows = [
            {
                "doctor_id": doctor_id,
                "day_of_week": w.day_of_week,
                "start_time": w.start_time,
                "end_time": w.end_time,
                "slot_minutes": w.slot_minutes,
                "timezone": w.timezone,
            }
            for w in windows
        ]
        sb.table("doctor_availability").insert(rows).execute()
    return {"status": "updated"}


# ------------------------------------------------------------------
# Blocks
# ------------------------------------------------------------------


@router.post("/doctors/{doctor_id}/blocks")
def create_block(
    doctor_id: str,
    block: BlockIn,
    current_user: Annotated[CurrentUser, Depends(get_current_superuser)],
):
    del current_user
    sb = get_supabase()
    res = (
        sb.table("doctor_blocks")
        .insert(
            {
                "doctor_id": doctor_id,
                "start_at": block.start_at,
                "end_at": block.end_at,
                "reason": block.reason,
            }
        )
        .execute()
    )
    data = getattr(res, "data", None) or []
    if not data:
        raise HTTPException(status_code=500, detail="Failed to create block")
    return data[0]


@router.get("/doctors/{doctor_id}/blocks")
def list_blocks(doctor_id: str):
    sb = get_supabase()
    res = (
        sb.table("doctor_blocks")
        .select("*")
        .eq("doctor_id", doctor_id)
        .order("start_at")
        .execute()
    )
    return getattr(res, "data", None) or []


# ------------------------------------------------------------------
# Vapi call monitoring
# ------------------------------------------------------------------


@router.get("/calls")
def list_calls(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    sb = get_supabase()
    query = (
        sb.table("conversations")
        .select(
            "id,call_id,patient_id,transcript,summary,created_at,"
            "call_status,outcome,ended_reason,started_at,ended_at,last_event_at,"
            "patients(id,uin,full_name,phone),"
            "appointments(id,status,start_at,end_at,urgency,reason,symptoms,doctors(full_name))"
        )
        .order("last_event_at", desc=True)
        .limit(limit)
    )
    if status:
        query = query.eq("call_status", status)
    res = query.execute()
    rows = getattr(res, "data", None) or []
    return [_shape_call(row) for row in rows if isinstance(row, dict)]


@router.delete("/doctors/{doctor_id}/blocks/{block_id}")
def delete_block(
    doctor_id: str,
    block_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_superuser)],
):
    del current_user
    sb = get_supabase()
    sb.table("doctor_blocks").delete().eq("id", block_id).eq(
        "doctor_id", doctor_id
    ).execute()
    return {"status": "deleted"}


# ------------------------------------------------------------------
# Patients (read-only for now)
# ------------------------------------------------------------------


@router.get("/patients")
def list_patients(
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    limit: int = Query(default=50, le=200),
):
    del current_user
    sb = get_supabase()
    res = (
        sb.table("patients")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return getattr(res, "data", None) or []


@router.get("/patients/{uin}")
def get_patient_by_uin(
    uin: str,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
):
    del current_user
    sb = get_supabase()
    res = sb.table("patients").select("*").eq("uin", uin).limit(1).execute()
    data = getattr(res, "data", None) or []
    if not data:
        raise HTTPException(status_code=404, detail="Patient not found")
    return data[0]


# ------------------------------------------------------------------
# Appointments (read-only for now)
# ------------------------------------------------------------------


@router.get("/appointments")
def list_appointments(
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    del current_user
    sb = get_supabase()
    query = (
        sb.table("appointments")
        .select("*,doctors(full_name),patients(uin,full_name)")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status:
        query = query.eq("status", status)
    res = query.execute()
    return getattr(res, "data", None) or []
