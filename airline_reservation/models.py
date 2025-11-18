"""SQLAlchemy models for the airline reservation system."""
from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Flight(Base):
    __tablename__ = "flights"
    __table_args__ = (
        UniqueConstraint("flight_number", name="uq_flight_number"),
        CheckConstraint("total_seats > 0", name="ck_total_seats_positive"),
        CheckConstraint("available_seats >= 0", name="ck_available_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    flight_number: Mapped[str] = mapped_column(String(8), nullable=False)
    origin: Mapped[str] = mapped_column(String(3), nullable=False)
    destination: Mapped[str] = mapped_column(String(3), nullable=False)
    departure_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    arrival_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    aircraft_type: Mapped[str] = mapped_column(String(20), nullable=False)
    total_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    available_seats: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)

    bookings: Mapped[List["Booking"]] = relationship(back_populates="flight", cascade="all, delete-orphan")


class Passenger(Base):
    __tablename__ = "passengers"
    __table_args__ = (UniqueConstraint("email", name="uq_passenger_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    bookings: Mapped[List["Booking"]] = relationship(back_populates="passenger", cascade="all, delete-orphan")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("flight_id", "seat_number", name="uq_flight_seat"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    flight_id: Mapped[int] = mapped_column(ForeignKey("flights.id", ondelete="CASCADE"))
    passenger_id: Mapped[int] = mapped_column(ForeignKey("passengers.id", ondelete="CASCADE"))
    seat_number: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    flight: Mapped[Flight] = relationship(back_populates="bookings")
    passenger: Mapped[Passenger] = relationship(back_populates="bookings")
    payment: Mapped["Payment"] = relationship(back_populates="booking", uselist=False, cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(Enum("pending", "confirmed", "failed", name="payment_status"), default="pending")
    transaction_ref: Mapped[str] = mapped_column(String(30), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    booking: Mapped[Booking] = relationship(back_populates="payment")
