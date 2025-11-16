import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, BigInteger, Integer, func, Boolean, ForeignKey, JSON
from sqlalchemy.orm import mapped_column, DeclarativeBase, Mapped, relationship


class Base(DeclarativeBase):
    """Базовая модель для всех таблиц"""
    pass


class UserModel(Base):
    """Таблица пользователей Telegram"""
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    access: Mapped[bool] = mapped_column(Boolean, default=False)

    # Связи
    nko_data: Mapped["NKODataModel"] = relationship("NKODataModel", back_populates="user", uselist=False)
    content_history: Mapped[list["ContentHistoryModel"]] = relationship("ContentHistoryModel", back_populates="user")
    api_keys: Mapped[list["AIAPIModel"]] = relationship("AIAPIModel", back_populates="user")
    access_links: Mapped[list["AccessLinksModel"]] = relationship("AccessLinksModel", back_populates="creator")


class AccessLinksModel(Base):
    """Модель для  ссылок доступа"""
    __tablename__ = "access_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, default=lambda: str(uuid.uuid4()))
    count_activate: Mapped[int] = mapped_column(Integer, default=99999)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id"))

    # Связь
    creator: Mapped["UserModel"] = relationship("UserModel", back_populates="access_links")


class AIAPIModel(Base):
    """Хранение API-ключей для ИИ-моделей"""
    __tablename__ = "aiapi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column("API_KEY", String(100), nullable=False)
    connected: Mapped[bool] = mapped_column(Boolean, default=False)

    # Связь
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="api_keys")

    @property
    def api_key(self) -> str:
        from utils.encryption import decrypt_api_key
        return decrypt_api_key(self.encrypted_api_key)

    @api_key.setter
    def api_key(self, plain_key: str):
        from utils.encryption import encrypt_api_key
        self.encrypted_api_key = encrypt_api_key(plain_key)


class NKODataModel(Base):
    """Данные об НКО, указанные пользователем"""
    __tablename__ = "nko_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id"), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    activities: Mapped[str] = mapped_column(Text, nullable=True)

    # Связь
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="nko_data")


class ContentHistoryModel(Base):
    """История генерации контента пользователем"""
    __tablename__ = "content_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id"), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=True)
    style: Mapped[str] = mapped_column(String(60), nullable=True)
    result: Mapped[str] = mapped_column(Text, nullable=True)
    additional_params: Mapped[dict] = mapped_column('additional_params', JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Связь
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="content_history")