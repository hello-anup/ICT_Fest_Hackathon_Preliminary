from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _unique_org(prefix: str) -> str:
    return f"{prefix}-{datetime.now().timestamp()}"


def _future(hours: int) -> str:
    return (
        datetime.now(timezone.utc)
        + timedelta(hours=hours)
    ).replace(
        minute=0,
        second=0,
        microsecond=0,
    ).isoformat()


def _register_and_login(
    org_name: str,
    username: str = "alice",
):
    register = client.post(
        "/auth/register",
        json={
            "org_name": org_name,
            "username": username,
            "password": "pw12345",
        },
    )

    assert register.status_code == 201

    login = client.post(
        "/auth/login",
        json={
            "org_name": org_name,
            "username": username,
            "password": "pw12345",
        },
    )

    assert login.status_code == 200

    return login.json()


def test_refresh_token_is_single_use():
    tokens = _register_and_login(
        _unique_org("refresh"),
    )

    refresh_token = tokens["refresh_token"]

    first = client.post(
        "/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert first.status_code == 200
    assert "access_token" in first.json()
    assert "refresh_token" in first.json()

    second = client.post(
        "/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert second.status_code == 401


def test_logout_revokes_access_token():
    tokens = _register_and_login(
        _unique_org("logout"),
    )

    headers = {
        "Authorization": (
            f"Bearer {tokens['access_token']}"
        ),
    }

    before_logout = client.get(
        "/rooms",
        headers=headers,
    )

    assert before_logout.status_code == 200

    logout = client.post(
        "/auth/logout",
        headers=headers,
    )

    assert logout.status_code == 200

    after_logout = client.get(
        "/rooms",
        headers=headers,
    )

    assert after_logout.status_code == 401


def test_room_stats_use_database_state():
    tokens = _register_and_login(
        _unique_org("stats"),
    )

    headers = {
        "Authorization": (
            f"Bearer {tokens['access_token']}"
        ),
    }

    room = client.post(
        "/rooms",
        json={
            "name": "Stats Room",
            "capacity": 4,
            "hourly_rate_cents": 1000,
        },
        headers=headers,
    )

    assert room.status_code == 201

    room_id = room.json()["id"]

    booking = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _future(100),
            "end_time": _future(102),
        },
        headers=headers,
    )

    assert booking.status_code == 201

    stats = client.get(
        f"/rooms/{room_id}/stats",
        headers=headers,
    )

    assert stats.status_code == 200

    body = stats.json()

    assert body["total_confirmed_bookings"] == 1
    assert body["total_revenue_cents"] == 2000


def test_admin_rejects_reversed_date_range():
    tokens = _register_and_login(
        _unique_org("report"),
    )

    headers = {
        "Authorization": (
            f"Bearer {tokens['access_token']}"
        ),
    }

    response = client.get(
        (
            "/admin/usage-report"
            "?from=2026-07-10"
            "&to=2026-07-09"
        ),
        headers=headers,
    )

    assert response.status_code == 400
    assert (
        response.json()["code"]
        == "INVALID_BOOKING_WINDOW"
    )


def test_cross_org_room_access_is_hidden():
    first_tokens = _register_and_login(
        _unique_org("first"),
    )

    first_headers = {
        "Authorization": (
            f"Bearer {first_tokens['access_token']}"
        ),
    }

    room = client.post(
        "/rooms",
        json={
            "name": "Private Room",
            "capacity": 4,
            "hourly_rate_cents": 1000,
        },
        headers=first_headers,
    )

    assert room.status_code == 201

    room_id = room.json()["id"]

    second_tokens = _register_and_login(
        _unique_org("second"),
        username="bob",
    )

    second_headers = {
        "Authorization": (
            f"Bearer {second_tokens['access_token']}"
        ),
    }

    response = client.get(
        f"/rooms/{room_id}/stats",
        headers=second_headers,
    )

    assert response.status_code == 404
    assert (
        response.json()["code"]
        == "ROOM_NOT_FOUND"
    )