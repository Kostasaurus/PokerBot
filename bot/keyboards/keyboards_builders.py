import math
from datetime import datetime, timedelta, timezone

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from bot.lexicon.phrases import LEXICON
from bot.utils.date_utils import MONTHS_NOMINATIVE, format_date_short_moscow, QUARTERS_NOMINATIVE


def create_inline_keyboard(
        width: int | tuple[int, ...],
        *args: str,
        **kwargs: str | tuple[str, str | None]
) -> InlineKeyboardMarkup:
    kb_builder = InlineKeyboardBuilder()
    buttons: list[InlineKeyboardButton] = []

    if args:
        for button in args:
            buttons.append(InlineKeyboardButton(
                text=LEXICON[button] if button in LEXICON else button,
                callback_data=button))
    if kwargs:
        for button, value in kwargs.items():
            if isinstance(value, tuple):
                text, style = value
            else:
                text, style = value, None
            buttons.append(InlineKeyboardButton(
                text=text,
                callback_data=button,
                style=style

            ))
    if not isinstance(width, tuple):
        kb_builder.row(*buttons, width=width)
    else:
        kb_builder.row(*buttons)
        kb_builder.adjust(*width)


    return kb_builder.as_markup()

def create_reply_keyboard(
        width: int | tuple[int, ...],
        *args: str,
            ) -> ReplyKeyboardMarkup:
    kb_builder = ReplyKeyboardBuilder()
    buttons: list[KeyboardButton] = []

    if args:
        for button in args:
            buttons.append(KeyboardButton(
                text=button))

    if not isinstance(width, tuple):
        kb_builder.row(*buttons, width=width)
    else:
        kb_builder.row(*buttons)
        kb_builder.adjust(*width)


    return kb_builder.as_markup(resize_keyboard=True, one_time_keyboard=False)



def tournaments_list_keyboard(tournaments_data: list[dict], month: int, year: int = 2026):

    buttons = {}

    for item in tournaments_data:
        t = item['tournament']
        reg = item['registered_count']
        total = t.max_tables * 10
        user_reg = item['user_registered']
        is_scheduled = t.status == 'scheduled' and (t.start_time + timedelta(hours=2) > datetime.now(timezone.utc))

        if is_scheduled:
            if user_reg:
                prefix = "✅"
                style = None
                status_text = f"(вы записаны, {reg}/{total})"
                callback_data = f"t:{year}:{month}:{t.id}:reg"
            elif reg >= total:
                prefix = "⛔"
                style = 'danger'
                status_text = f"(мест нет, {reg}/{total})"
                callback_data = f"t:{year}:{month}:{t.id}:full"

            else:
                prefix = "🎯"
                style = 'success'
                status_text = f"(свободно {total - reg} из {total})"
                callback_data = f"t:{year}:{month}:{t.id}:av"

        else:
            prefix = "🕸"
            style = None
            callback_data = f"t:{year}:{month}:{t.id}:fin"

            if user_reg:
                status_text = "(вы участвовали)"
            else:
                status_text = "(завершён)"

        button_text = f"{prefix} {format_date_short_moscow(t.start_time)}"


        buttons[callback_data] = (button_text, style)

    back_button = {f"months:{year}": '⬅ Назад к месяцам'}
    buttons.update(back_button)

    count = math.floor((len(buttons) - 1) / 2)
    width_list = [2 for i in range(count)]
    width_list.append(1)
    width = tuple(width_list)

    return create_inline_keyboard(width, **buttons)


def months_keyboard(year: int = 2026):
    months = {f"month:{year}:{month}": (f"{MONTHS_NOMINATIVE[month]}", 'primary') for month in range(1, 13)}
    change_year = year - 1 if year == 2026 else year + 1

    change_year_button = {f'year:{change_year}':f'{'⬅' if change_year == 2025 else ''}Турниры за {change_year:02d} год{'➡' if change_year == 2026 else ''}'}
    return create_inline_keyboard((4,4,4,1), **months)


def build_play_keyboard(tournaments_data: list[dict]) -> InlineKeyboardMarkup | tuple[str, InlineKeyboardMarkup] | None:
    if not tournaments_data:
        return None

    buttons = {}

    for item in tournaments_data:
        t = item['tournament']
        total = t.max_tables * 10
        reg = item['registered_count']
        full = reg >= total
        user_reg = item['user_registered']

        # date_str = t.start_time.strftime('%d.%m.%Y %H:%M')
        if user_reg:
            buttons.update({f'a_t:{t.id}:reg' : f'✅ {format_date_short_moscow(t.start_time)}'})

        elif full:
            buttons.update({f'tournament_is_full': (f'⛔ {format_date_short_moscow(t.start_time)}', 'danger')})
        else:
            buttons.update({f'a_t:{t.id}:av' : (f'🎯 {format_date_short_moscow(t.start_time)}', 'success')})

    return create_inline_keyboard(2, **buttons)

def build_scheduled_keyboard(tournaments_data) -> InlineKeyboardMarkup | None:
    if not tournaments_data:
        return None

    buttons = {}
    for item in tournaments_data:
        t = item['tournament']
        buttons.update({f'cancel_tournament:{t.id}':(f'{format_date_short_moscow(t.start_time)}', 'primary')})
    buttons.update({'all_scheduled': '⬅ Назад'})
    count = math.floor((len(buttons) - 1) / 2)
    width_list = [2 for i in range(count)]
    width_list.append(1)
    width = tuple(width_list)

    return create_inline_keyboard(width, **buttons)

def build_months_stats_keyboard(year: int) -> InlineKeyboardMarkup:
    months = {f"st_month:{year}:{month}": (f"{MONTHS_NOMINATIVE[month]}", 'primary') for month in range(1, 13)}
    change_year = year - 1 if year == 2026 else year + 1

    change_year_button = {
        f'view_months_st:{change_year}': f'{'⬅' if change_year == 2025 else ''}{change_year:02d} год{'➡' if change_year == 2026 else ''}'}
    change_mode_button = {f'view_quarters_st:{year}': 'По кварталам'}
    return create_inline_keyboard((4, 4, 4, 2), **months, **change_mode_button)

def build_quarters_stats_keyboard(year: int) -> InlineKeyboardMarkup:
    quarters = {f"st_quarter:{year}:{quarter}": (f"{QUARTERS_NOMINATIVE[quarter]}", 'primary') for quarter in range(1, 5)}
    change_year = year - 1 if year == 2026 else year + 1

    change_year_button = {
        f'view_quarters_st:{change_year}': f'{'⬅' if change_year == 2025 else ''}{change_year:02d} год{'➡' if change_year == 2026 else ''}'}
    change_mode_button = {f'view_months_st:{year}': 'По месяцам'}
    return create_inline_keyboard((2, 2, 2), **quarters, **change_mode_button)
