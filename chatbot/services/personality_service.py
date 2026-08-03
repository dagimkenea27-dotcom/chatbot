# chatbot/services/personality_service.py
import random
import os
from typing import Dict


class PersonalityService:
    """Manages chatbot personality and response enhancement."""
    
    def __init__(self):
        self.personality = {
            "name": "Sami",
            "nicknames": ["Sami", "Samiye"],
            "mood": "cheerful",
            "emojis": ["😊", "🌟", "✨", "💫", "☀️", "🌸"],
            "catchphrases": {
                "en": ["Oh, that's a great choice!", "I love that one!", "You have good taste!", "That's a classic!"],
                "am": ["በጣም ጥሩ ምርጫ ነው!", "እኔም ወድጄዋለሁ!", "በጣም ጥሩ ጣዕም አሎት!", "ያ የታወቀ ነው!"]
            }
        }
    
    def apply_enhancement(self, response: str, session, intent: str, sentiment: str) -> str:
        """Apply personality enhancements to the response."""
        if "━━━" in response or "PROMO" in response or response.startswith("⚠️") or response.startswith("["):
            return response
        
        lang = session.language if session else "en"
        
        if not any(emoji in response for emoji in ["😊", "🌟", "✨", "💫", "☀️", "🌸", "❤️", "💪", "🎯"]):
            if sentiment == "positive":
                response += random.choice([" 😊", " 🌟", " ✨"])
            elif sentiment == "negative":
                response += random.choice([" 💪", " 🤗", " ❤️"])
            else:
                response += random.choice([" 😊", " 🌸"])
        
        if random.random() < 0.1 and len(response.split()) > 15:
            encouragements = {
                "en": ["\n\nYou're doing great! Keep asking away! 💪", 
                       "\n\nI'm really enjoying helping you today! 😊"],
                "am": ["\n\nበጣም ጥሩ እየሆኑ ነው! መጠየቅዎን ይቀጥሉ! 💪",
                       "\n\nዛሬ መርዳት በጣም ደስ ብሎኛል! 😊"]
            }
            response += random.choice(encouragements.get(lang, encouragements["en"]))
        
        return response
    
    def wrap_natural(self, response: str, session, intent: str) -> str:
        """Prepend a natural opener to plain-text replies."""
        if intent in ("farewell", "human_support", "small_talk", "greeting") or "━━━" in response or "PROMO" in response or response.startswith("⚠️"):
            return response
        
        if len(response.split()) < 10 and intent not in ["greeting", "small_talk"]:
            if session and session.language == "am":
                additions = ["በእርግጥ! ", "እሺ። ", "እሺ — "]
            else:
                additions = ["Got it! ", "Alright! ", "Sure! "]
            return random.choice(additions) + response
        
        opener = self._natural_opener(session, intent)
        if opener and not response.lower().startswith(opener.strip().lower()):
            return opener + response
        return response
    
    def _natural_opener(self, session, intent: str) -> str:
        """Pick a short, human-sounding bridge phrase."""
        msg_count = session.message_count if session else 0
        lang = session.language if session else "en"
        
        openers = {
            "en": {
                "greeting": ["Hey! 🌟 I'm Sami! So glad you're here. ", "Hi there! ✨ I was just thinking about what new products we got! ", "Welcome! 🌸 I'm Sami, your personal shopping buddy. "],
                "product_search": ["Ooh, let me find that for you! 🎯 ", "I love searching for cool stuff! Let's see what I can find... 🔍 ", "Ooh, good taste! Let me pull up some options for you. ✨ "],
                "order_lookup": ["Of course! Let me check that for you. 📦 ", "I'll pull up your order details right away. Give me a sec! ", "Let me look that up for you! 🔎 "],
                "general": ["I'm here for you! 😊 ", "Got it! Let me think about that... 💭 ", "That's a great question! Let me help you out. 🌟 "]
            },
            "am": {
                "greeting": ["ሰላም! 🌟 እኔ ሳሚ ነኝ! እዚህ በመጡ ደስ ብሎኛል! ", "እንደምን አለህ/ሽ! ✨ አዲስ ምርቶች ስለመጡ እያሰብኩ ነበር! ", "እንኳን ደህና መጣህ/ሽ! 🌸 እኔ ሳሚ ነኝ፣ የግብይት ጓደኛዎ!"],
                "product_search": ["እሺ! እያፈላለግኩልዎ ነው! 🎯 ", "ጥሩ ነገሮችን መፈለግ እወዳለሁ! ምን እናገኛለን... 🔍 ", "በጣም ጥሩ ጣዕም! አንዳንድ አማራጮችን አመጣላችሁ። ✨ "],
                "order_lookup": ["እሺ! ያንን እያረጋገጥኩልዎ ነው። 📦 ", "የትዕዛዝ ዝርዝሮችዎን አሁን አመጣላለሁ። ", "ያንን እየተመለከትኩት ነው! 🔎 "],
                "general": ["እዚህ ነኝ! 😊 ", "ተረድቻለሁ! ስለዚህ እናስብ... 💭 ", "በጣም ጥሩ ጥያቄ! ልርዳዎት። 🌟 "]
            }
        }
        
        intent_map = {"greeting": "greeting", "product_search": "product_search", "order_lookup": "order_lookup"}
        opener_type = intent_map.get(intent, "general")
        choices = openers.get(lang, openers["en"]).get(opener_type, openers["en"]["general"])
        
        if msg_count > 2 and intent != "greeting":
            return random.choice(choices)
        elif intent == "greeting" and msg_count <= 2:
            return random.choice(choices)
        return random.choice(openers.get(lang, openers["en"]).get("general", openers["en"]["general"]))