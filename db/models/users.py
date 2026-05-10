from sqlalchemy import Boolean, Text, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from db.mixins.timestamp_mixins import CreatedAtMixin
from db.models.base import Base


class Users(Base, CreatedAtMixin):
    __tablename__ = 'users_info'

    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, primary_key=True)

    firstname: Mapped[str] = mapped_column(Text, unique=False)
    lastname: Mapped[str] = mapped_column(Text, unique=False)
    username: Mapped[str] = mapped_column(Text, unique=False)
    language: Mapped[str] = mapped_column(Text, unique=False)

    is_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)



