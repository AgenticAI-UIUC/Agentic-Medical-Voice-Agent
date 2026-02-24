from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.services.supabase_client import get_supabase

from .slot_generator import generate_slots_for_doctor

router = APIRouter(prefix="/doctors", tags=["doctors"])


class DoctorCreateIn(BaseModel):
    full_name: str
    specialties: list[str] = Field(default_factory=list)
    # default schedule: 9–5 with lunch 12–1, 60-min slots (Mon–Fri)
    create_default_schedule: bool = True
    generate_slots_days: int = 14


class DoctorCard(BaseModel):
    id: UUID
    full_name: str
    image_url: str | None = None
    specialties: list[str] = Field(default_factory=list)


class SlotItem(BaseModel):
    id: UUID
    start_at: datetime
    end_at: datetime
    status: str
    appointment_id: UUID | None = None


class DaySchedule(BaseModel):
    date: date
    slots: list[SlotItem] = Field(default_factory=list)


class DoctorScheduleResponse(BaseModel):
    doctor_id: UUID
    doctor_name: str
    start_date: date
    days: int
    schedule: list[DaySchedule]


@router.get("")
def list_doctors(
    current_user: CurrentUser,
    active_only: bool = Query(default=True),
) -> list[DoctorCard]:
    _ = current_user
    supabase = get_supabase()

    doctor_query = supabase.table("doctors").select("id,full_name,image_url,is_active")
    if active_only:
        doctor_query = doctor_query.eq("is_active", True)

    doctors_result = doctor_query.order("full_name").execute()
    doctors = getattr(doctors_result, "data", None) or []

    if not doctors:
        return []

    doctor_ids = [doctor["id"] for doctor in doctors]
    specialties_result = (
        supabase.table("doctor_specialties")
        .select("doctor_id,specialties(name)")
        .in_("doctor_id", doctor_ids)
        .execute()
    )
    specialties_rows = getattr(specialties_result, "data", None) or []

    specialties_by_doctor: dict[str, list[str]] = {}
    for row in specialties_rows:
        specialty = row.get("specialties")
        name = specialty.get("name") if isinstance(specialty, dict) else None
        if not name:
            continue
        doctor_id = row["doctor_id"]
        specialties_by_doctor.setdefault(doctor_id, []).append(name)

    return [
        DoctorCard(
            id=doctor["id"],
            full_name=doctor["full_name"],
            image_url=doctor.get("image_url"),
            specialties=sorted(specialties_by_doctor.get(doctor["id"], [])),
        )
        for doctor in doctors
    ]


@router.get("/{doctor_id}/schedule")
def get_doctor_schedule(
    doctor_id: UUID,
    current_user: CurrentUser,
    start_date: date = Query(default_factory=date.today),
    days: int = Query(default=7, ge=1, le=31),
) -> DoctorScheduleResponse:
    _ = current_user
    supabase = get_supabase()

    doctor_result = (
        supabase.table("doctors")
        .select("id,full_name")
        .eq("id", str(doctor_id))
        .limit(1)
        .execute()
    )
    doctor_data = getattr(doctor_result, "data", None) or []
    if not doctor_data:
        raise HTTPException(status_code=404, detail="Doctor not found")

    start_dt = datetime.combine(start_date, datetime.min.time()).isoformat()
    end_date = start_date + timedelta(days=days)
    end_dt = datetime.combine(end_date, datetime.min.time()).isoformat()

    slots_result = (
        supabase.table("appointment_slots")
        .select("id,start_at,end_at,status,appointment_id")
        .eq("doctor_id", str(doctor_id))
        .gte("start_at", start_dt)
        .lt("start_at", end_dt)
        .order("start_at")
        .execute()
    )
    slots = getattr(slots_result, "data", None) or []

    schedule_map: dict[date, list[SlotItem]] = {
        start_date + timedelta(days=offset): [] for offset in range(days)
    }

    for slot in slots:
        slot_item = SlotItem.model_validate(slot)
        slot_day = slot_item.start_at.date()
        if slot_day in schedule_map:
            schedule_map[slot_day].append(slot_item)

    return DoctorScheduleResponse(
        doctor_id=doctor_data[0]["id"],
        doctor_name=doctor_data[0]["full_name"],
        start_date=start_date,
        days=days,
        schedule=[
            DaySchedule(date=day, slots=schedule_map[day])
            for day in sorted(schedule_map.keys())
        ],
    )


@router.post("")
def create_doctor(payload: DoctorCreateIn, current_user: CurrentUser) -> dict[str, Any]:
    _ = current_user
    supabase = get_supabase()

    # 1) create doctor
    dres = supabase.table("doctors").insert({"full_name": payload.full_name}).execute()
    ddata = getattr(dres, "data", None) or []
    if not ddata:
        raise HTTPException(status_code=500, detail="Failed to create doctor")
    doctor = ddata[0]
    doctor_id = doctor["id"]

    # 2) specialties (optional)
    for s in payload.specialties:
        s = s.strip()
        if not s:
            continue
        # insert specialty if not exists
        sres = supabase.table("specialties").select("id").eq("name", s).limit(1).execute()
        sdata = getattr(sres, "data", None) or []
        if sdata:
            specialty_id = sdata[0]["id"]
        else:
            ins = supabase.table("specialties").insert({"name": s}).execute()
            ins_data = getattr(ins, "data", None) or []
            specialty_id = ins_data[0]["id"] if ins_data else None
        if specialty_id:
            supabase.table("doctor_specialties").insert({
                "doctor_id": doctor_id,
                "specialty_id": specialty_id,
            }).execute()

    # 3) default schedule (Mon–Fri)
    if payload.create_default_schedule:
        rows = []
        # schema day_of_week: Sun=0..Sat=6, so Mon=1..Fri=5
        for dow in [1, 2, 3, 4, 5]:
            rows.append({
                "doctor_id": doctor_id,
                "day_of_week": dow,
                "start_time": "09:00:00",
                "end_time": "17:00:00",
                "slot_minutes": 60,
                "break_start": "12:00:00",
                "break_end": "13:00:00",
                "timezone": "America/Chicago",
            })
        supabase.table("doctor_availability").insert(rows).execute()

    # 4) generate slots for next N days
    gen = generate_slots_for_doctor(
        doctor_id=doctor_id,
        start_date=date.today(),
        days=payload.generate_slots_days,
    )

    return {"doctor": doctor, "slots_generation": gen}


@router.post("/{doctor_id}/generate-slots")
def generate_slots(
    doctor_id: str,
    current_user: CurrentUser,
    days: int = 14,
) -> dict[str, Any]:
    _ = current_user
    gen = generate_slots_for_doctor(
        doctor_id=doctor_id,
        start_date=date.today(),
        days=days,
    )
    return {"doctor_id": doctor_id, "slots_generation": gen}
