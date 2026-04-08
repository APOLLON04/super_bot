import requests
import threading
import time
from datetime import datetime, timedelta
from src.core.config import settings

SUPA_HEADERS = {
    "apikey": settings.SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}"
}

def send_reminder(tg_id: int, text: str):
    requests.post(
        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": tg_id, "text": text, "parse_mode": "HTML"}
    )

def check_and_send_reminders():
    """Проверяет записи на завтра и шлёт напоминания"""
    try:
        tomorrow       = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow_start = f"{tomorrow}T00:00:00"
        tomorrow_end   = f"{tomorrow}T23:59:59"

        # Берём все записи на завтра со статусом pending/confirmed
        r = requests.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={
                "booked_at": f"gte.{tomorrow_start}",
                "order": "booked_at.asc"
            },
            timeout=10
        )
        bookings = r.json()
        bookings = [b for b in bookings
                    if b.get("status") in ("pending", "confirmed")
                    and b["booked_at"] <= tomorrow_end]

        if not bookings:
            return

        # Берём услуги для названий
        r2 = requests.get(
            f"https://web-production-bfb51b.up.railway.app/api/v1/services", timeout=10
        )
        services_map = {s["id"]: s["name"] for s in r2.json().get("services", [])}

        for booking in bookings:
            # Берём профиль клиента
            r3 = requests.get(
                f"{settings.SUPABASE_URL}/rest/v1/profiles",
                headers=SUPA_HEADERS,
                params={"id": f"eq.{booking['client_id']}"},
                timeout=10
            )
            profiles = r3.json()
            if not profiles or not profiles[0].get("tg_id"):
                continue

            tg_id        = profiles[0]["tg_id"]
            service_name = services_map.get(booking["service_id"], "Услуга")

            try:
                dt       = datetime.fromisoformat(booking["booked_at"].replace("Z", "+00:00"))
                time_str = dt.strftime("%d.%m.%Y в %H:%M")
            except Exception:
                time_str = booking["booked_at"]

            send_reminder(tg_id,
                "🔔 <b>Напоминание о записи!</b>\n\n"
                f"Завтра вас ждём на:\n"
                f"💅 <b>{service_name}</b>\n"
                f"📅 <b>{time_str}</b>\n\n"
                "Если нужно перенести — напишите нам заранее 😊"
            )
            print(f"✅ Напоминание отправлено: tg_id={tg_id}, услуга={service_name}")

    except Exception as e:
        print(f"❌ Ошибка напоминаний: {e}")


def run_reminder_loop():
    """Запускает проверку каждый день в 10:00"""
    print("⏰ Планировщик напоминаний запущен...")
    while True:
        now = datetime.now()
        # Отправляем напоминания каждый день в 10:00
        if now.hour == 10 and now.minute == 0:
            print(f"⏰ Запускаем напоминания ({now.strftime('%d.%m.%Y %H:%M')})")
            check_and_send_reminders()
            time.sleep(60)  # Ждём минуту чтобы не запустить дважды
        time.sleep(30)  # Проверяем каждые 30 секунд

