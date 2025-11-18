"""Minimal PyQt interface for the airline reservation system."""
from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from .services import add_passenger, book_seat, list_available_flights


def launch_ui(session_factory: sessionmaker) -> None:  # pragma: no cover - GUI helper
    try:
        from PyQt6 import QtCore, QtWidgets
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("PyQt6 is required to use the GUI") from exc

    class ReservationWindow(QtWidgets.QWidget):
        def __init__(self, session_factory: sessionmaker):
            super().__init__()
            self.session_factory = session_factory
            self.setWindowTitle("Airline Reservation Demo")
            self.origin = QtWidgets.QLineEdit()
            self.destination = QtWidgets.QLineEdit()
            self.passenger_name = QtWidgets.QLineEdit()
            self.passenger_email = QtWidgets.QLineEdit()
            self.passenger_phone = QtWidgets.QLineEdit()
            self.flight_list = QtWidgets.QListWidget()
            self.status_label = QtWidgets.QLabel("Select a flight and click Book")

            search_btn = QtWidgets.QPushButton("Refresh flights")
            search_btn.clicked.connect(self.refresh_flights)
            book_btn = QtWidgets.QPushButton("Book seat")
            book_btn.clicked.connect(self.book_selected)

            form = QtWidgets.QFormLayout()
            form.addRow("Origin", self.origin)
            form.addRow("Destination", self.destination)
            form.addRow(search_btn)
            form.addRow("Passenger name", self.passenger_name)
            form.addRow("Email", self.passenger_email)
            form.addRow("Phone", self.passenger_phone)
            form.addRow(book_btn)
            layout = QtWidgets.QVBoxLayout()
            layout.addLayout(form)
            layout.addWidget(self.flight_list)
            layout.addWidget(self.status_label)
            self.setLayout(layout)
            self.refresh_flights()

        def refresh_flights(self) -> None:
            self.flight_list.clear()
            with self.session_factory() as session:
                flights = list_available_flights(session)
            for flight in flights:
                label = (
                    f"{flight.flight_number} {flight.origin}->{flight.destination} "
                    f"({flight.available_seats}/{flight.total_seats})"
                )
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.ItemDataRole.UserRole, flight.id)
                self.flight_list.addItem(item)

        def book_selected(self) -> None:
            item = self.flight_list.currentItem()
            if not item:
                self.status_label.setText("Please select a flight")
                return
            first, *last = self.passenger_name.text().split()
            last_name = " ".join(last) if last else "Traveler"
            with self.session_factory() as session:
                passenger = add_passenger(
                    session,
                    first_name=first or "Guest",
                    last_name=last_name,
                    email=self.passenger_email.text() or "guest@example.com",
                    phone=self.passenger_phone.text() or "+1-555-1234",
                )
                try:
                    book_seat(
                        session,
                        flight_id=item.data(QtCore.Qt.ItemDataRole.UserRole),
                        passenger_id=passenger.id,
                        amount=199.0,
                    )
                    session.commit()
                    self.status_label.setText("Booking confirmed")
                except Exception as exc:  # pragma: no cover - GUI feedback
                    session.rollback()
                    self.status_label.setText(str(exc))
            self.refresh_flights()

    app = QtWidgets.QApplication([])
    window = ReservationWindow(session_factory)
    window.show()
    app.exec()
