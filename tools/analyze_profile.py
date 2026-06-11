"""性格特征分析工具。

从聊天记录中深度分析语言风格特征，生成可配置的 TOML 配置。
支持导出到 configs/ 目录供人格引擎直接加载。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


# ── 基础分析 ──────────────────────────────────────────

def analyze_sentiment(messages: list[dict]) -> dict:
    """分析情感倾向。"""
    positive_words = {"开心", "高兴", "喜欢", "太好了", "棒", "谢谢", "哈哈", "不错", "厉害", "爱了"}
    negative_words = {"难过", "生气", "讨厌", "烦", "伤心", "郁闷", "烦死了", "无聊", "无语"}

    pos_count = neg_count = total = 0
    for msg in messages:
        content = msg.get("content", "")
        if any(w in content for w in positive_words):
            pos_count += 1
            total += 1
        elif any(w in content for w in negative_words):
            neg_count += 1
            total += 1

    return {
        "positive_ratio": round(pos_count / max(total, 1), 2),
        "negative_ratio": round(neg_count / max(total, 1), 2),
    }


def analyze_formality(messages: list[dict]) -> float:
    """分析正式程度 (0.0=随意, 1.0=正式)。"""
    formal_markers = {"您好", "请问", "感谢", "抱歉", "不好意思", "麻烦", "您"}
    casual_markers = {"哈哈", "嘿嘿", "嗯嗯", "好的呀", "好嘞", "哦哦", "嗨", "呗", "啦", "咯"}

    formal = casual = 0
    for msg in messages:
        content = msg.get("content", "")
        if any(m in content for m in formal_markers):
            formal += 1
        if any(m in content for m in casual_markers):
            casual += 1

    total = formal + casual
    return round(formal / max(total, 1), 2)


def analyze_humor(messages: list[dict]) -> float:
    """分析幽默感。"""
    markers = {"哈哈", "呵呵", "开玩笑", "搞笑", "逗", "笑死", "哈哈哈", "笑不活", "整活"}
    count = sum(1 for msg in messages if any(m in msg.get("content", "") for m in markers))
    return round(min(count / max(len(messages), 1) * 8, 1.0), 2)


def analyze_curiosity(messages: list[dict]) -> float:
    """分析好奇心（提问频率）。"""
    q_count = sum(1 for msg in messages if "?" in msg.get("content", "") or "?" in msg.get("content", ""))
    return round(min(q_count / max(len(messages), 1) * 5, 1.0), 2)


def analyze_topic_preferences(messages: list[dict]) -> dict:
    """分析话题偏好。"""
    topics = {
        "technology": {"代码", "编程", "电脑", "手机", "软件", "AI", "科技", "互联网", "程序"},
        "entertainment": {"电影", "音乐", "游戏", "动漫", "综艺", "明星", "番", "追"},
        "daily_life": {"吃饭", "睡觉", "上班", "下班", "今天", "昨天", "明天", "出去"},
        "science": {"科学", "物理", "化学", "生物", "数学", "研究", "实验"},
        "philosophy": {"人生", "意义", "哲学", "思考", "为什么", "活着"},
    }
    scores = {}
    for topic, keywords in topics.items():
        count = sum(1 for msg in messages if any(k in msg.get("content", "") for k in keywords))
        scores[topic] = round(min(count / max(len(messages), 1) * 10, 1.0), 2)
    return scores


def analyze_emoji_usage(messages: list[dict]) -> tuple[bool, float]:
    """分析 emoji 使用频率。"""
    pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0\U000024C2-\U0001F251]"
    )
    count = sum(1 for msg in messages if pattern.search(msg.get("content", "")))
    ratio = count / max(len(messages), 1)
    return ratio > 0.08, round(ratio, 3)


# ── 深度分析（新增） ───────────────────────────────

def extract_top_words(messages: list[dict], sender: str | None = None, top_n: int = 20) -> list[tuple[str, int]]:
    """提取高频词（排除常见停用词）。"""
    stop_words = {"的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一",
                  "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
                  "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "什么"}
    words: list[str] = []
    for msg in messages:
        if sender and msg.get("sender") != sender:
            continue
        text = msg.get("content", "")
        # 中文分词简化版：按字符取2-4字词组
        chars = list(text)
        for i in range(len(chars) - 1):
            bigram = "".join(chars[i:i+2])
            if bigram.strip() and bigram not in stop_words and len(bigram) >= 2:
                words.append(bigram)
    return Counter(words).most_common(top_n)


def analyze_sentence_length(messages: list[dict], sender: str | None = None) -> dict:
    """分析句子长度分布。"""
    lengths = []
    for msg in messages:
        if sender and msg.get("sender") != sender:
            continue
        lengths.append(len(msg.get("content", "")))
    if not lengths:
        return {"avg": 0, "min": 0, "max": 0, "median": 0}
    sorted_l = sorted(lengths)
    return {
        "avg": round(sum(lengths) / len(lengths), 1),
        "min": min(lengths),
        "max": max(lengths),
        "median": sorted_l[len(sorted_l) // 2],
    }


def analyze_punctuation(messages: list[dict], sender: str | None = None) -> dict:
    """分析标点使用习惯。"""
    counts: dict[str, int] = Counter()
    for msg in messages:
        if sender and msg.get("sender") != sender:
            continue
        for ch in msg.get("content", ""):
            if ch in "。！？，、；：…～~.":
                counts[ch] += 1
    total = sum(counts.values()) or 1
    return {k: round(v / total, 3) for k, v in counts.most_common()}


def analyze_active_hours(messages: list[dict], sender: str | None = None) -> dict[str, int]:
    """分析活跃时段分布。"""
    hour_counts: dict[str, int] = {str(h): 0 for h in range(24)}
    for msg in messages:
        if sender and msg.get("sender") != sender:
            continue
        t = msg.get("time", "")
        if len(t) >= 16:
            try:
                h = int(t[11:13])
                hour_counts[str(h)] += 1
            except (ValueError, IndexError):
                pass
    return hour_counts


# ── 配置生成 ──────────────────────────────────────────

def build_profile(messages: list[dict], target_sender: str | None = None) -> dict:
    """构建完整的性格特征配置。"""
    sender_msgs = messages
    if target_sender:
        sender_msgs = [m for m in messages if m.get("sender") == target_sender]
        if not sender_msgs:
            print(f"警告: 未找到发送者 [{target_sender}]，使用全部数据")
            sender_msgs = messages

    sentiment = analyze_sentiment(sender_msgs)
    topics = analyze_topic_preferences(sender_msgs)
    formality = analyze_formality(sender_msgs)
    emoji_enabled, emoji_ratio = analyze_emoji_usage(sender_msgs)
    sent_len = analyze_sentence_length(sender_msgs)
    top_words = extract_top_words(sender_msgs, top_n=10)
    punct = analyze_punctuation(sender_msgs)
    hours = analyze_active_hours(sender_msgs)

    # 推断活跃时段
    active_slots = sorted(
        [(int(h), c) for h, c in hours.items() if c > 0],
        key=lambda x: -x[1],
    )
    typical_hour = active_slots[0][0] if active_slots else 12
    is_night_owl = typical_hour >= 22 or typical_hour <= 4

    profile = {
        "name": target_sender or "分析生成的角色",
        "description": f"基于{len(sender_msgs)}条聊天记录自动分析的性格",
        "traits": {
            "openness": round(0.5 + analyze_curiosity(sender_msgs) * 0.3, 2),
            "humor": analyze_humor(sender_msgs),
            "directness": round(0.4 + random_offset(), 2),
            "empathy": max(0.3, sentiment.get("positive_ratio", 0.5)),
            "curiosity": analyze_curiosity(sender_msgs),
            "formality": formality,
            "optimism": max(0.3, sentiment.get("positive_ratio", 0.5)),
        },
        "language": {
            "style": "casual" if formality < 0.5 else "witty" if analyze_humor(sender_msgs) > 0.4 else "formal",
            "emojis_enabled": emoji_enabled,
        },
        "interests": topics,
        "_analysis": {  # 详细分析数据（不写入 TOML，仅参考）
            "total_messages": len(sender_msgs),
            "avg_length": sent_len["avg"],
            "top_words": [w for w, _ in top_words[:10]],
            "typical_hour": typical_hour,
            "is_night_owl": is_night_owl,
            "emoji_ratio": emoji_ratio,
        },
    }
    return profile


def random_offset() -> float:
    """小随机偏移，避免生成完全相同的结果。"""
    import random
    return round(random.uniform(-0.1, 0.1), 2)


def export_toml(profile: dict, output_path: str) -> None:
    """导出为 TOML 配置文件。"""
    t = profile["traits"]
    lang = profile["language"]
    interests = profile["interests"]

    toml = f"""# 由 analyze_profile.py 自动生成
