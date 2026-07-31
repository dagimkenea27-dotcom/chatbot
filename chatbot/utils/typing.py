# chatbot/utils/typing.py
import random


def calc_typing_delay(response: str) -> int:
    """Calculate natural typing delay in milliseconds."""
    if "━━━" in response:
        return random.randint(900, 1400)
    words = max(1, len(response.split()))
    base = random.randint(700, 1100)
    per_word = min(words * 35, 2200)
    return base + per_word