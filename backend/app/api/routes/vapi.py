from fastapi import APIRouter, Request, HTTPException
from app.services.vapi_state import set_latest_call

router = APIRouter(prefix="/vapi", tags=["vapi"])

VAPI_SHARED_SECRET = None  # set from env later if you want

def verify_secret(req: Request):
    if not VAPI_SHARED_SECRET:
        return
    token = req.headers.get("x-vapi-secret")
    if token != VAPI_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("/events")
async def vapi_events(request: Request):
    payload = await request.json()
    msg = payload.get("message", {})
    msg_type = msg.get("type", "")
    call = payload.get("call") or msg.get("call") or {}
    call_id = call.get("id")

    caller_phone = call.get("customer", {}).get("number")

    recording_url = None
    if msg_type == "end-of-call-report":
        recording_url = msg.get("artifact", {}).get("recordingUrl")

    print(f"VAPI EVENT type={msg_type} call_id={call_id} phone={caller_phone} rec={recording_url}")

    if call_id or caller_phone:
        set_latest_call(call_id, caller_phone)

    return {"ok": True}
