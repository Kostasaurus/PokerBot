import uuid

from sqlalchemy import String, Integer, ForeignKey, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class TournamentRegistration(Base):
    __tablename__ = "tournaments_registration"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tg_id: Mapped[int] = mapped_column(ForeignKey("users_info.tg_id", ondelete="CASCADE"), nullable=False)
    tournament_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tournaments.id"), nullable=False)
    table: Mapped[int] = mapped_column(Integer, nullable=False)
    box: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    result: Mapped[int] = mapped_column(Integer, default=0)

