from aiogram import Bot
from aiogram.fsm.context import FSMContext

from bot.keyboards.keyboards_builders import create_inline_keyboard
from bot.lexicon.phrases import LEXICON
from bot.lexicon.templates import TemplateBuilder
from core.settings import settings
from managers.user_manager import UserManager


def parse_players_callback(data: str) -> tuple[str, str, str | None, str | None, str]:
    """Parse ps:/pd:/pa: callback data. Returns tournament_id, status, year, month, back_data."""
    info = data.split(':')
    if len(info) == 3:
        _, tournament_id, status = info
        back_data = f'a_t:{tournament_id}:{status}'
        return tournament_id, status, None, None, back_data
    if len(info) == 5:
        _, year, month, tournament_id, status = info
        back_data = f't:{year}:{month}:{tournament_id}:{status}'
        return tournament_id, status, year, month, back_data
    raise ValueError(f'Invalid players callback: {data}')


def players_list_keyboard(back_data: str, is_admin: bool) -> dict:
    action_suffix = back_data.split(':', 1)[1]
    buttons = {}
    if is_admin:
        buttons[f'pd:{action_suffix}'] = ('Удалить', 'danger')
        buttons[f'pa:{action_suffix}'] = ('Добавить', 'success')
    buttons[back_data] = '⬅ Назад'
    return buttons


def players_list_keyboard_width(is_admin: bool) -> tuple[int, ...]:
    return (2, 1) if is_admin else (1,)


def delete_player_keyboard_width(player_count: int) -> tuple[int, ...]:
    return tuple([2] * (player_count // 2) + ([1] if player_count % 2 else []) + [1])


async def refresh_players_view(
    bot: Bot,
    chat_id: int,
    message_id: int,
    tournament_id: str,
    viewer_tg_id: int,
    back_data: str,
) -> None:
    is_admin = viewer_tg_id in settings.bot.ADMINS
    players = await UserManager.get_all_players(tournament_id=tournament_id)
    buttons = players_list_keyboard(back_data, is_admin)
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=TemplateBuilder.show_tournament_players(players=players, tg_id=viewer_tg_id),
        reply_markup=create_inline_keyboard(players_list_keyboard_width(is_admin), **buttons),
    )


async def refresh_delete_player_list(bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    tournament_id = data['ps_tournament_id']
    back_data = data['ps_back_data']

    players = await UserManager.get_all_players(tournament_id=tournament_id)
    if not players:
        action_suffix = back_data.split(':', 1)[1]
        await bot.edit_message_text(
            chat_id=data['ps_chat_id'],
            message_id=data['ps_message_id'],
            text=LEXICON['no_players_to_delete'],
            reply_markup=create_inline_keyboard(1, **{f'ps:{action_suffix}': '⬅ Назад'}),
        )
        return

    buttons = {
        f'pdr:{tournament_id}:{player["tg_id"]}': (player['nickname'], 'danger')
        for player in players
    }
    action_suffix = back_data.split(':', 1)[1]
    buttons[f'ps:{action_suffix}'] = '⬅ Назад'

    await bot.edit_message_text(
        chat_id=data['ps_chat_id'],
        message_id=data['ps_message_id'],
        text=LEXICON['select_player_to_delete'],
        reply_markup=create_inline_keyboard(delete_player_keyboard_width(len(players)), **buttons),
    )
