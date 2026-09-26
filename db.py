"""
Простая SQLite-база для хранения расписания по группам.
При каждой новой загрузке фото расписание конкретной группы
полностью заменяется свежераспознанным (старое не копится).
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./schedule.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True)
    group = Column(String, index=True)
    day = Column(String)
    pair_number = Column(Integer)
    time = Column(String)
    subject = Column(String)
    room = Column(String)
    teacher = Column(String)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def replace_group_schedule(group: str, lessons: list[dict]) -> None:
    """Удаляет старое расписание группы и записывает новое."""
    db = SessionLocal()
    try:
        db.query(Lesson).filter(Lesson.group == group).delete()
        for l in lessons:
            db.add(
                Lesson(
                    group=group,
                    day=l.get("day", ""),
                    pair_number=int(l.get("pair_number") or 0),
                    time=l.get("time", ""),
                    subject=l.get("subject", ""),
                    room=l.get("room", ""),
                    teacher=l.get("teacher", ""),
                )
            )
        db.commit()
    finally:
        db.close()


def get_groups() -> list[str]:
    db = SessionLocal()
    try:
        rows = db.query(Lesson.group).distinct().all()
        return sorted({r[0] for r in rows})
    finally:
        db.close()


def get_schedule(group: str) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Lesson)
            .filter(Lesson.group == group)
            .order_by(Lesson.day, Lesson.pair_number)
            .all()
        )
        return [
            {
                "day": r.day,
                "pair_number": r.pair_number,
                "time": r.time,
                "subject": r.subject,
                "room": r.room,
                "teacher": r.teacher,
            }
            for r in rows
        ]
    finally:
        db.close()
