from datetime import datetime, timedelta
from typing import Iterable, List, Optional, Tuple

from pytz import UTC
from sqlalchemy import func
from sqlmodel import Session, select

from elroy.store.data_models import (ArchivalMemory, CalendarEvent,
                                     CalendarEventDB, MemoryEntity, Signup,
                                     User)
from elroy.store.message import Message


def create_signup(session: Session, name: str, phone: str, email: Optional[str]) -> None:
    session.add(Signup(name=name, phone=phone, email=email))
    session.commit()


def generate_daily_report(session: Session) -> str:
    """
    Generate a report for the trailing 24-hour period, including new users and message volume for each user.
    """
    report_lines = []
    now = datetime.now(UTC)
    yesterday = now - timedelta(days=1)

    # Fetch new users
    new_users = session.exec(select(User).where(User.created_at >= yesterday)).all()
    report_lines.append(f"New Users in the last 24 hours: {len(new_users)}")
    for user in new_users:
        report_lines.append(f"- (ID: {user.id})")

    # Fetch message volume for each user
    user_message_counts: List[Tuple[int, int]] = (
        session.query(Message.user_id, func.count(Message.id)).filter(Message.created_at >= yesterday, Message.role == "user").group_by(Message.user_id).all()  # type: ignore
    )
    report_lines.append("\nMessage Volume per User in the last 24 hours:")
    for user_id, message_count in user_message_counts:
        report_lines.append(f"- (ID: {user_id}): {message_count} messages")

    return "\n".join(report_lines)


def get_archival_messages(session: Session, user_id: int) -> Iterable[ArchivalMemory]:
    return session.exec(select(ArchivalMemory).where(ArchivalMemory.user_id == user_id)).all()


def get_entity_name_summary(session: Session, user_id: int, entity_name: str, entity_label: str) -> Optional[str]:
    memory_entity = session.exec(
        select(MemoryEntity).where(
            MemoryEntity.user_id == user_id,
            MemoryEntity.entity_name == entity_name,
            MemoryEntity.entity_label == entity_label,
        )
    ).first()
    return memory_entity.text if memory_entity else None


def fetch_persisted_calendar_events(session: Session, user_id: int) -> List[CalendarEvent]:
    events = session.exec(select(CalendarEventDB).where(CalendarEventDB.user_id == user_id)).all()
    return [
        CalendarEvent(
            event_id=event.event_id,
            summary=event.summary,
            description=event.description,
            start=event.start,
            end=event.end,
            location=event.location,
            attendee_emails=event.attendee_emails.split(",") if event.attendee_emails else [],
            recurrence=event.recurrence.split(",") if event.recurrence else [],
            reminders=event.reminders,
            visibility=event.visibility,
        )
        for event in events
    ]


def get_recent_and_soon_events(session: Session, user_id: int) -> List[CalendarEvent]:
    """Gets events for preceding 12 hours to following 12 hours."""
    db_events = session.exec(
        select(CalendarEventDB).where(
            CalendarEventDB.user_id == user_id,
            CalendarEventDB.start >= datetime.now() - timedelta(hours=12),
            CalendarEventDB.end <= datetime.now() + timedelta(hours=12),
        )
    ).all()
    return [
        CalendarEvent(
            event_id=event.event_id,
            summary=event.summary,
            description=event.description,
            start=event.start,
            end=event.end,
            location=event.location,
            attendee_emails=event.attendee_emails.split(",") if event.attendee_emails else [],
            recurrence=event.recurrence.split(",") if event.recurrence else [],
            reminders=event.reminders,
            visibility=event.visibility,
        )
        for event in db_events
    ]


def upsert_event_to_db(session: Session, user_id: int, event: CalendarEvent) -> None:
    persisted_event = session.exec(
        select(CalendarEventDB).where(CalendarEventDB.event_id == event.event_id, CalendarEventDB.user_id == user_id)
    ).one_or_none()
    if persisted_event:
        persisted_event.summary = event.summary
        persisted_event.description = event.description
        persisted_event.start = event.start
        persisted_event.end = event.end
        persisted_event.location = event.location
        persisted_event.attendee_emails = ",".join(event.attendee_emails) if event.attendee_emails else ""
        persisted_event.recurrence = ",".join(event.recurrence) if event.recurrence else ""
        persisted_event.reminders = event.reminders
        persisted_event.visibility = event.visibility
    else:
        persisted_event = CalendarEventDB(
            user_id=user_id,
            event_id=event.event_id,
            summary=event.summary,
            description=event.description,
            start=event.start,
            end=event.end,
            location=event.location,
            attendee_emails=", ".join(event.attendee_emails),
            recurrence=", ".join(event.recurrence),
            reminders=event.reminders,
            visibility=event.visibility,
        )
    session.add(persisted_event)
    session.commit()


def persist_archival_memory(session: Session, user_id: int, name: str, text: str) -> None:
    archival_memory = ArchivalMemory(user_id=user_id, name=name, text=text)
    session.add(archival_memory)
    session.commit()
    session.refresh(archival_memory)
    from elroy.store.embeddings import upsert_embedding

    archival_memory_id = archival_memory.id
    assert archival_memory_id

    upsert_embedding(session, archival_memory)
