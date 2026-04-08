import requests
from src.core.config import settings
from src.core.cache import get_cached, set_cache, is_cacheable

SYSTEM_PROMPT = """Ты — вежливый ИИ-ассистент салона красоты в Алматы.
Помогаешь клиентам: отвечаешь на вопросы об услугах, помогаешь записаться, сообщаешь цены.
Все цены указывай в тенге (₸).
Услуги салона:
- 💅 Маникюр классический — 4000 ₸ (60 мин)
- 💅 Маникюр с гель-лаком — 6000 ₸ (90 мин)
- 🦶 Педикюр классический — 5000 ₸ (60 мин)
- 🦶 Педикюр с гель-лаком — 7000 ₸ (90 мин)
- 👁 Наращивание ресниц 2D — 8000 ₸ (120 мин)
- 👁 Наращивание ресниц 3D — 10000 ₸ (150 мин)
- 👁 Ламинирование ресниц — 7000 ₸ (90 мин)
- 🌿 Шугаринг ноги — 8000 ₸ (90 мин)
- 🌿 Шугаринг бикини — 6000 ₸ (60 мин)
- 🌿 Шугаринг руки — 4000 ₸ (45 мин)
- ✨ Комплекс в 4 руки — 11000 ₸ (90 мин)
- ✨ Комплекс в 6 руки — 14000 ₸ (100 мин)
- 🎨 Дизайн ногтей — 300 ₸/ноготь (30 мин)
- 🧖 Уход за бровями — 3500 ₸ (45 мин)
Адрес: Алматы, ул. Примерная 1
Режим работы: 09:00 — 21:00 ежедневно
Оплата: наличные, перевод, терминал, сертификат
Отвечай кратко, дружелюбно, на языке клиента."""


def ask_ai(user_message: str, history: list = []) -> str:
    # Проверяем кэш только для безличных вопросов без истории
    if is_cacheable(user_message) and not history:
        cached = get_cached(user_message)
        if cached:
            print(f"✅ Кэш: {user_message[:30]}...")
            return cached

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type":  "application/json"
    }
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history[-10:]
    messages.append({"role": "user", "content": user_message})

    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json={
                "model":       "gpt-4o-mini",
                "messages":    messages,
                "max_tokens":  500,
                "temperature": 0.7
            },
            timeout=30
        )
        r.raise_for_status()
        answer = r.json()["choices"][0]["message"]["content"]

        # Кэшируем если вопрос универсальный
        if is_cacheable(user_message) and not history:
            set_cache(user_message, answer)

        return answer

    except requests.exceptions.Timeout:
        return "⏳ Сервер не отвечает. Попробуйте позже."
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"