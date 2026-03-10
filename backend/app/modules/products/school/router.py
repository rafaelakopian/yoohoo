"""Combines all School sub-routers into one APIRouter.

Mounted by the framework under /orgs/{slug}/ via ProductRegistry.
Only product-specific routers — framework routers (collaboration, members,
permissions) are mounted separately by the framework.
"""

from fastapi import APIRouter

from app.modules.products.school.student.router import router as student_router
from app.modules.products.school.attendance.router import router as attendance_router
from app.modules.products.school.schedule.router import router as schedule_router
from app.modules.products.school.notification.router import router as notification_router
from app.modules.products.school.billing.router import router as tuition_router

school_router = APIRouter()
school_router.include_router(student_router)
school_router.include_router(attendance_router)
school_router.include_router(schedule_router)
school_router.include_router(notification_router)
school_router.include_router(tuition_router)
