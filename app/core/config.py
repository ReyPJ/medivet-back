from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "MediVet API"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    SECRET_KEY: str = os.getenv("SECRET_KEY")

    DATABASE_URL: str = "sqlite:///./test.db"

    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER")
    TWILIO_TEMPLATE_ID: str = os.getenv("TWILIO_TEMPLATE_ID")


settings = Settings()
