"""聊天数据导入工具。

支持多种格式聊天记录导入：
  - JSON: [{"sender":"","content":"","time":""}, ...]
  - TXT:  微信导出格式 "2024-01-01 12:00 张三 消息内容"
  - CSV:  "sender,content,time"
自动检测格式，清洗去重，输出统一 JSON。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path


# ── 格式检测 ──────────────────────────────────────────

def detect_format(filepath: str) -> str:
    """自动检测文件格式。"""
    path = Path(filepath)
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    elif suffix == ".csv":
        return "csv"
    elif suffix == ".txt":
        return "txt"
    else:
        # 根据内容猜测
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(2048)
        if head.strip().startswith("["):
            return "json"
        if "," in head.split("\n")[0]:
            return "csv"
        return "txt"


# ── 各格式解析器 ──────────────────────────────────────

def parse_json(filepath: str) -> list[dict]:
    """解析 JSON 格式。"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        return data.get("messages", data.get("data", []))
    raise ValueError("不支持的 JSON 结构")


def parse_csv(filepath: str) -> list[dict]:
    """解析 CSV 格式。"""
    messages = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            msg = {
                "sender": row.get("sender", row.get("name", row.get("from", ""))),
                "content": row.get("content", row.get("text", row.get("message", ""))),
                "time": row.get("time", row.get("timestamp", row.get("date", ""))),
            }
            if msg["content"]:
                messages.append(msg)
    return messages


# 常见微信导出 TXT 格式：2024-01-01 12:00:00 张三 消息内容
TXT_PATTERN = re.compile(
    r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}[\s]\d{1,2}:\d{2}(?::\d{2})?)\s+"
    r"([^\s]+?)\s+(.+)"
)


def parse_txt(filepath: str) -> list[dict]:
    """解析 TXT 格式（微信导出等）。"""
    messages = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = TXT_PATTERN.match(line)
            if m:
                messages.append({
                    "time": m.group(1).strip(),
                    "sender": m.group(2).strip(),
                    "content": m.group(3).strip(),
                })
            else:
                # 尝试简单分割：时间 + 内容
                messages.append({
                    "time": "",
                    "sender": "",
                    "content": line,
                })
    return messages


# ── 统一入口 ──────────────────────────────────────────

def import_file(filepath: str) -> list[dict]:
    """导入聊天记录文件，自动识别格式。"""
    path = Path(filepath)
    if not path.exists():
        print(f"错误: 文件不存在: {filepath}")
        sys.exit(1)

    fmt = detect_format(filepath)
    parsers = {"json": parse_json, "csv": parse_csv, "txt": parse_txt}
    parser = parsers.get(fmt, parse_txt)

    messages = parser(filepath)
    print(f"检测格式: {fmt.upper()}  |  原始消息: {len(messages)} 条")
    return messages


def normalize(messages: list[dict]) -> list[dict]:
    """统一字段名并规范化时间格式。"""
    normalized = []
    for msg in messages:
        normalized.append({
            "sender": str(msg.get("sender", msg.get("name", ""))),
            "content": str(msg.get("content", msg.get("text", ""))),
            "time": str(msg.get("time", msg.get("timestamp", ""))),
        })
    return normalized


def clean(messages: list[dict]) -> list[dict]:
    """清洗数据：去重、过滤无意义消息。"""
    seen: set[tuple[str, str]] = set()
    cleaned = []

    skip_patterns = [
        r"^<.*>$",        # XML 标签如 <msg><emoji></emoji></msg>
        r"^\[.*\]$",      # 纯系统消息如 [图片] [表情]
        r"^https?://",     # 纯链接
    ]
    skip_re = [re.compile(p) for p in skip_patterns]

    for msg in messages:
        content = msg["content"].strip()
        sender = msg["sender"].strip()

        # 过滤空消息
        if not content or len(content) < 2:
            continue

        # 过滤系统消息
        if any(r.match(content) for r in skip_re):
            continue

        # 去重
        key = (sender, content[:60])
        if key in seen:
            continue
        seen.add(key)

        cleaned.append(msg)

    removed = len(messages) - len(cleaned)
    if removed:
        print(f"清洗后: {len(cleaned)} 条 (移除 {removed} 条)")
    return cleaned


def summary(messages: list[dict]) -> dict:
    """生成导入摘要。"""
    senders = {}
    for msg in messages:
        s = msg["sender"] or "unknown"
        senders[s] = senders.get(s, 0) + 1

    total_chars = sum(len(m["content"]) for m in messages)
    return {
        "total": len(messages),
        "senders": senders,
        "avg_length": round(total_chars / max(len(messages), 1), 1),
        "date_range": _date_range(messages),
    }


def _date_range(messages: list[dict]) -> str:
    """提取时间范围。"""
    times = []
    for m in messages:
        t = m.get("time", "")
        if t and len(t) >= 10:
            times.append(t[:10])
    if times:
        return f"{min(times)} ~ {max(times)}"
    return "未知"


def main():
    parser = argparse.ArgumentParser(description="导入聊天记录 (支持 JSON/CSV/TXT)")
    parser.add_argument("--file", "-f", required=True, help="聊天记录文件路径")
    parser.add_argument("--output", "-o", help="输出路径（默认 data/chat_exports/ 下）")
    parser.add_argument("--no-clean", action="store_true", help="跳过清洗步骤")
    args = parser.parse_args()

    # 导入
    messages = import_file(args.file)
    messages = normalize(messages)

    if not args.no_clean:
        messages = clean(messages)

    # 输出
    output_path = args.output or str(
        Path("data/chat_exports") / f"{Path(args.file).stem}_cleaned.json"
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    # 摘要
    s = summary(messages)
    print(f"\n{'='*40}")
    print(f"导入完成: {output_path}")
    print(f"总消息数: {s['total']}")
    print(f"发言者:   {', '.join(f'{k}({v})' for k, v in s['senders'].items())}")
    print(f"平均长度: {s['avg_length']} 字")
    print(f"时间范围: {s['date_range']}")
    print(f"{'='*40}")
    print("提示: 运行 analyze_profile.py --file <路径> 分析性格特征")


if __name__ == "__main__":
    main()
