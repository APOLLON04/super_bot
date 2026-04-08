import requests
import time
from src.core.config import settings

BASE_URL = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"


def send_message(chat_id: int, text: str, reply_markup: dict = None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{BASE_URL}/sendMessage", json=payload)


def send_inline_keyboard(chat_id: int, text: str, buttons: list[list[dict]]):
    """Inline кнопки (красивые, под сообщением)"""
    send_message(chat_id, text, reply_markup={"inline_keyboard": buttons})


def send_keyboard(chat_id: int, text: str, buttons: list):
    """Reply кнопки (для выбора услуги при записи)"""
    keyboard = [[{"text": btn}] for btn in buttons]
    keyboard.append([{"text": "❌ Отмена"}])
    send_message(chat_id, text, reply_markup={
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": True
    })


def send_reply_keyboard_remove(chat_id: int, text: str):
    send_message(chat_id, text, reply_markup={"remove_keyboard": True})


def answer_callback(callback_query_id: str, text: str = ""):
    requests.post(f"{BASE_URL}/answerCallbackQuery", json={
        "callback_query_id": callback_query_id,
        "text": text
    })

def edit_message(chat_id: int, message_id: int, text: str, buttons: list = None):
    """Редактировать существующее сообщение вместо отправки нового"""
    payload = {
        "chat_id":    chat_id,
        "message_id": message_id,
        "text":       text,
        "parse_mode": "HTML"
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    requests.post(f"{BASE_URL}/editMessageText", json=payload)

def get_updates(offset: int = 0) -> list:
    try:
        r = requests.get(f"{BASE_URL}/getUpdates", params={
            "offset": offset,
            "timeout": 30
        }, timeout=35)
        return r.json().get("result", [])
    except Exception:
        return []


def run_polling():
    print("🤖 Бот запущен...")
    offset = 0
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            if "message" in update:
                from src.tg_bot.handlers import handle_message
                handle_message(update["message"])
            elif "callback_query" in update:
                from src.tg_bot.handlers import handle_callback
                handle_callback(update["callback_query"])
        time.sleep(1)