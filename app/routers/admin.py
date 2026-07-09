"""Administrative reporting and export endpoints."""

from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..errors import AppError
from ..models import Booking, Room, User
from ..services.export import generate_export


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.get("/usage-report")
def usage_report(
    frm: str = Query(..., alias="from"),
    to: str = Query(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        from_date = datetime.strptime(
            frm,
            "%Y-%m-%d",
        ).date()

        to_date = datetime.strptime(
            to,
            "%Y-%m-%d",
        ).date()

    except ValueError:
        raise AppError(
            400,
            "INVALID_BOOKING_WINDOW",
            "Invalid date range",
        )

    if from_date > to_date:
        raise AppError(
            400,
            "INVALID_BOOKING_WINDOW",
            "'from' date must be before or equal to 'to' date",
        )

    start = datetime.combine(
        from_date,
        time.min,
        tzinfo=timezone.utc,
    ).replace(
        tzinfo=None,
    )

    end = datetime.combine(
        to_date + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc,
    ).replace(
        tzinfo=None,
    )

    rooms = (
        db.query(Room)
        .filter(
            Room.org_id == admin.org_id,
        )
        .order_by(
            Room.id.asc(),
        )
        .all()
    )

    result_rooms = []

    for room in rooms:
        bookings = (
            db.query(Booking)
            .filter(
                Booking.room_id == room.id,
                Booking.status == "confirmed",
                Booking.start_time >= start,
                Booking.start_time < end,
            )
            .all()
        )

        result_rooms.append(
            {
                "room_id": room.id,
                "room_name": room.name,
                "confirmed_bookings": len(bookings),
                "revenue_cents": sum(
                    booking.price_cents
                    for booking in bookings
                ),
            }
        )

    return {
        "from": frm,
        "to": to,
        "rooms": result_rooms,
    }


@router.get("/export")
def export(
    room_id: int | None = Query(None),
    include_all: bool = Query(False),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if room_id is not None:
        room = (
            db.query(Room)
            .filter(
                Room.id == room_id,
                Room.org_id == admin.org_id,
            )
            .first()
        )

        if room is None:
            raise AppError(
                404,
                "ROOM_NOT_FOUND",
                "Room not found",
            )

    csv_body = generate_export(
        db,
        admin.org_id,
        admin.id,
        room_id,
        include_all,
    )

    return Response(
        content=csv_body,
        media_type="text/csv",
    )