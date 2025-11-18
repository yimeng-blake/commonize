"""Utilities to populate the database with sample data for tests and demos."""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Dict, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .models import Flight, Passenger
from .services import add_flight, add_passenger, book_seat

AIRPORTS: Sequence[str] = (
    "ATL",
    "PEK",
    "DXB",
    "LAX",
    "HND",
    "ORD",
    "LHR",
    "HKG",
    "PVG",
    "CDG",
)
AIRCRAFT = ("A320", "A350", "B737", "B787")
FIRST_NAMES = ("Ava", "Noah", "Liam", "Mia", "Lucas", "Emma", "Ethan", "Isabella")
LAST_NAMES = ("Johnson", "Williams", "Smith", "Brown", "Garcia", "Lee")


def _random_datetime(days_from_now: int) -> datetime:
    start = datetime.utcnow() + timedelta(days=days_from_now)
    hour = random.randint(5, 22)
    minute = random.choice((0, 15, 30, 45))
    return start.replace(hour=hour, minute=minute, second=0, microsecond=0)


def generate_sample_data(
    session_factory: sessionmaker[Session],
    *,
    flights: int = 25,
    passengers: int = 200,
    bookings: int = 500,
) -> Dict[str, int]:
    """Populate the database with deterministic pseudo-random data."""

    random.seed(42)
    with session_factory() as session:
        for index in range(flights):
            origin, destination = random.sample(AIRPORTS, 2)
            departure = _random_datetime(random.randint(1, 10))
            arrival = departure + timedelta(hours=random.randint(2, 12))
            add_flight(
                session,
                flight_number=f"AR{1000 + index}",
                origin=origin,
                destination=destination,
                departure_time=departure,
                arrival_time=arrival,
                aircraft_type=random.choice(AIRCRAFT),
                total_seats=random.choice((90, 120, 180)),
            )
        for index in range(passengers):
            add_passenger(
                session,
                first_name=random.choice(FIRST_NAMES),
                last_name=random.choice(LAST_NAMES),
                email=f"test{index}@example.com",
                phone=f"+1-555-{index:04d}",
            )
        session.commit()

    successful = 0
    with session_factory() as session:
        flight_ids = [flight.id for flight in session.scalars(select(Flight))]
        passenger_ids = [passenger.id for passenger in session.scalars(select(Passenger))]
        if not flight_ids or not passenger_ids:
            return {"flights": 0, "passengers": 0, "bookings": 0}
        for _ in range(bookings):
            flight_id = random.choice(flight_ids)
            passenger_id = random.choice(passenger_ids)
            try:
                book_seat(
                    session,
                    flight_id=flight_id,
                    passenger_id=passenger_id,
                    amount=random.choice((120.0, 180.0, 220.0)),
                )
                successful += 1
            except Exception:
                session.rollback()
        session.commit()
    return {"flights": flights, "passengers": passengers, "bookings": successful}
