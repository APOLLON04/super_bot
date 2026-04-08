import hashlib
import time

# Простой кэш в памяти
# Структура: {хэш_вопроса: {"answer": "...", "expires": timestamp}}
_cache = {}
CACHE_TTL = 60 * 60 * 24  # 24 часа

# Вопросы которые кэшируем — универсальные безличные
CACHEABLE_KEYWORDS = [
    "адрес", "где находит", "как доехать",
    "режим работы", "часы работы", "когда работает", "во сколько",
    "цена", "сколько стоит", "прайс", "стоимость",
    "маникюр", "педикюр", "шугаринг", "ресниц", "ламинир", "брови",
    "записаться", "как записать", "как записат",
    "оплата", "платит", "наличн", "терминал", "перевод",
    "сертификат", "подарок",
    "в 4 руки", "в 6 руки", "комплекс",
    "больно", "болезненно", "болит",
    "сколько времени", "сколько длится", "долго ли",
    "парковка", "метро", "остановка",
    "инстаграм", "instagram", "2gis", "вотсап", "телеграм"
]


def _make_key(text: str) -> str:
    """Нормализуем текст и делаем хэш"""
    normalized = text.lower().strip()
    return hashlib.md5(normalized.encode()).hexdigest()


def is_cacheable(text: str) -> bool:
    """Стоит ли кэшировать этот вопрос"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in CACHEABLE_KEYWORDS)


def get_cached(text: str) -> str | None:
    """Получить кэшированный ответ если есть"""
    key    = _make_key(text)
    entry  = _cache.get(key)
    if not entry:
        return None
    if time.time() > entry["expires"]:
        del _cache[key]
        return None
    return entry["answer"]


def set_cache(text: str, answer: str):
    """Сохранить ответ в кэш"""
    key          = _make_key(text)
    _cache[key]  = {
        "answer":  answer,
        "expires": time.time() + CACHE_TTL
    }


def cache_stats() -> dict:
    """Статистика кэша для отладки"""
    now    = time.time()
    active = {k: v for k, v in _cache.items() if v["expires"] > now}
    return {"total": len(active), "keys": len(_cache)}