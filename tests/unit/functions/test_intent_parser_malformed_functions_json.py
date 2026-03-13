from src.functions.intent_parser import IntentParser


def test_parse_recovers_from_malformed_leading_functions_key_with_quote():
    parser = IntentParser()
    malformed = '{functions":[{"name":"create_schedule","parameters":{"time":"09:00","message":"Here is your lesson extract."}}]}'

    result = parser.parse(malformed)

    assert result.success is True
    assert result.is_fallback is False
    assert len(result.functions) == 1
    assert result.functions[0]["name"] == "create_schedule"
    assert result.functions[0]["parameters"]["time"] == "09:00"


def test_parse_recovers_from_malformed_leading_functions_key_with_colon():
    parser = IntentParser()
    malformed = '{functions:[{"name":"create_schedule","parameters":{"time":"10:00","message":"Reminder"}}]}'

    result = parser.parse(malformed)

    assert result.success is True
    assert result.is_fallback is False
    assert len(result.functions) == 1
    assert result.functions[0]["name"] == "create_schedule"
    assert result.functions[0]["parameters"]["time"] == "10:00"
