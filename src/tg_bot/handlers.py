import requests as req
from datetime import datetime, timedelta
from src.tg_bot.bot import (
    send_message, send_inline_keyboard,
    send_keyboard, send_reply_keyboard_remove,
    answer_callback, edit_message
)
from src.core.config import settings
from src.core.ai_client import ask_ai
from src.core.finance import (
    get_revenue_for_period, get_all_staff_salary,
    parse_date_input, get_master_salary
)

API = "http://localhost:8000/api/v1"
SUPA_HEADERS = {
    "apikey":        settings.SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation"
}

user_states = {}

CATEGORY_ICONS = {
    "Маникюр":   "💅",
    "Педикюр":   "🦶",
    "Ресницы":   "👁",
    "Шугаринг":  "🌿",
    "Комплексы": "✨",
    "Дизайн":    "🎨",
    "Брови":     "🧖",
    "Другое":    "💫"
}

PAYMENT_METHODS = {
    "cash":        "💵 Наличные",
    "transfer":    "📲 Перевод",
    "terminal":    "💳 Терминал",
    "certificate": "🎁 Сертификат"
}


# ═══════════════════════════════════════
# РОЛЬ
# ═══════════════════════════════════════

def get_role(tg_id: int) -> str:
    if tg_id in settings.CREATOR_IDS:  return "creator"
    if tg_id in settings.DIRECTOR_IDS: return "director"
    if tg_id in settings.ADMIN_IDS:    return "admin"
    if tg_id in settings.MASTER_IDS:   return "master"
    return "client"


# ═══════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════

def send_main_menu(chat_id: int, role: str, full_name: str, message_id: int = None):
    menus = {
        "client": {
            "text": f"👋 Привет, <b>{full_name}</b>!\nДобро пожаловать в наш салон красоты 💅",
            "buttons": [
                [{"text": "💅 Услуги и цены",   "callback_data": "services"},
                 {"text": "📝 Записаться",       "callback_data": "book"}],
                [{"text": "🗓 Мои записи",       "callback_data": "mybookings"},
                 {"text": "❓ Частые вопросы",   "callback_data": "faq"}],
                [{"text": "💬 Задать вопрос",    "callback_data": "ai_chat"},
                 {"text": "📍 Контакты",         "callback_data": "contacts"}]
            ]
        },
        "master": {
            "text": f"👩‍🎨 Привет, мастер <b>{full_name}</b>!",
            "buttons": [
                [{"text": "📋 Записи на сегодня", "callback_data": "master_today"},
                 {"text": "📅 Записи на неделю",  "callback_data": "master_week"}],
                [{"text": "✅ Завершить запись",   "callback_data": "master_complete_select"}]
            ]
        },
        "admin": {
            "text": f"🛠 Панель администратора\n<b>{full_name}</b>",
            "buttons": [
                [{"text": "📋 Записи сегодня",  "callback_data": "admin_today"},
                 {"text": "👥 Клиенты",         "callback_data": "admin_clients"}],
                [{"text": "➕ Добавить услугу",  "callback_data": "admin_add_service"},
                 {"text": "📊 Статистика",       "callback_data": "admin_stats"}],
                [{"text": "💰 Принять оплату",   "callback_data": "admin_payment"},
                 {"text": "🔔 Рассылка",         "callback_data": "admin_broadcast"}]
            ]
        },
        "director": {
            "text": f"👔 Панель директора\n<b>{full_name}</b>",
            "buttons": [
                [{"text": "📊 Финансовый отчёт", "callback_data": "dir_report_day"},
                 {"text": "👥 Зарплаты",         "callback_data": "dir_salary"}],
                [{"text": "📋 Записи сегодня",   "callback_data": "admin_today"},
                 {"text": "👥 Клиенты",          "callback_data": "admin_clients"}],
                [{"text": "⚙️ Ставки",           "callback_data": "dir_set_rates"},
                 {"text": "💰 Принять оплату",   "callback_data": "admin_payment"}]
            ]
        },
        "creator": {
            "text": f"⚡️ Режим создателя\n<b>{full_name}</b>",
            "buttons": [
                [{"text": "📊 Финансовый отчёт", "callback_data": "dir_report_day"},
                 {"text": "👥 Зарплаты",         "callback_data": "dir_salary"}],
                [{"text": "📋 Записи сегодня",   "callback_data": "admin_today"},
                 {"text": "👥 Клиенты",          "callback_data": "admin_clients"}],
                [{"text": "⚙️ Ставки",           "callback_data": "dir_set_rates"},
                 {"text": "💰 Принять оплату",   "callback_data": "admin_payment"}],
                [{"text": "🔔 Рассылка",         "callback_data": "admin_broadcast"},
                 {"text": "➕ Добавить услугу",   "callback_data": "admin_add_service"}]
            ]
        }
    }
    menu = menus.get(role, menus["client"])
    if message_id:
        edit_message(chat_id, message_id, menu["text"], menu["buttons"])
    else:
        send_inline_keyboard(chat_id, menu["text"], menu["buttons"])


# ═══════════════════════════════════════
# ОБРАБОТЧИК СООБЩЕНИЙ
# ═══════════════════════════════════════

def handle_message(message: dict):
    chat_id   = message["chat"]["id"]
    text      = message.get("text", "")
    user      = message.get("from", {})
    tg_id     = user.get("id")
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    role      = get_role(tg_id)

    if text in ("/start", "/menu"):
        user_states.pop(chat_id, None)
        send_main_menu(chat_id, role, full_name)
        return

    if text == "/cancel":
        user_states.pop(chat_id, None)
        send_reply_keyboard_remove(chat_id, "❌ Отменено.")
        send_main_menu(chat_id, role, full_name)
        return

    if chat_id in user_states:
        handle_smart_fsm(chat_id, text, user, full_name)
        return

    ai_chat(chat_id, text, user, full_name)


# ═══════════════════════════════════════
# УМНЫЙ FSM
# ═══════════════════════════════════════

