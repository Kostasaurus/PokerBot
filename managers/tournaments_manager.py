import datetime
import logging
import math
import random
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, extract
from sqlalchemy import select, insert, delete, case, update

from core.core_dependency.db_dependency import connection
from db.models.canceled_registrations import CanceledRegistration
from db.models.tournaments import Tournament
from db.models.tournaments_registration import TournamentRegistration
from db.models.users import Users
from db.models.users_registered import UsersRegistered
from managers.user_manager import UserManager
from schemas.tournament_schemas import TournamentRead, TournamentRegistrationBase, TournamentRegistrationReturn, \
    AddingTournament

logger = logging.getLogger(__name__)

class TournamentManager:

    @staticmethod
    @connection
    async def get_tournaments_by_month(session, year: int, month: int, user_id: int):

        reg_stats = (
            select(
                TournamentRegistration.tournament_id,
                func.count().label('registered_count'),
                func.bool_or(TournamentRegistration.tg_id == user_id).label('user_registered')
            )
            .group_by(TournamentRegistration.tournament_id)
            .subquery()
        )

        query = (
            select(
                Tournament,
                func.coalesce(reg_stats.c.registered_count, 0).label('registered_count'),
                func.coalesce(reg_stats.c.user_registered, False).label('user_registered')
            )
            .outerjoin(reg_stats, Tournament.id == reg_stats.c.tournament_id)
            .where(
                extract('year', Tournament.start_time) == year,
                extract('month', Tournament.start_time) == month
            )
            .order_by(Tournament.start_time)
        )

        result = await session.execute(query)
        rows = result.mappings().all()

        tournaments_data = []
        for row in rows:
            tournaments_data.append({
                'tournament': row['Tournament'],
                'registered_count': row['registered_count'],
                'user_registered': row['user_registered']
            })
        return tournaments_data


    @staticmethod
    @connection
    async def get_tournament_detail(session, tournament_id: int) -> TournamentRead | None:
        result = await session.execute(
            select(Tournament).where(Tournament.id == tournament_id)
        )
        tournament = result.scalar_one_or_none()

        return TournamentRead(
            id=tournament.id,
            title=tournament.title,
            start_time=tournament.start_time,
            max_tables=tournament.max_tables,
            status=tournament.status
        ) if tournament else None


    @staticmethod
    @connection
    async def check_is_box_available(session, tournament_id: int, box: int, table: int):
        stmt = select(func.count()).where(TournamentRegistration.tournament_id == tournament_id, TournamentRegistration.table == table, TournamentRegistration.box == box)
        occupied = await session.execute(stmt)
        return True if occupied < 1 else False


    @staticmethod
    @connection
    async def register_user_for_tournament(session, user_id: int, tournament_id: int):
        result = await session.execute(select(Tournament).where(Tournament.id == tournament_id))
        logger.info('checking tournament')
        tournament_result = result.scalar_one_or_none()
        if not tournament_result or tournament_result.status != 'scheduled':
            raise ValueError("Турнир недоступен для записи")
        tournament = TournamentRead(**tournament_result.__dict__)


        count_query = select(func.count()).where(TournamentRegistration.tournament_id == tournament_id)
        count = (await session.execute(count_query)).scalar()
        if count >= tournament.max_tables * 9:
            raise ValueError("Все места заняты")

        table_num = math.ceil(count / 9)
        table_num = table_num if table_num > 0 else 1
        box = random.randint(1, 9)

        while not TournamentManager.check_is_box_available(tournament_id=tournament_id, box=box, table=table_num):
                box = random.randint(1, 9)




        registration = TournamentRegistrationBase(
            tg_id=user_id,
            tournament_id=tournament_id,
            table=table_num,
            box=box
        )
        await session.execute(insert(TournamentRegistration).values(**registration.model_dump()))
        await session.commit()
        logger.info(f"Пользователь {user_id} записан на турнир {tournament_id}, бокс {box} table {table_num}")
        return TournamentRegistrationReturn(
            tournament_id=tournament_id,
            table=table_num,
            box=box,
            title=tournament.title,
            start_time=tournament.start_time,
            max_tables=tournament.max_tables,
        )

    @staticmethod
    @connection
    async def get_user_scheduled_tournaments(session, user_id: int, limit: int | None = None):

        query = (
            select(Tournament, TournamentRegistration.box.label('box'))
            .join(TournamentRegistration, Tournament.id == TournamentRegistration.tournament_id)
            .where(
                TournamentRegistration.tg_id == user_id,
                Tournament.start_time > func.now()
            )
            .order_by(Tournament.start_time)
        )
        if limit is not None:
            query = query.limit(limit)
        result = await session.execute(query)
        row = result.mappings().all()

        return [{
                'tournament': row.Tournament,
                'box': row.box
        }] if limit != 1 else ({
                'tournament': row.Tournament,
                'box': row.box
        } if row else None)


    @staticmethod
    @connection
    async def get_tournaments_with_status(
            session,
            user_id: int,
            tournament_id: uuid.UUID | None = None,
            only_future: bool = True,
            month: int | None = None,
            year: int | None = None
    ) -> list[dict] | dict | None:

        reg_stats = (
            select(
                TournamentRegistration.tournament_id,
                func.count().label('total_registered'),
                func.bool_or(TournamentRegistration.tg_id == user_id).label('user_registered'),
                func.max(
                    case(
                        (TournamentRegistration.tg_id == user_id, TournamentRegistration.box),
                        else_=None
                    )
                ).label('box'),

                func.max(
                    case(
                        (TournamentRegistration.tg_id == user_id, TournamentRegistration.table),
                        else_=None
                    )
                ).label('user_table')
            )
            .group_by(TournamentRegistration.tournament_id)
            .subquery()
        )

        query = (
            select(
                Tournament,
                func.coalesce(reg_stats.c.total_registered, 0).label('registered_count'),
                func.coalesce(reg_stats.c.user_registered, False).label('user_registered'),
                reg_stats.c.box.label('box'),
                reg_stats.c.user_table.label('table')
            )
            .outerjoin(reg_stats, Tournament.id == reg_stats.c.tournament_id)
        )

        if tournament_id is not None:
            query = query.where(Tournament.id == tournament_id)
        else:
            if only_future:
                query = query.where(
                    Tournament.start_time > func.now(),
                    Tournament.status == 'scheduled'
                )
            if year is not None and month is not None:
                query = query.where(
                    extract('year', Tournament.start_time) == year,
                    extract('month', Tournament.start_time) == month
                )

        query = query.order_by(Tournament.start_time)

        result = await session.execute(query)
        rows = result.all()

        if not rows:
            return None if tournament_id is not None else []

        if tournament_id is not None:
            row = rows[0]
            return {
                'tournament': row.Tournament,
                'registered_count': row.registered_count,
                'user_registered': row.user_registered,
                'box': row.box,
                'table': row.table
            }
        else:
            return [
                {
                    'tournament': row.Tournament,
                    'registered_count': row.registered_count,
                    'user_registered': row.user_registered,
                    'box': row.box,
                    'table': row.table
                }
                for row in rows
            ]


    @staticmethod
    @connection
    async def cancel_user_registration(session, tg_id: int, tournament_id: uuid.UUID) -> None:

        stmt1 = delete(TournamentRegistration).where(TournamentRegistration.tg_id == tg_id, TournamentRegistration.tournament_id == tournament_id)
        stm2 = insert(CanceledRegistration).values(tg_id = tg_id, tournament_id=tournament_id)

        result = await session.execute(stmt1)
        await session.execute(stm2)
        await session.commit()
        logger.info("Пользователь %d отменил запись на турнир %s", tg_id, tournament_id)



    @staticmethod
    @connection
    async def get_user_scheduled_tournament(session, user_id: int, tournament_id: uuid.UUID):
        query = (
            select(Tournament, TournamentRegistration.box.label('box'))
            .select_from(TournamentRegistration)
            .join(Tournament, Tournament.id == TournamentRegistration.tournament_id)
            .where(
                TournamentRegistration.tg_id == user_id,
                Tournament.id == tournament_id
            )
        )
        result = await session.execute(query)
        row = result.mappings().first()
        if row:
            return {
                'tournament': row['Tournament'],
                'box': row['box']
            }
        return None

    @staticmethod
    @connection
    async def add_new_tournament(session, tournament: AddingTournament):
        query = (
            insert(Tournament).values(tournament.model_dump())
        )
        await session.execute(query)
        await session.commit()
        logger.info('New tournament added')


    @staticmethod
    @connection
    async def get_table_distribution(session, tournament_id: uuid.UUID) -> dict[int, int]:

        query = (
            select(TournamentRegistration.table, func.count().label('count'))
            .where(TournamentRegistration.tournament_id == tournament_id)
            .group_by(TournamentRegistration.table)
            .order_by(TournamentRegistration.table)
        )
        result = await session.execute(query)
        rows = result.all()
        return {row.table: row.count for row in rows}


    import uuid

    @staticmethod
    @connection
    async def set_dealer(
            session,
            tournament_id: uuid.UUID,
            nickname: str,
            table_number: int | None = None
    ):

        tg_id = await UserManager.find_tg_id_by_username(username=nickname)
        if not tg_id:
            return f"❌ Пользователя с ником {nickname} не существует!"

        user_reg = await session.execute(
            select(TournamentRegistration).where(
                TournamentRegistration.tg_id == tg_id,
                TournamentRegistration.tournament_id == tournament_id,
                # TournamentRegistration.box == table_number
            )
        )
        registration = user_reg.scalar_one_or_none()

        if registration:
            if registration.box > 0:
                return f"❌ Пользователь {nickname} уже зарегистрирован на этот турнир как игрок."
            elif registration.table == table_number:
                return f"❌ Пользователь {nickname} уже зарегистрирован на этот стол как крупье."


        tournament = await session.execute(
            select(Tournament.max_tables).where(Tournament.id == tournament_id)
        )
        max_tables = tournament.scalar_one_or_none()
        if max_tables is None:
            return "❌ Турнир не найден."

        if table_number is not None:
            if not (1 <= table_number <= max_tables):
                return f"❌ Номер стола должен быть от 1 до {max_tables}."
            target_table = table_number
            existing_dealer = await session.execute(
                select(TournamentRegistration).where(
                    TournamentRegistration.tournament_id == tournament_id,
                    TournamentRegistration.table == target_table,
                    TournamentRegistration.box == 0
                )
            )
            dealer_record = existing_dealer.scalar_one_or_none()
            if dealer_record:
                await session.execute(
                    delete(TournamentRegistration).where(
                        TournamentRegistration.id == dealer_record.id
                    )
                )
                logger.info(f"Старый крупье на столе {target_table} удалён (id={dealer_record.id})")
        else:
            target_table = None
            for t in range(1, max_tables + 1):
                dealer_check = await session.execute(
                    select(TournamentRegistration).where(
                        TournamentRegistration.tournament_id == tournament_id,
                        TournamentRegistration.table == t,
                        TournamentRegistration.box == 0
                    )
                )
                if not dealer_check.scalar_one_or_none():
                    target_table = t
                    break
            if target_table is None:
                return "❌ На всех столах уже есть крупье. Невозможно назначить нового без указания номера стола."

        new_record = TournamentRegistration(
            tg_id=tg_id,
            tournament_id=tournament_id,
            table=target_table,
            box=0
        )
        session.add(new_record)
        await session.commit()
        logger.info(f"Крупье c ником {nickname} (tg_id={tg_id}) назначен на турнир {tournament_id}, стол {target_table}")
        return target_table

    @staticmethod
    @connection
    async def update_tournaments_status(session):
        now = datetime.now(timezone.utc)
        stmt = (
            update(Tournament)
            .where(Tournament.start_time + timedelta(hours=2) < now, Tournament.status != 'finished')
            .values(status='finished')
        )
        result = await session.execute(stmt)
        await session.commit()
        if result.rowcount:
            logger.info(f"Обновлено {result.rowcount} турниров на статус 'finished'")

    @staticmethod
    @connection
    async def check_user_tournament_registration(session, tournament_id: uuid.UUID | str, nickname: str):
        tg_id = await UserManager.find_tg_id_by_username(username=nickname)

        if not tg_id:
            return f"❌ Пользователя с ником {nickname} не существует!"

        user_reg = await session.execute(
            select(TournamentRegistration).where(
                TournamentRegistration.tg_id == tg_id,
                TournamentRegistration.tournament_id == tournament_id,

            )
        )

        if not user_reg.scalar_one_or_none():
            return f"❌ Пользователь с ником {nickname} не участвовал в этом турнире!"

        return tg_id

    @staticmethod
    @connection
    async def add_results(session, tournament_id: uuid.UUID | str, results: dict):
        # updated = 0
        for tg_id, result in results.items():
            stmt = (
                update(TournamentRegistration)
                .where(TournamentRegistration.tg_id == tg_id, TournamentRegistration.tournament_id == tournament_id)
                .values(result=result)
            )
            res = await session.execute(stmt)
            # updated += res.rowcount
        await session.commit()
        # return updated





