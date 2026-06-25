"""
aion-mini 聊天路由 — 精简版
只保留：对话 CRUD、消息收发、AI 回复流
"""

import json, time, asyncio
from datetime import datetime
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from typing import Optional

from config import DEFAULT_MODEL, load_worldbook, MODELS
from database import get_db
from ws import manager
from ai_providers import stream_ai
from memory import recall_memories, instant_digest, get_embedding, _pack_embedding

router = APIRouter()

# ── 对话 CRUD ─────────────────────────────────────
@router.get("/api/conversations")
async def list_conversations():
    async with get_db() as db:
        cur = await db.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conv_id = c.id AND m.role IN ('user','assistant')) AS message_count "
            "FROM conversations c ORDER BY c.updated_at DESC"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

@router.post("/api/conversations")
async def create_conversation(body: dict):
    now = time.time()
    conv_id = f"conv_{int(now*1000)}"
    title = body.get("title", "新对话")
    model = body.get("model", DEFAULT_MODEL)
    async with get_db() as db:
        await db.execute(
            "INSERT INTO conversations (id, title, model, created_at, updated_at) VALUES (?,?,?,?,?)",
            (conv_id, title, model, now, now)
        )
        await db.commit()
    conv = {"id": conv_id, "title": title, "model": model, "created_at": now, "updated_at": now}
    await manager.broadcast({"type": "conv_created", "data": conv})
    return conv

@router.put("/api/conversations/{conv_id}")
async def update_conversation(conv_id: str, body: dict):
    async with get_db() as db:
        if body.get("title") is not None:
            await db.execute("UPDATE conversations SET title=?, updated_at=? WHERE id=?",
                             (body["title"], time.time(), conv_id))
        if body.get("model") is not None:
            await db.execute("UPDATE conversations SET model=?, updated_at=? WHERE id=?",
                             (body["model"], time.time(), conv_id))
        await db.commit()
    await manager.broadcast({"type": "conv_updated", "data": {"id": conv_id, **body}})
    return {"ok": True}

@router.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    async with get_db() as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
        await db.commit()
    await manager.broadcast({"type": "conv_deleted", "data": {"id": conv_id}})
    return {"ok": True}

# ── 消息 CRUD ─────────────────────────────────────
@router.get("/api/conversations/{conv_id}/messages")
async def list_messages(conv_id: str, limit: int = Query(50, ge=1, le=500), before: Optional[float] = None):
    async with get_db() as db:
        if before:
            cur = await db.execute(
                "SELECT * FROM messages WHERE conv_id=? AND created_at<? ORDER BY created_at DESC LIMIT ?",
                (conv_id, before, limit)
            )
        else:
            cur = await db.execute(
                "SELECT * FROM messages WHERE conv_id=? ORDER BY created_at DESC LIMIT ?",
                (conv_id, limit)
            )
        rows = list(reversed(await cur.fetchall()))
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["attachments"] = json.loads(d.get("attachments") or "[]")
            except:
                d["attachments"] = []
            d["starred"] = d.get("starred") or 0
            result.append(d)
        return result