def is_question_or_offtopic(text: str, step: str) -> bool:
    import re
    if step == "choose_datetime":
        if re.search(r'\d{1,2}[.\-/]\d{1,2}', text):
            return False
        date_words = ["завтра", "послезавтра", "сегодня", "понедельник",
                      "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        if any(w in text.lower() for w in date_words):
            return False
    if step == "enter_phone":
        import re
        if re.search(r'[\d\+\-\(\) ]{7,}', text):
            return False
    if step == "broadcast_text":
        return False

    question_signs = ["?", "как", "где", "когда", "сколько", "почему",
                      "что", "кто", "адрес", "цена", "стоит", "работаете",
                      "можно", "есть ли", "скажите", "уточните", "расскажите"]
    if any(s in text.lower() for s in question_signs):
        return True
    if len(text) > 30:
        return True
    return False


def handle_smart_fsm(chat_id: int, text: str, user: dict, full_name: str):
    state = user_states.get(chat_id)
    if not state:
        ai_chat(chat_id, text, user, full_name)
        return

    step = state["step"]

    if text in ("/cancel", "❌ Отмена"):
        user_states.pop(chat_id, None)
        send_reply_keyboard_remove(chat_id, "❌ Отменено.")
        role = get_role(user.get("id"))
        send_main_menu(chat_id, role, full_name)
        return

    # Рассылка — просто сохраняем текст
    if step == "set_rate":
        handle_fsm_step(chat_id, text, user, full_name, state)
        return
    
    if step == "broadcast_text":
        handle_fsm_step(chat_id, text, user, full_name, state)
        return

    # Перенос — ввод новой даты
    if step == "reschedule_datetime":
        handle_fsm_step(chat_id, text, user, full_name, state)
        return

    if is_question_or_offtopic(text, step):
        history = []
        try:
            r = req.get(
                f"{settings.SUPABASE_URL}/rest/v1/profiles",
                headers=SUPA_HEADERS,
                params={"tg_id": f"eq.{user.get('id')}"},
                timeout=5
            )
            profiles = r.json()
            if profiles:
                from src.database.supabase_client import get_chat_history
                history = get_chat_history(profiles[0]["id"], limit=6)
        except Exception:
            pass

        ai_reply = ask_ai(text, history)
        step_hints = {
            "choose_datetime":   "📅 Введите дату и время для записи\n<i>Формат: ДД.ММ.ГГГГ ЧЧ:ММ</i>",
            "enter_phone":       "📞 Введите ваш номер телефона",
            "reschedule_datetime": "📅 Введите новую дату\n<i>Формат: ДД.ММ.ГГГГ ЧЧ:ММ</i>"
        }
        hint = step_hints.get(step, "")
        send_inline_keyboard(chat_id,
            f"{ai_reply}\n\n<i>↩️ {hint}</i>",
            [[{"text": "❌ Отменить", "callback_data": "cancel_booking"}]]
        )
        return

    handle_fsm_step(chat_id, text, user, full_name, state)


def handle_fsm_step(chat_id: int, text: str, user: dict, full_name: str, state: dict):
    step = state["step"]

    # Запись — выбор даты
    if step == "choose_datetime":
        try:
            dt = datetime.strptime(text.strip(), "%d.%m.%Y %H:%M")
            if dt < datetime.now():
                send_message(chat_id, "⚠️ Дата не может быть в прошлом.")
                return
            from src.database.supabase_client import check_time_available
            available, master_id = check_time_available(
                state["data"]["service_id"], dt.isoformat()
            )
            if not available:
                send_message(chat_id,
                    "😔 <b>Это время уже занято.</b>\n\n"
                    "Введите другое время:\n<i>ДД.ММ.ГГГГ ЧЧ:ММ</i>"
                )
                return
            state["data"]["booked_at"]         = dt.isoformat()
            state["data"]["booked_at_display"] = dt.strftime("%d.%m.%Y в %H:%M")
            state["data"]["master_id"]         = master_id
            state["step"] = "enter_phone"
            send_message(chat_id,
                f"✅ Дата: <b>{state['data']['booked_at_display']}</b>\n\n"
                "📞 Введите ваш номер телефона:\n<i>Например: +7 777 123 45 67</i>"
            )
        except ValueError:
            send_message(chat_id, "⚠️ Формат: <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>\nНапример: 27.03.2026 14:00")

    # Запись — телефон
    elif step == "enter_phone":
        phone = text.strip()
        if len(phone) < 7:
            send_message(chat_id, "⚠️ Введите корректный номер телефона.")
            return

        # Проверяем дубль записи
        from src.database.supabase_client import check_duplicate_booking
        is_duplicate = check_duplicate_booking(
            phone,
            state["data"]["service_id"],
            state["data"]["booked_at"]
        )
        if is_duplicate:
            send_inline_keyboard(chat_id,
                "⚠️ <b>Вы уже записаны на это время!</b>\n\n"
                "У вас уже есть активная запись рядом с этим временем.\n"
                "Хотите посмотреть ваши записи?",
                [
                    [{"text": "🗓 Мои записи",  "callback_data": "mybookings"}],
                    [{"text": "📝 Другое время", "callback_data": "book"}],
                    [{"text": "🏠 Меню",         "callback_data": "main_menu"}]
                ]
            )
            user_states.pop(chat_id, None)
            return

        state["data"]["phone"] = phone

        # Создаём/обновляем профиль с телефоном
        from src.database.supabase_client import upsert_profile_by_phone
        tg_user   = state["user"]
        full_name = f"{tg_user.get('first_name', '')} {tg_user.get('last_name', '')}".strip()
        upsert_profile_by_phone(
            phone     = phone,
            full_name = full_name,
            tg_id     = tg_user.get("id")
        )

        finish_booking(chat_id, state, tg_user, full_name)

    # Перенос — новая дата
    elif step == "reschedule_datetime":
        try:
            dt = datetime.strptime(text.strip(), "%d.%m.%Y %H:%M")
            if dt < datetime.now():
                send_message(chat_id, "⚠️ Дата не может быть в прошлом.")
                return
            from src.database.supabase_client import check_time_available
            available, master_id = check_time_available(
                state["data"]["service_id"], dt.isoformat()
            )
            if not available:
                send_message(chat_id, "😔 Это время занято. Введите другое:")
                return

            # Обновляем запись
            req.patch(
                f"{settings.SUPABASE_URL}/rest/v1/bookings",
                headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
                params={"id": f"eq.{state['data']['booking_id']}"},
                json={
                    "booked_at": dt.isoformat(),
                    "master_id": master_id,
                    "status":    "pending"
                },
                timeout=10
            )
            user_states.pop(chat_id, None)
            date_str = dt.strftime("%d.%m.%Y в %H:%M")

            send_inline_keyboard(chat_id,
                f"✅ <b>Запись перенесена!</b>\n\n"
                f"{state['data']['service_name']}\n"
                f"📅 Новая дата: <b>{date_str}</b>",
                [[{"text": "🏠 Главное меню", "callback_data": "main_menu"}]]
            )

            # Уведомляем мастера
            notify_about_booking({
                "service_name":      state["data"]["service_name"],
                "service_id":        state["data"]["service_id"],
                "booked_at_display": date_str,
                "phone":             state["data"].get("phone", "—")
            }, full_name)

        except ValueError:
            send_message(chat_id, "⚠️ Формат: <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>")

    # Рассылка — текст
    elif step == "broadcast_text":
        text_to_send = text
        role = get_role(user.get("id"))
        user_states.pop(chat_id, None)

        # Получаем всех клиентов с tg_id
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/profiles",
            headers=SUPA_HEADERS,
            params={"role": "eq.client"},
            timeout=10
        )
        clients = r.json()
        sent = 0
        for c in clients:
            if c.get("tg_id"):
                try:
                    send_message(c["tg_id"],
                        f"📢 <b>Сообщение от салона:</b>\n\n{text_to_send}"
                    )
                    sent += 1
                except Exception:
                    pass

        send_inline_keyboard(chat_id,
            f"✅ Рассылка отправлена!\n📨 Получили: <b>{sent}</b> клиентов",
            [[{"text": "🏠 Главное меню", "callback_data": "main_menu"}]]
        )
    
    elif step == "set_rate":
        try:
            rate       = float(text.strip().replace("%", "").replace(",", "."))
            profile_id = state["data"]["profile_id"]
            role       = state["data"]["role"]
            name       = state["data"]["name"]

            if rate < 0 or rate > 100:
                send_message(chat_id, "⚠️ Введите число от 0 до 100.")
                return

            # Upsert ставки
            # Проверяем есть ли уже
            r = req.get(
                f"{settings.SUPABASE_URL}/rest/v1/salary_rates",
                headers=SUPA_HEADERS,
                params={"profile_id": f"eq.{profile_id}"},
                timeout=10
            )
            existing = r.json()

            if existing:
                req.patch(
                    f"{settings.SUPABASE_URL}/rest/v1/salary_rates",
                    headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
                    params={"profile_id": f"eq.{profile_id}"},
                    json={"rate": rate, "updated_at": datetime.now().isoformat()},
                    timeout=10
                )
            else:
                req.post(
                    f"{settings.SUPABASE_URL}/rest/v1/salary_rates",
                    headers=SUPA_HEADERS,
                    json={
                        "profile_id": profile_id,
                        "rate":       rate,
                        "role":       role
                    },
                    timeout=10
                )

            user_states.pop(chat_id, None)
            send_inline_keyboard(chat_id,
                f"✅ <b>Ставка обновлена!</b>\n\n"
                f"👤 {name}\n"
                f"💰 Новая ставка: <b>{rate}%</b>",
                [[{"text": "⚙️ Другие ставки", "callback_data": "dir_set_rates"},
                  {"text": "🏠 Меню",          "callback_data": "main_menu"}]]
            )
        except ValueError:
            send_message(chat_id, "⚠️ Введите число, например: 35")

    elif step == "finance_custom_date":
        dates = parse_date_input(text)
        if not dates:
            send_message(chat_id,
                "⚠️ Не могу распознать дату.\n"
                "Попробуйте: <b>25.03.2026</b> или <b>01.03.2026-25.03.2026</b>"
            )
            return
        user_states.pop(chat_id, None)
        date_from, date_to = dates
        show_finance_for_period(chat_id,
            # Нет message_id в FSM — отправляем новым сообщением
            0, f"{date_from[:10]}"
        )