def check_and_send_review_requests():
    """Отправляет просьбу об отзыве после завершения визита"""
    try:
        now       = datetime.now()
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        two_hours_ago = (now - timedelta(hours=2)).isoformat()

        # Берём записи которые закончились 1-2 часа назад со статусом pending/confirmed
        r = requests.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={
                "booked_at": f"gte.{two_hours_ago}",
                "order":     "booked_at.asc"
            },
            timeout=10
        )
        bookings = r.json()

        # Фильтруем — только те что закончились ~час назад
        target = []
        for b in bookings:
            if b.get("status") not in ("pending", "confirmed"):
                continue
            try:
                dt = datetime.fromisoformat(b["booked_at"].replace("Z", "+00:00"))
                # Убираем timezone для сравнения
                dt_naive = dt.replace(tzinfo=None)
                if two_hours_ago[:19] <= dt_naive.isoformat() <= one_hour_ago[:19]:
                    target.append(b)
            except Exception:
                continue

        if not target:
            return

        # Получаем услуги
        r2 = requests.get(
            f"https://web-production-bfb51b.up.railway.app/api/v1/services", timeout=10
        )
        services_map = {s["id"]: s for s in r2.json().get("services", [])}

        for booking in target:
            # Получаем профиль клиента
            r3 = requests.get(
                f"{settings.SUPABASE_URL}/rest/v1/profiles",
                headers=SUPA_HEADERS,
                params={"id": f"eq.{booking['client_id']}"},
                timeout=10
            )
            profiles = r3.json()
            if not profiles or not profiles[0].get("tg_id"):
                continue

            tg_id   = profiles[0]["tg_id"]
            service = services_map.get(booking["service_id"], {})
            service_name = service.get("name", "услугу")

            # Отмечаем запись как завершённую
            requests.patch(
                f"{settings.SUPABASE_URL}/rest/v1/bookings",
                headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
                params={"id": f"eq.{booking['id']}"},
                json={"status": "completed"},
                timeout=10
            )

            # Отправляем просьбу об отзыве
            if settings.TWOGIS_REVIEW_URL:
                requests.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id":    tg_id,
                        "parse_mode": "HTML",
                        "text": (
                            f"💅 Надеемся, вам понравилась <b>{service_name}</b>!\n\n"
                            "Будем очень благодарны если оставите отзыв на 2GIS — "
                            "это помогает нам становиться лучше 🙏\n\n"
                            f"👇 <a href='{settings.TWOGIS_REVIEW_URL}'>Оставить отзыв на 2GIS</a>"
                        ),
                        "reply_markup": {"inline_keyboard": [[
                            {"text": "⭐️ Оставить отзыв на 2GIS",
                             "url": settings.TWOGIS_REVIEW_URL}
                        ]]}
                    }
                )
                print(f"✅ Отзыв запрошен: tg_id={tg_id}, услуга={service_name}")

    except Exception as e:
        print(f"❌ Ошибка запроса отзыва: {e}")


def run_reminder_loop():
    print("⏰ Планировщик напоминаний запущен...")
    while True:
        now = datetime.now()

        # Напоминания за день — каждый день в 10:00
        if now.hour == 10 and now.minute == 0:
            print(f"⏰ Напоминания за день ({now.strftime('%d.%m.%Y %H:%M')})")
            check_and_send_reminders()
            time.sleep(61)

        # Напоминания за 2 часа — каждые 15 минут проверяем
        if now.minute % 15 == 0:
            check_and_send_2hour_reminders()

        # Запросы отзывов — каждые 30 минут
        if now.minute in (0, 30):
            check_and_send_review_requests()

        time.sleep(30)


def check_and_send_2hour_reminders():
    """Напоминание клиентам за 2 часа до записи"""
    try:
        now         = datetime.now()
        target_from = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
        target_to   = (now + timedelta(hours=2, minutes=15)).strftime("%Y-%m-%dT%H:%M")

        r = requests.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={
                "booked_at": f"gte.{target_from}:00",
                "status":    "in.(pending,confirmed)",
                "order":     "booked_at.asc"
            },
            timeout=10
        )
        bookings = [
            b for b in r.json()
            if b["booked_at"][:16] <= target_to
        ]

        if not bookings:
            return

        import os
        api_url = os.environ.get("RAILWAY_URL", "http://localhost:8000")
        r2 = requests.get(f"{api_url}/api/v1/services", timeout=10)
        services_map = {s["id"]: s["name"] for s in r2.json().get("services", [])}

        for booking in bookings:
            r3 = requests.get(
                f"{settings.SUPABASE_URL}/rest/v1/profiles",
                headers=SUPA_HEADERS,
                params={"id": f"eq.{booking['client_id']}"},
                timeout=10
            )
            profiles = r3.json()
            if not profiles or not profiles[0].get("tg_id"):
                continue

            tg_id        = profiles[0]["tg_id"]
            service_name = services_map.get(booking["service_id"], "услугу")

            try:
                dt       = datetime.fromisoformat(booking["booked_at"].replace("Z", "+00:00"))
                time_str = dt.replace(tzinfo=None).strftime("%H:%M")
            except Exception:
                time_str = "—"

            requests.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id":    tg_id,
                    "parse_mode": "HTML",
                    "text": (
                        f"⏰ <b>Напоминание!</b>\n\n"
                        f"Через 2 часа вас ждём на:\n"
                        f"💅 <b>{service_name}</b>\n"
                        f"🕐 <b>в {time_str}</b>\n\n"
                        "Ждём вас! 😊"
                    )
                }
            )
            print(f"✅ 2ч напоминание: tg_id={tg_id}")

    except Exception as e:
        print(f"❌ Ошибка 2ч напоминания: {e}")