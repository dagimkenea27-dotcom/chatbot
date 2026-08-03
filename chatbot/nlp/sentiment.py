# chatbot/nlp/sentiment.py
"""
Sentiment analysis for the GojoShop chatbot.

Supports English, Amharic and transliterated Amharic. ``analyze`` returns a
simple label for backward compatibility while ``analyze_scored`` exposes a
numeric polarity score plus the label.
"""
from __future__ import annotations

import re
from typing import Tuple


class SentimentAnalyzer:
    """Analyzes sentiment in user messages."""

    def __init__(self) -> None:
        self.positive_words = [
            # English
            "love", "great", "amazing", "excellent", "perfect", "wonderful",
            "fantastic", "good", "like", "happy", "delighted", "pleased",
            "awesome", "best", "nice", "cool", "impressive", "beautiful",
            # Amharic
            "ወደድኩት", "ወድጄ", "በጣም ጥሩ", "ደስ", "ጥሩ", "እሺ", "ረክቻለሁ",
            "አሪፍ", "ውብ", "ምርጥ", "ደስተኛ",
            # transliterated Amharic
            "arif", "gobez", "lekchu", "desta", "tiru",
        ]
        self.negative_words = [
            # English
            "bad", "terrible", "awful", "horrible", "disappointed", "unhappy",
            "frustrated", "annoyed", "upset", "angry", "wrong", "broken",
            "useless", "waste", "hate", "disgusting", "worst", "failed",
            "damaged", "defective", "delay", "delayed", "late", "scam",
            # Amharic
            "መጥፎ", "አስከፊ", "ዘግይቷል", "ተሰበረ", "አልወደድኩም", "ተጎዳ",
            "ጉድለት", "አልደረሰም", "አልመጣም", "ተበሳጨሁ", "አስከፊ",
            # transliterated Amharic
            "metfo", "askefi", "zegitoal", "tesebre", "alderesem", "almetam",
            "tebesachu", "gudlet", "tegoda",
        ]

        #: Multiword phrases that shift sentiment strongly.
        self.intensifier_phrases = [
            "not working", "doesn't work", "did not work", "won't work",
            "never arrived", "never came", "too late", "so bad", "really bad",
        ]

    def analyze(self, message: str) -> str:
        """Return a sentiment label: positive / negative / curious / grateful / neutral."""
        label, _ = self.analyze_scored(message)
        return label

    def analyze_scored(self, message: str) -> Tuple[str, int]:
        """Analyze sentiment and return ``(label, score)``.

        ``score`` is ``positive_count - negative_count``; positive means the
        message is net positive, negative net negative and zero neutral.
        """
        message_lower = message.lower()

        positive_count = sum(1 for word in self.positive_words
                             if word in message_lower)
        negative_count = sum(1 for word in self.negative_words
                             if word in message_lower)

        # Strongly negative phrases add weight regardless of single words.
        negative_count += sum(1 for phrase in self.intensifier_phrases
                              if phrase in message_lower)

        score = positive_count - negative_count

        if score > 0:
            return "positive", score
        if score < 0:
            return "negative", score
        if "?" in message:
            return "curious", score
        if re.search(r"\b(thanks|thank|አመሰግናለሁ|ameseginalehu)\b", message_lower):
            return "grateful", score
        return "neutral", score
