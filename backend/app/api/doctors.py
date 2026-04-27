from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_current_active_user
from app.config import settings
from app.services.slot_engine import _generate_theoretical_slots, _is_blocked
from app.supabase import get_supabase

router = APIRouter(prefix="/doctors", tags=["doctors"])


class DoctorCard(BaseModel):
    id: str
    full_name: str
    image_url: str | None = None
    specialties: list[str] = Field(default_factory=list)


class DoctorSlot(BaseModel):
    id: str
    start_at: str
    end_at: str
    status: str
    appointment_id: str | None = None


class DaySchedule(BaseModel):
    date: str
    slots: list[DoctorSlot]


class DoctorSchedule(BaseModel):
    doctor_id: str
    doctor_name: str
    start_date: str
    days: int
    schedule: list[DaySchedule]


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _overlaps(
    start_at: datetime,
    end_at: datetime,
    other_start: datetime,
    other_end: datetime,
) -> bool:
    return start_at < other_end and end_at > other_start


@router.get("", response_model=list[DoctorCard])
@router.get("/", response_model=list[DoctorCard], include_in_schema=False)
def list_doctors(
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    active_only: bool = Query(default=True),
) -> list[DoctorCard]:
    del current_user

    sb = get_supabase()
    query = sb.table("doctors").select("id,full_name,image_url,is_active")
    if active_only:
        query = query.eq("is_active", True)
    doctors = getattr(query.order("full_name").execute(), "data", None) or []
    if not doctors:
        return []

    doctor_ids = [doctor["id"] for doctor in doctors]
    specialty_rows = (
        getattr(
            sb.table("doctor_specialties")
            .select("doctor_id,specialties(name)")
            .in_("doctor_id", doctor_ids)
            .execute(),
            "data",
            None,
        )
        or []
    )

    specialties_by_doctor: dict[str, list[str]] = {
        doctor_id: [] for doctor_id in doctor_ids
    }
    for row in specialty_rows:
        specialty = row.get("specialties")
        name = specialty.get("name") if isinstance(specialty, dict) else None
        if name:
            specialties_by_doctor.setdefault(row["doctor_id"], []).append(str(name))

    return [
        DoctorCard(
            id=doctor["id"],
            full_name=doctor["full_name"],
            image_url=doctor.get("image_url"),
            specialties=specialties_by_doctor.get(doctor["id"], []),
        )
        for doctor in doctors
    ]


@router.get("/{doctor_id}/schedule", response_model=DoctorSchedule)
def get_doctor_schedule(
    doctor_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    start_date: date,
    days: int = Query(default=7, ge=1, le=14),
) -> DoctorSchedule:
    del current_user

    sb = get_supabase()
    doctor_rows = (
        getattr(
            sb.table("doctors")
            .select("id,full_name,is_active")
            .eq("id", doctor_id)
            .limit(1)
            .execute(),
            "data",
            None,
        )
        or []
    )
    if not doctor_rows or not doctor_rows[0].get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    clinic_tz = ZoneInfo(settings.CLINIC_TIMEZONE)
    start_local = datetime.combine(start_date, time.min, tzinfo=clinic_tz)
    end_local = start_local + timedelta(days=days)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    availability = (
        getattr(
            sb.table("doctor_availability")
            .select("day_of_week,start_time,end_time,slot_minutes,timezone")
            .eq("doctor_id", doctor_id)
            .execute(),
            "data",
            None,
        )
        or []
    )
    appointments = (
        getattr(
            sb.table("appointments")
            .select("id,start_at,end_at,status")
            .eq("doctor_id", doctor_id)
            .neq("status", "CANCELLED")
            .lt("start_at", end_utc.isoformat())
            .gt("end_at", start_utc.isoformat())
            .execute(),
            "data",
            None,
        )
        or []
    )
    blocks = (
        getattr(
            sb.table("doctor_blocks")
            .select("start_at,end_at")
            .eq("doctor_id", doctor_id)
            .lt("start_at", end_utc.isoformat())
            .gt("end_at", start_utc.isoformat())
            .execute(),
            "data",
            None,
        )
        or []
    )

    appointment_ranges: list[tuple[datetime, datetime, dict[str, Any]]] = [
        (_parse_datetime(row["start_at"]), _parse_datetime(row["end_at"]), row)
        for row in appointments
    ]
    block_ranges = [
        (_parse_datetime(row["start_at"]), _parse_datetime(row["end_at"]))
        for row in blocks
    ]

    slots_by_day: dict[str, list[DoctorSlot]] = {
        (start_date + timedelta(days=offset)).isoformat(): []
        for offset in range(days)
    }
    for slot_start, slot_end in _generate_theoretical_slots(
        availability,
        start_utc,
        end_utc,
    ):
        if slot_end <= start_utc or slot_start >= end_utc:
            continue

        appointment = next(
            (
                row
                for appt_start, appt_end, row in appointment_ranges
                if _overlaps(slot_start, slot_end, appt_start, appt_end)
            ),
            None,
        )
        if appointment:
            slot_status = "BOOKED"
            appointment_id = appointment["id"]
        elif _is_blocked(slot_start, slot_end, block_ranges):
            slot_status = "BLOCKED"
            appointment_id = None
        else:
            slot_status = "AVAILABLE"
            appointment_id = None

        day_key = slot_start.astimezone(clinic_tz).date().isoformat()
        if day_key not in slots_by_day:
            continue

        slots_by_day[day_key].append(
            DoctorSlot(
                id=f"{doctor_id}:{slot_start.isoformat()}",
                start_at=slot_start.isoformat(),
                end_at=slot_end.isoformat(),
                status=slot_status,
                appointment_id=appointment_id,
            )
        )

    return DoctorSchedule(
        doctor_id=doctor_id,
        doctor_name=doctor_rows[0]["full_name"],
        start_date=start_date.isoformat(),
        days=days,
        schedule=[
            DaySchedule(date=day, slots=sorted(slots, key=lambda slot: slot.start_at))
            for day, slots in slots_by_day.items()
        ],
    )
