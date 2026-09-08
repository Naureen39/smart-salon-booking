import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.models.staff_profile import StaffProfile
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.staff_profile import StaffProfileCreate, StaffProfileRead, StaffProfileUpdate

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("", response_model=list[StaffProfileRead])
async def list_staff(db: AsyncSession = Depends(get_db)) -> list[StaffProfile]:
    result = await db.scalars(select(StaffProfile))
    return list(result)


@router.get("/{staff_id}", response_model=StaffProfileRead)
async def get_staff(staff_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> StaffProfile:
    staff = await db.get(StaffProfile, staff_id)
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff profile not found")
    return staff


@router.post("", response_model=StaffProfileRead, status_code=status.HTTP_201_CREATED)
async def create_staff(
    payload: StaffProfileCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> StaffProfile:
    staff = StaffProfile(**payload.model_dump())
    db.add(staff)
    await db.commit()
    await db.refresh(staff)
    return staff


@router.put("/{staff_id}", response_model=StaffProfileRead)
async def update_staff(
    staff_id: uuid.UUID,
    payload: StaffProfileUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> StaffProfile:
    staff = await db.get(StaffProfile, staff_id)
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff profile not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(staff, field, value)

    await db.commit()
    await db.refresh(staff)
    return staff


@router.delete("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff(
    staff_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> None:
    staff = await db.get(StaffProfile, staff_id)
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff profile not found")

    await db.delete(staff)
    await db.commit()
