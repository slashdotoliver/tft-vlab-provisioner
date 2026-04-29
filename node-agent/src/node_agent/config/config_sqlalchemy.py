from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@dataclass(frozen=True)
class DatabaseConfig:
    database_url: str = "postgresql+psycopg://manager_db_user:password@servidor_db:5432/lab_db"
    pool_size: int = 3
    max_overflow: int = 10
    pool_pre_ping: bool = True
    pool_recycle_seconds: int = 3600


def generate_session_factory(database_config: DatabaseConfig, debug: bool = False) -> sessionmaker:
    return sessionmaker(
        bind=(
            create_engine(
                url=database_config.database_url,
                pool_size=database_config.pool_size,
                echo_pool="debug" if debug else None,
                max_overflow=database_config.max_overflow,
                pool_pre_ping=database_config.pool_pre_ping,
                pool_recycle=database_config.pool_recycle_seconds,
            )
        ),
        autocommit=False,
        autoflush=False,
    )
