"""
aion-mini — 入口文件
精简版：只保留聊天 + 记忆系统
"""

import asyncio, logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from config import BASE_DIR, PUBLIC_DIR
from database import init_db
from ws import manager
from memory import Memory

memory = Memory()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

# ── 静态文件（public/ 图标资源）──────────────────
app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR)), name="public")

# ── 路由 ─────────────────────────────────────────
from routes import chat, settings, memories

app.include_router(chat.router, tags=["chat"])
app.include_router(settings.router, tags=["settings"])
app.include_router(memories.router, tags=["memories"])

# ── 首页 ─────────────────────────────────────────
@app.get("/")
async def home():
    return FileResponse(str(BASE_DIR / "static" / "home.html"))

@app.get("/chat")
async def chat_page():
    return FileResponse(str(BASE_DIR / "static" / "chat.html"))

# ── WebSocket 路由（复用姐姐的ws连接管理）────────
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(ws)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
