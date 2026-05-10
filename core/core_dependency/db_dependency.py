from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine

from core.settings import settings


class DBDependency:
    _instance: Optional['DBDependency'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._engine = create_async_engine(
                url=settings.db_settings.postgres_url,
                echo=settings.db_settings.DB_ECHO,
                connect_args = {"timeout": 10},
                pool_size = 5,
                pool_timeout = 10,
                pool_recycle = 3600
            )
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                expire_on_commit=False
            )
            self._initialized = True

    @property
    def db_session(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    @property
    def db_engine(self) -> AsyncEngine:
        return self._engine

def get_db_engine() -> AsyncEngine:
    return DBDependency().db_engine

def connection(func, db: DBDependency = DBDependency()):
    async def wrapper(*args, **kwargs):
        async with db.db_session() as session:
            return await func(session, *args, **kwargs)

    return wrapper