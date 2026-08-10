from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.admin_catalog import router as admin_catalog_router
from app.api.v1.applications import router as applications_router
from app.api.v1.attendance import router as attendance_router
from app.api.v1.auth import router as auth_router
from app.api.v1.auth_mobile import router as auth_mobile_router
from app.api.v1.club import router as club_router
from app.api.v1.club_access import router as club_access_router
from app.api.v1.club_disciplines import router as club_disciplines_router
from app.api.v1.competitions import router as competitions_router
from app.api.v1.disciplines import router as disciplines_router
from app.api.v1.documents import router as documents_router
from app.api.v1.dues import router as dues_router
from app.api.v1.events import router as events_router
from app.api.v1.functions import router as functions_router
from app.api.v1.members import router as members_router
from app.api.v1.push import router as push_router
from app.api.v1.shooting import router as shooting_router
from app.api.v1.shot_entries import router as shot_entries_router
from app.api.v1.sports import router as sports_router
from app.api.v1.stream import router as stream_router
from app.api.v1.sync import router as sync_router
from app.api.v1.target_types import router as target_types_router
from app.api.v1.units import router as units_router

router = APIRouter()

router.include_router(admin_router, prefix="/admin", tags=["admin"])
router.include_router(admin_catalog_router, prefix="/admin/catalog", tags=["admin-catalog"])
router.include_router(applications_router, prefix="/applications", tags=["applications"])
router.include_router(attendance_router, prefix="/attendance", tags=["attendance"])
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(auth_mobile_router, prefix="/auth/mobile", tags=["auth-mobile"])
router.include_router(club_router, prefix="/club", tags=["club"])
router.include_router(club_access_router, prefix="/club/access", tags=["club-access"])
router.include_router(
    club_disciplines_router, prefix="/club-disciplines", tags=["club-disciplines"]
)
router.include_router(competitions_router, prefix="/competitions", tags=["competitions"])
router.include_router(disciplines_router, prefix="/disciplines", tags=["disciplines"])
router.include_router(documents_router, prefix="/documents", tags=["documents"])
router.include_router(dues_router, prefix="/dues", tags=["dues"])
router.include_router(shot_entries_router, prefix="/entries", tags=["entries"])
router.include_router(events_router, prefix="/events", tags=["events"])
router.include_router(functions_router, prefix="/functions", tags=["functions"])
router.include_router(members_router, prefix="/members", tags=["members"])
router.include_router(push_router, prefix="/push", tags=["push"])
router.include_router(shooting_router, prefix="/modules/shooting", tags=["shooting"])
router.include_router(sports_router, prefix="/sports", tags=["sports"])
router.include_router(stream_router, prefix="/stream", tags=["stream"])
router.include_router(sync_router, prefix="/sync", tags=["sync"])
router.include_router(target_types_router, prefix="/target-types", tags=["target-types"])
router.include_router(units_router, prefix="/units", tags=["units"])