# ═══════════════════════════════════════
# CALLBACK КНОПКИ
# ═══════════════════════════════════════

def handle_callback(callback: dict):
    chat_id    = callback["message"]["chat"]["id"]
    message_id = callback["message"]["message_id"]
    data       = callback.get("data", "")
    user       = callback.get("from", {})
    tg_id      = user.get("id")
    full_name  = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    role       = get_role(tg_id)

    answer_callback(callback["id"])

    # Динамические callback'и
    if data.startswith("set_rate:"):
        if role in ("director", "creator"):
            start_set_rate(chat_id, message_id, data.replace("set_rate:", ""), user)
        return
    if data.startswith("finance_period:"):
        period = data.replace("finance_period:", "")
        show_finance_for_period(chat_id, message_id, period)
        return
    if data.startswith("cat:"):
        show_services_by_category(chat_id, message_id, data.replace("cat:", ""))
        return
    if data.startswith("book_cat:"):
        show_services_in_category_for_booking(chat_id, message_id, data.replace("book_cat:", ""))
        return
    if data.startswith("pick_service:"):
        pick_service_for_booking(chat_id, message_id, data.replace("pick_service:", ""), user)
        return
    if data.startswith("cancel_booking_id:"):
        confirm_cancel_booking(chat_id, message_id, data.replace("cancel_booking_id:", ""))
        return
    if data.startswith("confirm_cancel:"):
        do_cancel_booking(chat_id, message_id, data.replace("confirm_cancel:", ""), user)
        return
    if data.startswith("reschedule_id:"):
        start_reschedule(chat_id, message_id, data.replace("reschedule_id:", ""), user)
        return
    if data.startswith("pay_booking:"):
        show_payment_methods(chat_id, message_id, data.replace("pay_booking:", ""))
        return
    if data.startswith("pay_method:"):
        parts = data.replace("pay_method:", "").split(":")
        if len(parts) == 2:
            process_payment(chat_id, message_id, parts[0], parts[1], user)
        return
    if data.startswith("master_done:"):
        master_complete_booking(chat_id, message_id, data.replace("master_done:", ""), user)
        return
    if data == "cancel_booking":
        user_states.pop(chat_id, None)
        send_main_menu(chat_id, role, full_name, message_id)
        return
    if data.startswith("salary_period:"):
        period = data.replace("salary_period:", "")
        if role in ("director", "creator"):
            show_salary_for_period(chat_id, message_id, period)
        else:
            edit_message(chat_id, message_id, "⛔️ Нет доступа.")
        return

    if data == "finance_custom_date":
        user_states[chat_id] = {
            "step": "finance_custom_date",
            "user": user,
            "data": {}
        }
        edit_message(chat_id, message_id,
            "✏️ <b>Введите дату или период:</b>\n\n"
            "<i>Примеры:\n"
            "• 25.03.2026\n"
            "• 01.03.2026-25.03.2026</i>",
            [[{"text": "❌ Отмена", "callback_data": "dir_report_day"}]]
        )
        return

    # Статичные callback'и
    handlers = {
        "services":              lambda: show_service_categories(chat_id, message_id),
        "book":                  lambda: show_service_categories_for_booking(chat_id, message_id),
        "mybookings":            lambda: show_my_bookings(chat_id, user, message_id),
        "faq":                   lambda: show_faq(chat_id, message_id),
        "ai_chat":               lambda: edit_message(chat_id, message_id, "💬 Напишите ваш вопрос — отвечу!"),
        "contacts":              lambda: show_contacts(chat_id, message_id),
        "admin_today":           lambda: show_all_bookings_today(chat_id, message_id) if role in ("admin","director","creator") else edit_message(chat_id, message_id, "⛔️ Нет доступа."),
        "admin_stats":           lambda: show_stats_today(chat_id, message_id) if role in ("admin","director","creator") else edit_message(chat_id, message_id, "⛔️ Нет доступа."),
        "dir_report_day":        lambda: show_stats_today(chat_id, message_id) if role in ("admin","director","creator") else edit_message(chat_id, message_id, "⛔️ Нет доступа."),
        "dir_revenue":           lambda: show_revenue(chat_id, message_id) if role in ("director","creator") else edit_message(chat_id, message_id, "⛔️ Нет доступа."),
        "admin_clients":         lambda: show_clients(chat_id, message_id) if role in ("admin","director","creator") else edit_message(chat_id, message_id, "⛔️ Нет доступа."),
        "admin_payment":         lambda: show_bookings_for_payment(chat_id, message_id) if role in ("admin","director","creator","master") else edit_message(chat_id, message_id, "⛔️ Нет доступа."),
        "admin_broadcast":       lambda: start_broadcast(chat_id, message_id, user) if role in ("admin","director","creator") else edit_message(chat_id, message_id, "⛔️ Нет доступа."),
        "master_today":          lambda: show_master_bookings(chat_id, tg_id, "today", message_id),
        "master_week":           lambda: show_master_bookings(chat_id, tg_id, "week", message_id),
        "master_complete_select":lambda: show_master_active_bookings(chat_id, tg_id, message_id),
        "main_menu":             lambda: send_main_menu(chat_id, role, full_name, message_id),
        "dir_report_day":    lambda: start_finance_report(chat_id, message_id, "today"),
        "dir_report_month":  lambda: start_finance_report(chat_id, message_id, "month"),
        "dir_salary":        lambda: start_salary_report(chat_id, message_id, user) if role in ("director","creator") else edit_message(chat_id, message_id, "⛔️ Нет доступа."),
        "dir_set_rates":     lambda: show_set_rates(chat_id, message_id) if role in ("director","creator") else edit_message(chat_id, message_id, "⛔️ Нет доступа."),
    }

    handler = handlers.get(data)
    if handler:
        handler()
    else:
        edit_message(chat_id, message_id, "🚧 Раздел в разработке.",
            [[{"text": "🏠 Главное меню", "callback_data": "main_menu"}]])


# ═══════════════════════════════════════
# УСЛУГИ
# ═══════════════════════════════════════

def get_all_services() -> list:
    r = req.get(f"{API}/services", timeout=10)
    return r.json().get("services", [])


def show_service_categories(chat_id: int, message_id: int):
    try:
        services   = get_all_services()
        categories = list(dict.fromkeys(s.get("category", "Другое") for s in services))
        buttons = []
        row = []
        for cat in categories:
            icon = CATEGORY_ICONS.get(cat, "💫")
            row.append({"text": f"{icon} {cat}", "callback_data": f"cat:{cat}"})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([{"text": "🏠 Главное меню", "callback_data": "main_menu"}])
        edit_message(chat_id, message_id, "💅 <b>Выберите категорию:</b>", buttons)
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка загрузки.")


