import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile
from pydantic import ValidationError

from bot.FSM.FSM import Registration, Actions, Admin
from bot.filters.user_filters import IsNotRegistered, IsRegistered, IsAdmin
from bot.keyboards.keyboards_builders import (
    create_inline_keyboard, tournaments_list_keyboard,
    months_keyboard, build_scheduled_keyboard, build_play_keyboard, build_quarters_stats_keyboard,
    build_months_stats_keyboard
)
from bot.lexicon.phrases import LEXICON
from bot.lexicon.templates import TemplateBuilder
from bot.utils.date_utils import get_date_range_for_year, get_quarter_range, get_date_range_for_month
from bot.utils.ante_utils import refresh_ante_player_list
from bot.utils.results_utils import refresh_results_player_list
from bot.utils.players_utils import (
    parse_players_callback,
    players_list_keyboard,
    players_list_keyboard_width,
    refresh_delete_player_list,
)
from core.settings import settings
from managers.tournaments_manager import TournamentManager
from managers.user_manager import UserManager
from schemas.user_schemas import RegisterUser, Nickname

logger = logging.getLogger(__name__)
callback_router = Router()


# ===== Navigation: year/month selection =====

# Return to the month selection view for a given year
@callback_router.callback_query(F.data.startswith('months:'))
async def back_to_months(call: CallbackQuery, state: FSMContext):
    logger.info("User %d navigated back to months", call.from_user.id)
    await call.answer()
    await call.message.delete_reply_markup()
    _, year = call.data.split(":")
    year = int(year)
    await call.message.edit_text(LEXICON['tournaments'], reply_markup=months_keyboard(year=year))

