import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InputFile, FSInputFile

from bot.FSM.FSM import Registration, Actions, Admin
from bot.filters.user_filters import IsRegistered, IsNotRegistered, IsAdmin
from bot.keyboards.keyboards_builders import create_inline_keyboard, months_keyboard, build_play_keyboard
from bot.keyboards.keyboards_dict import KEYBOARDS
from bot.keyboards.set_menu import set_user_menu
from bot.lexicon.phrases import LEXICON
from bot.lexicon.templates import TemplateBuilder
from bot.utils.date_utils import get_current_quarter, get_quarter_range
from core.settings import settings
from managers.tournaments_manager import TournamentManager
from managers.user_manager import UserManager
from schemas.user_schemas import CreateUser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

commands_router = Router()


@commands_router.message(CommandStart())
async def process_start_command(message: Message, state: FSMContext):
    user = message.from_user
    logger.info(f"Пользователь {user.id} (@{user.username}) запустил /start")

    is_admin = user.id in settings.bot.ADMINS
    await set_user_menu(message.bot, user.id, is_admin)

    if await UserManager.check_user_exists(user_id=user.id):
        if await UserManager.check_registration(user_id=user.id):
            logger.info(f"Пользователь {user.id} уже зарегистрирован")
            await message.answer(
                LEXICON['registered_started'],
                reply_markup=create_inline_keyboard(1, **{'play':'записаться', 'tournaments':'все турниры'})
            )
        else:
            logger.info(f"Пользователь {user.id} еще не зарегистрирован")
            await message.answer(
                LEXICON['unregistered_started'],
                reply_markup=create_inline_keyboard(1, **{'register':'Зарегистрироваться'},)
            )
    else:
        logger.info(f"Новый пользователь {user.id}")


        user_data = CreateUser(
            tg_id=user.id,
            firstname=user.first_name,
            lastname=user.last_name,
            username=user.username,
            language=user.language_code,
            is_registered=False
        )
        await UserManager.create_user(user=user_data)
        await state.set_state(Actions.starting)

        await message.answer(
            LEXICON['new_user'],
            reply_markup=create_inline_keyboard(1, **{'register':'Зарегистрироваться'})
        )


@commands_router.message(Command('help'))
async def process_help_command(message: Message):
    logger.info(f"Пользователь {message.from_user.id} запросил /help")
    await message.answer(LEXICON[message.text])


@commands_router.message(Command('faq'))
async def process_faq_command(message: Message):
    logger.info(f"Пользователь {message.from_user.id} запросил /faq")
    await message.answer(LEXICON[message.text])


@commands_router.message(Command('tournaments'))
async def process_tournaments_command(message: Message):
    logger.info(f"Пользователь {message.from_user.id} запросил /tournaments")
    await message.answer(LEXICON[message.text], reply_markup=months_keyboard())


@commands_router.message(Command('register'), IsNotRegistered())
async def process_register_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} запросил /register")

    logger.info(f"Пользователь {user_id} начинает процесс регистрации")
    agreement = FSInputFile(path='bot/assets/ПОЛЬЗОВАТЕЛЬСКОЕ_СОГЛАШЕНИЕ.docx')
    await message.answer_document(document=agreement, caption=LEXICON['starting_registration'], reply_markup=create_inline_keyboard(1, **{
        'accept_terms':'ПРИНЯТЬ'
    }))
    await state.set_state(Registration.waiting_agreement)

@commands_router.message(Command('register'), IsRegistered())
async def process_register_command_for_registered(message: Message, state: FSMContext):
    await message.answer(LEXICON['register_command_for_registered'], reply_markup=KEYBOARDS.get(message.text))




@commands_router.message(Command('play'), IsRegistered())
async def cmd_play(message: Message, state: FSMContext):
    logger.info(f"Пользователь {message.from_user.id} запросил /play")
    data = await TournamentManager.get_tournaments_with_status(user_id=message.from_user.id)
    markup = build_play_keyboard(data)
    await message.answer(("Нет предстоящих турниров." if not markup else "Список предстоящих турниров:"), reply_markup=markup)

@commands_router.message(Command('stats'))
async def process_statistics_command(message: Message):
    logger.info(f"Пользователь {message.from_user.id} запросил /statistics")
    current = get_current_quarter()
    date_range = get_quarter_range(*current)

    quarter_statistics = await UserManager.get_all_users_stats(*date_range)
    await message.answer(text=TemplateBuilder.show_stats(
        tg_id=message.from_user.id,
        stats=quarter_statistics,
        year=current[0],
        quarter=current[1]
    ), reply_markup=create_inline_keyboard(2, **{
     f'view_quarters_st:{current[0]}':f'К {current[0]} году',
     f'stats_all':'За все время'
    }))


@commands_router.message(Command('scheduled'), IsRegistered())
async def process_scheduled_command(message: Message):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} запросил /scheduled")

    tournaments = await TournamentManager.get_tournaments_with_status(
        user_id=user_id,
        only_future=True
    )

    my_tournaments = [t for t in tournaments if t['user_registered']]

    if not my_tournaments:
        await message.answer("У вас нет запланированных турниров.")
        return

    closest = my_tournaments[0]

    await message.answer(
        TemplateBuilder.build_closest_tournament(closest),
        reply_markup=create_inline_keyboard(
            1,
            **{f'cancel_scheduled:{closest['tournament'].id}':'Отменить запись', 'all_scheduled': 'Все запланированные игры'}
        )
    )



@commands_router.message(Command('delete'))
async def process_clean_command(message: Message):
    logger.info(f"Пользователь {message.from_user.id} запросил /delete")
    await message.answer('Вы точно уверены, что хотите стереть всю информацию о себе?\nЭто действие нельзя отменить', reply_markup=create_inline_keyboard(1, **{'confirm_delete': 'Абсолютно'}))

@commands_router.message(Command('contacts'))
async def process_contacts_command(message: Message):
    await message.answer(LEXICON[message.text])

@commands_router.message(Command('rules'))
async def process_rules_command(message: Message):
    await message.answer(LEXICON[message.text])


@commands_router.message(Command('add_tournament'), IsAdmin())
async def process_add_tournament_command(message: Message, state: FSMContext):
    await message.answer(LEXICON['add_tournament'])
    await state.set_state(Admin.waiting_tournament_info)

@commands_router.message(Command('play', 'scheduled'), IsNotRegistered())
async def for_unregistered(message: Message):
    await message.answer('Сначала необходимо зарегистрироваться!')

# @commands_router.message(Command('add_results'), IsAdmin())
# async def process_add_results_command(message: Message, state: FSMContext):
#     await m
