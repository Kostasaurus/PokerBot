import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class TournamentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    start_time: datetime.datetime
    max_tables: int = 9


class TournamentRead(TournamentBase):
    id: uuid.UUID
    status: str
    model_config = ConfigDict(from_attributes=True)


class TournamentRegistrationBase(BaseModel):
    tg_id: int
    tournament_id: uuid.UUID | int
    table: int
    box: int

class TournamentRegistrationCreate(TournamentRegistrationBase):
    """Создание записи (id генерируется автоматически)"""
    pass

class TournamentRegistrationRead(TournamentRegistrationBase):
    """Чтение записи с id"""
    id: uuid.UUID | int
    tournament_id: uuid.UUID | int
    box: int
    model_config = ConfigDict(from_attributes=True)

# Дополнительно: схема для ответа с количеством мест
class TournamentDetail(TournamentRead):
    registered_count: int  # можно добавить вычисляемое поле

class TournamentRegistrationReturn(TournamentBase):
    tournament_id: uuid.UUID | int
    box: int
    table: int

class ActivesTournamentsCheck(BaseModel):
    tournament_id: uuid.UUID | int
    status: str

class AddingTournament(BaseModel):
    title: str
    max_tables: int = 3
    start_time: datetime.datetime