def show_services_by_category(chat_id: int, message_id: int, category: str):
    try:
        services = get_all_services()
        filtered = [s for s in services if s.get("category") == category]
        icon = CATEGORY_ICONS.get(category, "💫")
        msg  = f"{icon} <b>{category}:</b>\n\n"
        for s in filtered:
            msg += f"<b>{s['name']}</b>\n💰 {int(s['price'])} ₸ · ⏱ {s['duration_min']} мин\n"
            if s.get("description"):
                msg += f"<i>{s['description']}</i>\n"
            msg += "\n"
        edit_message(chat_id, message_id, msg, [
            [{"text": "📝 Записаться",  "callback_data": "book"}],
            [{"text": "◀️ Назад",       "callback_data": "services"},
             {"text": "🏠 Меню",        "callback_data": "main_menu"}]
        ])
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка загрузки.")


def show_service_categories_for_booking(chat_id: int, message_id: int):
    try:
        services   = get_all_services()
        categories = list(dict.fromkeys(s.get("category", "Другое") for s in services))
        buttons = []
        row = []
        for cat in categories:
            icon = CATEGORY_ICONS.get(cat, "💫")
            row.append({"text": f"{icon} {cat}", "callback_data": f"book_cat:{cat}"})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([{"text": "❌ Отмена", "callback_data": "main_menu"}])
        edit_message(chat_id, message_id, "📋 <b>Выберите категорию:</b>", buttons)
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка загрузки.")


def show_services_in_category_for_booking(chat_id: int, message_id: int, category: str):
    try:
        services = get_all_services()
        filtered = [s for s in services if s.get("category") == category]
        icon     = CATEGORY_ICONS.get(category, "💫")
        buttons  = []
        for s in filtered:
            buttons.append([{
                "text":          f"{s['name']} — {int(s['price'])} ₸",
                "callback_data": f"pick_service:{s['id']}"
            }])
        buttons.append([
            {"text": "◀️ Назад",  "callback_data": "book"},
            {"text": "❌ Отмена", "callback_data": "main_menu"}
        ])
        edit_message(chat_id, message_id, f"{icon} <b>{category}</b>\nВыберите услугу:", buttons)
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка загрузки.")


def pick_service_for_booking(chat_id: int, message_id: int, service_id: str, user: dict):
    try:
        services = get_all_services()
        service  = next((s for s in services if s["id"] == service_id), None)
        if not service:
            edit_message(chat_id, message_id, "❌ Услуга не найдена.")
            return
        user_states[chat_id] = {
            "step": "choose_datetime",
            "user": user,
            "data": {
                "service_id":   service["id"],
                "service_name": service["name"]
            }
        }
        edit_message(chat_id, message_id,
            f"✅ Услуга: <b>{service['name']}</b>\n"
            f"💰 {int(service['price'])} ₸ · ⏱ {service['duration_min']} мин\n\n"
            "📅 <b>Введите дату и время:</b>\n"
            "<i>Формат: ДД.ММ.ГГГГ ЧЧ:ММ\nНапример: 27.03.2026 14:00</i>",
            [[{"text": "❌ Отменить", "callback_data": "cancel_booking"}]]
        )
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка.")


# ═══════════════════════════════════════
# ЗАВЕРШЕНИЕ ЗАПИСИ
# ═══════════════════════════════════════

def finish_booking(chat_id: int, state: dict, user: dict, full_name: str):
    data = state["data"]
    try:
        # Ищем профиль по телефону (единый across всех каналов)
        from src.database.supabase_client import upsert_profile_by_phone
        profile = upsert_profile_by_phone(
            phone     = data["phone"],
            full_name = full_name,
            tg_id     = user.get("id")
        )
        profile_id = profile["id"]
        req.post(f"{API}/bookings", json={
            "client_id":  profile_id,
            "service_id": data["service_id"],
            "booked_at":  data["booked_at"],
            "master_id":  data.get("master_id"),
            "notes":      f"Телефон: {data['phone']}"
        }, timeout=10)
        user_states.pop(chat_id, None)
        notify_about_booking(data, full_name)
        send_inline_keyboard(chat_id,
            "✅ <b>Запись подтверждена!</b>\n\n"
            f"{data['service_name']}\n"
            f"📅 {data['booked_at_display']}\n"
            f"📞 {data['phone']}\n\nЖдём вас! 😊",
            [[{"text": "🏠 Главное меню", "callback_data": "main_menu"}]]
        )
    except Exception:
        user_states.pop(chat_id, None)
        send_message(chat_id, "❌ Ошибка при записи. Попробуйте позже.")


# ═══════════════════════════════════════
# МОИ ЗАПИСИ + ОТМЕНА + ПЕРЕНОС
# ═══════════════════════════════════════

def show_my_bookings(chat_id: int, user: dict, message_id: int):
    try:
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/profiles",
            headers=SUPA_HEADERS,
            params={"tg_id": f"eq.{user.get('id')}"},
            timeout=10
        )
        profiles = r.json()
        if not profiles:
            edit_message(chat_id, message_id, "😔 У вас пока нет записей.",
                [[{"text": "📝 Записаться", "callback_data": "book"}]])
            return

        profile_id = profiles[0]["id"]
        r2 = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={
                "client_id": f"eq.{profile_id}",
                "status":    "in.(pending,confirmed)",
                "order":     "booked_at.asc"
            },
            timeout=10
        )
        bookings = r2.json()
        if not bookings:
            edit_message(chat_id, message_id, "😔 Активных записей нет.",
                [[{"text": "📝 Записаться", "callback_data": "book"},
                  {"text": "🏠 Меню",       "callback_data": "main_menu"}]])
            return

        services_map = {s["id"]: s["name"] for s in get_all_services()}
        msg = "🗓 <b>Ваши записи:</b>\n\n"
        buttons = []
        for b in bookings:
            try:
                dt       = datetime.fromisoformat(b["booked_at"].replace("Z", "+00:00"))
                date_str = dt.strftime("%d.%m.%Y в %H:%M")
            except Exception:
                date_str = b["booked_at"]
            sname = services_map.get(b["service_id"], "Услуга")
            msg  += f"💅 <b>{sname}</b>\n📅 {date_str}\n⏳ Ожидает подтверждения\n\n"
            buttons.append([
                {"text": f"🔄 Перенести — {sname[:20]}", "callback_data": f"reschedule_id:{b['id']}"},
                {"text": f"❌ Отменить",                 "callback_data": f"cancel_booking_id:{b['id']}"}
            ])
        buttons.append([{"text": "📝 Новая запись", "callback_data": "book"},
                        {"text": "🏠 Меню",         "callback_data": "main_menu"}])
        edit_message(chat_id, message_id, msg, buttons)
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка загрузки.")


def confirm_cancel_booking(chat_id: int, message_id: int, booking_id: str):
    edit_message(chat_id, message_id,
        "❓ <b>Вы уверены что хотите отменить запись?</b>\n\n"
        "Отменить запись можно не позднее чем за 2 часа.",
        [
            [{"text": "✅ Да, отменить",  "callback_data": f"confirm_cancel:{booking_id}"},
             {"text": "◀️ Назад",         "callback_data": "mybookings"}]
        ]
    )


