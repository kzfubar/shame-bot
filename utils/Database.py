import configparser
import logging
from pathlib import Path
from typing import Callable, Concatenate, ParamSpec, Sequence, TypeVar

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


def migrate_from_cfg(config: configparser.ConfigParser) -> list[User]:
    todoist_key_by_email = dict(config.items("TODOIST_KEY_BY_EMAIL"))
    discord_id_by_email = dict(config.items("DISCORD_ID_BY_EMAIL"))
    todoist_id_by_email = {a: b for b, a in config.items("EMAIL_BY_TODOIST_ID")}

    migrated_users = []
    for email, todoist_id in todoist_id_by_email.items():
        if email not in todoist_key_by_email:
            logger.error("No todoist key found for email: %s", email)
            continue
        logger.info("Migrating user: %s", email)

        migrated_users.append(
            User(
                email=email,
                discord_id=discord_id_by_email.get(email),
                todoist_id=todoist_id,
                todoist_token=todoist_key_by_email[email],
            )
        )
    return migrated_users


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

        if "TODOIST_KEY_BY_EMAIL" in config:
            logger.info("Migrating from old config database")
            migrated_users = migrate_from_cfg(config)

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


def validate_db[T, **P](
    db_function: Callable[Concatenate[Session, P], T],
) -> Callable[P, T]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        session_maker = _session_maker or load_db()
        with session_maker() as session:
            return db_function(session, *args, **kwargs)

    return wrapper


@validate_db
def get_users(session: Session) -> Sequence[User]:
    return session.execute(select(User)).scalars().all()


@validate_db
def add_discord_to_user(session: Session, email: str, discord_id: int) -> bool:
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if not user:
        return False

    if user.discord_id is not None:
        raise EmailClaimedError

    user.discord_id = discord_id
    session.commit()

    return True


@validate_db
def get_user_by_discord_id(session: Session, discord_id: int) -> User | None:
    return session.execute(
        select(User).where(User.discord_id == discord_id)
    ).scalar_one_or_none()


@validate_db
def discord_id_exists(session: Session, discord_id: int) -> bool:
    return (
        session.execute(
            select(User).where(User.discord_id == discord_id)
        ).scalar_one_or_none()
        is not None
    )


@validate_db
def add_user(session: Session, user: User) -> None:
    session.add(user)
    session.commit()


@validate_db
def get_user_by_email(session: Session, email: str) -> User | None:
    return session.execute(select(User).where(User.email == email)).scalar_one_or_none()


@validate_db
def get_user_by_todoist_id(session: Session, todoist_id: str) -> User | None:
    return session.execute(
        select(User).where(User.todoist_id == todoist_id)
    ).scalar_one_or_none()