# 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}

[personality]
name = "{profile['name']}"
description = "{profile['description']}"

[personality.traits]
openness = {t['openness']}
humor = {t['humor']}
directness = {t['directness']}
empathy = {t['empathy']}
curiosity = {t['curiosity']}
formality = {t['formality']}
optimism = {t['optimism']}

[personality.mood]
initial = "neutral"
volatility = 0.3

[personality.interests]
"""
    for k, v in interests.items():
        toml += f"{k} = {v}\n"

    toml += f"""
[personality.language]
style = "{lang['style']}"
emojis_enabled = {"true" if lang['emojis_enabled'] else "false"}
typo_frequency = 0.05
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(toml)
    print(f"TOML 配置已导出: {output_path}")


# ── 主入口 ────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="分析聊天记录性格特征")
    parser.add_argument("--file", "-f", required=True, help="清洗后的聊天记录 JSON 路径")
    parser.add_argument("--sender", "-s", help="目标说话者（留空则分析全部）")
    parser.add_argument("--output-json", help="输出 JSON 路径")
    parser.add_argument("--output-toml", help="输出 TOML 配置路径（直接用于项目）")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"错误: 文件不存在: {args.file}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        messages = json.load(f)

    if not messages:
        print("错误: 无消息数据")
        sys.exit(1)

    print(f"分析 {len(messages)} 条消息" + (f" (目标: {args.sender})" if args.sender else ""))

    profile = build_profile(messages, target_sender=args.sender)

    # 输出 JSON
    json_path = args.output_json or str(path.with_name(f"{path.stem}_profile.json"))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    # 输出 TOML
    if args.output_toml:
        export_toml(profile, args.output_toml)

    # 报告
    a = profile["_analysis"]
    print(f"\n{'='*40}")
    print(f"分析完成: {json_path}")
    print(f"{'='*40}")
    print(f"目标对象:  {profile['name']}")
    print(f"消息数量:  {a['total_messages']}")
    print(f"平均句长:  {a['avg_length']} 字")
    print(f"高频词:    {' '.join(a['top_words'][:8])}")
    print(f"活跃时段:  {a['typical_hour']} 点左右")
    print(f"夜猫子:    {'是' if a['is_night_owl'] else '否'}")
    print(f"\n性格参数:")
    for k, v in profile["traits"].items():
        bar = "█" * int(v * 10) + "░" * (10 - int(v * 10))
        print(f"  {k:12s} {v:.2f}  {bar}")
    print(f"\n语言风格: {profile['language']['style']}")
    print(f"Emoji:    {'常用' if profile['language']['emojis_enabled'] else '不常用'}")
    if args.output_toml:
        print(f"\n提示: 将 {args.output_toml} 的内容合并到 configs/default.toml 即可应用")


if __name__ == "__main__":
    main()
