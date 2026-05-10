import logging
import uuid

from sqlalchemy import insert, select, update, delete, func
from sqlalchemy.exc import IntegrityError

from core.core_dependency.db_dependency import connection
from db.models.tournaments import Tournament
from db.models.tournaments_registration import TournamentRegistration
from db.models.users import Users
from db.models.users_registered import UsersRegistered
from schemas.user_schemas import CreateUser, RegisterUser

logger = logging.getLogger(__name__)

class UserManager:

    @staticmethod
    @connection
    async def check_user_exists( session, user_id: int) -> bool:
        result = await session.execute(select(Users).where(Users.tg_id == user_id))
        return result.scalar_one_or_none() is not None

    @staticmethod
    @connection
    async def find_tg_id_by_username( session, username: str):
        user_result = await session.execute(
            select(Users.tg_id).where(Users.username == username.replace('@', ''))
        )
        tg_id = user_result.scalar_one_or_none()
        return tg_id


    @staticmethod
    @connection
    async def check_registration( session, user_id: int) -> bool:
        result = await session.execute(
            select(UsersRegistered).where(UsersRegistered.tg_id == user_id)
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    @connection
    async def create_user( session, user: CreateUser) -> str | None:
        logger.info("Создание пользователя: tg_id=%d, username=%s", user.tg_id, user.username)
        stmt = insert(Users).values(**user.model_dump())
        try:
            await session.execute(stmt)
            await session.commit()
            logger.info("Пользователь tg_id=%d успешно создан", user.tg_id)
        except IntegrityError:
            await session.rollback()
            logger.warning("Пользователь с tg_id=%d уже существует", user.tg_id)
        except Exception as e:
            await session.rollback()
            logger.error("Ошибка при создании пользователя tg_id=%d: %s", user.tg_id, e, exc_info=True)
            raise

    @staticmethod
    @connection
    async def register_user(session, user: RegisterUser):
        logger.info("Регистрация пользователя: tg_id=%d, email=%s, nickname=%s",
                    user.tg_id, user.email, user.nickname)
        stmt1 = insert(UsersRegistered).values(**user.model_dump())
        stmt2 = (
            update(Users)
            .where(Users.tg_id == user.tg_id)
            .values(is_registered=True)
        )
        try:
            await session.execute(stmt1)
            await session.execute(stmt2)
            await session.commit()
            logger.info("Пользователь tg_id=%d успешно зарегистрирован", user.tg_id)
        except IntegrityError as e:
            await session.rollback()
            orig = e.orig
            constraint_name = getattr(orig, 'constraint_name', None)
            if constraint_name is None:
                msg = str(orig).lower()
                if 'email' in msg:
                    constraint_name = 'users_email_key'
                elif 'nickname' in msg:
                    constraint_name = 'users_nickname_key'

            if constraint_name in ('users_email_key', 'uq_users_email'):
                logger.warning("Регистрация: email '%s' уже занят", user.email)
                raise ValueError("Пользователь с таким email уже существует")
            elif constraint_name in ('users_nickname_key', 'uq_users_nickname'):
                logger.warning("Регистрация: никнейм '%s' уже занят", user.nickname)
                raise ValueError("Этот никнейм уже занят")
            else:
                logger.error("Неизвестная ошибка целостности при регистрации пользователя tg_id=%d: %s",
                             user.tg_id, e, exc_info=True)
                raise
        except Exception as e:
            await session.rollback()
            logger.error("Ошибка при регистрации пользователя tg_id=%d: %s", user.tg_id, e, exc_info=True)
            raise


    @staticmethod
    @connection
    async def check_email_exists(session, email: str, exclude_tg_id: int | None = None) -> bool:
        query = select(UsersRegistered).where(UsersRegistered.email == email)
        if exclude_tg_id is not None:
            query = query.where(UsersRegistered.tg_id != exclude_tg_id)
        result = await session.execute(query)
        return result.scalar_one_or_none() is not None


    @staticmethod
    @connection
    async def check_nickname_exists(session, nickname: str, exclude_tg_id: int | None = None) -> bool:
        query = select(UsersRegistered).where(UsersRegistered.nickname == nickname)
        if exclude_tg_id is not None:
            query = query.where(UsersRegistered.tg_id != exclude_tg_id)
        result = await session.execute(query)
        return result.scalar_one_or_none() is not None


    @staticmethod
    @connection
    async def register_user(session, user: RegisterUser) -> None:

        logger.info("Регистрация пользователя: tg_id=%d, email=%s, nickname=%s",
                    user.tg_id, user.email, user.nickname)


        stmt1 = insert(UsersRegistered).values(**user.model_dump())
        stmt2 = (
            update(Users)
            .where(Users.tg_id == user.tg_id)
            .values(is_registered=True)
        )
        try:
            await session.execute(stmt1)
            await session.execute(stmt2)
            await session.commit()
            logger.info("Пользователь tg_id=%d успешно зарегистрирован", user.tg_id)
        except IntegrityError as e:
            await session.rollback()
            # Всё равно анализируем ошибку базы на случай гонки данных
            orig = e.orig
            msg = str(orig).lower()
            if 'email' in msg:
                raise ValueError("Пользователь с таким email уже существует")
            elif 'nickname' in msg:
                raise ValueError("Этот никнейм уже занят")
            else:
                logger.error("Неизвестная ошибка целостности при регистрации: %s", e, exc_info=True)
                raise
        except Exception as e:
            await session.rollback()
            logger.error("Ошибка при регистрации пользователя tg_id=%d: %s", user.tg_id, e, exc_info=True)
            raise


    @staticmethod
    @connection
    async def delete_user(session, user_id: int) -> None:
        stmt1 = delete(TournamentRegistration).where(TournamentRegistration.tg_id == user_id)
        stmt2 = delete(UsersRegistered).where(UsersRegistered.tg_id == user_id)
        stmt3 = delete(Users).where(Users.tg_id == user_id)
        try:
            await session.execute(stmt1)
            await session.execute(stmt2)
            await session.execute(stmt3)
            await session.commit()
        except Exception:
            logger.exception('Error during deleting user')

    from datetime import datetime

    @staticmethod
    @connection
    async def get_all_users_stats(
        session,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        tournament_id: uuid.UUID | str | None = None
    ) -> list[dict]:

        query = (
            select(
                TournamentRegistration.tg_id,
                UsersRegistered.nickname,
                func.sum(TournamentRegistration.result).label('total')
            )
            .join(Tournament, Tournament.id == TournamentRegistration.tournament_id)
            .join(UsersRegistered, UsersRegistered.tg_id == TournamentRegistration.tg_id)
            .where(Tournament.status == 'finished')
            .group_by(TournamentRegistration.tg_id, UsersRegistered.nickname)
            .order_by(func.sum(TournamentRegistration.result).desc())
        )
        if start_date:
            query = query.where(Tournament.start_time >= start_date)
        if end_date:
            query = query.where(Tournament.start_time < end_date)
        if tournament_id:
            query = query.where(Tournament.id == tournament_id)

        result = await session.execute(query)
        rows = result.all()
        return [
            {'tg_id': row.tg_id, 'username': row.nickname, 'total': row.total or 0}
            for row in rows
        ]