from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.core.ai_client import ask_ai
from src.database.supabase_client import (
    get_or_create_profile, get_active_services,
    save_message, get_chat_history,
    create_booking, get_client_bookings
)

router = APIRouter()

class ChatRequest(BaseModel):
    tg_id: int
    full_name: str
    message: str

class BookingRequest(BaseModel):
    client_id: str
    service_id: str
    booked_at: str
    notes: str = ""


@router.get("/services")
def list_services():
    return {"services": get_active_services()}


@router.post("/chat")
def chat(req: ChatRequest):
    profile = get_or_create_profile(req.tg_id, req.full_name)
    pid = profile["id"]
    history = get_chat_history(pid)
    reply = ask_ai(req.message, history)
    save_message(pid, "user", req.message)
    save_message(pid, "assistant", reply)
    return {"reply": reply}


@router.post("/bookings")
def book(req: BookingRequest):
    try:
        return {"booking": create_booking(req.client_id, req.service_id, req.booked_at, req.notes)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bookings/{client_id}")
def bookings(client_id: str):
    return {"bookings": get_client_bookings(client_id)}