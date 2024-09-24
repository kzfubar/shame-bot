import configparser
import logging
from pathlib import Path
from typing import ParamSpec, Sequence, TypeVar

from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, mapped_column, sessionmaker

logger = logging.getLogger(__name__)


Base = declarative_base()


class EmailClaimedError(Exception):
    pass


class User(Base):
    __tablename__ = "users"
    email = mapped_column(String, primary_key=True)
    discord_id = mapped_column(Integer, nullable=True)
    todoist_id = mapped_column(String)
    todoist_token = mapped_column(String)

    def __repr__(self) -> str:
        return f"<User(email={self.email}, discord_id={self.discord_id}, todoist_id={self.todoist_id})>"


_session_maker: sessionmaker | None = None


def load_db() -> sessionmaker:
    logger.info("Loading database")
    db_path = Path(__file__).parent.parent / "data" / "database.sqlite"
    migrated_users = []

    if not db_path.exists():
        logger.info("Creating database at %s", db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        config_path = Path(__file__).parent.parent / "settings.cfg"
        config = configparser.ConfigParser()
        config.read(config_path)

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    global _session_maker  # noqa: PLW0603
    _session_maker = sessionmaker(bind=engine)

    if migrated_users:
        with _session_maker() as session:
            session.add_all(migrated_users)
            session.commit()
    return _session_maker


T = TypeVar("T")
P = ParamSpec("P")


def get_session() -> Session:
    session_maker = _session_maker or load_db()
    return session_maker()


def get_users(session: Session) -> Sequence[User]:
    return session.execute(select(User)).scalars().all()


def add_discord_to_user(session: Session, email: str, discord_id: int) -> bool:
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if not user:
        return False

    if user.discord_id is not None:
        raise EmailClaimedError

    user.discord_id = discord_id
    session.commit()

    return True


def get_user_by_discord_id(session: Session, discord_id: int) -> User | None:
    return session.execute(
        select(User).where(User.discord_id == discord_id)
    ).scalar_one_or_none()


def discord_id_exists(session: Session, discord_id: int) -> bool:
    return (
        session.execute(
            select(User).where(User.discord_id == discord_id)
        ).scalar_one_or_none()
        is not None
    )


def add_user(session: Session, user: User) -> None:
    session.add(user)
    session.commit()


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_user_by_todoist_id(session: Session, todoist_id: str) -> User | None:
    return session.execute(
        select(User).where(User.todoist_id == todoist_id)
    ).scalar_one_or_none()
