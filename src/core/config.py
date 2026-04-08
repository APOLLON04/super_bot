from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    APP_ENV: str   = os.getenv("APP_ENV", "development")
    APP_HOST: str  = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int  = int(os.getenv("APP_PORT", 8000))

    SUPABASE_URL:      str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")

    OPENAI_API_KEY:     str = os.getenv("OPENAI_API_KEY", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Telegram ID людей с особыми ролями — вписывай свои
    CREATOR_IDS:   list = [int(x) for x in os.getenv("CREATOR_IDS", "").split(",") if x]
    DIRECTOR_IDS:  list = [int(x) for x in os.getenv("DIRECTOR_IDS", "").split(",") if x]
    ADMIN_IDS:     list = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
    MASTER_IDS:    list = [int(x) for x in os.getenv("MASTER_IDS", "").split(",") if x]

    TWOGIS_REVIEW_URL: str = os.getenv("TWOGIS_REVIEW_URL", "")

    RAILWAY_URL: str = os.getenv("RAILWAY_URL", "http://localhost:8000")

settings = Settings()