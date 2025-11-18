"""Business logic for the airline reservation system."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, List, Optional, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Booking, Flight, Passenger, Payment


class PaymentDeclinedError(RuntimeError):
    """Raised when the mock payment gateway declines a charge."""


@dataclass
class PaymentResult:
    success: bool
    transaction_ref: str
    message: str = ""


def mock_payment_gateway(amount: float, passenger_id: int) -> PaymentResult:
    """Naive mock payment integration that always succeeds for deterministic tests."""

    return PaymentResult(success=True, transaction_ref=f"TXN-{passenger_id}-{int(amount * 100)}")


class SeatAllocator:
    """Seat allocation helper that ensures deterministic seat numbering."""

    seat_letters: Sequence[str] = tuple("ABCDEF")

    @classmethod
    def next_available_seat(cls, session: Session, flight_id: int, total_seats: int) -> str:
        existing = set(
            session.scalars(
                select(Booking.seat_number).where(Booking.flight_id == flight_id)
            )
        )
        rows = max(total_seats // len(cls.seat_letters), 1) + 1
        for row in range(1, rows + 1):
            for letter in cls.seat_letters:
                seat = f"{row}{letter}"
                if seat not in existing:
                    return seat
        raise ValueError("no seats available")


def add_flight(
    session: Session,
    *,
    flight_number: str,
    origin: str,
    destination: str,
    departure_time: datetime,
    arrival_time: datetime,
    aircraft_type: str,
    total_seats: int,
) -> Flight:
    """Create a flight entry."""

    flight = Flight(
        flight_number=flight_number,
        origin=origin,
        destination=destination,
        departure_time=departure_time,
        arrival_time=arrival_time,
        aircraft_type=aircraft_type,
        total_seats=total_seats,
        available_seats=total_seats,
    )
    session.add(flight)
    session.flush()
    return flight


def add_passenger(
    session: Session,
    *,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
) -> Passenger:
    passenger = Passenger(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
    )
    session.add(passenger)
    session.flush()
    return passenger


def list_available_flights(session: Session) -> List[Flight]:
    return list(session.scalars(select(Flight).where(Flight.available_seats > 0)))


def search_flights(
    session: Session,
    *,
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    departure_date: Optional[datetime] = None,
) -> List[Flight]:
    stmt: Select[tuple[Flight]] = select(Flight)
    if origin:
        stmt = stmt.where(Flight.origin == origin.upper())
    if destination:
        stmt = stmt.where(Flight.destination == destination.upper())
    if departure_date:
        start = departure_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        stmt = stmt.where(Flight.departure_time >= start, Flight.departure_time < end)
    return list(session.scalars(stmt))


def _persist_payment(session: Session, booking: Booking, amount: float, result: PaymentResult) -> Payment:
    payment = Payment(
        booking=booking,
        amount=amount,
        status="confirmed" if result.success else "failed",
        transaction_ref=result.transaction_ref,
    )
    session.add(payment)
    session.flush()
    return payment


def book_seat(
    session: Session,
    *,
    flight_id: int,
    passenger_id: int,
    seat_number: Optional[str] = None,
    amount: float = 0.0,
    payment_fn: Callable[[float, int], PaymentResult] = mock_payment_gateway,
) -> Booking:
    """Reserve a seat and process a payment atomically."""

    with session.begin_nested():
        flight = session.get(Flight, flight_id, with_for_update=True)
        if not flight:
            raise ValueError("flight not found")
        if flight.available_seats <= 0:
            raise ValueError("flight sold out")
        passenger = session.get(Passenger, passenger_id)
        if not passenger:
            raise ValueError("passenger not found")
        chosen_seat = seat_number or SeatAllocator.next_available_seat(
            session, flight_id=flight_id, total_seats=flight.total_seats
        )
        booking = Booking(flight=flight, passenger=passenger, seat_number=chosen_seat)
        session.add(booking)
        try:
            session.flush()
        except IntegrityError as exc:
            raise ValueError("seat already booked") from exc
        payment_result = payment_fn(amount, passenger_id)
        if not payment_result.success:
            raise PaymentDeclinedError(payment_result.message or "payment declined")
        _persist_payment(session, booking, amount, payment_result)
        booking.status = "confirmed"
        flight.available_seats -= 1
        passenger.loyalty_points += int(amount // 10)
    return booking


def cancel_booking(session: Session, *, booking_id: int) -> None:
    with session.begin_nested():
        booking = session.get(Booking, booking_id, with_for_update=True)
        if not booking:
            raise ValueError("booking not found")
        flight = booking.flight
        if booking.status == "cancelled":
            return
        booking.status = "cancelled"
        flight.available_seats += 1


def summarize_capacity(session: Session) -> List[dict]:
    rows = session.execute(
        select(
            Flight.flight_number,
            Flight.origin,
            Flight.destination,
            Flight.available_seats,
            Flight.total_seats,
            func.count(Booking.id).label("bookings"),
        ).outerjoin(Booking)
        .group_by(Flight.id)
    ).all()
    return [
        {
            "flight": row.flight_number,
            "route": f"{row.origin}-{row.destination}",
            "available": row.available_seats,
            "capacity": row.total_seats,
            "bookings": row.bookings,
        }
        for row in rows
    ]