# Switch between years (2025/2026) and show month grid
@callback_router.callback_query(F.data.startswith('year:'))
async def change_year(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    _, year = call.data.split(":")
    year = int(year)
    logger.info("User %d switched to year %d", call.from_user.id, year)
    await call.message.edit_text(call.message.text, reply_markup=months_keyboard(year=year))


# ===== Tournament listing by month =====

# Show all tournaments for a selected month with status indicators
@callback_router.callback_query(F.data.startswith("month:"))
async def show_month_tournaments(call: CallbackQuery):
    user_id = call.from_user.id
    await call.answer()
    await call.message.delete_reply_markup()
    _, year_str, month_str = call.data.split(":")
    year, month = int(year_str), int(month_str)
    logger.info("User %d requested tournaments for %02d.%d", user_id, month, year)

    tournaments = await TournamentManager.get_tournaments_by_month(year, month, user_id=user_id)
    if not tournaments:
        await call.message.edit_text(
            f'В этом месяце турниров не было',
            reply_markup=create_inline_keyboard(1, **{f"months:{year}": "⬅ Назад к месяцам"})
        )

        return

    text = TemplateBuilder.show_tournaments_in_month(
        tournaments=tournaments, month=month, year=year,
        is_admin=user_id in settings.bot.ADMINS,
    )
    await call.message.edit_text(
        text,
        reply_markup=tournaments_list_keyboard(tournaments, month=month, year=year)
    )


# ===== Individual tournament details and actions =====

# Show tournament details depending on its availability status (av=available, reg=registered, full/unavailable)
@callback_router.callback_query(F.data.startswith("t:"))
async def show_tournament_detail_handler(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    await state.clear()
    _, year, month, tournament_id, status = call.data.split(":")
    logger.info("User %d viewing tournament %s (status=%s)", call.from_user.id, tournament_id, status)

    tournament_info = await TournamentManager.get_tournaments_with_status(tournament_id=tournament_id, user_id=call.from_user.id, only_future=False, month=month, year=year)
    if not tournament_info:
        await call.message.edit_text(text='Пока нет информации о турнире', reply_markup=create_inline_keyboard(1, **{f'month:{year}:{month}': '⬅ к месяцу'}))
        return

    tournament = tournament_info['tournament']
    if status == 'av':
       
        text = (
            TemplateBuilder.show_available_tournament_info(
                tournament_info, is_admin=call.from_user.id in settings.bot.ADMINS
            )
        )
        reply_markup = create_inline_keyboard(1, **{
            f'play:{year}:{month}:{tournament_id}': ('Участвовать', 'success'),
            f'month:{year}:{month}': '⬅ к месяцу'
        }) if call.from_user.id not in settings.bot.ADMINS else create_inline_keyboard(
            (1, 1, 2, 2, 1, 1), **{
            f'ps:{year}:{month}:{tournament_id}:{status}': ('Участники', 'primary'),
            f'finish_t:{year}:{month}:{tournament_id}:{status}': ('Закрыть регистрацию', 'danger'),
            f'ante:t:{year}:{month}:{tournament_id}:{status}': ('+ вход', 'primary'),
            f'd:t:{year}:{month}:{tournament_id}:{status}': ('+ крупье', 'primary'),
            f'ed:t:{year}:{month}:{tournament_id}:{status}': ('Изменить', 'primary'),
            f'rm_t:{year}:{month}:{tournament_id}:{status}': ('Удалить', 'danger'),
            f'play:{year}:{month}:{tournament_id}': ('Участвовать', 'success'),
            f'month:{year}:{month}': '⬅ к месяцу'
        })
    elif status == 'reg':
        # text = f'{tournament.title}\n\n{tournament.start_time}'
        text = TemplateBuilder.show_users_tournament_info(tournament_info)
        reply_markup = create_inline_keyboard(1, **{
            f'c_t:{year}:{month}:{tournament_id}': ('Отменить запись', 'danger'),
            f'month:{year}:{month}': '⬅ к месяцу'
        }) if call.from_user.id not in settings.bot.ADMINS else create_inline_keyboard(
            (1, 1, 2, 2, 1, 1), **{
            f'ps:{year}:{month}:{tournament_id}:{status}': ('Участники', 'primary'),
            f'finish_t:{year}:{month}:{tournament_id}:{status}': ('Закрыть регистрацию', 'danger'),
            f'ante:t:{year}:{month}:{tournament_id}:{status}': ('+ вход', 'primary'),
            f'd:t:{year}:{month}:{tournament_id}:{status}': ('+ крупье', 'primary'),
            f'ed:t:{year}:{month}:{tournament_id}:{status}': ('Изменить', 'primary'),
            f'rm_t:{year}:{month}:{tournament_id}:{status}': ('Удалить', 'danger'),
            f'c_t:{year}:{month}:{tournament_id}': ('Отменить запись', 'danger'),
            f'month:{year}:{month}': '⬅ к месяцу'
        })
    elif status == 'fin':
        results = await UserManager.get_all_users_stats(tournament_id=tournament_id)
        text=TemplateBuilder.show_tournament_stats(tournament=tournament, results=results, tg_id=call.from_user.id)
        reply_markup = create_inline_keyboard(1, **{
            f'month:{year}:{month}': '⬅ к месяцу',
        }) if call.from_user.id not in settings.bot.ADMINS else create_inline_keyboard(
            (1, 2, 1, 1), **{
            f'ps:{year}:{month}:{tournament_id}:{status}': ('Участники', 'primary'),
            f'ante:t:{year}:{month}:{tournament_id}:{status}': ('+ вход', 'primary'),
            f'r:{year}:{month}:{tournament_id}:{status}':('+ результат', 'primary'),            
            f'rm_t:{year}:{month}:{tournament_id}:{status}': ('Удалить турнир', 'danger'),
            f'month:{year}:{month}': '⬅ к месяцу'
        })

    await call.message.edit_text(
        text=text,
        reply_markup=reply_markup
    )

# Confirm registration for a tournament (from the detail view)
@callback_router.callback_query(F.data.startswith("play:"))
async def confirm_tournament_registration(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()
    _, year, month, tournament_id = call.data.split(":")
    logger.info("User %d asking confirmation for tournament %s", call.from_user.id, tournament_id)

    await call.message.edit_text(
        "Подтвердить запись на турнир?",
        reply_markup=create_inline_keyboard(1, **{
            f"confirmed:{tournament_id}": ('Подтвердить', 'success'),
            f"t:{year}:{month}:{tournament_id}:av": '⬅ Назад'
        })
    )

# Register user to tournament after confirmation
@callback_router.callback_query(F.data.startswith("confirmed:"))
async def register_to_tournament(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()
    _, tournament_id = call.data.split(":")
    logger.info("User %d confirmed registration for tournament %s", call.from_user.id, tournament_id)

    try:
        tournament_info = await TournamentManager.register_user_for_tournament(
            user_id=call.from_user.id, tournament_id=tournament_id
        )
        await call.message.edit_text(
            text=TemplateBuilder.register_user_for_tournament_template(tournament_info), reply_markup=None
        )
    except ValueError as e:
        logger.warning("Registration failed for user %d: %s", call.from_user.id, e)
        await call.answer(str(e), show_alert=True)

# Detail view of a tournament from the /play list (active tournaments)
@callback_router.callback_query(F.data.startswith("a_t:"))
async def show_active_tournament_detail(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()
    _, tournament_id, status = call.data.split(":")
    logger.info("User %d viewing active tournament %s (status=%s)", call.from_user.id, tournament_id, status)

    if status == 'reg':
        tournament_info = await TournamentManager.get_tournaments_with_status(
            user_id=call.from_user.id, tournament_id=tournament_id, only_future=True
        )
        text=TemplateBuilder.show_users_tournament_info(tournament_info)
        reply_markup=create_inline_keyboard(1, **{
            f"cancel_tournament:{tournament_id}": ('Отменить запись', 'danger'),
            'play': '⬅ Назад'
        }) if call.from_user.id not in settings.bot.ADMINS else create_inline_keyboard(
            (1, 2, 2, 1, 1),
            **{
            f'ps:{tournament_id}:{status}': ('Участники', 'primary'),
            f'ante:a_t:{tournament_id}:{status}': ('+ вход', 'primary'),
            f'd:a_t:{tournament_id}:{status}': ('+ крупье', 'primary'),
            f'ed:a_t:{tournament_id}:{status}': ('Изменить', 'primary'),
            f'rm_a_t:{tournament_id}:{status}': ('Удалить', 'danger'),
            f"cancel_tournament:{tournament_id}": ('Отменить запись', 'danger'),
            'play': '⬅ Назад',
        })

    elif status == 'av':
        tournament_info = await TournamentManager.get_tournaments_with_status(
            user_id=call.from_user.id, tournament_id=tournament_id
        )
        text=TemplateBuilder.show_available_tournament_info(
            tournament_info, is_admin=call.from_user.id in settings.bot.ADMINS
        )
        reply_markup=create_inline_keyboard(1, **{
            f"play_command:{tournament_id}": ('Участвовать', 'success'),
            'play': '⬅ Назад'
        }) if call.from_user.id not in settings.bot.ADMINS else create_inline_keyboard(
            (1, 2, 2, 1, 1),
            **{
            f'ps:{tournament_id}:{status}': ('Участники', 'primary'),
            f'ante:a_t:{tournament_id}:{status}': ('+ вход', 'primary'),
            f'd:a_t:{tournament_id}:{status}': ('+ крупье', 'primary'),
            f'ed:a_t:{tournament_id}:{status}': ('Изменить', 'primary'),
            f'rm_a_t:{tournament_id}:{status}': ('Удалить', 'danger'),
            f"play_command:{tournament_id}": ('Участвовать', 'success'),
            'play': '⬅ Назад'
        })

    await call.message.edit_text(text=text, reply_markup=reply_markup)


# Quick registration from /play list (alternative to play:)
@callback_router.callback_query(F.data.startswith('play_command:'))
async def quick_register_from_play(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()
    _, tournament_id = call.data.split(":")
    logger.info("User %d quick-register from play list to tournament %s", call.from_user.id, tournament_id)

    await call.message.edit_text(
        "Подтвердить запись на турнир?",
        reply_markup=create_inline_keyboard(1, **{
            f"confirmed:{tournament_id}": ('Подтвердить', 'success'),
            f"a_t:{tournament_id}:av": '⬅ Назад'
        })
    )

# Redirect to the /play view with all upcoming tournaments
@callback_router.callback_query(F.data == 'play')
async def handle_play_button(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()
    logger.info("User %d opened /play list", call.from_user.id)

    data = await TournamentManager.get_tournaments_with_status(user_id=call.from_user.id)
    markup = build_play_keyboard(data)
    await call.message.edit_text(
        "Нет предстоящих турниров." if not markup else "Ближайшие турниры:",
        reply_markup=markup
    )

# Dummy callback for greyed-out buttons (e.g., "No places available")
@callback_router.callback_query(F.data == "pass")
async def dummy_callback(call: CallbackQuery):
    logger.debug("User %d pressed disabled button", call.from_user.id)
    await call.answer("Это действие недоступно", show_alert=False)

# Alert when tournament is fully booked
@callback_router.callback_query(F.data == 'tournament_is_full')
async def tournament_is_full_handler(call: CallbackQuery):
    logger.info("User %d tried to register to a full tournament", call.from_user.id)
    await call.answer('К сожалению, все места заняты', show_alert=False)



@callback_router.callback_query(F.data == 'all_scheduled')
async def show_all_scheduled_tournaments(call: CallbackQuery):
    user_id = call.from_user.id
    await call.answer()
    await call.message.delete_reply_markup()
    logger.info("User %d requested all scheduled tournaments", user_id)

    tournaments = await TournamentManager.get_tournaments_with_status(
        user_id=user_id,
        only_future=True
    )

    my_tournaments = [t for t in tournaments if t['user_registered']]

    if not my_tournaments:
        await call.message.edit_text("У вас нет запланированных турниров.")
        return

    await call.message.edit_text(
        TemplateBuilder.build_closest_tournaments(my_tournaments),
        reply_markup=create_inline_keyboard(1, **{
            'cancel_registration': ('Выбрать и отменить', 'danger'),
            'scheduled': '⬅ Назад'
                                                  })
    )

# Show the cancel registration menu (list of user's registered tournaments)
@callback_router.callback_query(F.data == 'cancel_registration')
async def show_cancel_menu(call: CallbackQuery):
    user_id = call.from_user.id
    await call.answer()
    await call.message.delete_reply_markup()
    logger.info("User %d opened cancel registration menu", user_id)

    all_tournaments = await TournamentManager.get_tournaments_with_status(
        user_id=user_id,
        only_future=True
    )

    my_tournaments = [t for t in all_tournaments if t['user_registered']]

    await call.message.edit_text(
        'Выберите, какой турнир хотите отменить',
        reply_markup=build_scheduled_keyboard(my_tournaments)
    )

# Cancel specific tournament (from the cancel menu)
@callback_router.callback_query(F.data.startswith("cancel_tournament:"))
async def cancel_tournament_from_menu(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()
    _, tournament_id = call.data.split(":")
    logger.info("User %d requesting cancellation for tournament %s", call.from_user.id, tournament_id)

    await call.message.edit_text(
        "Вы уверены, что хотите отменить запись?",
        reply_markup=create_inline_keyboard(1, **{
            f"confirm_cancel:{tournament_id}": ('Абсолютно', 'danger'),
            'cancel_registration': '⬅ Назад'
        })
    )

@callback_router.callback_query(F.data == "scheduled")
async def back_to_scheduled(call: CallbackQuery):
    user_id = call.from_user.id
    await call.answer()
    logger.info(f"Пользователь {user_id} запросил /scheduled")

    tournaments = await TournamentManager.get_tournaments_with_status(
        user_id=user_id,
        only_future=True
    )

    my_tournaments = [t for t in tournaments if t['user_registered']]

    if not my_tournaments:
        await call.message.answer("У вас нет запланированных турниров.")
        return

    closest = my_tournaments[0]

    await call.message.edit_text(
        TemplateBuilder.build_closest_tournament(closest),
        reply_markup=create_inline_keyboard(
            1,
            **{f'cancel_scheduled:{closest['tournament'].id}': ('Отменить запись', 'danger'),
               'all_scheduled': ('Все запланированные игры', 'primary')}
        )
    )


@callback_router.callback_query(F.data.startswith("cancel_scheduled"))
async def cancel_tournament_from_scheduled(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()
    _, tournament_id = call.data.split(":")
    logger.info("User %d requesting cancellation for tournament %s (from scheduled)", call.from_user.id, tournament_id)

    await call.message.edit_text(
        "Вы уверены, что хотите отменить запись?",
        reply_markup=create_inline_keyboard(1, **{
            f"confirm_cancel:{tournament_id}": ('Абсолютно', 'danger'),
            f"scheduled": '⬅ Назад'
        })
    )


# Cancel specific tournament (from the tournament detail view)
@callback_router.callback_query(F.data.startswith("c_t:"))
async def cancel_tournament_from_detail(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()
    _, year, month, tournament_id = call.data.split(":")
    logger.info("User %d requesting cancellation for tournament %s (from detail)", call.from_user.id, tournament_id)

    await call.message.edit_text(
        "Вы уверены, что хотите отменить запись?",
        reply_markup=create_inline_keyboard(1, **{
            f"confirm_cancel:{tournament_id}": ('Абсолютно', 'danger'),
            f"t:{year}:{month}:{tournament_id}:reg": '⬅ Назад'
        })
    )

# Actual deletion of registration
@callback_router.callback_query(F.data.startswith("confirm_cancel:"))
async def confirm_cancel_registration_handler(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()
    _, tournament_id = call.data.split(":")
    logger.info("User %d confirmed cancellation for tournament %s", call.from_user.id, tournament_id)

    try:
        await TournamentManager.cancel_user_registration(tg_id=call.from_user.id, tournament_id=tournament_id)
        await call.message.edit_text("Запись отменена.")
    except ValueError as e:
        logger.warning("Cancellation failed for user %d: %s", call.from_user.id, e)
        await call.answer(str(e), show_alert=True)


# ===== Registration entry points =====

# Start registration process for unregistered users
@callback_router.callback_query(F.data == 'register', IsNotRegistered())
async def start_registration_unregistered(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    await call.answer()
    await call.message.delete_reply_markup()
    logger.info("User %d started registration (not registered)", user_id)

    agreement = FSInputFile(path=LEXICON['agreement_file'])
    await call.message.answer_document(document=agreement, caption=LEXICON['starting_registration'],
                                  reply_markup=create_inline_keyboard(1, **{
                                      'accept_terms': ('ПРИНЯТЬ', 'primary')
                                  }))
    await state.set_state(Registration.waiting_agreement)

# Inform already registered users
@callback_router.callback_query(F.data == 'register', IsRegistered())
async def registration_already_registered(call: CallbackQuery):
    user_id = call.from_user.id
    await call.answer()
    await call.message.delete_reply_markup()
    logger.info("User %d tried to register again but is already registered", user_id)

    await call.message.answer(LEXICON['register_command_for_registered'])

# Open tournament selection by months
@callback_router.callback_query(F.data == 'tournaments')
async def handle_tournaments_button(call: CallbackQuery):
    user_id = call.from_user.id
    await call.answer()
    await call.message.delete_reply_markup()
    logger.info("User %d opened tournaments list", user_id)

    await call.message.answer(LEXICON[call.data], reply_markup=months_keyboard())

@callback_router.callback_query(F.data == 'accept_terms')
async def accept_terms(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    reply_markup = create_inline_keyboard(1, **{
        'use_tg_nickname': ('Использовать тг-никнейм', 'primary')}) if call.from_user.username else None
    await call.message.answer(LEXICON['ask_nickname'], reply_markup=reply_markup)
    await state.set_state(Registration.waiting_nickname)


# delete all user info after confirmation
@callback_router.callback_query(F.data == 'confirm_delete')
async def confirm_delete_handler(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()
    await UserManager.delete_user(call.from_user.id)
    await call.message.edit_text(text=LEXICON['deleted'])




@callback_router.callback_query(F.data == 'use_tg_nickname', StateFilter(Registration.waiting_nickname))
async def use_tg_nickname_handler(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()

    try:
        nickname = Nickname(nickname=call.from_user.username)
    except ValidationError:
        await call.message.answer(LEXICON['invalid_nickname'])
        return
    if not await UserManager.check_nickname_exists(call.from_user.username):
        await state.update_data(nickname=call.from_user.username.replace('@', ''))
        data = await state.get_data()


        await UserManager.register_user(user=RegisterUser(
            tg_id=call.from_user.id,
            email=None,
            nickname=data['nickname']
        ))
        await call.message.answer(LEXICON['user_registered'])


        await state.set_state(Actions.just_registered)
        await state.update_data(data={'is_registered': True})
    else:
        await call.message.reply(LEXICON['nickname_taken'])



# ---- Admin options ----

@callback_router.callback_query(F.data == 'delete_state')
async def delete_state_handler(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    await state.clear()
    await call.message.edit_text('Оке, зыбыли', reply_markup=None)


@callback_router.callback_query(F.data.startswith('ed:'), IsAdmin())
async def edit_tournament_handler(call: CallbackQuery, state: FSMContext):
    if call.data.startswith('ed:a_t:'):
        tournament_id, status = call.data.split(':')[2:]
        back_data = f'a_t:{tournament_id}:{status}'
    else:
        year, month, tournament_id, status = call.data.split(':')[2:]
        back_data = f't:{year}:{month}:{tournament_id}:{status}'

    await call.answer()
    await call.message.delete_reply_markup()
    await call.message.edit_text(
        LEXICON['edit_tournament'],
        reply_markup=create_inline_keyboard(1, **{back_data: '⬅ Назад'}),
    )
    await state.set_state(Admin.waiting_edit_tournament_info)
    await state.update_data(edit_tournament_id=tournament_id, edit_back_button=back_data)


@callback_router.callback_query(F.data.startswith('finish_t:'), IsAdmin())
async def close_tournament_registration_handler(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()
    _, year, month, tournament_id, _status = call.data.split(':')
    logger.info("Admin %d closed registration for tournament %s", call.from_user.id, tournament_id)

    closed = await TournamentManager.close_tournament_registration(tournament_id=tournament_id)
    if not closed:
        await call.answer('Турнир не найден', show_alert=True)
        return

    await call.message.answer(LEXICON['registration_closed'])


@callback_router.callback_query(F.data.startswith('d:'))
async def dealer_handler(call: CallbackQuery, state: FSMContext):
    if call.data.startswith('d:a_t:'):
        tournament_id, status = call.data.split(':')[2:]
        button_data = f'a_t:{tournament_id}:{status}'
    elif call.data.startswith('d:t:'):
        year, month, tournament_id, status = call.data.split(':')[2:]
        button_data = f't:{year}:{month}:{tournament_id}:{status}'
    await call.answer()
    await call.message.delete_reply_markup()
    tables = await TournamentManager.get_table_distribution(tournament_id)
    text = (
        'Укажите ник участника\n'
        '(через пробел можно указать номер стола)\n'
        '(Если стол не указан, то будет использован первый пустой\n\n'
        'Распределение столов:\n'
    )
    for table, count in tables.items():
        text += f"Стол {table}: {count}/9 участников\n"
    await call.message.edit_text(text, reply_markup=create_inline_keyboard(1, **{button_data: '⬅ Назад'}))
    await state.set_state(Admin.waiting_dealer)
    await state.update_data(data={'dealer_tournament_id': tournament_id})


@callback_router.callback_query(F.data.startswith('r:'))
async def add_results_handler(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    _, year, month, tournament_id, status = call.data.split(':')

    await state.set_state(Admin.waiting_results)
    await state.update_data(
        tournament_id=tournament_id,
        results_year=int(year),
        results_month=int(month),
        results_status=status,
        results={},
    )

    sent = await call.message.answer(LEXICON['select_player_for_results'])
    await state.update_data(
        results_chat_id=sent.chat.id,
        results_message_id=sent.message_id,
    )
    await refresh_results_player_list(call.message.bot, state)


@callback_router.callback_query(F.data.startswith('rp:'), IsAdmin())
async def select_player_for_result(call: CallbackQuery, state: FSMContext):
    await call.answer()
    _, tournament_id, tg_id = call.data.split(':', 2)
    tg_id = int(tg_id)

    players = await UserManager.get_all_players(tournament_id=tournament_id)
    player = next((p for p in players if p['tg_id'] == tg_id), None)
    if not player:
        await call.answer('Игрок не найден', show_alert=True)
        return

    await state.set_state(Admin.waiting_result_score)
    await state.update_data(
        result_player_tg_id=tg_id,
        result_player_nickname=player['nickname'],
    )
    await call.message.answer(
        LEXICON['enter_result_score'].format(nickname=player['nickname'])        
    )


@callback_router.callback_query(F.data == 'res_back', IsAdmin())
async def back_to_results_player_list(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(Admin.waiting_results)
    await refresh_results_player_list(call.message.bot, state)


@callback_router.callback_query(F.data == 'save_results', StateFilter(Admin.waiting_results))
async def save_results_handler(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    data = await state.get_data()
    results = data.get("results", {})
    if not results:
        await call.message.answer('Нет ни одного результата для сохранения!')
        return
    tournament_id = data.get('tournament_id')
    await TournamentManager.add_results(tournament_id=tournament_id, results=results)
    await call.message.edit_text('Данные добавлены!', reply_markup=None)

    showresults = await UserManager.get_all_users_stats(tournament_id=tournament_id)
    tournament_info = await TournamentManager.get_tournament_by_id(tournament_id=tournament_id)
    year = data.get('results_year', tournament_info.start_time.year)
    month = data.get('results_month', tournament_info.start_time.month)
    status = data.get('results_status', 'fin')

    await call.message.answer(
        text=TemplateBuilder.show_tournament_stats(
            tournament=tournament_info, results=showresults, tg_id=0
        ),
        reply_markup=create_inline_keyboard(1, **{
            f'r:{year}:{month}:{tournament_id}:{status}': ('Добавить результат', 'primary'),
        }),
    )
    await state.clear()
    


@callback_router.callback_query(F.data == 'stats_all')
async def show_all_stats(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    stats = await UserManager.get_all_users_stats()
    await call.message.edit_text(text=TemplateBuilder.show_stats(tg_id=call.from_user.id, stats=stats), reply_markup=create_inline_keyboard(1, **{
        'stats_years':('К годам', 'primary')
    }))


@callback_router.callback_query(F.data == 'stats_years')
async def show_all_stats_years_nav(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    text = call.message.text
    year = datetime.now().year
    await call.message.edit_text(text=text, reply_markup=create_inline_keyboard(2, **{
        f'view_quarters_st:{year}': (str(year), 'primary'),
    }))


@callback_router.callback_query(F.data.startswith('view_quarters_st:'))
async def show_year_stats_quarter_mode(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    year = int(call.data.split(':')[1])

    stats = await UserManager.get_all_users_stats(*get_date_range_for_year(year))
    await call.message.edit_text(text=TemplateBuilder.show_stats(tg_id=call.from_user.id, stats=stats, year=year),
                                 reply_markup=build_quarters_stats_keyboard(year=year))

@callback_router.callback_query(F.data.startswith('view_months_st:'))
async def show_year_stats_month_mode(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    year = int(call.data.split(':')[1])

    stats = await UserManager.get_all_users_stats(*get_date_range_for_year(year))
    await call.message.edit_text(text=TemplateBuilder.show_stats(tg_id=call.from_user.id, stats=stats, year=year),
                                 reply_markup=build_months_stats_keyboard(year=year))

@callback_router.callback_query(F.data.startswith('st_quarter:'))
async def show_quarter_stats(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    year, quarter = map(int, call.data.split(":")[1:])

    stats = await UserManager.get_all_users_stats(*get_quarter_range(year, quarter))
    await call.message.edit_text(text=TemplateBuilder.show_stats(tg_id=call.from_user.id, stats=stats, year=year, quarter=quarter),
                                 reply_markup=create_inline_keyboard(2, **{f'view_quarters_st:{year}':(f'К {year}', 'primary'), f'stats_all':('За все время', 'primary')}))

@callback_router.callback_query(F.data.startswith('st_month:'))
async def show_month_stats(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    year, month = map(int, call.data.split(":")[1:])

    stats = await UserManager.get_all_users_stats(*get_date_range_for_month(year, month))
    await call.message.edit_text(text=TemplateBuilder.show_stats(tg_id=call.from_user.id, stats=stats, year=year, month=month),
                                 reply_markup=create_inline_keyboard(2, **{f'view_months_st:{year}':(f'К {year}', 'primary'), f'stats_all':('За все время', 'primary')}))



@callback_router.callback_query(F.data.startswith('rm_'), IsAdmin())
async def request_delete_tournament(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()

    if call.data.startswith('rm_a_t:'):
        _, tournament_id, status = call.data.split(':')
        confirm_data = f'yes_rm_a_t:{tournament_id}'
        back_data = f'a_t:{tournament_id}:{status}'
    else:
        _, year, month, tournament_id, status = call.data.split(':')
        confirm_data = f'yes_rm_t:{year}:{month}:{tournament_id}'
        back_data = f't:{year}:{month}:{tournament_id}:{status}'

    logger.info("Admin %d requested delete for tournament %s", call.from_user.id, tournament_id)
    await call.message.edit_text(
        LEXICON['confirm_delete_tournament'],
        reply_markup=create_inline_keyboard(1, **{
            confirm_data: ('Абсолютно', 'danger'),
            back_data: '⬅ Назад',
        })
    )


@callback_router.callback_query(F.data.startswith('yes_rm_'), IsAdmin())
async def confirm_delete_tournament(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()

    if call.data.startswith('yes_rm_a_t:'):
        _, tournament_id = call.data.split(':')
        from_play = True
    else:
        _, year, month, tournament_id = call.data.split(':')
        from_play = False

    logger.info("Admin %d confirmed delete for tournament %s", call.from_user.id, tournament_id)
    deleted = await TournamentManager.delete_tournament(tournament_id=tournament_id)
    if not deleted:
        await call.answer('Турнир не найден', show_alert=True)
        return

    if from_play:
        data = await TournamentManager.get_tournaments_with_status(user_id=call.from_user.id)
        markup = build_play_keyboard(data)
        suffix = "Нет предстоящих турниров." if not markup else "Ближайшие турниры:"
        await call.message.edit_text(
            f"{LEXICON['tournament_deleted']}\n\n{suffix}",
            reply_markup=markup,
        )
    else:
        await call.message.edit_text(
            LEXICON['tournament_deleted'],
            reply_markup=create_inline_keyboard(1, **{f'month:{year}:{month}': '⬅ к месяцу'}),
        )


@callback_router.callback_query(F.data.startswith('ante:'), IsAdmin())
async def show_ante_player_list(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()

    if call.data.startswith('ante:a_t:'):
        _, tournament_id, status = call.data.split(':')[1:]
        back_data = f'a_t:{tournament_id}:{status}'
    else:
        _, year, month, tournament_id, status = call.data.split(':')[1:]
        back_data = f't:{year}:{month}:{tournament_id}:{status}'

    players = await UserManager.get_all_players(tournament_id=tournament_id)        
    
    if not players:
        await call.answer('Нет игроков для фиксации входа', show_alert=True)
        return

    await state.update_data(
        ante_chat_id=call.message.chat.id,
        ante_message_id=call.message.message_id,
        ante_tournament_id=tournament_id,
        ante_back_data=back_data,
    )
    await refresh_ante_player_list(call.message.bot, state)


@callback_router.callback_query(F.data.startswith('ante_r:'), IsAdmin())
async def record_ante_entry_handler(call: CallbackQuery, state: FSMContext):
    _, tournament_id, tg_id = call.data.split(':', 2)
    recorded = await TournamentManager.record_player_ante_entry(
        tournament_id=tournament_id,
        tg_id=int(tg_id),
    )
    if not recorded:
        await call.answer('Не удалось зафиксировать вход', show_alert=True)
        return

    await call.answer(LEXICON['entry_recorded'], show_alert=True)
    await refresh_ante_player_list(call.message.bot, state)


@callback_router.callback_query(F.data.startswith('ps:'))
async def show_players(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    if await state.get_state() == Admin.waiting_add_player.state:
        await state.clear()
    tournament_id, status, _, _, back_data = parse_players_callback(call.data)

    is_admin = call.from_user.id in settings.bot.ADMINS
    players = await UserManager.get_all_players(tournament_id=tournament_id)
    buttons = players_list_keyboard(back_data, is_admin)
    await call.message.edit_text(
        text=TemplateBuilder.show_tournament_players(players=players, tg_id=call.from_user.id),
        reply_markup=create_inline_keyboard(players_list_keyboard_width(is_admin), **buttons),
    )


@callback_router.callback_query(F.data.startswith('pd:'), IsAdmin())
async def show_delete_player_list(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    tournament_id, _, _, _, back_data = parse_players_callback(f'ps:{call.data[3:]}')

    players = await UserManager.get_all_players(tournament_id=tournament_id)
    if not players:
        await call.answer('Нет игроков для удаления', show_alert=True)
        return

    await state.update_data(
        ps_chat_id=call.message.chat.id,
        ps_message_id=call.message.message_id,
        ps_tournament_id=tournament_id,
        ps_back_data=back_data,
        ps_viewer_tg_id=call.from_user.id,
    )
    await refresh_delete_player_list(call.message.bot, state)


@callback_router.callback_query(F.data.startswith('pdr:'), IsAdmin())
async def delete_player_from_tournament(call: CallbackQuery, state: FSMContext):
    _, tournament_id, tg_id = call.data.split(':', 2)
    tg_id = int(tg_id)

    players = await UserManager.get_all_players(tournament_id=tournament_id)
    if not any(p['tg_id'] == tg_id for p in players):
        await call.answer('Игрок не найден', show_alert=True)
        return

    await TournamentManager.cancel_user_registration(tg_id=tg_id, tournament_id=tournament_id)
    await call.answer(LEXICON['player_removed'], show_alert=True)
    await refresh_delete_player_list(call.message.bot, state)


@callback_router.callback_query(F.data.startswith('pa:'), IsAdmin())
async def start_add_player(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete_reply_markup()
    tournament_id, _, _, _, back_data = parse_players_callback(f'ps:{call.data[3:]}')

    await state.set_state(Admin.waiting_add_player)
    await state.update_data(
        add_player_tournament_id=tournament_id,
        add_player_back_data=back_data,
        add_player_chat_id=call.message.chat.id,
        add_player_message_id=call.message.message_id,
        add_player_viewer_tg_id=call.from_user.id,
    )
    action_suffix = back_data.split(':', 1)[1]
    await call.message.edit_text(
        LEXICON['enter_player_nickname'],
        reply_markup=create_inline_keyboard(1, **{f'ps:{action_suffix}': '⬅ Назад'}),
    )







