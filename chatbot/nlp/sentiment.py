# chatbot/nlp/sentiment.py


class SentimentAnalyzer:
    """Analyzes sentiment in user messages."""
    
    def __init__(self):
        self.positive_words = [
            "love", "great", "amazing", "excellent", "perfect", "wonderful",
            "fantastic", "good", "like", "happy", "delighted", "pleased",
            "ወድጄ", "በጣም", "ደስ", "ጥሩ", "እሺ", "ረክቻለሁ"
        ]
        self.negative_words = [
            "bad", "terrible", "awful", "horrible", "disappointed", "unhappy",
            "frustrated", "annoyed", "upset", "angry", "wrong", "broken",
            "መጥፎ", "አስከፊ", "ዘግይቷል", "ተሰበረ", "አልወደድኩም"
        ]
    
    def analyze(self, message: str) -> str:
        """Analyze sentiment of a message."""
        message_lower = message.lower()
        
        positive_count = sum(1 for word in self.positive_words if word in message_lower)
        negative_count = sum(1 for word in self.negative_words if word in message_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        elif "?" in message:
            return "curious"
        elif "thanks" in message_lower or "thank" in message_lower:
            return "grateful"
        else:
            return "neutral"