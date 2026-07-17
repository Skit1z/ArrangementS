"""聚合 v1 路由。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admins,
    auth,
    config,
    people,
    semesters,
    timetables,
    vacations,
    venues,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(admins.router)
api_router.include_router(people.router)
api_router.include_router(semesters.router)
api_router.include_router(timetables.router)
api_router.include_router(vacations.router)
api_router.include_router(venues.router)
api_router.include_router(config.router)
