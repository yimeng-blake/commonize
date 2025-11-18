from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest
import tempfile
from pathlib import Path

from airline_reservation.database import create_session_factory
from airline_reservation.dataset import generate_sample_data
from airline_reservation.models import Base, Flight, Passenger
from airline_reservation.services import (
    PaymentDeclinedError,
    add_flight,
    add_passenger,
    book_seat,
)


def make_in_memory_session_factory():
    db_file = Path(tempfile.mkstemp(prefix="airline-test", suffix=".db")[1])
    engine, session_factory = create_session_factory(
        f"sqlite+pysqlite:///{db_file}", echo=False
    )
    Base.metadata.create_all(engine)
    return session_factory


def test_booking_updates_availability_and_loyalty_points():
    session_factory = make_in_memory_session_factory()
    with session_factory() as session:
        flight = add_flight(
            session,
            flight_number="AR900",
            origin="LAX",
            destination="JFK",
            departure_time=datetime.utcnow(),
            arrival_time=datetime.utcnow() + timedelta(hours=5),
            aircraft_type="A320",
            total_seats=2,
        )
        passenger = add_passenger(
            session,
            first_name="Test",
            last_name="User",
            email="user@example.com",
            phone="+1-555-0000",
        )
        session.commit()
    with session_factory() as session:
        booking = book_seat(
            session,
            flight_id=flight.id,
            passenger_id=passenger.id,
            amount=300.0,
        )
        session.commit()
    with session_factory() as session:
        refreshed_flight = session.get(Flight, flight.id)
        refreshed_passenger = session.get(Passenger, passenger.id)
    assert refreshed_flight.available_seats == 1
    assert refreshed_passenger.loyalty_points == 30
    assert booking.status == "confirmed"


def test_payment_failure_rolls_back():
    session_factory = make_in_memory_session_factory()
    with session_factory() as session:
        flight = add_flight(
            session,
            flight_number="AR901",
            origin="LAX",
            destination="ORD",
            departure_time=datetime.utcnow(),
            arrival_time=datetime.utcnow() + timedelta(hours=4),
            aircraft_type="A320",
            total_seats=1,
        )
        passenger = add_passenger(
            session,
            first_name="Test",
            last_name="Failure",
            email="failure@example.com",
            phone="+1-555-1111",
        )
        session.commit()

    def failing_payment(amount: float, passenger_id: int):
        from airline_reservation.services import PaymentResult

        return PaymentResult(False, "DECLINED", "card declined")

    with session_factory() as session:
        with pytest.raises(PaymentDeclinedError):
            book_seat(
                session,
                flight_id=flight.id,
                passenger_id=passenger.id,
                amount=200.0,
                payment_fn=failing_payment,
            )
        session.rollback()
    with session_factory() as session:
        refreshed_flight = session.get(Flight, flight.id)
        assert refreshed_flight.available_seats == 1


def test_concurrent_booking_respects_capacity():
    session_factory = make_in_memory_session_factory()
    with session_factory() as session:
        flight = add_flight(
            session,
            flight_number="AR777",
            origin="SEA",
            destination="DEN",
            departure_time=datetime.utcnow(),
            arrival_time=datetime.utcnow() + timedelta(hours=2),
            aircraft_type="B737",
            total_seats=4,
        )
        passengers = [
            add_passenger(
                session,
                first_name=f"User{i}",
                last_name="Concurrent",
                email=f"user{i}@example.com",
                phone=f"+1-555-2{i:03d}",
            )
            for i in range(6)
        ]
        session.commit()

    def attempt(passenger_id: int):
        with session_factory() as session:
            try:
                book_seat(
                    session,
                    flight_id=flight.id,
                    passenger_id=passenger_id,
                    amount=150.0,
                )
                session.commit()
                return True
            except Exception:
                session.rollback()
                return False

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, [p.id for p in passengers]))

    assert 0 < sum(results) <= 4

    with session_factory() as session:
        refreshed = session.get(Flight, flight.id)
        assert refreshed.available_seats + sum(results) == 4


def test_dataset_generator_creates_records():
    session_factory = make_in_memory_session_factory()
    summary = generate_sample_data(session_factory, flights=5, passengers=20, bookings=25)
    with session_factory() as session:
        flight_count = session.query(Flight).count()
        passenger_count = session.query(Passenger).count()
    assert flight_count == 5
    assert passenger_count == 20
    assert summary["bookings"] <= 25
