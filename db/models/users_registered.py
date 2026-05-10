from sqlalchemy import Text, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from db.mixins.timestamp_mixins import TimestampsMixin
from db.models.base import Base


class UsersRegistered(Base, TimestampsMixin):
    __tablename__ = 'users_registered'

    tg_id: Mapped[int] = mapped_column(ForeignKey("users_info.tg_id", ondelete="CASCADE"), nullable=False, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    nickname: Mapped[str] = mapped_column(Text, unique=True)
