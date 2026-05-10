from datetime import datetime

from pydantic import ValidationError

from managers.tournaments_manager import TournamentManager
from schemas.tournament_schemas import AddingTournament


async def process_tournament_info(message_text: str):
    info = message_text.split(sep='--')
    if len(info) == 3:
        title, max_tables, raw_start_time = info
    elif len(info) == 2:
        title, raw_start_time = info
        max_tables = 3
    else:
        return f"Неверный формат!\nПеределывай!"

    start_time = datetime.strptime(raw_start_time, "%d.%m.%Y %H:%M")

    now = datetime.now()

    if start_time < now:
        return "Дата уже прошла!\nПеределывай!"

    try:
        new_tournament = AddingTournament(title=title, max_tables=int(max_tables), start_time=start_time)
        await TournamentManager.add_new_tournament(new_tournament)
    except ValidationError as e:
        return e.message
