from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.auth_mobile import router as auth_mobile_router
from app.api.v1.club import router as club_router
from app.api.v1.competitions import router as competitions_router
from app.api.v1.disciplines import router as disciplines_router
from app.api.v1.dues import router as dues_router
from app.api.v1.events import router as events_router
from app.api.v1.members import router as members_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(auth_mobile_router, prefix="/auth/mobile", tags=["auth-mobile"])
router.include_router(club_router, prefix="/club", tags=["club"])
router.include_router(competitions_router, prefix="/competitions", tags=["competitions"])
router.include_router(disciplines_router, prefix="/disciplines", tags=["disciplines"])
router.include_router(dues_router, prefix="/dues", tags=["dues"])
router.include_router(events_router, prefix="/events", tags=["events"])
router.include_router(members_router, prefix="/members", tags=["members"])
