# 表情包库

把图片放到对应分类的目录下，机器人会自动加载。

## 目录结构

```
data/memes/
├── general/      # 通用表情包
├── happy/        # 开心
├── sad/          # 难过
├── angry/        # 生气
├── excited/      # 兴奋
├── tired/        # 累
└── memes.json    # 可选：手动配置
```

## memes.json 格式

```json
[
  {"id": "meme1", "path": "data/memes/general/meme1.png", "category": "general", "tags": ["猫"], "description": "一只猫的表情包"},
  {"id": "meme2", "path": "data/memes/happy/haha.jpg", "category": "happy", "tags": ["笑"], "description": "哈哈大笑"}
]
```

支持格式: png, jpg, jpeg, gif, webp
