import uuid

from sqlalchemy import BigInteger, ForeignKey, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.mixins.id_mixins import IDMixin
from db.mixins.timestamp_mixins import CreatedAtMixin
from db.models.base import Base


class TournamentAnteEntry(Base, IDMixin, CreatedAtMixin):
    __tablename__ = "tournament_ante_entries"

    tournament_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        nullable=False,
    )
    tg_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users_info.tg_id", ondelete="CASCADE"),
        nullable=False,
    )
