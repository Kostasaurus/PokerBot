from datetime import datetime

from pydantic import ValidationError

from managers.tournaments_manager import TournamentManager
from schemas.tournament_schemas import AddingTournament


async def parse_tournament_input(
    message_text: str,
    *,
    default_title: str | None = None,
    default_max_tables: int = 4,
    allow_past: bool = False,
) -> AddingTournament | str:
    info = message_text.split(sep='--')
    if len(info) == 3:
        title, max_tables, raw_start_time = info
        max_tables = int(max_tables)
    elif len(info) == 2:
        title, raw_start_time = info
        max_tables = default_max_tables
    elif len(info) == 1:
        raw_start_time = info[0]
        if default_title is not None:
            title = default_title
            max_tables = default_max_tables
        else:
            count = await TournamentManager.count_all_tournaments()
            title = 'Турнир №' + str(count)
            max_tables = 4
    else:
        return "Неверный формат!\nПеределывай!"

    try:
        start_time = datetime.strptime(raw_start_time.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        return "Неверный формат даты!\nПеределывай!"

    if not allow_past and start_time < datetime.now():
        return "Дата уже прошла!\nПеределывай!"

    try:
        return AddingTournament(title=title.strip(), max_tables=max_tables, start_time=start_time)
    except ValidationError as e:
        return str(e)


async def process_tournament_info(message_text: str):
    parsed = await parse_tournament_input(message_text)
    if isinstance(parsed, str):
        return parsed
    await TournamentManager.add_new_tournament(parsed)


async def process_edit_tournament_info(message_text: str, tournament_id: str):
    tournament = await TournamentManager.get_tournament_by_id(tournament_id)
    if not tournament:
        return "Турнир не найден!"

    parsed = await parse_tournament_input(
        message_text,
        default_title=tournament.title,
        default_max_tables=tournament.max_tables,
        allow_past=True,
    )
    if isinstance(parsed, str):
        return parsed

    updated = await TournamentManager.update_tournament(tournament_id=tournament_id, tournament=parsed)
    if not updated:
        return "Турнир не найден!"
