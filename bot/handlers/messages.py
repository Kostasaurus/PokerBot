from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReactionTypeEmoji
from pydantic import ValidationError

from bot.FSM.FSM import Registration, Actions, Admin
from bot.filters.user_filters import IsAdmin
from bot.keyboards.keyboards_builders import create_inline_keyboard
from bot.lexicon.phrases import LEXICON
from bot.utils.adding_tournament_utils import process_tournament_info
from managers.tournaments_manager import TournamentManager
from managers.user_manager import UserManager
from schemas.user_schemas import Nickname, RegisterUser
from schemas.user_schemas import UserEmail, OneUserResult

message_router = Router()


@message_router.message(StateFilter(Registration.waiting_email))
async def get_user_email(message: Message, state: FSMContext):
    try:
        email = UserEmail(email=message.text)

    except ValidationError:
        await message.reply(LEXICON['invalid_email'])
        await message.react([ReactionTypeEmoji(emoji='👎')])
        return
    if not await UserManager.check_email_exists(message.text):
        await state.update_data(email=message.text)
        await message.react([ReactionTypeEmoji(emoji='👍')])
        reply_markup = create_inline_keyboard(1, use_tg_nickname=('Использовать тг-никнейм', 'primary')) if message.from_user.username else None
        await message.answer(LEXICON['ask_nickname'], reply_markup=reply_markup)
        await state.set_state(Registration.waiting_nickname)
    else:
        await message.reply(LEXICON['email_taken'])
        await message.react([ReactionTypeEmoji(emoji='👎')])
        return

@message_router.message(StateFilter(Registration.waiting_nickname))
async def get_user_nickname(message: Message, state: FSMContext):
    try:
        nickname = Nickname(nickname=message.text)
    except ValidationError:
        await message.answer(LEXICON['invalid_nickname'])
        await message.react([ReactionTypeEmoji(emoji='👎')])
        return
    if not await UserManager.check_nickname_exists(message.text):
        await state.update_data(nickname=message.text.replace('@', ''))
        data = await state.get_data()
        await message.react([ReactionTypeEmoji(emoji='👍')])


        await UserManager.register_user(user=RegisterUser(
            tg_id=message.from_user.id,
            nickname=data['nickname']
        ))
        await message.answer(LEXICON['user_registered'])


        await state.set_state(Actions.just_registered)
        await state.update_data(data={'is_registered': True})
    else:
        await message.reply(LEXICON['nickname_taken'])
        await message.react([ReactionTypeEmoji(emoji='👎')])
        return


@message_router.message(StateFilter(Admin.waiting_tournament_info))
async def add_tournament_info(message: Message, state: FSMContext):
    result = await process_tournament_info(message.text)
    if not result:
        await message.reply('Турнир успешно добавлен!')
        await message.react([ReactionTypeEmoji(emoji='👍')])
        await state.clear()
    else:
        await message.reply(result, reply_markup=create_inline_keyboard(1, **{'delete_state': ('Отменить', 'danger')}))
        await message.react([ReactionTypeEmoji(emoji='👎')])


@message_router.message(StateFilter(Admin.waiting_dealer), IsAdmin())
async def add_dealer(message: Message, state: FSMContext):
    items = message.text.split()
    if len(items) == 1:
        nick = items[0].replace('@', '')
        table = None
    elif len(items) == 2:
        nick = items[0].replace('@', '')
        table = int(items[1])
    else:
        await message.reply(f"Неверный формат!\nПеределывай!", reply_markup=create_inline_keyboard(1, delete_state=('Отменить', 'danger')))
        await message.react([ReactionTypeEmoji(emoji='👎')])
        return
    data = await state.get_data()
    tournament_id = data['dealer_tournament_id']
    result =  await TournamentManager.set_dealer(tournament_id=tournament_id, nickname=nick, table_number=table)
    if isinstance(result, int):
        await message.answer(f'Добавлен дилер {nick}\nСтол {result}')
        await state.clear()
    else:
        await message.reply(text=result, reply_markup=create_inline_keyboard(1, delete_state=('Отменить', 'danger')))
        await message.react([ReactionTypeEmoji(emoji='👎')])

@message_router.message(StateFilter(Admin.waiting_results), IsAdmin())
async def add_result(message: Message, state: FSMContext):
    info = message.text.split(' ')
    if len(info) != 2:
        await message.reply(text='Фигню написал, переделывай!')
        await message.react([ReactionTypeEmoji(emoji='👎')])
        return
    nickname, result = info
    try:
        OneUserResult(username=nickname, result=int(result))
    except ValidationError:
        await message.reply(text='Фигню написал, переделывай!')
        await message.react([ReactionTypeEmoji(emoji='👎')])
        return
    data = await state.get_data()

    tg_id = await TournamentManager.check_user_tournament_registration(tournament_id=data['tournament_id'], nickname=nickname)
    if isinstance(tg_id, int):
        current_results = data.get('results', {})
        current_results[tg_id] = int(result)
        await state.update_data(results=current_results)
        await message.react([ReactionTypeEmoji(emoji='👍')])
    else:
        await message.reply(tg_id)




