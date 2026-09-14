"""Seeds a fresh dev database with the minimum data needed to actually use the
booking flow: one location, one staff member (bookable every weekday), a
starter service menu, and an admin login.

There's no earlier version of this script; the admin/staff accounts and
service menu used in prior manual testing were created ad hoc through the
admin API and lived only in that dev database's data, not in the repo. A
Docker volume reset (or a fresh clone) starts with zero services and zero
staff, so the chat's booking flow has nothing to ever offer, "couldn't find a
service" for even a real, correctly-spelled name is the expected result on an
unseeded database, not a bug in the booking code itself.

Usage:
    python -m scripts.seed_demo_data
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.location import Location
from app.db.models.service import Service
from app.db.models.staff_profile import StaffProfile
from app.db.models.user import User
from app.db.session import async_session_factory

ADMIN_EMAIL = "admin@glowdesk.example"
ADMIN_PASSWORD = "AdminPass123!"
STYLIST_EMAIL = "stylist@glowdesk.example"
STYLIST_PASSWORD = "StylistPass123!"

WORKING_HOURS = {day: ["09:00-17:00"] for day in ("mon", "tue", "wed", "thu", "fri", "sat")}

SERVICES = [
    ("Haircut", "hair", 30, 4500),
    ("Gel Manicure", "nails", 45, 5500),
    ("Classic Manicure", "nails", 30, 3500),
    ("Pedicure", "nails", 45, 6000),
    ("Facial", "skincare", 60, 8500),
    ("Full Body Massage", "spa", 60, 9500),
]


async def _get_or_create_user(
    db: AsyncSession, *, email: str, password: str, full_name: str, role: str
) -> User:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        return existing
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


async def seed() -> dict[str, int]:
    async with async_session_factory() as db:
        await _get_or_create_user(db, email=ADMIN_EMAIL, password=ADMIN_PASSWORD, full_name="Admin", role="admin")
        stylist_user = await _get_or_create_user(
            db, email=STYLIST_EMAIL, password=STYLIST_PASSWORD, full_name="Stylist", role="staff"
        )

        location = await db.scalar(select(Location).where(Location.name == "Main Branch"))
        if location is None:
            location = Location(name="Main Branch", timezone="UTC")
            db.add(location)
            await db.flush()

        staff = await db.scalar(select(StaffProfile).where(StaffProfile.user_id == stylist_user.id))
        if staff is None:
            staff = StaffProfile(
                user_id=stylist_user.id,
                location_id=location.id,
                title="Senior Stylist",
                working_hours=WORKING_HOURS,
            )
            db.add(staff)

        services_created = 0
        for name, category, duration_minutes, price_cents in SERVICES:
            existing_service = await db.scalar(select(Service).where(Service.name == name))
            if existing_service is not None:
                continue
            db.add(
                Service(
                    name=name,
                    category=category,
                    duration_minutes=duration_minutes,
                    price_cents=price_cents,
                )
            )
            services_created += 1

        await db.commit()
        return {"services_created": services_created}


def main() -> None:
    result = asyncio.run(seed())
    print(f"Seeded demo data. New services created: {result['services_created']}.")
    print(f"Admin login: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"Staff login: {STYLIST_EMAIL} / {STYLIST_PASSWORD}")


if __name__ == "__main__":
    main()
