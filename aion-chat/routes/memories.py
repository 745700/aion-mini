"""
aion-mini 记忆路由
"""

import json, time
from fastapi import APIRouter, Query
from config import get_embedding_config
from memory import Memory

memory = Memory()
router = APIRouter()

@router.get("/api/memories")
async def list_memories(limit: int = Query(50, ge=1, le=500)):
    async with memory.db as db:
        cur = await db.execute(
            "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

@router.post("/api/memories")
async def add_memory(body: dict):
    content = body.get("content", "").strip()
    if not content:
        return {"error": "content is required"}
    
    now = time.time()
    mem_id = f"mem_{int(now*1000)}"
    vec = await memory.embed(content)
    
    async with memory.db as db:
        await db.execute(
            "INSERT INTO memories (id, content, type, created_at, source_conv, embedding, keywords, importance) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (mem_id, content, body.get("type", "用户录入"), now,
             body.get("source_conv", ""),
             json.dumps(vec.tolist()) if vec is not None else None,
             body.get("keywords", ""), body.get("importance", 0.5))
        )
        await db.commit()
    
    return {"id": mem_id, "content": content, "created_at": now}

@router.delete("/api/memories/{mem_id}")
async def delete_memory(mem_id: str):
    async with memory.db as db:
        await db.execute("DELETE FROM memories WHERE id=?", (mem_id,))
        await db.commit()
    return {"ok": True}

@router.get("/api/memories/search")
async def search_memories(q: str = Query(""), limit: int = Query(10, ge=1, le=50)):
    if not q.strip():
        return []
    results = await memory.recall(q, limit=limit)
    return [{"content": r["content"], "type": r["type"],
             "created_at": r["created_at"], "score": r["score"]} for r in results]
