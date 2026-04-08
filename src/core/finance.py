import requests
from datetime import datetime, timedelta
from src.core.config import settings

SUPA_HEADERS = {
    "apikey":        settings.SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation"
}


def get_revenue_for_period(date_from: str, date_to: str) -> dict:
    """
    Считает выручку за период.
    date_from, date_to — строки формата YYYY-MM-DD
    Возвращает dict с деталями.
    """
    r = requests.get(
        f"{settings.SUPABASE_URL}/rest/v1/bookings",
        headers=SUPA_HEADERS,
        params={
            "booked_at":      f"gte.{date_from}T00:00:00",
            "payment_method": "not.is.null",
            "order":          "booked_at.asc"
        },
        timeout=10
    )
    bookings = r.json()
    bookings = [b for b in bookings if b["booked_at"] <= f"{date_to}T23:59:59"]

    # Услуги для цен
    r2 = requests.get(
        f"https://web-production-bfb51b.up.railway.app/api/v1/services", timeout=10
    )
    services_map = {s["id"]: s for s in r2.json().get("services", [])}

    # Считаем по способам оплаты
    by_method = {}
    by_master = {}
    total     = 0

    for b in bookings:
        service = services_map.get(b["service_id"], {})
        price   = float(service.get("price", 0))
        method  = b.get("payment_method", "other")
        master_id = b.get("master_id")

        total += price
        by_method[method] = by_method.get(method, 0) + price

        if master_id:
            if master_id not in by_master:
                by_master[master_id] = {"revenue": 0, "count": 0}
            by_master[master_id]["revenue"] += price
            by_master[master_id]["count"]   += 1

    return {
        "total":      total,
        "count":      len(bookings),
        "by_method":  by_method,
        "by_master":  by_master,
        "date_from":  date_from,
        "date_to":    date_to
    }


def get_master_salary(master_profile_id: str, date_from: str, date_to: str) -> dict:
    """Считает зарплату мастера за период"""

    # Получаем ставку
    r = requests.get(
        f"{settings.SUPABASE_URL}/rest/v1/salary_rates",
        headers=SUPA_HEADERS,
        params={"profile_id": f"eq.{master_profile_id}"},
        timeout=10
    )
    rates = r.json()
    rate  = float(rates[0]["rate"]) if rates else 30.0

    # Находим master_id по profile_id
    r2 = requests.get(
        f"{settings.SUPABASE_URL}/rest/v1/masters",
        headers=SUPA_HEADERS,
        params={"profile_id": f"eq.{master_profile_id}"},
        timeout=10
    )
    masters = r2.json()
    if not masters:
        return {"error": "Мастер не найден"}

    master_id = masters[0]["id"]

    # Записи мастера за период
    r3 = requests.get(
        f"{settings.SUPABASE_URL}/rest/v1/bookings",
        headers=SUPA_HEADERS,
        params={
            "master_id":      f"eq.{master_id}",
            "booked_at":      f"gte.{date_from}T00:00:00",
            "payment_method": "not.is.null"
        },
        timeout=10
    )
    bookings = r3.json()
    bookings = [b for b in bookings if b["booked_at"] <= f"{date_to}T23:59:59"]

    r4 = requests.get(
        f"https://web-production-bfb51b.up.railway.app/api/v1/services", timeout=10
    )
    services_map = {s["id"]: s for s in r4.json().get("services", [])}

    revenue = sum(
        float(services_map.get(b["service_id"], {}).get("price", 0))
        for b in bookings
    )
    salary = revenue * rate / 100

    return {
        "revenue":   revenue,
        "rate":      rate,
        "salary":    salary,
        "count":     len(bookings),
        "date_from": date_from,
        "date_to":   date_to
    }


def get_all_staff_salary(date_from: str, date_to: str) -> list:
    """Зарплата всех сотрудников за период"""

    # Все ставки
    r = requests.get(
        f"{settings.SUPABASE_URL}/rest/v1/salary_rates",
        headers=SUPA_HEADERS,
        timeout=10
    )
    rates = r.json()

    result = []
    for rate_entry in rates:
        profile_id = rate_entry["profile_id"]

        # Профиль сотрудника
        r2 = requests.get(
            f"{settings.SUPABASE_URL}/rest/v1/profiles",
            headers=SUPA_HEADERS,
            params={"id": f"eq.{profile_id}"},
            timeout=10
        )
        profiles = r2.json()
        if not profiles:
            continue

        profile = profiles[0]
        role    = rate_entry["role"]

        if role == "master":
            data = get_master_salary(profile_id, date_from, date_to)
        else:
            # Для админа — % от общей выручки
            rev_data = get_revenue_for_period(date_from, date_to)
            rate     = float(rate_entry["rate"])
            salary   = rev_data["total"] * rate / 100
            data     = {
                "revenue": rev_data["total"],
                "rate":    rate,
                "salary":  salary,
                "count":   rev_data["count"]
            }

        result.append({
            "name":    profile["full_name"],
            "role":    role,
            "rate":    data.get("rate", 0),
            "revenue": data.get("revenue", 0),
            "salary":  data.get("salary", 0),
            "count":   data.get("count", 0)
        })

    return result


def parse_date_input(text: str) -> tuple[str, str] | None:
    """
    Парсит текст пользователя в даты.
    Понимает:
    - "сегодня"
    - "вчера"
    - "эта неделя"
    - "этот месяц"
    - "25.03.2026"  (один день)
    - "01.03.2026-25.03.2026" (период)
    Возвращает (date_from, date_to) или None если не распознал.
    """
    text  = text.strip().lower()
    today = datetime.now().date()

    if text in ("сегодня", "today"):
        d = today.strftime("%Y-%m-%d")
        return d, d

    if text in ("вчера", "yesterday"):
        d = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        return d, d

    if text in ("эта неделя", "неделя", "эту неделю", "за неделю"):
        start = today - timedelta(days=today.weekday())
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

    if text in ("этот месяц", "месяц", "за месяц"):
        start = today.replace(day=1)
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

    if text in ("прошлый месяц", "прошлый мес"):
        first_this = today.replace(day=1)
        last_prev  = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev.strftime("%Y-%m-%d"), last_prev.strftime("%Y-%m-%d")

    # Один день: 25.03.2026
    import re
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', text):
        try:
            d = datetime.strptime(text, "%d.%m.%Y").strftime("%Y-%m-%d")
            return d, d
        except Exception:
            return None

    # Период: 01.03.2026-25.03.2026
    match = re.match(r'^(\d{2}\.\d{2}\.\d{4})[- ](\d{2}\.\d{2}\.\d{4})$', text)
    if match:
        try:
            d_from = datetime.strptime(match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
            d_to   = datetime.strptime(match.group(2), "%d.%m.%Y").strftime("%Y-%m-%d")
            return d_from, d_to
        except Exception:
            return None

    return None