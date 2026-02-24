from typing import Optional

_latest_call_id: Optional[str] = None
_latest_caller_phone: Optional[str] = None

def set_latest_call(call_id: str | None, caller_phone: str | None):
    global _latest_call_id, _latest_caller_phone
    if call_id:
        _latest_call_id = call_id
    if caller_phone:
        _latest_caller_phone = caller_phone

def get_latest_call():
    return _latest_call_id, _latest_caller_phone