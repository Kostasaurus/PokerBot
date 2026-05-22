from aiogram import Bot
from aiogram.fsm.context import FSMContext

from bot.keyboards.keyboards_builders import create_inline_keyboard
from bot.lexicon.phrases import LEXICON
from managers.user_manager import UserManager


def ante_player_button_label(player: dict) -> str:
    count = player.get('ante_count', 0)
    return f"{player['nickname']} ({count})"


def ante_keyboard_width(player_count: int) -> tuple[int, ...]:
    return tuple([2] * (player_count // 2) + ([1] if player_count % 2 else []) + [1])


async def refresh_ante_player_list(bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    tournament_id = data['ante_tournament_id']
    back_data = data['ante_back_data']

    players = [
        p for p in await UserManager.get_all_players(tournament_id=tournament_id)
        if p['box'] > 0
    ]
    if not players:
        await bot.edit_message_text(
            chat_id=data['ante_chat_id'],
            message_id=data['ante_message_id'],
            text='Нет игроков для фиксации входа.',
            reply_markup=create_inline_keyboard(1, **{back_data: '⬅ Назад'}),
        )
        return

    buttons = {
        f'ante_r:{tournament_id}:{player["tg_id"]}': (
            ante_player_button_label(player),
            'primary',
        )
        for player in players
    }
    buttons[back_data] = '⬅ Назад'

    total_entries = sum(p['ante_count'] for p in players)
    text = LEXICON['select_player_for_ante']
    if total_entries:
        text += f"\n\nВсего входов: {total_entries}"

    await bot.edit_message_text(
        chat_id=data['ante_chat_id'],
        message_id=data['ante_message_id'],
        text=text,
        reply_markup=create_inline_keyboard(ante_keyboard_width(len(players)), **buttons),
    )
