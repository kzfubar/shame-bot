import configparser
import logging
from pathlib import Path
from typing import ParamSpec, Sequence, TypeVar

from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logger = logging.getLogger(__name__)


class EmailClaimedError(Exception):
    pass


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(primary_key=True)
    discord_id: Mapped[int | None] = mapped_column()
    todoist_id: Mapped[str] = mapped_column()
    todoist_token: Mapped[str] = mapped_column()

    def __repr__(self) -> str:
        return f"<User(email={self.email}, discord_id={self.discord_id}, todoist_id={self.todoist_id})>"


class Score(Base):
    __tablename__ = "scores"
    email: Mapped[str] = mapped_column(primary_key=True)
    streak: Mapped[int] = mapped_column()

    def __repr__(self) -> str:
        return f"<Score(email={self.email}, streak={self.streak})>"


_session_maker: sessionmaker[Session] | None = None


def load_db() -> sessionmaker[Session]:
    logger.info("Loading database")
    db_path = Path(__file__).parent.parent / "data" / "database.sqlite"

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


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_user_by_todoist_id(session: Session, todoist_id: str) -> User | None:
    return session.execute(
        select(User).where(User.todoist_id == todoist_id)
    ).scalar_one_or_none()


def add_score(session: Session, score: Score) -> None:
    session.add(score)


def get_score_by_email(session: Session, email: str) -> Score | None:
    return session.execute(
        select(Score).where(Score.email == email)
    ).scalar_one_or_none()
