"""Web 管理界面 — FastAPI 后端。

提供机器人的状态监控、配置编辑、日志查看等功能。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import shutil
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
import tomllib

app = FastAPI(title="Human-like Chatbot 管理界面")

# ── 工具函数 ──────────────────────────────────────

CONFIG_PATH = Path("configs/default.toml")
CHROMA_PATH = Path("data/chroma_db")
PROFILES_DIR = Path("data/profiles")
CHAT_EXPORTS_DIR = Path("data/chat_exports")


def _read_file(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _load_toml_config() -> dict:
    """加载当前 TOML 配置。"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    return {}


def _save_toml_config(content: str) -> bool:
    """保存 TOML 配置。"""
    try:
        CONFIG_PATH.write_text(content, encoding="utf-8")
        return True
    except OSError:
        return False


def _get_sleep_state() -> str:
    """根据当前时间获取睡眠状态（简化版，不依赖 scheduler）。"""
    hour = datetime.now().hour
    if 8 <= hour < 22:
        return "活跃"
    elif 22 <= hour < 23:
        return "犯困"
    elif 23 <= hour or hour < 1:
        return "浅睡"
    elif 1 <= hour < 6:
        return "深睡"
    else:
        return "刚醒"


# ── API 路由 ──────────────────────────────────────

@app.get("/api/status")
async def get_status():
    """获取机器人运行状态。"""
    return {
        "name": "小夜",
        "online": True,
        "sleep_state": _get_sleep_state(),
        "mood": "happy",
        "platform": "QQ",
        "uptime": "运行中",
        "version": "0.1.0",
    }


@app.get("/api/config")
async def get_config():
    """获取当前配置。"""
    raw = _read_file(CONFIG_PATH)
    parsed = _load_toml_config()
    return {"raw": raw, "parsed": parsed}


@app.post("/api/config")
async def save_config(data: dict):
    """保存配置。"""
    content = data.get("content", "")
    if not content.strip():
        raise HTTPException(400, "配置内容不能为空")
    ok = _save_toml_config(content)
    return {"success": ok, "message": "配置已保存" if ok else "保存失败"}


@app.get("/api/stats")
async def get_stats():
    """获取用量统计。"""
    # 从成长引擎读取
    growth_stats = {}
    stats_path = PROFILES_DIR / "growth_stats.json"
    if stats_path.exists():
        try:
            growth_stats = json.loads(stats_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # ChromaDB 大小
    chroma_size = 0
    if CHROMA_PATH.exists():
        for f in CHROMA_PATH.rglob("*"):
            if f.is_file():
                chroma_size += f.stat().st_size

    return {
        "total_turns": growth_stats.get("total_turns", 0),
        "unique_users": len(growth_stats.get("unique_users", [])),
        "vocabulary_size": growth_stats.get("vocabulary_size", 0),
        "chroma_db_size_mb": round(chroma_size / 1024 / 1024, 1),
        "last_update": growth_stats.get("last_update", "未知"),
    }


@app.get("/api/tone_lexicon")
async def get_tone_lexicon():
    """获取学习到的词汇。"""
    path = PROFILES_DIR / "tone_lexicon.json"
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    # 按频率排序取前 50
    sorted_items = sorted(data.items(), key=lambda x: -x[1])[:50]
    return {"lexicon": [{"word": w, "count": c} for w, c in sorted_items]}


@app.get("/api/logs")
async def get_logs(lines: int = 50):
    """获取最近日志。"""
    # 尝试从不同位置读取日志
    log_candidates = [
        Path("data/logs/latest.log"),
        Path("logs/latest.log"),
    ]
    for log_path in log_candidates:
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8", errors="ignore")
            log_lines = content.strip().split("\n")[-lines:]
            return {"logs": log_lines}
    return {"logs": ["日志文件未找到"]}


@app.get("/api/chat_exports")
async def list_chat_exports():
    """列出已导入的聊天记录。"""
    files = []
    if CHAT_EXPORTS_DIR.exists():
        for f in sorted(CHAT_EXPORTS_DIR.glob("*_cleaned.json")):
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    return {"files": files}


@app.get("/api/chat_exports/{filename}")
async def get_chat_export(filename: str):
    """获取某份聊天记录内容。"""
    path = CHAT_EXPORTS_DIR / filename
    if not path.exists():
        raise HTTPException(404, "文件不存在")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"messages": data[:100], "total": len(data)}  # 只返回前 100 条


@app.post("/api/chat_import")
async def import_chat_file(file: UploadFile = File(...)):
    """上传并导入聊天记录文件。"""
    # 验证格式
    if not file.filename or not file.filename.endswith((".json", ".csv", ".txt")):
        raise HTTPException(400, "仅支持 .json / .csv / .txt 格式")

    # 保存上传文件
    CHAT_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    save_path = CHAT_EXPORTS_DIR / file.filename
    try:
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except OSError as e:
        raise HTTPException(500, f"文件保存失败: {e}")

    # 调用导入管线
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from tools.import_chat import import_file, normalize, clean, summary

        messages = import_file(str(save_path))
        messages = normalize(messages)
        messages = clean(messages)

        # 保存清洗后的文件
        cleaned_path = CHAT_EXPORTS_DIR / f"{Path(file.filename).stem}_cleaned.json"
        import json as _json
        with open(cleaned_path, "w", encoding="utf-8") as f:
            _json.dump(messages, f, ensure_ascii=False, indent=2)

        s = summary(messages)
        return {
            "success": True,
            "filename": cleaned_path.name,
            "summary": s,
            "message": f"导入 {s['total']} 条消息，来自 {len(s['senders'])} 个发言者",
        }
    except Exception as e:
        raise HTTPException(500, f"导入失败: {e}")


# ── 页面路由 ──────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """返回管理界面首页。"""
    html_path = Path(__file__).parent / "templates" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>index.html 未找到</h1>", status_code=404)


async def start_web_async(host: str = "127.0.0.1", port: int = 8080):
    """以 asyncio 任务方式启动 Web 服务器（与机器人共用事件循环）。"""
    import uvicorn
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    print(f"Web 管理界面: http://{host}:{port}")
    await server.serve()


if __name__ == "__main__":
    import asyncio
    asyncio.run(start_web_async())
