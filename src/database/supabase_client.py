import requests
from src.core.config import settings

HEADERS = {
    "apikey": settings.SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
    "Content-Type": "application/json"
}

BASE = settings.SUPABASE_URL + "/rest/v1"


def db_get(table: str, params: dict = {}) -> list:
    """Получить записи из таблицы"""
    r = requests.get(f"{BASE}/{table}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()


def db_insert(table: str, data: dict) -> dict:
    """Вставить запись в таблицу"""
    h = {**HEADERS, "Prefer": "return=representation"}
    r = requests.post(f"{BASE}/{table}", headers=h, json=data)
    r.raise_for_status()
    return r.json()[0]


# ── Profiles ──────────────────────────────────────────

def get_or_create_profile(tg_id: int, full_name: str) -> dict:
    result = db_get("profiles", {"tg_id": f"eq.{tg_id}"})
    if result:
        return result[0]
    return db_insert("profiles", {
        "tg_id": tg_id,
        "full_name": full_name,
        "role": "client"
    })


# ── Services ──────────────────────────────────────────

def get_active_services() -> list:
    return db_get("services", {"is_active": "eq.true"})


# ── Chat History ──────────────────────────────────────

def save_message(profile_id: str, role: str, content: str):
    db_insert("chat_history", {
        "profile_id": profile_id,
        "role": role,
        "content": content
    })


def get_chat_history(profile_id: str, limit: int = 10) -> list:
    result = db_get("chat_history", {
        "profile_id": f"eq.{profile_id}",
        "order": "created_at.desc",
        "limit": limit
    })
    return list(reversed(result))


# ── Bookings ──────────────────────────────────────────

def create_booking(client_id: str, service_id: str, booked_at: str, notes: str = "") -> dict:
    return db_insert("bookings", {
        "client_id": client_id,
        "service_id": service_id,
        "booked_at": booked_at,
        "notes": notes,
        "status": "pending"
    })


def get_client_bookings(client_id: str) -> list:
    return db_get("bookings", {"client_id": f"eq.{client_id}"})

def check_time_available(service_id: str, booked_at: str) -> tuple[bool, str]:
    """
    Проверяет свободно ли время у любого мастера для данной услуги.
    Возвращает (доступно: bool, master_id или сообщение об ошибке: str)
    """
    # Находим мастеров которые умеют эту услугу
    r = requests.get(
        f"{settings.SUPABASE_URL}/rest/v1/master_services",
        headers=HEADERS,
        params={"service_id": f"eq.{service_id}"},
        timeout=10
    )
    master_links = r.json()

    if not master_links:
        # Нет привязанных мастеров — разрешаем запись, уведомим админа
        return True, None

    # Проверяем каждого мастера
    for link in master_links:
        master_id = link["master_id"]

        # Проверяем активность мастера
        r2 = requests.get(
            f"{settings.SUPABASE_URL}/rest/v1/masters",
            headers=HEADERS,
            params={"id": f"eq.{master_id}", "is_active": "eq.true"},
            timeout=10
        )
        if not r2.json():
            continue

        # Вызываем SQL функцию через RPC
        r3 = requests.post(
            f"{settings.SUPABASE_URL}/rest/v1/rpc/check_master_availability",
            headers=HEADERS,
            json={
                "p_master_id":  master_id,
                "p_service_id": service_id,
                "p_booked_at":  booked_at
            },
            timeout=10
        )
        if r3.json() is True:
            return True, master_id  # Нашли свободного мастера

    return False, "busy"  # Все мастера заняты

def upsert_profile_by_phone(
    phone:     str,
    full_name: str,
    tg_id:     int  = None,
    wa_id:     str  = None
) -> dict:
    """
    Главная функция создания/обновления профиля.
    Ищет по номеру телефона — если есть, обновляет tg_id/wa_id.
    Если нет — создаёт новый.
    Это решает проблему одного человека в разных мессенджерах.
    """
    r = requests.post(
        f"{settings.SUPABASE_URL}/rest/v1/rpc/upsert_profile_by_phone",
        headers=HEADERS,
        json={
            "p_phone":     phone,
            "p_full_name": full_name,
            "p_tg_id":     tg_id,
            "p_wa_id":     wa_id
        },
        timeout=10
    )
    r.raise_for_status()
    return r.json()


def check_duplicate_booking(phone: str, service_id: str, booked_at: str) -> bool:
    """
    Проверяет нет ли уже записи этого человека
    на ту же услугу в то же время (из любого канала).
    Возвращает True если дубль найден.
    """
    # Находим профиль по телефону
    r = requests.get(
        f"{settings.SUPABASE_URL}/rest/v1/profiles",
        headers=HEADERS,
        params={"phone": f"eq.{phone}"},
        timeout=10
    )
    profiles = r.json()
    if not profiles:
        return False

    profile_id = profiles[0]["id"]

    # Проверяем есть ли уже запись в это время
    from datetime import datetime, timedelta
    dt      = datetime.fromisoformat(booked_at)
    dt_from = (dt - timedelta(minutes=30)).isoformat()
    dt_to   = (dt + timedelta(minutes=30)).isoformat()

    r2 = requests.get(
        f"{settings.SUPABASE_URL}/rest/v1/bookings",
        headers=HEADERS,
        params={
            "client_id": f"eq.{profile_id}",
            "booked_at": f"gte.{dt_from}",
            "status":    "in.(pending,confirmed)"
        },
        timeout=10
    )
    bookings = r2.json()

    # Фильтруем только те что попадают в окно ±30 мин
    for b in bookings:
        b_dt = datetime.fromisoformat(b["booked_at"].replace("Z", "+00:00")).replace(tzinfo=None)
        if dt_from <= b_dt.isoformat() <= dt_to:
            return True

    return False