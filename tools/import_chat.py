"""聊天数据导入工具。

支持导入 JSON 格式的聊天记录，提取语言风格特征。
"""

import argparse
import json
import sys
from pathlib import Path


def import_json(filepath: str) -> list[dict]:
    """导入 JSON 格式聊天记录。

    支持的格式：
    - 数组格式: [{"sender": "name", "content": "text", "time": "..."}, ...]
    """
    path = Path(filepath)
    if not path.exists():
        print(f"错误: 文件不存在: {filepath}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        messages = data
    elif isinstance(data, dict):
        messages = data.get("messages", data.get("data", []))
    else:
        print("错误: 不支持的 JSON 格式")
        sys.exit(1)

    print(f"导入 {len(messages)} 条消息")
    return messages


def clean_messages(messages: list[dict]) -> list[dict]:
    """清洗数据：去重、过滤短消息。"""
    seen = set()
    cleaned = []

    for msg in messages:
        content = msg.get("content", "").strip()
        if not content or len(content) < 2:
            continue

        # 去重
        key = (msg.get("sender", ""), content[:50])
        if key in seen:
            continue
        seen.add(key)

        cleaned.append(msg)

    print(f"清洗后: {len(cleaned)} 条消息 (移除 {len(messages) - len(cleaned)} 条)")
    return cleaned


def main():
    parser = argparse.ArgumentParser(description="导入聊天记录")
    parser.add_argument("--file", "-f", required=True, help="聊天记录文件路径")
    parser.add_argument("--output", "-o", help="输出路径（默认覆盖原文件）")
    args = parser.parse_args()

    messages = import_json(args.file)
    messages = clean_messages(messages)

    output_path = args.output or args.file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    print(f"已保存到: {output_path}")
    print("提示: 运行 analyze_profile.py 分析性格特征")


if __name__ == "__main__":
    main()
