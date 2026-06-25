"""
aion-mini 全局配置
"""

import json, time, re
from pathlib import Path

# ── 路径 ─────────────────────────────────────────
BASE_DIR = Path(__file__).parent
PUBLIC_DIR = BASE_DIR / "public"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "chat.db"
CHATS_DIR = DATA_DIR / "chats"
CHATS_DIR.mkdir(exist_ok=True)

SETTINGS_PATH = DATA_DIR / "settings.json"
WORLDBOOK_PATH = DATA_DIR / "worldbook.json"
CHAT_STATUS_PATH = DATA_DIR / "chat_status.json"
DIGEST_ANCHOR_PATH = DATA_DIR / "digest_anchor.json"

# ── Settings ─────────────────────────────────────
def load_settings():
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    defaults = {
        "gemini_key": "",
        "siliconflow_key": "",
        "gemini_free_key": "",
        "aipro_key": "",
        "selected_model": "Gemini-3.5-flash",
    }
    save_settings(defaults)
    return defaults

def save_settings(data: dict):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

SETTINGS = load_settings()

def get_key(provider: str) -> str:
    if provider == "gemini":
        return SETTINGS.get("gemini_key", "")
    if provider == "gemini_free":
        return SETTINGS.get("gemini_free_key", "") or SETTINGS.get("gemini_key", "")
    if provider == "aipro":
        return SETTINGS.get("aipro_key", "")
    return SETTINGS.get("siliconflow_key", "")

def get_sentinel_config() -> dict:
    return {
        "api_key": SETTINGS.get("sentinel_key", ""),
        "model": SETTINGS.get("sentinel_model", "gemini-2.0-flash"),
        "base_url": SETTINGS.get("sentinel_base_url", ""),
    }

def get_embedding_config() -> dict:
    base_url = SETTINGS.get("embedding_base_url", "").strip()
    api_key = SETTINGS.get("embedding_api_key", "").strip()
    model = SETTINGS.get("embedding_model", "").strip()
    if base_url and api_key:
        return {
            "base_url": base_url.rstrip("/"),
            "api_key": api_key,
            "model": model or "Qwen/Qwen3-Embedding-8B",
            "use_openai": True,
        }
    return {
        "base_url": "",
        "api_key": get_key("gemini_free"),
        "model": "gemini-embedding-001",
        "use_openai": False,
    }

# ── Worldbook ────────────────────────────────────
def _default_worldbook() -> dict:
    return {
        "ai_persona": "",
        "user_persona": "",
        "system_prompt": "",
        "system_prompt_enabled": True,
        "ai_name": "AI",
        "user_name": "你",
    }

def load_worldbook():
    defaults = _default_worldbook()
    if WORLDBOOK_PATH.exists():
        try:
            data = json.loads(WORLDBOOK_PATH.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                defaults.update(data)
        except:
            pass
    return defaults

def save_worldbook(data: dict):
    WORLDBOOK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

# ── Chat Status ──────────────────────────────────
def load_chat_status() -> dict:
    if CHAT_STATUS_PATH.exists():
        try:
            return json.loads(CHAT_STATUS_PATH.read_text(encoding='utf-8'))
        except:
            pass
    return {"status": "", "updated_at": 0}

def save_chat_status(status: str):
    data = {"status": status, "updated_at": time.time()}
    CHAT_STATUS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

# ── Digest Anchor ────────────────────────────────
def load_digest_anchor() -> float:
    if DIGEST_ANCHOR_PATH.exists():
        try:
            data = json.loads(DIGEST_ANCHOR_PATH.read_text(encoding='utf-8'))
            return float(data.get("last_digest_ts", 0.0))
        except:
            pass
    return 0.0

def save_digest_anchor(ts: float):
    data = {"last_digest_ts": ts, "updated_at": time.time()}
    DIGEST_ANCHOR_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

# ── 姐姐兼容：UPLOADS_DIR / CODEX_UPLOADS_DIR（视觉识别用）───────
UPLOADS_DIR = DATA_DIR / "uploads"
CODEX_UPLOADS_DIR = DATA_DIR / "codex_uploads"
for _d in [UPLOADS_DIR, CODEX_UPLOADS_DIR]:
    _d.mkdir(exist_ok=True)

# ── 模型配置 ─────────────────────────────────────
MODELS = {
    "DeepSeek-V4-Pro":   {"provider": "aipro", "model": "deepseek-v4-pro", "vision": False},
    "DeepSeek-V4-Flash":  {"provider": "aipro", "model": "deepseek-v4-flash", "vision": False},
    "Gemini-3.5-flash":   {"provider": "gemini", "model": "gemini-3.5-flash", "vision": True},
    "Gemini-3.1-pro":     {"provider": "gemini", "model": "gemini-3.1-pro-preview", "vision": True},
    "Kimi-K2.6":          {"provider": "siliconflow", "model": "Pro/moonshotai/Kimi-K2.6", "vision": True},
    "硅基GLM-5.1":        {"provider": "siliconflow", "model": "Pro/zai-org/GLM-5.1", "vision": False},
}

DEFAULT_MODEL = "Gemini-3.5-flash"
