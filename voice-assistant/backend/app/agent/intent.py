from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class IntentResult:
    intent: str
    slots: dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    raw: str = ""


_INTENT_TEMPLATES = {
    "weather": ["天气", "温度", "下雨", "晴天", "气温", "刮风", "天气怎么样"],
    "translate": ["翻译", "translate", "翻成", "用英文说", "用中文说"],
    "alarm": ["闹钟", "提醒", "定时", "几点", "叫醒", "提醒我"],
    "search": ["搜索", "查一下", "找一下", "搜一下", "百度一下"],
    "reminder": ["记住", "别忘了", "备忘", "记一下"],
    "greeting": ["你好", "嗨", "早上好", "晚上好", "hi", "hello"],
    "goodbye": ["再见", "拜拜", "明天见", "bye", "see you"],
    "help": ["帮助", "功能", "能做什么", "你会什么", "help"],
}

_SLOT_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "weather": [
        (r"(北京|上海|广州|深圳|杭州|成都|武汉|南京|天津|重庆|西安)", "city"),
        (r"(今天|明天|后天|昨天|周末|下周)", "date"),
    ],
    "alarm": [
        (r"(\d{1,2}:\d{2})", "time"),
        (r"(\d{1,2})点", "time"),
    ],
    "translate": [
        (r"(中文|英文|日文|法文|德文|韩文|俄文)", "target_lang"),
    ],
}


def classify_intent(text: str) -> IntentResult:
    text_lower = text.lower()
    for intent, triggers in _INTENT_TEMPLATES.items():
        for t in triggers:
            if t.lower() in text_lower:
                slots = extract_slots(intent, text)
                return IntentResult(
                    intent=intent, slots=slots,
                    confidence=0.8, raw=text,
                )
    return IntentResult(intent="general", raw=text, confidence=0.3)


def extract_slots(intent: str, text: str) -> dict[str, str]:
    slots: dict[str, str] = {}
    patterns = _SLOT_PATTERNS.get(intent, [])
    for pattern, slot_name in patterns:
        m = re.search(pattern, text)
        if m:
            slots[slot_name] = m.group(1)
    return slots