def do_cancel_booking(chat_id: int, message_id: int, booking_id: str, user: dict):
    try:
        # Проверяем что до записи больше 2 часов
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={"id": f"eq.{booking_id}"},
            timeout=10
        )
        bookings = r.json()
        if not bookings:
            edit_message(chat_id, message_id, "❌ Запись не найдена.")
            return

        booking = bookings[0]
        dt      = datetime.fromisoformat(booking["booked_at"].replace("Z", "+00:00"))
        dt_naive = dt.replace(tzinfo=None)

        if dt_naive - datetime.now() < timedelta(hours=2):
            edit_message(chat_id, message_id,
                "⚠️ <b>Отменить нельзя.</b>\n\n"
                "До записи осталось менее 2 часов.\n"
                "Пожалуйста, свяжитесь с нами напрямую 📞",
                [[{"text": "📍 Контакты",  "callback_data": "contacts"},
                  {"text": "🏠 Меню",      "callback_data": "main_menu"}]]
            )
            return

        # Отменяем
        req.patch(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
            params={"id": f"eq.{booking_id}"},
            json={"status": "cancelled"},
            timeout=10
        )

        # Уведомляем админа
        services_map = {s["id"]: s["name"] for s in get_all_services()}
        sname = services_map.get(booking["service_id"], "Услуга")
        msg   = (
            f"❌ <b>Клиент отменил запись!</b>\n\n"
            f"💅 {sname}\n"
            f"📅 {dt_naive.strftime('%d.%m.%Y в %H:%M')}\n"
        )
        for aid in settings.ADMIN_IDS + settings.CREATOR_IDS:
            send_message(aid, msg)

        edit_message(chat_id, message_id,
            "✅ <b>Запись отменена.</b>\n\nЕсли захотите — запишитесь снова 😊",
            [[{"text": "📝 Записаться", "callback_data": "book"},
              {"text": "🏠 Меню",       "callback_data": "main_menu"}]]
        )
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка. Попробуйте позже.")


def start_reschedule(chat_id: int, message_id: int, booking_id: str, user: dict):
    try:
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={"id": f"eq.{booking_id}"},
            timeout=10
        )
        bookings = r.json()
        if not bookings:
            edit_message(chat_id, message_id, "❌ Запись не найдена.")
            return

        booking      = bookings[0]
        services_map = {s["id"]: s["name"] for s in get_all_services()}
        sname        = services_map.get(booking["service_id"], "Услуга")

        user_states[chat_id] = {
            "step": "reschedule_datetime",
            "user": user,
            "data": {
                "booking_id":   booking_id,
                "service_id":   booking["service_id"],
                "service_name": sname,
                "phone":        booking.get("notes", "").replace("Телефон: ", "")
            }
        }
        edit_message(chat_id, message_id,
            f"🔄 <b>Перенос записи</b>\n\n"
            f"Услуга: <b>{sname}</b>\n\n"
            "📅 Введите новую дату и время:\n"
            "<i>Формат: ДД.ММ.ГГГГ ЧЧ:ММ\nНапример: 28.03.2026 15:00</i>",
            [[{"text": "❌ Отмена", "callback_data": "mybookings"}]]
        )
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка.")


# ═══════════════════════════════════════
# FAQ
# ═══════════════════════════════════════

def show_faq(chat_id: int, message_id: int):
    try:
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/faq",
            headers=SUPA_HEADERS,
            params={"is_active": "eq.true", "order": "order_num.asc"},
            timeout=10
        )
        faqs = r.json()
        if not faqs:
            edit_message(chat_id, message_id, "😔 FAQ пока не добавлен.",
                [[{"text": "🏠 Меню", "callback_data": "main_menu"}]])
            return

        msg = "❓ <b>Частые вопросы:</b>\n\n"
        for f in faqs:
            msg += f"<b>{f['question']}</b>\n{f['answer']}\n\n"

        edit_message(chat_id, message_id, msg, [
            [{"text": "💬 Задать свой вопрос", "callback_data": "ai_chat"}],
            [{"text": "🏠 Главное меню",        "callback_data": "main_menu"}]
        ])
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка загрузки.")


# ═══════════════════════════════════════
# ПАНЕЛЬ МАСТЕРА
# ═══════════════════════════════════════

def show_master_bookings(chat_id: int, tg_id: int, period: str, message_id: int):
    try:
        # Находим мастера по tg_id
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/masters",
            headers=SUPA_HEADERS,
            params={"tg_id": f"eq.{tg_id}"},
            timeout=10
        )
        masters = r.json()
        if not masters:
            edit_message(chat_id, message_id,
                "⚠️ Ваш профиль мастера не найден.\nОбратитесь к администратору.",
                [[{"text": "🏠 Меню", "callback_data": "main_menu"}]])
            return

        master_id = masters[0]["id"]
        today     = datetime.now().strftime("%Y-%m-%d")

        if period == "today":
            params = {
                "master_id": f"eq.{master_id}",
                "booked_at": f"gte.{today}T00:00:00",
                "status":    "in.(pending,confirmed)",
                "order":     "booked_at.asc"
            }
            title = "📋 Записи на сегодня"
        else:
            week_end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            params   = {
                "master_id": f"eq.{master_id}",
                "booked_at": f"gte.{today}T00:00:00",
                "status":    "in.(pending,confirmed)",
                "order":     "booked_at.asc"
            }
            title = "📅 Записи на неделю"

        r2       = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params=params,
            timeout=10
        )
        bookings = r2.json()

        if not bookings:
            edit_message(chat_id, message_id,
                f"{title}\n\n😊 Записей нет — можно отдохнуть!",
                [[{"text": "🏠 Меню", "callback_data": "main_menu"}]])
            return

        services_map = {s["id"]: s["name"] for s in get_all_services()}

        # Получаем телефоны клиентов
        client_ids = list(set(b["client_id"] for b in bookings))
        clients_map = {}
        for cid in client_ids:
            rc = req.get(
                f"{settings.SUPABASE_URL}/rest/v1/profiles",
                headers=SUPA_HEADERS,
                params={"id": f"eq.{cid}"},
                timeout=10
            )
            result = rc.json()
            if result:
                clients_map[cid] = result[0]

        msg = f"{title} (<b>{len(bookings)}</b>):\n\n"
        for b in bookings:
            try:
                dt       = datetime.fromisoformat(b["booked_at"].replace("Z", "+00:00"))
                time_str = dt.strftime("%d.%m %H:%M")
            except Exception:
                time_str = "—"
            sname  = services_map.get(b["service_id"], "Услуга")
            client = clients_map.get(b["client_id"], {})
            cname  = client.get("full_name", "Клиент")
            notes  = b.get("notes", "")
            msg   += f"🕐 <b>{time_str}</b> — {sname}\n"
            msg   += f"   👤 {cname}"
            if notes:
                msg += f" · {notes}"
            msg += "\n\n"

        edit_message(chat_id, message_id, msg,
            [[{"text": "✅ Завершить запись", "callback_data": "master_complete_select"},
              {"text": "🏠 Меню",             "callback_data": "main_menu"}]]
        )
    except Exception as e:
        edit_message(chat_id, message_id, f"❌ Ошибка загрузки.")


def show_master_active_bookings(chat_id: int, tg_id: int, message_id: int):
    """Показать активные записи мастера для отметки выполнения"""
    try:
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/masters",
            headers=SUPA_HEADERS,
            params={"tg_id": f"eq.{tg_id}"},
            timeout=10
        )
        masters = r.json()
        if not masters:
            edit_message(chat_id, message_id, "⚠️ Профиль мастера не найден.")
            return

        master_id = masters[0]["id"]
        today     = datetime.now().strftime("%Y-%m-%d")
        r2        = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={
                "master_id": f"eq.{master_id}",
                "booked_at": f"gte.{today}T00:00:00",
                "status":    "in.(pending,confirmed)",
                "order":     "booked_at.asc"
            },
            timeout=10
        )
        bookings     = r2.json()
        services_map = {s["id"]: s["name"] for s in get_all_services()}

        if not bookings:
            edit_message(chat_id, message_id, "😊 Нет активных записей на сегодня.",
                [[{"text": "🏠 Меню", "callback_data": "main_menu"}]])
            return

        buttons = []
        for b in bookings:
            try:
                dt       = datetime.fromisoformat(b["booked_at"].replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M")
            except Exception:
                time_str = "—"
            sname = services_map.get(b["service_id"], "Услуга")
            buttons.append([{
                "text":          f"✅ {time_str} — {sname}",
                "callback_data": f"master_done:{b['id']}"
            }])
        buttons.append([{"text": "🏠 Меню", "callback_data": "main_menu"}])
        edit_message(chat_id, message_id, "✅ <b>Выберите выполненную запись:</b>", buttons)
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка.")


def master_complete_booking(chat_id: int, message_id: int, booking_id: str, user: dict):
    """Мастер отмечает запись выполненной"""
    try:
        req.patch(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
            params={"id": f"eq.{booking_id}"},
            json={"status": "completed"},
            timeout=10
        )
        # Уведомляем админа об оплате
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={"id": f"eq.{booking_id}"},
            timeout=10
        )
        booking      = r.json()[0] if r.json() else {}
        services_map = {s["id"]: s["name"] for s in get_all_services()}
        sname        = services_map.get(booking.get("service_id", ""), "Услуга")

        for aid in settings.ADMIN_IDS + settings.CREATOR_IDS:
            send_message(aid,
                f"✅ <b>Визит завершён!</b>\n\n"
                f"💅 {sname}\n"
                f"📝 {booking.get('notes', '')}\n\n"
                f"💰 Не забудьте принять оплату!"
            )

        edit_message(chat_id, message_id,
            "✅ <b>Запись отмечена как выполненная!</b>\n\nАдмин получил уведомление об оплате.",
            [[{"text": "📋 Мои записи", "callback_data": "master_today"},
              {"text": "🏠 Меню",       "callback_data": "main_menu"}]]
        )
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка.")


