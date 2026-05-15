import logging

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
    await call.message.edit_text(call.message.text, reply_markup=months_keyboard(year=year))

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

    text = TemplateBuilder.show_tournaments_in_month(tournaments=tournaments, month=month, year=year)
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
    tournament = tournament_info['tournament']
    if not tournament_info:
        await call.message.edit_text(text='Пока нет информации о турнире', reply_markup=create_inline_keyboard(1, **{f'month:{year}:{month}': '⬅ к месяцу'}))
        return

    if status == 'av':
        reg_count = tournament_info['registered_count']

        text = (
            TemplateBuilder.show_available_tournament_info(tournament_info)
        )
        reply_markup = create_inline_keyboard(1, **{
            f'play:{year}:{month}:{tournament_id}': ('Участвовать', 'success'),
            f'month:{year}:{month}': '⬅ к месяцу'
        }) if not IsAdmin() else create_inline_keyboard(1, **{
            f'ps:{year}:{month}:{tournament_id}:{status}': ('Участники', 'primary'),
             f'd:t:{year}:{month}:{tournament_id}:{status}': ('Добавить крупье', 'primary'),
            f'play:{year}:{month}:{tournament_id}': ('Участвовать', 'success'),
            f'month:{year}:{month}': '⬅ к месяцу'
        })
    elif status == 'reg':
        # text = f'{tournament.title}\n\n{tournament.start_time}'
        text = TemplateBuilder.show_users_tournament_info(tournament_info)
        reply_markup = create_inline_keyboard(1, **{
            f'c_t:{year}:{month}:{tournament_id}': ('Отменить запись', 'danger'),
            f'month:{year}:{month}': '⬅ к месяцу'
        }) if not IsAdmin() else create_inline_keyboard(1, **{
            f'ps:{year}:{month}:{tournament_id}:{status}': ('Участники', 'primary'),
            f'd:t:{year}:{month}:{tournament_id}:{status}': ('Добавить крупье', 'primary'),
            f'c_t:{year}:{month}:{tournament_id}': ('Отменить запись', 'danger'),
            f'month:{year}:{month}': '⬅ к месяцу'
        })
    elif status == 'fin':
        results = await UserManager.get_all_users_stats(tournament_id=tournament_id)
        text=TemplateBuilder.show_tournament_stats(tournament=tournament, results=results, tg_id=call.from_user.id)
        reply_markup = create_inline_keyboard(1, **{
            f'month:{year}:{month}': '⬅ к месяцу',
        }) if not IsAdmin() else create_inline_keyboard(1, **{
            f'r:{year}:{month}:{tournament_id}:{status}':('Добавить результат', 'primary'),
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
        }) if not IsAdmin() else create_inline_keyboard(1, **{
            f'ps:{tournament_id}:{status}': ('Участники', 'primary'),
            f'd:a_t:{tournament_id}:{status}': ('Добавить крупье', 'primary'),
            f"cancel_tournament:{tournament_id}": ('Отменить запись', 'danger'),
            'play': '⬅ Назад',
        })

    elif status == 'av':
        tournament_info = await TournamentManager.get_tournaments_with_status(
            user_id=call.from_user.id, tournament_id=tournament_id
        )
        text=TemplateBuilder.show_available_tournament_info(tournament_info)
        reply_markup=create_inline_keyboard(1, **{
            f"play_command:{tournament_id}": ('Участвовать', 'success'),
            'play': '⬅ Назад'
        }) if not IsAdmin() else create_inline_keyboard(1, **{
            f'ps:{tournament_id}:{status}': ('Участники', 'primary'),
            f'd:a_t:{tournament_id}:{status}': ('Добавить крупье', 'primary'),
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
            "play": '⬅ Назад'
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
        "Нет предстоящих турниров." if not markup else "Список предстоящих турниров:",
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

    await call.message.edit_text(LEXICON['add_results'], reply_markup=create_inline_keyboard(1, **{
        f't:{year}:{month}:{tournament_id}:{status}':('Отменить', 'danger'),
        f'save_results':('Сохранить', 'success')
    }))
    await state.update_data(tournament_id=tournament_id)
    await state.set_state(Admin.waiting_results)

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
    await call.message.edit_text(text=text, reply_markup=create_inline_keyboard(2, **{
        # 'view_quarters_st:2025':('2025', 'primary'),
        'view_quarters_st:2026':('2026', 'primary'),

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



@callback_router.callback_query(F.data.startswith('ps:'))
async def show_players(call: CallbackQuery):
    await call.answer()
    await call.message.delete_reply_markup()
    info = call.data.split(':')
    if len(info) == 3:
        _, tournament_id, status = info
        reply_markup = create_inline_keyboard(1, **{f'a_t:{tournament_id}:{status}':'⬅ Назад'})
    elif len(info) == 5:
        _, year, month, tournament_id, status = info
        reply_markup = create_inline_keyboard(1, **{f't:{year}:{month}:{tournament_id}:{status}': '⬅ Назад'})

    players = await UserManager.get_all_players(tournament_id=tournament_id)
    await call.message.edit_text(text=TemplateBuilder.show_tournament_players(players=players, tg_id=call.from_user.id), reply_markup=reply_markup)







