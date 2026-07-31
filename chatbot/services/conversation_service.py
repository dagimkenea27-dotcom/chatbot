# chatbot/services/conversation_service.py
from typing import Dict, Optional


class ConversationService:
    """Manages conversation flow and proactive follow-ups."""
    
    def __init__(self):
        pass
    
    def add_proactive_followup(self, response: str, session, intent: str, context) -> str:
        """Add proactive follow-up questions to keep conversation going."""
        if "━━━" in response or response.startswith("⚠️") or response.startswith("["):
            return response
        
        if "?" in response:
            return response
        
        if intent == "farewell":
            return response
        
        lang = session.language
        raw_name = session.user_name
        name_str = f" {raw_name}" if raw_name else ""
        name_str_en = f", {raw_name}" if raw_name else ""
        
        followups = {
            "product_search": {
                "en": f"\n\nWould you like to see more details about any of these{name_str_en}? 🤔",
                "am": f"\n\nለማንኛውም ተጨማሪ ዝርዝር ማየት ይፈልጋሉ{name_str}? 🤔"
            },
            "product_followup": {
                "en": f"\n\nAnything else you'd like to know about this product{name_str_en}? 😊",
                "am": f"\n\nስለዚህ ምርት ሌላ ማወቅ የሚፈልጉት ነገር አለ{name_str}? 😊"
            },
            "add_last_product": {
                "en": f"\n\nWould you like to keep shopping or head to checkout{name_str_en}? 🛒",
                "am": f"\n\nመግዛትዎን መቀጠል ይፈልጋሉ ወይስ ሂሳብ መክፈል{name_str}? 🛒"
            },
            "order_lookup": {
                "en": f"\n\nIs there anything else about your order you'd like to check{name_str_en}? 📦",
                "am": f"\n\nስለ ትዕዛዝዎ ሌላ ማወቅ የሚፈልጉት ነገር አለ{name_str}? 📦"
            },
            "shipping": {
                "en": f"\n\nWould you like me to help you track a specific order{name_str_en}? 🚚",
                "am": f"\n\nየተወሰነ ትዕዛዝ ለመከታተል መርዳት ይፈልጋሉ{name_str}? 🚚"
            },
            "payment": {
                "en": f"\n\nWould you like to know more about our payment methods{name_str_en}? 💳",
                "am": f"\n\nስለ ክፍያ ዘዴዎቻችን ተጨማሪ ማወቅ ይፈልጋሉ{name_str}? 💳"
            },
            "help": {
                "en": f"\n\nWhich of these would you like to explore first{name_str_en}? 😊",
                "am": f"\n\nከእነዚህ ውስጥ መጀመሪያ ማወቅ የሚፈልጉት የትኛው ነው{name_str}? 😊"
            }
        }
        
        if intent in followups:
            followup = followups[intent].get(lang, followups[intent]["en"])
            if not any(q in response for q in ["?", "?"]):
                return response + followup
        
        return response