# ═══════════════════════════════════════
# ОПЛАТА (АДМИН)
# ═══════════════════════════════════════

def show_bookings_for_payment(chat_id: int, message_id: int):
    """Показать завершённые записи без оплаты"""
    try:
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={
                "status":         "eq.completed",
                "payment_method": "is.null",
                "order":          "booked_at.desc",
                "limit":          "10"
            },
            timeout=10
        )
        bookings     = r.json()
        services_map = {s["id"]: s["name"] for s in get_all_services()}

        if not bookings:
            edit_message(chat_id, message_id,
                "✅ Все оплаты приняты!",
                [[{"text": "🏠 Меню", "callback_data": "main_menu"}]])
            return

        buttons = []
        for b in bookings:
            try:
                dt       = datetime.fromisoformat(b["booked_at"].replace("Z", "+00:00"))
                time_str = dt.strftime("%d.%m %H:%M")
            except Exception:
                time_str = "—"
            sname = services_map.get(b["service_id"], "Услуга")
            buttons.append([{
                "text":          f"💰 {time_str} — {sname}",
                "callback_data": f"pay_booking:{b['id']}"
            }])
        buttons.append([{"text": "🏠 Меню", "callback_data": "main_menu"}])
        edit_message(chat_id, message_id,
            "💰 <b>Выберите запись для оплаты:</b>", buttons)
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка загрузки.")


def show_payment_methods(chat_id: int, message_id: int, booking_id: str):
    """Выбор способа оплаты"""
    edit_message(chat_id, message_id,
        "💰 <b>Выберите способ оплаты:</b>",
        [
            [{"text": "💵 Наличные",   "callback_data": f"pay_method:{booking_id}:cash"},
             {"text": "📲 Перевод",    "callback_data": f"pay_method:{booking_id}:transfer"}],
            [{"text": "💳 Терминал",   "callback_data": f"pay_method:{booking_id}:terminal"},
             {"text": "🎁 Сертификат", "callback_data": f"pay_method:{booking_id}:certificate"}],
            [{"text": "◀️ Назад",      "callback_data": "admin_payment"}]
        ]
    )


def process_payment(chat_id: int, message_id: int, booking_id: str, method: str, user: dict):
    """Записываем оплату"""
    try:
        # Получаем запись
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={"id": f"eq.{booking_id}"},
            timeout=10
        )
        booking = r.json()[0] if r.json() else {}

        services_map = {s["id"]: s for s in get_all_services()}
        service      = services_map.get(booking.get("service_id", ""), {})
        price        = service.get("price", 0)
        sname        = service.get("name", "Услуга")
        method_label = PAYMENT_METHODS.get(method, method)

        # Сохраняем оплату
        req.patch(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers={**SUPA_HEADERS, "Prefer": "return=minimal"},
            params={"id": f"eq.{booking_id}"},
            json={
                "payment_method": method,
                "payment_amount": price
            },
            timeout=10
        )

        edit_message(chat_id, message_id,
            f"✅ <b>Оплата принята!</b>\n\n"
            f"💅 {sname}\n"
            f"💰 Сумма: <b>{int(price):,} ₸</b>\n"
            f"💳 Способ: <b>{method_label}</b>",
            [
                [{"text": "💰 Следующая оплата", "callback_data": "admin_payment"}],
                [{"text": "🏠 Главное меню",      "callback_data": "main_menu"}]
            ]
        )
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка записи оплаты.")


# ═══════════════════════════════════════
# РАССЫЛКА
# ═══════════════════════════════════════

def start_broadcast(chat_id: int, message_id: int, user: dict):
    user_states[chat_id] = {
        "step": "broadcast_text",
        "user": user,
        "data": {}
    }
    edit_message(chat_id, message_id,
        "📢 <b>Рассылка клиентам</b>\n\n"
        "Напишите текст сообщения которое получат все клиенты:",
        [[{"text": "❌ Отмена", "callback_data": "main_menu"}]]
    )


# ═══════════════════════════════════════
# АДМИН ПАНЕЛЬ
# ═══════════════════════════════════════

def show_all_bookings_today(chat_id: int, message_id: int):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        r     = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={"booked_at": f"gte.{today}T00:00:00", "order": "booked_at.asc"},
            timeout=10
        )
        bookings = r.json()
        if not bookings:
            edit_message(chat_id, message_id, "📋 На сегодня записей нет.",
                [[{"text": "🏠 Меню", "callback_data": "main_menu"}]])
            return

        services_map = {s["id"]: s["name"] for s in get_all_services()}
        status_map   = {
            "pending":   "⏳",
            "confirmed": "✅",
            "cancelled": "❌",
            "completed": "🏁"
        }
        msg = f"📋 <b>Записи на сегодня ({len(bookings)}):</b>\n\n"
        for b in bookings:
            try:
                dt       = datetime.fromisoformat(b["booked_at"].replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M")
            except Exception:
                time_str = "—"
            status = status_map.get(b.get("status", ""), "")
            msg   += f"{status} <b>{time_str}</b> — {services_map.get(b['service_id'], 'Услуга')}\n"
            if b.get("notes"):
                msg += f"   📞 {b['notes']}\n"
        edit_message(chat_id, message_id, msg,
            [[{"text": "💰 Принять оплату", "callback_data": "admin_payment"},
              {"text": "🏠 Меню",           "callback_data": "main_menu"}]])
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка загрузки.")


def show_stats_today(chat_id: int, message_id: int):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        r     = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={"booked_at": f"gte.{today}T00:00:00"},
            timeout=10
        )
        bookings     = r.json()
        services_map = {s["id"]: s["price"] for s in get_all_services()}

        total     = len(bookings)
        completed = len([b for b in bookings if b.get("status") == "completed"])
        cancelled = len([b for b in bookings if b.get("status") == "cancelled"])
        revenue   = sum(
            services_map.get(b["service_id"], 0)
            for b in bookings
            if b.get("payment_method")
        )

        edit_message(chat_id, message_id,
            f"📊 <b>Статистика за сегодня:</b>\n\n"
            f"📋 Всего записей: <b>{total}</b>\n"
            f"🏁 Завершено: <b>{completed}</b>\n"
            f"❌ Отменено: <b>{cancelled}</b>\n"
            f"💰 Выручка: <b>{int(revenue):,} ₸</b>\n"
            f"📅 {today}",
            [[{"text": "💰 Принять оплату", "callback_data": "admin_payment"},
              {"text": "🏠 Меню",           "callback_data": "main_menu"}]]
        )
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка загрузки.")


