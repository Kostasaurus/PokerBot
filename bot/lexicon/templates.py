from bot.utils.date_utils import format_datetime_moscow, MONTHS_NOMINATIVE, format_date_short_moscow


class TemplateBuilder:

    @classmethod
    def build_closest_tournament(cls, item):
        t = item['tournament']
        box = item['box']
        table = item['table']
        return (
            f"Ваш ближайший турнир —\n"
            f"{t.title}\n\n"
            f"Начало {format_datetime_moscow(t.start_time)}\n"
            f"Стол: {table}\n"
            f"{f'Бокс: {box}\n\n' if box > 0 else 'Вы крупье'}"
            f"Удачи!"
        )

    @classmethod
    def build_closest_tournaments(cls, items):
        text = "Ваши запланированные игры:\n\n"
        for item in items:
            t = item['tournament']
            box = item['box']
            table = item['table']
            text += (
                f"{t.title}\n"
                f"Начало {format_datetime_moscow(t.start_time)}\n"
                f"Стол: {table}\n"
            f"{f'Бокс: {box}\n\n' if box > 0 else 'Вы крупье'}"
            )
        return text

    @classmethod
    def show_users_tournament_info(cls, tournament):
        t = tournament['tournament']
        box = tournament['box']
        table = tournament['table']
        text = (
            "Информация о турнире:\n\n"
            f"{t.title}\n"
            f"Начало {format_datetime_moscow(t.start_time)}\n"
            f"Стол: {table}\n"
            f"{f'Бокс: {box}\n\n' if box > 0 else 'Вы крупье'}"
                )
        return text

    @classmethod
    def show_available_tournament_info(cls, tournament):
        t = tournament['tournament']
        reg_count = tournament['registered_count']


        text = (
            "Информация о турнире:\n\n"
            f"{t.title}\n"
            f"Начало {format_datetime_moscow(t.start_time)}\n"
            f"Записалось {reg_count}/{t.max_tables * 10}"
        )
        return text

    @classmethod
    def register_user_for_tournament_template(cls, tournament):

        text = (
            f"Вы записаны на турнир!\n\n"
            f"Начало {format_datetime_moscow(tournament.start_time)}\n\n"
            f"Стол: {tournament.table}\n"
            f"{f'Бокс: {tournament.box}\n\n' if tournament.box > 0 else 'Вы крупье'}"
        )
        return text

    @classmethod
    def show_tournaments_in_month(cls, tournaments, month, year):

        text = (
            f"Турниры за {MONTHS_NOMINATIVE[month]} {year}\n\n"
        )
        for tournament in tournaments:
            t = tournament['tournament']
            reg_count = tournament['registered_count']
            user_registered = tournament['user_registered']
            if t.status == 'scheduled':
                if user_registered and reg_count > 1:
                    reg_info = '(вы тоже)'
                elif not user_registered and reg_count:
                    reg_info = '(а вы нет)'
                elif user_registered and reg_count == 1:
                    reg_info = '(это вы)'
                else:
                    reg_info = ''
                text += (
                        f"• {t.title}\n"
                        f"{format_datetime_moscow(t.start_time)}\n"
                f"Записалось {reg_count}/{t.max_tables * 10} {reg_info}\n\n"
                )
            else:
                text += (
                    f"• {t.title}\n"
                        f"{format_datetime_moscow(t.start_time)}\n"
                "(завершён)\n\n"
                )
        return text

    @staticmethod
    def format_player(player: dict, highlight=False):
        tg_id = player['tg_id']
        nickname = player['nickname']
        username = player.get('tg_username')


        display_name = f'<a href="tg://user?id={tg_id}">{nickname}</a>'

        base = f"{display_name}   {player['table']}-{player['box']}"

        if highlight:
            return f"➡️<b>{base}</b>⬅️"
        return base





    @classmethod
    def show_stats(cls, tg_id: int, stats:list[dict], year: int | None = None, quarter: int | None = None, month: int | None = None):

        text = ''
        if not year:
            text = f"<b>Статистика за все время</b>\n\n"
        elif year and not quarter and not month:
            text = f"<b>Статистика за {year} год</b>\n\n"
        elif quarter and not month:
            text = f"<b>Статистика за {quarter}-й квартал {year} года</b>\n\n"
        elif month:
            text = f"<b>Статистика за {MONTHS_NOMINATIVE[month]} {year} года</b>\n\n"

        if not stats:
            text += 'Тут пока пусто...'
            return text

        for user in stats:
            if user['tg_id'] == tg_id:
                text += f"➡️<b>{user['username']} - {user['total']}</b>⬅️\n"
            else:
                text += f"{user['username']} - {user['total']}\n"

        return text

    @classmethod
    def show_tournament_stats(cls, tournament, results: list[dict], tg_id: int):


        text = f"<b>{tournament.title}</b>\n{format_date_short_moscow(tournament.start_time)}\n\n"

        if not results:
            text += 'Тут пока пусто...'
            return text

        for user in results:
            if user['tg_id'] == tg_id:
                text += f"➡️<b>{user['username']} - {user['total']}</b>⬅️\n"
            else:
                text += f"{user['username']} - {user['total']}\n"

        return text





    @classmethod
    def show_tournament_players(cls, players: list[dict], tg_id: int):
        text = (
            f"<b>Список участников</b>\n"
            f"Tг-ник (ник)   стол-бокс\n\n"
                )

        if not players:
            text += 'Тут пока пусто...'
            return text
        for player in players:
            is_me = (player['tg_id'] == tg_id)
            text += cls.format_player(player, highlight=is_me) + "\n"
        return text



