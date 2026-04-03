from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.club import router as club_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(club_router, prefix="/club", tags=["club"])
