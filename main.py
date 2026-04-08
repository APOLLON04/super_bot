import uvicorn
import threading
from fastapi import FastAPI
from src.core.config import settings
from src.api.routes import router

app = FastAPI(title="Beauty Salon Bot", version="1.0.0")
app.include_router(router, prefix="/api/v1")

@app.get("/")
def health():
    return {"status": "ok", "env": settings.APP_ENV}

def start_bot():
    from src.tg_bot.bot import run_polling
    run_polling()

def start_reminders():
    from src.core.reminder import run_reminder_loop
    run_reminder_loop()

if __name__ == "__main__":
    # Бот в отдельном потоке
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()

    # Планировщик напоминаний в отдельном потоке
    reminder_thread = threading.Thread(target=start_reminders, daemon=True)
    reminder_thread.start()

    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=False)