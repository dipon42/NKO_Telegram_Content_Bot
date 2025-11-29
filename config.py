import os
from dataclasses import dataclass
from typing import Tuple

from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    BOT_TOKEN: str
    DATABASE_URL: str
    ENCRYPTION_KEY: str
    GIGACHAT_CREDENTIALS: str
    ADMIN_IDS: Tuple[int, ...]

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("BOT_TOKEN")
        if token is None:
            raise ValueError("BOT_TOKEN не указан, укажите его в .env!")

        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            raise ValueError("ENCRYPTION_KEY не установлен!")

        gigachat_credentials = os.getenv("GIGACHAT_CREDENTIALS")
        if not gigachat_credentials:
            raise ValueError("GIGACHAT_CREDENTIALS не установлены!")

        database = os.getenv("DATABASE_URL","sqlite+aiosqlite:///./nko_bot.db")

        admins_env = os.getenv("ADMIN_IDS", "")
        admin_ids: tuple[int, ...] = tuple(
            int(tg_id.strip())
            for tg_id in admins_env.split(",")
            if tg_id.strip().isdigit()
        )

        return cls(
            BOT_TOKEN=token,
            DATABASE_URL=database,
            ENCRYPTION_KEY=encryption_key,
            GIGACHAT_CREDENTIALS=gigachat_credentials,
            ADMIN_IDS=admin_ids,
        )

config = Config.from_env()