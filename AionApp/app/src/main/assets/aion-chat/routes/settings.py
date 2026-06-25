"""
aion-mini 设置路由
"""

import json
from fastapi import APIRouter
from config import SETTINGS, SETTINGS_PATH, save_settings, load_worldbook, save_worldbook

router = APIRouter()

@router.get("/api/settings")
async def get_settings():
    return SETTINGS

@router.put("/api/settings")
async def update_settings(body: dict):
    for k, v in body.items():
        SETTINGS[k] = v
    save_settings(SETTINGS)
    return SETTINGS

@router.get("/api/worldbook")
async def get_worldbook():
    return load_worldbook()

@router.put("/api/worldbook")
async def update_worldbook(body: dict):
    save_worldbook(body)
    return body

@router.get("/api/models")
async def list_models():
    from config import MODELS
    return MODELS
