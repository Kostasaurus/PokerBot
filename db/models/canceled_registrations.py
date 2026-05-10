import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from db.mixins.id_mixins import IDMixin
from db.mixins.timestamp_mixins import CreatedAtMixin
from db.models.base import Base


class CanceledRegistration(Base, IDMixin, CreatedAtMixin):
    __tablename__ = "canceled_registrations"

    tg_id: Mapped[int] = mapped_column(ForeignKey("users_info.tg_id", ondelete="CASCADE"), nullable=False)
    tournament_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tournaments.id"), nullable=False)
