import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
    JWT_ALGORITHM = "HS256"
    CORS_ORIGINS = ["*"]
    MAX_ROOMS_PER_HOUR = 10
    MAX_ROOM_NAME_LENGTH = 200
    MIN_ROOM_NAME_LENGTH = 1
    MAX_MESSAGES_FETCH = 50

settings = Settings()