@router.post("/api/conversations/{conv_id}/send")
async def send_message(conv_id: str, body: dict):
    """发送消息 + AI 流式回复（SSE）"""
    client_id = body.get("client_id", "")
    if client_id:
        manager.set_last_sender(client_id)

    now = time.time()
    msg_id = f"msg_{int(now*1000)}"
    content = body.get("content", "")
    attachments = body.get("attachments", [])
    context_limit = body.get("context_limit", 20)
    temperature = body.get("temperature")
    max_tokens = body.get("max_tokens")

    att_json = json.dumps(attachments, ensure_ascii=False)
    async with get_db() as db:
        await db.execute(
            "INSERT INTO messages (id, conv_id, role, content, created_at, attachments) VALUES (?,?,?,?,?,?)",
            (msg_id, conv_id, "user", content, now, att_json)
        )
        await db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conv_id))
        await db.commit()

    user_msg = {"id": msg_id, "conv_id": conv_id, "role": "user",
                "content": content, "created_at": now, "attachments": attachments}
    await manager.broadcast({"type": "msg_created", "data": user_msg})

    # 获取模型
    async with get_db() as db:
        cur = await db.execute("SELECT model FROM conversations WHERE id=?", (conv_id,))
        row = await cur.fetchone()
        model_key = row["model"] if row else DEFAULT_MODEL

    wb = load_worldbook()
    ai_name = wb.get("ai_name", "AI")
    user_name = wb.get("user_name", "用户")

    # 构建历史上下文
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM messages WHERE conv_id=? ORDER BY created_at DESC LIMIT ?",
            (conv_id, context_limit * 2)
        )
        history_rows = list(reversed(await cur.fetchall()))

    history = []
    for r in history_rows:
        d = dict(r)
        try:
            d["attachments"] = json.loads(d.get("attachments") or "[]")
        except:
            d["attachments"] = []
        history.append({"role": d["role"], "content": d["content"]})

    # 注入人设
    prefix = []
    if wb.get("ai_persona"):
        prefix.append({"role": "user", "content": f"[{ai_name}人设]\n{wb['ai_persona']}"})
        prefix.append({"role": "assistant", "content": "收到。"})
    if wb.get("user_persona"):
        prefix.append({"role": "user", "content": f"[{user_name}信息]\n{wb['user_persona']}"})
        prefix.append({"role": "assistant", "content": "收到。"})
    if prefix:
        history = prefix + history

    # 记忆召回
    recent = [m for m in history if m["role"] in ("user", "assistant")][-3:]
    digest = await instant_digest(recent)
    keywords = digest.get("keywords", [])
    topic = digest.get("topic", "")
    recalled = []
    if topic:
        query = f"{topic} {' '.join(keywords)}"
        recalled, _ = await recall_memories(query, query_keywords=keywords)
    if recalled:
        mem_lines = "\n".join([f"- {m['content']}" for m in recalled[:5]])
        history.append({"role": "user", "content": f"[相关记忆]\n{mem_lines}"})
        history.append({"role": "assistant", "content": "收到，我会参考这些记忆。"}) if False else None

    # 当前时间
    now_str = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    history.append({"role": "user", "content": f"系统时间：{now_str}"})

    ai_msg_id = f"msg_{int(time.time()*1000)}"
    usage_meta = {}
    q: asyncio.Queue = asyncio.Queue()
    cancel_event = asyncio.Event()
    active_generations = {conv_id: cancel_event}

    async def bg():
        full_text = ""
        has_error = False
        try:
            await q.put({"id": ai_msg_id, "type": "start"})
            async for chunk in stream_ai(history, model_key, usage_meta,
                                          max_tokens=max_tokens, cancel_event=cancel_event):
                full_text += chunk
                await q.put({"type": "chunk", "content": chunk})

        except Exception as e:
            has_error = True
            err = f"\n[错误: {e}]"
            full_text += err
            await q.put({"type": "chunk", "content": err})

        stripped = full_text.strip()
        if stripped.startswith("[错误]") or not stripped:
            has_error = True

        # 记忆录入
        for m in recall_memories._MEMORY_PAT.findall(full_text) if hasattr(recall_memories, '_MEMORY_PAT') else []:
            pass  # 简化版不处理

        att_json2 = "[]"
        now2 = time.time()
        async with get_db() as db:
            await db.execute(
                "INSERT INTO messages (id, conv_id, role, content, created_at, attachments) VALUES (?,?,?,?,?,?)",
                (ai_msg_id, conv_id, "assistant", full_text, now2, att_json2)
            )
            await db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now2, conv_id))
            await db.commit()

        ai_msg = {"id": ai_msg_id, "conv_id": conv_id, "role": "assistant",
                  "content": full_text, "created_at": now2, "attachments": []}
        await manager.broadcast({"type": "msg_created", "data": ai_msg})
        await q.put({"type": "debug", "data": {
            "model": model_key, "usage": usage_meta if usage_meta else None,
            "has_error": has_error
        }})
        await q.put({"type": "done"})

    asyncio.create_task(bg())

    async def gen():
        while True:
            data = await q.get()
            if data.get("type") == "done":
                break
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")

# ── 中止生成 ─────────────────────────────────────
@router.post("/api/conversations/{conv_id}/abort")
async def abort(conv_id: str):
    return {"ok": True}

# ── 消息编辑重发 ─────────────────────────────────
@router.put("/api/messages/{msg_id}")
async def update_message(msg_id: str, body: dict):
    async with get_db() as db:
        await db.execute("UPDATE messages SET content=? WHERE id=?", (body.get("content", ""), msg_id))
        await db.commit()
        cur = await db.execute("SELECT * FROM messages WHERE id=?", (msg_id,))
        msg = await cur.fetchone()
        if msg:
            d = dict(msg)
            try: d["attachments"] = json.loads(d.get("attachments") or "[]")
            except: d["attachments"] = []
            await manager.broadcast({"type": "msg_updated", "data": d})
    return {"ok": True}

@router.delete("/api/messages/{msg_id}")
async def delete_message(msg_id: str):
    async with get_db() as db:
        await db.execute("DELETE FROM messages WHERE id=?", (msg_id,))
        await db.commit()
    await manager.broadcast({"type": "msg_deleted", "data": {"id": msg_id}})
    return {"ok": True}

# ── 导出对话 ─────────────────────────────────────
@router.get("/api/conversations/{conv_id}/export")
async def export_conversation(conv_id: str):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM messages WHERE conv_id=? ORDER BY created_at", (conv_id,))
        msgs = await cur.fetchall()
    return [{"id": m["id"], "role": m["role"], "content": m["content"],
             "created_at": m["created_at"]} for m in msgs]
