"""性格特征分析工具。

从聊天记录中分析语言风格特征，生成可被人格引擎加载的配置。
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path


def analyze_sentiment(messages: list[dict]) -> dict:
    """分析情感倾向。"""
    positive_words = {"开心", "高兴", "喜欢", "太好了", "棒", "谢谢", "哈哈", "不错", "厉害"}
    negative_words = {"难过", "生气", "讨厌", "烦", "伤心", "郁闷", "烦死了", "无聊"}

    pos_count = 0
    neg_count = 0
    total = 0

    for msg in messages:
        content = msg.get("content", "")
        for word in positive_words:
            if word in content:
                pos_count += 1
                total += 1
                break
        for word in negative_words:
            if word in content:
                neg_count += 1
                total += 1
                break

    return {
        "positive_ratio": round(pos_count / max(total, 1), 2),
        "negative_ratio": round(neg_count / max(total, 1), 2),
    }


def analyze_formality(messages: list[dict]) -> float:
    """分析正式程度 (0.0=随意, 1.0=正式)。"""
    formal_markers = {"您好", "请问", "感谢", "抱歉", "不好意思", "麻烦"}
    casual_markers = {"哈哈", "嘿嘿", "嗯嗯", "好的呀", "好嘞", "哦哦", "嗨"}

    formal = 0
    casual = 0

    for msg in messages:
        content = msg.get("content", "")
        for m in formal_markers:
            if m in content:
                formal += 1
                break
        for m in casual_markers:
            if m in content:
                casual += 1
                break

    total = formal + casual
    if total == 0:
        return 0.5
    return round(formal / total, 2)


def analyze_humor(messages: list[dict]) -> float:
    """分析幽默感。"""
    humor_markers = {"哈哈", "呵呵", "开玩笑", "搞笑", "逗", "笑死", "哈哈哈", "😄", "😆"}
    count = sum(1 for msg in messages if any(
        m in msg.get("content", "") for m in humor_markers
    ))
    return round(min(count / max(len(messages), 1) * 10, 1.0), 2)


def analyze_curiosity(messages: list[dict]) -> float:
    """分析好奇心（通过提问频率）。"""
    question_count = sum(1 for msg in messages if "?" in msg.get("content", "") or "?" in msg.get("content", ""))
    return round(min(question_count / max(len(messages), 1) * 5, 1.0), 2)


def analyze_topic_preferences(messages: list[dict]) -> dict:
    """分析话题偏好。"""
    topics = {
        "technology": {"代码", "编程", "电脑", "手机", "软件", "AI", "科技", "互联网"},
        "entertainment": {"电影", "音乐", "游戏", "动漫", "综艺", "明星"},
        "daily_life": {"吃饭", "睡觉", "上班", "下班", "今天", "昨天", "明天"},
        "science": {"科学", "物理", "化学", "生物", "数学", "研究"},
        "philosophy": {"人生", "意义", "哲学", "思考", "为什么"},
    }

    scores = {}
    for topic, keywords in topics.items():
        count = sum(1 for msg in messages if any(
            k in msg.get("content", "") for k in keywords
        ))
        scores[topic] = round(min(count / max(len(messages), 1) * 10, 1.0), 2)

    return scores


def analyze_emoji_usage(messages: list[dict]) -> bool:
    """分析是否常用 emoji。"""
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0\U000024C2-\U0001F251]"
    )
    emoji_count = sum(1 for msg in messages if emoji_pattern.search(msg.get("content", "")))
    return emoji_count / max(len(messages), 1) > 0.1


def build_profile(messages: list[dict]) -> dict:
    """构建完整的性格特征配置。"""
    sentiment = analyze_sentiment(messages)
    topics = analyze_topic_preferences(messages)
    formality = analyze_formality(messages)

    return {
        "name": "分析生成的角色",
        "description": "基于聊天记录自动分析生成的性格特征",
        "traits": {
            "openness": 0.6,
            "humor": analyze_humor(messages),
            "directness": 0.5,
            "empathy": max(0.3, sentiment.get("positive_ratio", 0.5)),
            "curiosity": analyze_curiosity(messages),
            "formality": formality,
            "optimism": max(0.3, sentiment.get("positive_ratio", 0.5)),
        },
        "language": {
            "style": "formal" if formality > 0.6 else "casual",
            "emojis_enabled": analyze_emoji_usage(messages),
            "typo_frequency": 0.03,
        },
        "interests": topics,
    }


def main():
    parser = argparse.ArgumentParser(description="分析聊天记录性格特征")
    parser.add_argument("--file", "-f", required=True, help="聊天记录文件路径")
    parser.add_argument("--output", "-o", help="输出路径")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"错误: 文件不存在: {args.file}")
        return

    with open(path, "r", encoding="utf-8") as f:
        messages = json.load(f)

    if not messages:
        print("错误: 无消息数据")
        return

    profile = build_profile(messages)

    output_path = args.output or str(path.with_name(f"{path.stem}_profile.json"))
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    print(f"性格特征已保存到: {output_path}")
    print(f"\n分析结果概览:")
    print(f"  幽默感: {profile['traits']['humor']}")
    print(f"  正式程度: {profile['traits']['formality']}")
    print(f"  乐观程度: {profile['traits']['optimism']}")
    print(f"  Emoji: {'启用' if profile['language']['emojis_enabled'] else '不常用'}")
    print(f"  语言风格: {profile['language']['style']}")
    print(f"  兴趣偏好: {json.dumps(profile['interests'], ensure_ascii=False)}")


if __name__ == "__main__":
    main()
