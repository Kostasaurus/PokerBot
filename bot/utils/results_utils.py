from aiogram import Bot
from aiogram.fsm.context import FSMContext

from bot.keyboards.keyboards_builders import create_inline_keyboard
from bot.lexicon.phrases import LEXICON
from managers.user_manager import UserManager


def results_player_button_label(player: dict, pending: dict) -> str:
    tg_id = player['tg_id']
    score = pending.get(str(tg_id), pending.get(tg_id))
    if score is None and player.get('result'):
        score = player['result']
    if score is not None:
        return f"{player['nickname']} ({score})"
    return player['nickname']


def results_keyboard_width(player_count: int) -> tuple[int, ...]:
    return tuple([2] * (player_count // 2) + ([1] if player_count % 2 else []) + [1, 1])


async def refresh_results_player_list(bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    tournament_id = data['tournament_id']
    pending = data.get('results', {})
    year = data['results_year']
    month = data['results_month']
    status = data['results_status']

    players = await UserManager.get_all_players(tournament_id=tournament_id)        
    
    if not players:
        await bot.edit_message_text(
            chat_id=data['results_chat_id'],
            message_id=data['results_message_id'],
            text='Нет игроков для добавления результатов.',
            reply_markup=create_inline_keyboard(1, **{
                f't:{year}:{month}:{tournament_id}:{status}': ('Отменить', 'danger'),
            }),
        )
        return

    buttons = {
        f'rp:{tournament_id}:{player["tg_id"]}': (
            results_player_button_label(player, pending),
            'primary',
        )
        for player in players
    }
    buttons['save_results'] = ('Сохранить', 'success')
    buttons[f't:{year}:{month}:{tournament_id}:{status}'] = ('Отменить', 'danger')

    saved_count = len(pending)
    text = LEXICON['select_player_for_results']
    if saved_count:
        text += f"\n\nДобавлено: {saved_count}"

    await bot.edit_message_text(
        chat_id=data['results_chat_id'],
        message_id=data['results_message_id'],
        text=text,
        reply_markup=create_inline_keyboard(results_keyboard_width(len(players)), **buttons),
    )
