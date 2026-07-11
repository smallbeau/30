from app.agent.intent import classify_intent, extract_slots


def test_classify_weather():
    result = classify_intent("今天北京天气怎么样")
    assert result.intent == "weather"
    assert result.confidence >= 0.3


def test_classify_translate():
    result = classify_intent("把你好翻译成英文")
    assert result.intent == "translate"


def test_classify_greeting():
    result = classify_intent("你好")
    assert result.intent == "greeting"


def test_classify_general():
    result = classify_intent("给我讲个故事")
    assert result.intent == "general"


def test_classify_help():
    result = classify_intent("你能做什么")
    assert result.intent == "help"


def test_extract_slots_city():
    slots = extract_slots("weather", "北京今天天气")
    assert "city" in slots


def test_extract_slots_time():
    slots = extract_slots("alarm", "早上7点叫醒我")
    assert "time" in slots


def test_extract_slots_translate():
    slots = extract_slots("translate", "翻译成英文")
    assert "target_lang" in slots
