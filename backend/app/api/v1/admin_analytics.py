from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.db.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ping")
async def admin_ping(_user: User = Depends(require_role("staff", "admin"))) -> dict[str, str]:
    """Minimal RBAC-protected route proving the require_role dependency works end to end."""
    return {"message": "admin access granted"}
