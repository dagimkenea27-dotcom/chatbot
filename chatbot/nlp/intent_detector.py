# chatbot/nlp/intent_detector.py
import re
from typing import Optional, Dict


class IntentDetector:
    """Detects user intent from messages."""
    
    def __init__(self):
        self.affirmative = {"yes", "yeah", "yep", "sure", "ok", "okay", "y", "correct", "right", "አዎ", "እሺ", "አው", "ትክክል", "አዎን"}
        self.negative = {"no", "nope", "nah", "not really", "n", "አይ", "አይደለም", "አይሆንም", "አይደል"}
    
    def detect(self, message: str, session, context, session_service) -> str:
        """Detect user intent."""
        message_lower = message.lower().strip()
        last_intent = session.last_intent or session.current_intent
        
        # 1. Check for awaiting follow-up
        if context.awaiting_followup:
            if self.is_affirmative(message_lower) or self.is_negative(message_lower):
                if context.last_question_type == "search":
                    return "product_search"
                elif context.last_question_type == "order":
                    return "order_lookup"
                elif context.last_question_type == "help":
                    return "help"
        
        # 2. Complaint / Negative sentiment
        complaint_patterns = [
            r'(weeks?|months?|days?)\s+(ago|late|delay|wait)',
            r'(hasn\'t|haven\'t|didn\'t)\s+(arrived|come|shown up|delivered)',
            r'(not|never)\s+(received|got|get)',
            r'(broken|damaged|defective|faulty|not working|doesn\'t work)',
            r'(frustrating|annoying|upset|angry|disappointed|terrible|horrible|awful)',
            r'(ዘግይቷል|ተሰበረ|ተጎዳ|ጉድለት|ተበሳጨሁ)',
            r'(አልደረሰም|አልመጣም|አልተሰራም)',
        ]
        
        is_complaint = any(re.search(pattern, message_lower) for pattern in complaint_patterns)
        has_order_mention = any(w in message_lower for w in ["order", "ትዕዛዝ", "my order", "purchase"])
        
        if is_complaint or (has_order_mention and session.user_mood == "negative"):
            order_id = self.extract_order_id(message)
            if order_id:
                session.last_order_id = order_id
                return "order_lookup"
            elif session.last_order_id:
                return "order_followup"
            else:
                return "human_support"
        
        # 3. Human support
        if self.wants_human_support(message_lower):
            return "human_support"
        if session.human_support_requested and self.is_affirmative(message_lower):
            return "human_support"
        
        # 4. Contextual follow-ups
        if self.is_affirmative(message_lower):
            if last_intent == "checkout" and session.cart:
                return "checkout"
            if last_intent == "order_lookup" and not session.last_order_id:
                return "order_lookup"
            if last_intent == "product_search" and session.last_search_keyword:
                return "product_search"
            if session.last_order_id:
                return "order_followup"
        
        if self.is_negative(message_lower):
            return "farewell"
        
        # 5. Product reference
        if session.last_products and self.references_last_item(message_lower):
            if any(w in message_lower for w in ["add", "buy", "get", "purchase", "order", "ጨምር", "ግዛ", "እዘዝ"]):
                return "add_last_product"
            return "product_followup"
        
        if session.last_search_keyword and any(
            phrase in message_lower for phrase in ["show more", "more options", "anything else", "see more", "ተጨማሪ", "ሌላ"]
        ):
            return "repeat_search"
        
        # 6. Order lookup
        order_id = self.extract_order_id(message)
        if order_id:
            product_keywords = ["buy", "purchase", "search", "find", "looking", "show", "price", "cost", "ግዛ", "ፈልግ", "አሳይ", "ዋጋ", "felge", "mayet", "megzat"]
            if not any(kw in message_lower for kw in product_keywords):
                session.last_order_id = order_id
                return "order_lookup"
        
        if any(w in message_lower for w in ["my order", "order status", "track", "tracking", "where is my", "ትዕዛዜ", "ትዕዛዝ","የእኔ ትዕዛዝ", "ትዕዛዝ ሁኔታ", "መቼ ይደርሳል"]):
            return "order_lookup"
        
        if session.last_order_id and any(
            w in message_lower for w in ["status", "arrive", "when", "delivery", "update", "delayed", "ሁኔታ", "መቼ", "አድራሻ"]
        ):
            return "order_followup"
        
        # 7. Support topics
        if re.search(r'\b(buy|add|ግዛ|ጨምር)[-_]?(\d+)\b', message_lower) or message_lower.startswith('/buy_'):
            return "add_to_cart_id"
        
        topic_map = {
            r"payment|pay|telebirr|amole|ቴሌብር|አሞሌ|ክፍያ": "payment",
            r"shipping|delivery|arrive|ማድረሻ|አቅርቦት": "shipping",
            r"return|returns|refund|exchange|defective|መመለስ|ተመላሽ|ቀይር": "returns",
            r"warranty|repair|broken|damage|ዋስትና|ጥገና|የተሰበረ": "warranty",
            r"contact|email|phone|call|reach|address|location|ያናግሩ|ኢሜይል|ስልክ|አድራሻ": "contact",
            r"hours|open|close|business hours|ሰዓት|ሰዓቶች|ስራ ሰዓት": "hours",
            r"promo|promotion|discount|deal|offer|sale|coupon|code|voucher|ቅናሽ|ዋጋ ቅናሽ": "promotions",
            r"loyalty|points|rewards|membership|ነጥብ|ታማኝ|ሽልማት": "loyalty",
            r"cancel|cancellation|ሰርዝ|ስርዝ": "cancellation",
            r"checkout|check out": "checkout",
            r"help|support|assist|problem|እርዳታ|እገዛ|ችግር": "help",
        }
        
        for pattern, intent in topic_map.items():
            if re.search(r'\b(' + pattern + r')\b', message_lower):
                return intent
        
        # 8. Greetings and farewells
        if any(w in message_lower for w in ["hello", "hi", "hey", "good morning", "selam", "ሰላም", "እንደምን", "ሠላም"]):
            return "greeting"
        if any(w in message_lower for w in ["bye", "goodbye", "see you", "thanks", "thank", "ቻው", "ደህና ሁን"]):
            return "farewell"
        
        # 9. Small talk
        if self.is_small_talk(message_lower):
            return "small_talk"
        
        # 10. Product search
        if any(w in message_lower for w in ["buy", "purchase", "price", "cost", "search", "find", "looking for", 
                                            "recommend", "show me", "ግዛ", "ፈልግ", "አሳይ"]):
            return "product_search"
        
        return "general"
    
    def is_affirmative(self, message: str) -> bool:
        return message.lower().strip() in self.affirmative
    
    def is_negative(self, message: str) -> bool:
        return message.lower().strip() in self.negative
    
    def is_small_talk(self, message_lower: str) -> bool:
        """Detect casual small talk."""
        small_talk_phrases = [
            "how are you", "how's it going", "how's your day", "how's the weather",
            "what's up", "what's new", "how's work", "how's family",
            "good morning", "good afternoon", "good evening", "good night",
            "እንደምን አለህ", "ሰላም", "እንደምን አደርክ", "እንደምን አላችሁ",
            "ትንሽ እረፍት", "ደህና ነህ", "ቡና ጠጣህ"
        ]
        
        shopping_phrases = ["buy", "purchase", "order", "price", "shop", "ምርት", "ግዛ", "ፈልግ", "አሳይ"]
        
        is_small_talk = any(phrase in message_lower for phrase in small_talk_phrases)
        if any(phrase in message_lower for phrase in shopping_phrases):
            return False
        return is_small_talk
    
    def wants_human_support(self, message_lower: str) -> bool:
        """Detect when user wants human support."""
        phrases = [
            "human", "real person", "speak to someone", "customer service",
            "live agent", "human support", "representative", "not a bot",
            "not helping", "useless", "frustrated", "complaint", "supervisor",
            "ከሰው", "ሰው ጋር", "የደንበኛ", "ወኪል", "አገናኝ"
        ]
        return any(phrase in message_lower for phrase in phrases)
    
    def extract_order_id(self, message: str) -> Optional[str]:
        """Extract order ID from message."""
        message_stripped = message.strip()
        
        # Check if this is clearly a product search first
        product_indicators = ["buy", "purchase", "search", "find", "looking", "show", 
                              "price", "cost", "cheap", "expensive", "ግዛ", "ፈልግ", "አሳይ", "ዋጋ"]
        if any(w in message.lower() for w in product_indicators):
            return None
        
        # If the message is just a number (likely an order ID)
        if re.match(r'^\d{4,}$', message_stripped):
            return message_stripped
        
        # Explicit order ID patterns
        m = re.search(r'\b(ORD[-_\s]?\d+)\b', message, re.IGNORECASE)
        if m:
            return m.group(1)
        
        m = re.search(r'#(\d{4,})', message)
        if m:
            return m.group(1)
        
        # Contextual order ID
        message_lower = message.lower()
        if any(w in message_lower for w in ["order", "track", "tracking", "ትዕዛዝ", "ትዕዛዜን", "ትእዛዜ"]):
            m = re.search(r'\b(\d{4,})\b', message)
            if m:
                return m.group(1)
        
        return None
    
    def references_last_item(self, message: str) -> bool:
        """Check if message references the last item."""
        message_lower = message.lower()
        return any(
            phrase in message_lower
            for phrase in [
                "that one", "this one", "the first", "first one", "second one",
                "add it", "buy it", "get it", "purchase it", "order it",
                "how much is it", "tell me more", "more about it", "about that",
                "እሱን", "ይህንን", "ያንን", "ጨምረው", "ጨምሪው", "ግዛው", "ዋጋው ስንት ነው"
            ]
        ) or message_lower.strip() in {"it", "that", "this", "እሱ", "ይሄ", "ያ"}