def show_revenue(chat_id: int, message_id: int):
    try:
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/bookings",
            headers=SUPA_HEADERS,
            params={"payment_method": "not.is.null"},
            timeout=10
        )
        bookings     = r.json()
        services_map = {s["id"]: s["price"] for s in get_all_services()}

        by_method = {}
        for b in bookings:
            m     = b.get("payment_method", "other")
            price = services_map.get(b["service_id"], 0)
            by_method[m] = by_method.get(m, 0) + price

        total = sum(by_method.values())
        msg   = f"💰 <b>Общая выручка:</b>\n\n"
        for method, amount in by_method.items():
            label = PAYMENT_METHODS.get(method, method)
            msg  += f"{label}: <b>{int(amount):,} ₸</b>\n"
        msg += f"\n📊 Итого: <b>{int(total):,} ₸</b>"

        edit_message(chat_id, message_id, msg,
            [[{"text": "🏠 Меню", "callback_data": "main_menu"}]])
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка загрузки.")


def show_clients(chat_id: int, message_id: int):
    try:
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/profiles",
            headers=SUPA_HEADERS,
            params={"role": "eq.client", "order": "created_at.desc", "limit": "20"},
            timeout=10
        )
        clients = r.json()
        if not clients:
            edit_message(chat_id, message_id, "👥 Клиентов пока нет.",
                [[{"text": "🏠 Меню", "callback_data": "main_menu"}]])
            return
        msg = f"👥 <b>Последние клиенты ({len(clients)}):</b>\n\n"
        for c in clients:
            msg += f"• <b>{c['full_name']}</b>"
            if c.get("phone"):
                msg += f" — {c['phone']}"
            msg += "\n"
        edit_message(chat_id, message_id, msg,
            [[{"text": "🏠 Меню", "callback_data": "main_menu"}]])
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка загрузки.")


# ═══════════════════════════════════════
# КОНТАКТЫ
# ═══════════════════════════════════════

def show_contacts(chat_id: int, message_id: int):
    edit_message(chat_id, message_id,
        "📍 <b>Наш адрес:</b>\nАлматы, ул. Примерная 1\n\n"
        "📞 <b>Телефон:</b> +7 777 000 00 00\n"
        "🕐 <b>Режим работы:</b> 09:00 — 21:00\n"
        "📱 <b>Instagram:</b> @salon_beauty",
        [[{"text": "🏠 Главное меню", "callback_data": "main_menu"}]]
    )


# ═══════════════════════════════════════
# ИИ ЧАТ
# ═══════════════════════════════════════

def ai_chat(chat_id: int, text: str, user: dict, full_name: str):
    try:
        send_message(chat_id, "🤔 Думаю...")
        r = req.post(f"{API}/chat", json={
            "tg_id":     user.get("id"),
            "full_name": full_name,
            "message":   text
        }, timeout=30)
        reply = r.json().get("reply", "Не могу ответить прямо сейчас.")
        send_inline_keyboard(chat_id, reply,
            [[{"text": "🏠 Главное меню", "callback_data": "main_menu"}]]
        )
    except Exception:
        send_message(chat_id, "❌ Сервер недоступен.")


# ═══════════════════════════════════════
# УВЕДОМЛЕНИЕ МАСТЕРУ
# ═══════════════════════════════════════

def notify_about_booking(data: dict, client_name: str):
    try:
        r        = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/master_services",
            headers=SUPA_HEADERS,
            params={"service_id": f"eq.{data['service_id']}"},
            timeout=10
        )
        links    = r.json()
        notified = False
        if links:
            r2      = req.get(
                f"{settings.SUPABASE_URL}/rest/v1/masters",
                headers=SUPA_HEADERS,
                params={"id": f"eq.{links[0]['master_id']}", "is_active": "eq.true"},
                timeout=10
            )
            masters = r2.json()
            if masters and masters[0].get("tg_id"):
                send_message(masters[0]["tg_id"],
                    "🔔 <b>Новая запись!</b>\n\n"
                    f"💅 {data['service_name']}\n"
                    f"📅 {data['booked_at_display']}\n"
                    f"👤 {client_name}\n"
                    f"📞 {data.get('phone', '—')}"
                )
                notified = True
        if not notified:
            for aid in settings.ADMIN_IDS + settings.CREATOR_IDS:
                send_message(aid,
                    "🔔 <b>Новая запись!</b>\n\n"
                    f"💅 {data['service_name']}\n"
                    f"📅 {data['booked_at_display']}\n"
                    f"👤 {client_name}\n"
                    f"📞 {data.get('phone', '—')}\n\n"
                    "⚠️ Мастер не назначен!"
                )
    except Exception as e:
        for cid in settings.CREATOR_IDS:
            send_message(cid, f"⚠️ Ошибка уведомления: {e}")


# ═══════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ
# ═══════════════════════════════════════

def get_or_create_profile_id(user: dict, full_name: str) -> str:
    r = req.get(
        f"{settings.SUPABASE_URL}/rest/v1/profiles",
        headers=SUPA_HEADERS,
        params={"tg_id": f"eq.{user.get('id')}"},
        timeout=10
    )
    result = r.json()
    if result:
        return result[0]["id"]
    r2 = req.post(
        f"{settings.SUPABASE_URL}/rest/v1/profiles",
        headers=SUPA_HEADERS,
        json={"tg_id": user.get("id"), "full_name": full_name, "role": "client"},
        timeout=10
    )
    return r2.json()[0]["id"]

# ═══════════════════════════════════════
# ФИНАНСЫ — РУКОВОДИТЕЛЬ
# ═══════════════════════════════════════

PAYMENT_LABELS = {
    "cash":        "💵 Наличные",
    "transfer":    "📲 Перевод",
    "terminal":    "💳 Терминал",
    "certificate": "🎁 Сертификат"
}


def start_finance_report(chat_id: int, message_id: int, preset: str):
    """Меню выбора периода для отчёта"""
    edit_message(chat_id, message_id,
        "📊 <b>Финансовый отчёт</b>\n\n"
        "Выберите период или напишите дату:\n\n"
        "<i>Примеры:\n"
        "• сегодня\n"
        "• вчера\n"
        "• эта неделя\n"
        "• этот месяц\n"
        "• прошлый месяц\n"
        "• 25.03.2026\n"
        "• 01.03.2026-25.03.2026</i>",
        [
            [{"text": "📅 Сегодня",       "callback_data": "finance_period:сегодня"},
             {"text": "📅 Вчера",         "callback_data": "finance_period:вчера"}],
            [{"text": "📅 Эта неделя",    "callback_data": "finance_period:эта неделя"},
             {"text": "📅 Этот месяц",    "callback_data": "finance_period:этот месяц"}],
            [{"text": "📅 Прошлый месяц", "callback_data": "finance_period:прошлый месяц"}],
            [{"text": "✏️ Своя дата",     "callback_data": "finance_custom_date"}],
            [{"text": "🏠 Меню",          "callback_data": "main_menu"}]
        ]
    )


def show_finance_for_period(chat_id: int, message_id: int, period: str):
    """Показать финансовый отчёт за период"""
    dates = parse_date_input(period)
    if not dates:
        edit_message(chat_id, message_id,
            "⚠️ Не могу распознать дату. Попробуйте:\n"
            "<i>сегодня / вчера / эта неделя / 25.03.2026</i>",
            [[{"text": "◀️ Назад", "callback_data": "dir_report_day"}]]
        )
        return

    date_from, date_to = dates
    data = get_revenue_for_period(date_from, date_to)

    # Форматируем период
    if date_from == date_to:
        period_str = datetime.strptime(date_from, "%Y-%m-%d").strftime("%d.%m.%Y")
    else:
        d1 = datetime.strptime(date_from, "%Y-%m-%d").strftime("%d.%m.%Y")
        d2 = datetime.strptime(date_to,   "%Y-%m-%d").strftime("%d.%m.%Y")
        period_str = f"{d1} — {d2}"

    msg  = f"📊 <b>Отчёт: {period_str}</b>\n\n"
    msg += f"📋 Оплаченных записей: <b>{data['count']}</b>\n"
    msg += f"💰 Общая выручка: <b>{int(data['total']):,} ₸</b>\n\n"

    if data["by_method"]:
        msg += "💳 <b>По способам оплаты:</b>\n"
        for method, amount in data["by_method"].items():
            label = PAYMENT_LABELS.get(method, method)
            pct   = (amount / data["total"] * 100) if data["total"] > 0 else 0
            msg  += f"  {label}: <b>{int(amount):,} ₸</b> ({pct:.0f}%)\n"

    # Информация по мастерам
    if data["by_master"]:
        msg += "\n👩‍🎨 <b>По мастерам:</b>\n"
        for master_id, mdata in data["by_master"].items():
            # Получаем имя мастера
            try:
                r = req.get(
                    f"{settings.SUPABASE_URL}/rest/v1/masters",
                    headers=SUPA_HEADERS,
                    params={"id": f"eq.{master_id}"},
                    timeout=5
                )
                masters = r.json()
                name = masters[0]["full_name"] if masters else "Мастер"
            except Exception:
                name = "Мастер"
            msg += f"  • {name}: <b>{int(mdata['revenue']):,} ₸</b> ({mdata['count']} записей)\n"

    edit_message(chat_id, message_id, msg, [
        [{"text": "👥 Зарплаты сотрудников", "callback_data": f"dir_salary"}],
        [{"text": "◀️ Другой период",         "callback_data": "dir_report_day"},
         {"text": "🏠 Меню",                  "callback_data": "main_menu"}]
    ])


def start_salary_report(chat_id: int, message_id: int, user: dict):
    """Меню зарплат"""
    edit_message(chat_id, message_id,
        "👥 <b>Зарплаты сотрудников</b>\n\n"
        "Выберите период:",
        [
            [{"text": "📅 Сегодня",       "callback_data": "salary_period:сегодня"},
             {"text": "📅 Эта неделя",    "callback_data": "salary_period:эта неделя"}],
            [{"text": "📅 Этот месяц",    "callback_data": "salary_period:этот месяц"},
             {"text": "📅 Прошлый месяц", "callback_data": "salary_period:прошлый месяц"}],
            [{"text": "⚙️ Настроить ставки", "callback_data": "dir_set_rates"}],
            [{"text": "🏠 Меню",             "callback_data": "main_menu"}]
        ]
    )


def show_salary_for_period(chat_id: int, message_id: int, period: str):
    """Показать зарплаты за период"""
    dates = parse_date_input(period)
    if not dates:
        edit_message(chat_id, message_id, "⚠️ Не могу распознать период.",
            [[{"text": "◀️ Назад", "callback_data": "dir_salary"}]])
        return

    date_from, date_to = dates
    staff = get_all_staff_salary(date_from, date_to)

    if date_from == date_to:
        period_str = datetime.strptime(date_from, "%Y-%m-%d").strftime("%d.%m.%Y")
    else:
        d1 = datetime.strptime(date_from, "%Y-%m-%d").strftime("%d.%m")
        d2 = datetime.strptime(date_to,   "%Y-%m-%d").strftime("%d.%m.%Y")
        period_str = f"{d1} — {d2}"

    if not staff:
        edit_message(chat_id, message_id,
            "⚠️ Нет сотрудников с настроенными ставками.\n\n"
            "Настройте ставки через кнопку ниже.",
            [[{"text": "⚙️ Настроить ставки", "callback_data": "dir_set_rates"},
              {"text": "🏠 Меню",             "callback_data": "main_menu"}]])
        return

    msg        = f"👥 <b>Зарплаты за {period_str}:</b>\n\n"
    total_sala = 0

    for s in staff:
        role_icon = "👩‍🎨" if s["role"] == "master" else "🛠"
        msg       += f"{role_icon} <b>{s['name']}</b>\n"
        msg       += f"   Выручка: {int(s['revenue']):,} ₸\n"
        msg       += f"   Ставка: {s['rate']}%\n"
        msg       += f"   💰 К выплате: <b>{int(s['salary']):,} ₸</b>\n\n"
        total_sala += s["salary"]

    msg += f"📊 Итого к выплате: <b>{int(total_sala):,} ₸</b>"

    edit_message(chat_id, message_id, msg, [
        [{"text": "⚙️ Настроить ставки", "callback_data": "dir_set_rates"}],
        [{"text": "◀️ Другой период",    "callback_data": "dir_salary"},
         {"text": "🏠 Меню",            "callback_data": "main_menu"}]
    ])


def show_set_rates(chat_id: int, message_id: int):
    """Показать всех сотрудников для настройки ставок"""
    try:
        # Все мастера
        r = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/masters",
            headers=SUPA_HEADERS,
            params={"is_active": "eq.true"},
            timeout=10
        )
        masters = r.json()

        # Текущие ставки
        r2 = req.get(
            f"{settings.SUPABASE_URL}/rest/v1/salary_rates",
            headers=SUPA_HEADERS,
            timeout=10
        )
        rates_list = r2.json()
        rates_map  = {r["profile_id"]: r["rate"] for r in rates_list}

        msg     = "⚙️ <b>Настройка ставок</b>\n\nВыберите сотрудника:"
        buttons = []

        for m in masters:
            profile_id = m.get("profile_id")
            rate       = rates_map.get(profile_id, 30)
            buttons.append([{
                "text":          f"👩‍🎨 {m['full_name']} — {rate}%",
                "callback_data": f"set_rate:{profile_id}:master"
            }])

        buttons.append([{"text": "🏠 Меню", "callback_data": "main_menu"}])
        edit_message(chat_id, message_id, msg, buttons)
    except Exception:
        edit_message(chat_id, message_id, "❌ Ошибка загрузки.")


def start_set_rate(chat_id: int, message_id: int, data: str, user: dict):
    """Начать ввод новой ставки"""
    parts      = data.split(":")
    profile_id = parts[0]
    role       = parts[1] if len(parts) > 1 else "master"

    # Получаем имя
    r = req.get(
        f"{settings.SUPABASE_URL}/rest/v1/profiles",
        headers=SUPA_HEADERS,
        params={"id": f"eq.{profile_id}"},
        timeout=10
    )
    profiles = r.json()
    if not profiles:
            edit_message(chat_id, message_id,
                "⚠️ Профиль сотрудника не найден в системе.\n"
                "Убедитесь что мастер привязан к профилю в БД.",
                [[{"text": "◀️ Назад", "callback_data": "dir_set_rates"}]]
            )
            return
            
    name = profiles[0].get("full_name", "Сотрудник")

    # Текущая ставка
    r2 = req.get(
        f"{settings.SUPABASE_URL}/rest/v1/salary_rates",
        headers=SUPA_HEADERS,
        params={"profile_id": f"eq.{profile_id}"},
        timeout=10
    )
    rates        = r2.json()
    current_rate = rates[0]["rate"] if rates else 30

    user_states[chat_id] = {
        "step": "set_rate",
        "user": user,
        "data": {
            "profile_id": profile_id,
            "role":       role,
            "name":       name
        }
    }

    edit_message(chat_id, message_id,
        f"⚙️ <b>Ставка для {name}</b>\n\n"
        f"Текущая ставка: <b>{current_rate}%</b>\n\n"
        "Введите новый процент (например: 35):",
        [[{"text": "❌ Отмена", "callback_data": "dir_set_rates"}]]
    )