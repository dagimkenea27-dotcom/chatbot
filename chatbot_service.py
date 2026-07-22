# chatbot_service.py
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import random
import os


class GojoShopChatbot:
    def __init__(self, db_manager=None):
        self.context = {}
        self.user_sessions = {}
        self.product_catalog = self.load_product_catalog()
        self.faq_data = self.load_faq()
        self.db = db_manager          # injected DatabaseManager (or None)
        self.support_requests: List[Dict] = []
        self.translations = self.load_translations()

    def load_translations(self) -> Dict:
        """Load localization files"""
        translations = {}
        base_dir = os.path.dirname(os.path.abspath(__file__))
        i18n_dir = os.path.join(base_dir, "i18n")
        for lang in ["en", "am"]:
            path = os.path.join(i18n_dir, f"{lang}.json")
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        translations[lang] = json.load(f)
                except Exception as e:
                    print(f"Error loading {lang}.json: {e}")
            else:
                translations[lang] = {}
        return translations

    def translate(self, session: Dict, key: str, **kwargs) -> str:
        """Helper to get translated string for active language in session"""
        lang = session.get("language", "en")
        text = self.translations.get(lang, {}).get("bot", {}).get(key)
        if text is None:
            text = self.translations.get("en", {}).get("bot", {}).get(key, key)
        try:
            return text.format(**kwargs)
        except Exception:
            return text

    def load_product_catalog(self) -> Dict:
        """Load product catalog (replace with actual DB/data)"""
        return {
            "electronics": {
                "phones": ["iPhone 15", "Samsung Galaxy S24", "Google Pixel 8"],
                "laptops": ["MacBook Pro", "Dell XPS 13", "HP Spectre"],
                "accessories": ["AirPods", "Chargers", "Phone Cases"]
            },
            "clothing": {
                "men": ["T-shirts", "Jeans", "Jackets", "Suits"],
                "women": ["Dresses", "Tops", "Skirts", "Handbags"],
                "kids": ["T-shirts", "Shorts", "Shoes"]
            },
            "home": {
                "furniture": ["Sofas", "Tables", "Chairs", "Beds"],
                "kitchen": ["Cookware", "Utensils", "Appliances"],
                "decor": ["Wall Art", "Vases", "Rugs", "Lamps"]
            }
        }

    def load_faq(self) -> Dict:
        """Load FAQ data"""
        return {
            "shipping": {
                "question": "How long does shipping take?",
                "answer": "Delivery takes 2-5 business days within Ethiopia. Express shipping is available for 1-2 days."
            },
            "returns": {
                "question": "What is your return policy?",
                "answer": "We accept returns within 30 days of purchase. Items must be unused and in original packaging."
            },
            "payment": {
                "question": "What payment methods do you accept?",
                "answer": "We accept Telebirr, Amole, Credit/Debit cards, and Cash on Delivery."
            },
            "warranty": {
                "question": "Do you offer warranty?",
                "answer": "Yes, all electronics come with 1-year manufacturer warranty. Extended warranty available for purchase."
            }
        }

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------

    def save_session(self, user_id: str):
        """Persist user session to database."""
        if self.db is not None and hasattr(self.db, "save_user_session") and user_id in self.user_sessions:
            self.db.save_user_session(user_id, self.user_sessions[user_id])

    def _ensure_session(self, user_id: str):
        """Initialize session if it doesn't exist yet, checking the database first."""
        if user_id not in self.user_sessions:
            session = None
            if self.db is not None and hasattr(self.db, "get_user_session"):
                session = self.db.get_user_session(user_id)
            
            if session is None:
                session = {
                    "user_id": user_id,
                    "conversation_history": [],
                    "current_intent": None,
                    "last_intent": None,
                    "last_product": None,
                    "last_products": [],
                    "last_search_keyword": None,
                    "last_product_filters": {},
                    "last_order_id": None,
                    "message_count": 0,
                    "human_support_requested": False,
                    "cart": [],
                    "language": "en"
                }
                if self.db is not None and hasattr(self.db, "save_user_session"):
                    self.db.save_user_session(user_id, session)
            self.user_sessions[user_id] = session
        else:
            self.user_sessions[user_id]["user_id"] = user_id

    def reset_session(self, user_id: str):
        """Clear conversation context for a user and reactivate the AI chat."""
        active_req = self.get_active_support_request(user_id)
        if active_req:
            self.update_support_request_status(active_req["id"], "resolved")

        # Clear cart from DB
        if self.db is not None and hasattr(self.db, "clear_cart"):
            self.db.clear_cart(user_id)

        self.user_sessions.pop(user_id, None)
        if self.db is not None and hasattr(self.db, "delete_user_session"):
            self.db.delete_user_session(user_id)
        self._ensure_session(user_id)


    def _record_turn(self, session: Dict, role: str, text: str, intent: str = None):
        """Store a structured conversation turn for context."""
        session["conversation_history"].append({
            "role": role,
            "text": text,
            "intent": intent,
            "timestamp": datetime.now().isoformat(),
        })
        if len(session["conversation_history"]) > 20:
            session["conversation_history"] = session["conversation_history"][-20:]

    def _recent_user_messages(self, session: Dict, limit: int = 3) -> List[str]:
        """Return the last few user messages for context."""
        turns = [t["text"] for t in session.get("conversation_history", []) if t.get("role") == "user"]
        return turns[-limit:]

    def _is_affirmative(self, message: str) -> bool:
        return message.lower().strip() in {
            "yes", "yeah", "yep", "sure", "ok", "okay", "please", "y", "correct", "right",
            "አዎ", "እሺ", "ይሁን", "ትክክል", "አዎን"
        }

    def _is_negative(self, message: str) -> bool:
        return message.lower().strip() in {
            "no", "nope", "nah", "not really", "n",
            "አይ", "አይደለም", "አይሆንም", "አይደል"
        }

    def _references_last_item(self, message: str) -> bool:
        message_lower = message.lower()
        return any(
            phrase in message_lower
            for phrase in [
                "that one", "this one", "the first", "first one", "second one",
                "add it", "buy it", "get it", "purchase it", "order it",
                "how much is it", "tell me more", "more about it", "about that",
                "እሱን", "ይህንን", "ያንን", "ጨምረው", "ጨምሪው", "ግዛው", "ዋጋው ስንት ነው", "ስለ እሱ",
            ]
        ) or message_lower.strip() in {"it", "that", "this", "እሱ", "ይሄ", "ያ"}

    def calc_typing_delay(self, response: str) -> int:
        """Estimate a natural typing delay in milliseconds."""
        if "━━━" in response:
            return random.randint(900, 1400)
        words = max(1, len(response.split()))
        base = random.randint(700, 1100)
        per_word = min(words * 35, 2200)
        return base + per_word

    def _natural_opener(self, session: Dict, intent: str) -> str:
        """Pick a short, human-sounding bridge phrase based on context."""
        last_intent = session.get("last_intent")
        msg_count = session.get("message_count", 0)

        if session.get("language") == "am":
            if intent == "greeting":
                hour = datetime.now().hour
                if hour < 12:
                    return random.choice(["እንደምን አደሩ! ", "ሰላም! "])
                if hour < 17:
                    return random.choice(["እንደምን ዋሉ! ", "ሰላም! "])
                return random.choice(["እንደምን አመሹ! ", "ሰላም! "])

            if msg_count > 2:
                contextual_am = {
                    "product_search": ["እሺ፣ ልፈልግልዎ። ", "አንድ አፍታ — እያፈላለግኩ ነው። ", "እሺ፣ አሁን እፈልጋለሁ። "],
                    "order_lookup": ["በእርግጥ — ላምጣው። ", "እሺ፣ ትዕዛዝዎን እያረጋገጥኩ ነው። ", "አንድ ሰከንድ፣ እያየሁት ነው። "],
                    "order_followup": ["ስለ ትዕዛዝዎ — ", "እሺ። ", "እሺ፣ ልፈትሽልዎ። "],
                    "shipping": ["ስለ ማድረሻ ለመርዳት ደስተኛ ነኝ። ", "እሺ — ማድረሻ የሚከናወነው በዚህ መልኩ ነው። "],
                    "returns": ["ምንም ችግር የለም። ", "እዚህ ላይ መርዳት እችላለሁ። "],
                    "payment": ["በፍጹም። ", "እሺ — የክፍያ አማራጮቻችን እነዚህ ናቸው። "],
                    "checkout": ["በጣም ጥሩ። ", "እሺ — "],
                    "add_to_cart_id": ["ተከናውኗል! ", "እሺ — "],
                    "add_last_product": ["ጥሩ ምርጫ ነው! ", "እሺ — "],
                    "product_followup": ["ስለዚህ እቃ — ", "እሺ — "],
                    "general": ["ተረድቻለሁ። ", "እሺ። ", "እሺ — "],
                }
                if intent in contextual_am:
                    return random.choice(contextual_am[intent])

            if last_intent == "product_search" and intent == "product_search":
                return random.choice(["እየፈለግኩ ነው:: ", "ልፈልግልዎ:: "])
            return ""

        if intent == "greeting":
            hour = datetime.now().hour
            if hour < 12:
                return random.choice(["Good morning! ", "ሰላም! "])
            if hour < 17:
                return random.choice(["Good afternoon! ", "Hey! "])
            return random.choice(["Good evening! ", "Hey there! "])

        if msg_count > 2:
            contextual = {
                "product_search": ["Sure, let me look that up for you. ", "One moment — I'll find that. ", "Got it, searching now. "],
                "order_lookup": ["Of course — let me pull that up. ", "Sure, checking your order now. ", "One sec, looking that up. "],
                "order_followup": ["Right, about your order — ", "Sure thing. ", "Let me check on that for you. "],
                "shipping": ["Happy to help with delivery. ", "Sure — here's how shipping works. "],
                "returns": ["No problem. ", "I can help with that. "],
                "payment": ["Absolutely. ", "Sure — here are our payment options. "],
                "checkout": ["Sounds good. ", "Alright — "],
                "add_to_cart_id": ["Done! ", "Got it — "],
                "add_last_product": ["Nice choice! ", "Sure thing — "],
                "product_followup": ["About that item — ", "Sure — "],
                "general": ["I hear you. ", "Got it. ", "Sure — "],
            }
            if intent in contextual:
                return random.choice(contextual[intent])

        if last_intent == "product_search" and intent == "product_search":
            return random.choice(["Looking into that now. ", "Let me search for that. "])

        return ""

    def _wrap_natural(self, response: str, session: Dict, intent: str) -> str:
        """Prepend a natural opener to plain-text replies (not rich cards)."""
        if intent in ("greeting", "farewell", "human_support") or "━━━" in response or response.startswith("⚠️"):
            return response
        opener = self._natural_opener(session, intent)
        if opener and not response.lower().startswith(opener.strip().lower()):
            return opener + response
        return response

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def get_response(self, user_id: str, message: str) -> str:
        """Main entry point for getting chatbot response"""
        self._ensure_session(user_id)
        session = self.user_sessions[user_id]
        if self.db is not None and hasattr(self.db, "get_cart_items_by_user"):
            session["cart"] = self.db.get_cart_items_by_user(user_id)
        session["message_count"] = session.get("message_count", 0) + 1
        self._record_turn(session, "user", message)

        # Check for command to set language manually
        lang_match = re.match(r'^/(?:language|lang)\s+(en|am)\b', message.lower().strip())
        if lang_match:
            new_lang = lang_match.group(1)
            session["language"] = new_lang
            self.save_session(user_id)
            if new_lang == "am":
                return "ቋንቋ ወደ አማርኛ ተቀይሯል።"
            else:
                return "Language set to English."

        # Auto-detect if message contains Amharic script
        if re.search(r'[\u1200-\u137f]', message):
            session["language"] = "am"

        # Check for command to exit support mode
        if message.lower().strip() in {"exit", "reset", "stop support"}:
            active_req = self.get_active_support_request(user_id)
            if active_req:
                active_req["status"] = "resolved"
                active_req["updated_at"] = datetime.now().isoformat()
                session["human_support_requested"] = False
                session["current_intent"] = "general"
                self.save_session(user_id)
                return self.translate(session, "support_ended")

        # Check if user is actively in a live support request session
        active_req = self.get_active_support_request(user_id)
        if active_req:
            # Add message to support chat history
            self.add_support_chat_message(active_req["id"], "user", message)
            # Return special token to indicate support mode
            self.save_session(user_id)
            return "[SUPPORT_MODE]"

        intent = self.detect_intent(message, session)
        session["last_intent"] = session.get("current_intent")
        session["current_intent"] = intent

        response = self.generate_response(intent, message, session)
        response = self._wrap_natural(response, session, intent)
        self._record_turn(session, "assistant", response, intent)
        self.save_session(user_id)
        return response

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------

    def detect_intent(self, message: str, session: Dict) -> str:
        """Detect user intent from message"""
        message_lower = message.lower().strip()
        last_intent = session.get("last_intent") or session.get("current_intent")

        # --- Contextual short follow-ups ---
        if self._is_affirmative(message_lower):
            if last_intent == "checkout" and session.get("cart"):
                return "checkout"
            if last_intent == "order_lookup" and not session.get("last_order_id"):
                return "order_lookup"
            if last_intent == "product_search" and session.get("last_search_keyword"):
                return "product_search"
            if session.get("last_order_id"):
                return "order_followup"

        if self._is_negative(message_lower):
            return "farewell"

        if session.get("last_products") and self._references_last_item(message_lower):
            if any(w in message_lower for w in ["add", "buy", "get", "purchase", "order", "ጨምር", "ግዛ", "እዘዝ"]):
                return "add_last_product"
            return "product_followup"

        if session.get("last_search_keyword") and any(
            phrase in message_lower
            for phrase in ["show more", "more options", "anything else", "other options", "see more", "ተጨማሪ", "ሌላ"]
        ):
            return "repeat_search"

        if session.get("last_order_id") and any(
            w in message_lower for w in ["status", "arrive", "when", "delivery", "update", "still", "delayed", "where is it", "ሁኔታ", "መቼ", "ማድረሻ", "የደረሰ"]
        ):
            return "order_followup"

        # --- Human support / escalation ---
        if self._wants_human_support(message_lower):
            return "human_support"
        if session.get("human_support_requested") and self._is_affirmative(message_lower):
            return "human_support"

        # --- Direct buy / add to cart commands (e.g. /buy_85 or buy 85) ---
        if re.search(r'\b(buy|add|ግዛ|ጨምር)[-_\s]?(\d+)\b', message_lower) or message_lower.startswith('/buy_'):
            return "add_to_cart_id"

        if self._extract_product_filters(message_lower) and self._extract_search_keyword(message_lower):
            return "product_search"

        # --- Order lookup ---
        # Explicit order ID pattern: ORD-XXXX, #XXXX, or bare digits 4+
        if re.search(r'\b(ord[-\s]?\d+|#\d{4,}|\d{4,})\b', message_lower):
            return "order_lookup"
        # Order-related phrases (with prior order context = follow-up)
        if any(w in message_lower for w in ["my order", "order status", "track", "tracking", "where is my", "order number", "ትዕዛዜ", "ትዕዛዝ", "ሁኔታ", "ቁጥር"]):
            return "order_lookup"
        # Follow-up on previously looked-up order
        if session.get("last_order_id") and any(
            w in message_lower for w in ["status", "arrive", "when", "delivery", "update", "still", "delayed", "ሁኔታ", "መቼ", "አድራሻ"]
        ):
            return "order_followup"

        # --- Payment (before checkout to avoid collision) ---
        if any(w in message_lower for w in ["telebirr", "amole", "ቴሌብር", "አሞሌ", "ክፍያ"]):
            return "payment"

        # --- Product search and buy intents ---
        if any(w in message_lower for w in ["buy", "purchase", "order", "price", "cost", "search", "find", "looking for", "recommend", "show me", "ግዛ", "ፈልግ", "አሳይ", "ዋጋው", "እፈልጋለሁ"]):
            return "product_search"
        if any(w in message_lower for w in ["cart", "checkout", "ጋሪ", "ክፈል"]):
            return "checkout"

        # --- Support ---
        if any(w in message_lower for w in ["shipping", "delivery", "arrive", "ማድረሻ", "አቅርቦት", "መቼ"]):
            return "shipping"
        if any(w in message_lower for w in ["return", "refund", "exchange", "defective", "መመለስ", "ተመላሽ", "ቀይር"]):
            return "returns"
        if any(w in message_lower for w in ["payment", "pay", "card", "visa", "mastercard", "ክፍያ", "ካርድ"]):
            return "payment"
        if any(w in message_lower for w in ["warranty", "repair", "broken", "damage", "ዋስትና", "ጥገና", "የተሰበረ"]):
            return "warranty"

        # --- General ---
        if any(w in message_lower for w in ["help", "support", "assist", "problem", "እርዳታ", "እገዛ", "ችግር"]):
            return "help"
        if any(w in message_lower for w in ["hello", "hi", "hey", "good morning", "selam", "ሰላም", "እንደምን"]):
            return "greeting"
        if any(w in message_lower for w in ["bye", "goodbye", "see you", "thanks", "thank", "ቻው", "ደህና ሁን", "ምስጋና"]):
            return "farewell"

        # Bare product keyword search (e.g. "baby shoes", "leather bag")
        if self._extract_search_keyword(message):
            return "product_search"

        return "general"

    def _wants_human_support(self, message_lower: str) -> bool:
        """Detect when the user wants to speak with a real person."""
        phrases = [
            "human", "real person", "real human", "speak to someone", "talk to someone",
            "talk to a person", "speak to a person", "customer service", "customer support",
            "live agent", "live support", "human agent", "human support", "call support",
            "call me", "representative", "operator", "staff member", "not a bot",
            "not helping", "useless", "frustrated", "complaint", "supervisor", "manager",
            "speak to human", "talk to human", "connect me", "transfer me",
            "ከሰው", "ሰው ጋር", "የደንበኛ", "ወኪል", "አገናኝ", "ከተወካይ"
        ]
        return any(phrase in message_lower for phrase in phrases)

    def log_support_request(self, user_id: str, message: str, session: Dict) -> Dict:
        """Record a human-support handoff for follow-up."""
        metadata = {
            "last_intent": session.get("current_intent"),
            "last_order_id": session.get("last_order_id"),
            "last_search_keyword": session.get("last_search_keyword"),
            "cart": list(session.get("cart", [])),
        }
        
        entry = None
        if self.db is not None and hasattr(self.db, "create_support_request"):
            req_id = f"SUP-{random.randint(10000, 99999)}"
            entry = self.db.create_support_request(req_id, user_id, message, metadata)

        if not entry:
            entry = {
                "id": f"SUP-{len(self.support_requests) + 1:05d}",
                "status": "open",
                "user_id": user_id,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata,
                "messages": [
                    {
                        "sender": "user",
                        "text": message,
                        "timestamp": datetime.now().isoformat()
                    }
                ],
            }
        
        self.support_requests.append(entry)
        if len(self.support_requests) > 200:
            self.support_requests = self.support_requests[-200:]
        session["human_support_requested"] = True
        return entry

    def get_active_support_request(self, user_id: str) -> Optional[Dict]:
        """Get the current active support request (open or in_progress) for a user."""
        if self.db is not None and hasattr(self.db, "get_active_support_request"):
            db_req = self.db.get_active_support_request(user_id)
            if db_req:
                return db_req
        for req in reversed(self.support_requests):
            if req.get("user_id") == user_id and req.get("status") in {"open", "in_progress"}:
                return req
        return None

    def add_support_chat_message(self, request_id: str, sender: str, text: str) -> Optional[Dict]:
        """Add a message to the support chat history."""
        if self.db is not None and hasattr(self.db, "add_support_message"):
            db_msg = self.db.add_support_message(request_id, sender, text)
            if db_msg:
                # Also update in-memory object if present
                for req in self.support_requests:
                    if req.get("id") == request_id:
                        req.setdefault("messages", []).append(db_msg)
                return db_msg
        for req in self.support_requests:
            if req.get("id") == request_id:
                msg = {
                    "sender": sender,
                    "text": text,
                    "timestamp": datetime.now().isoformat()
                }
                req.setdefault("messages", []).append(msg)
                return msg
        return None

    def list_support_requests(self, limit: int = 50) -> List[Dict]:
        """List support requests from DB or memory."""
        if self.db is not None and hasattr(self.db, "list_support_requests"):
            db_requests = self.db.list_support_requests(limit)
            if db_requests:
                return db_requests
        return self.support_requests[-limit:]

    def update_support_request_status(self, request_id: str, status: str) -> Dict | None:
        """Update support request status in DB and memory."""
        if status not in {"open", "in_progress", "resolved"}:
            return None
        updated_db = None
        if self.db is not None and hasattr(self.db, "update_support_request_status"):
            updated_db = self.db.update_support_request_status(request_id, status)
        
        for request in self.support_requests:
            if request.get("id") == request_id:
                request["status"] = status
                request["updated_at"] = datetime.now().isoformat()
                return request
        return updated_db

    # ------------------------------------------------------------------
    # Response dispatcher
    # ------------------------------------------------------------------

    def generate_response(self, intent: str, message: str, session: Dict) -> str:
        """Generate response based on intent"""
        handlers = {
            "greeting":           self.handle_greeting,
            "product_search":     self.handle_product_search,
            "purchase":           self.handle_product_search,
            "add_to_cart_id":     self.handle_add_to_cart_id,
            "add_last_product":   self.handle_add_last_product,
            "product_followup":   self.handle_product_followup,
            "repeat_search":      self.handle_repeat_search,
            "shipping":           self.handle_shipping,
            "returns":            self.handle_returns,
            "payment":            self.handle_payment,
            "warranty":           self.handle_warranty,
            "checkout":           self.handle_checkout,
            "help":               self.handle_help,
            "human_support":      self.handle_human_support,
            "farewell":           self.handle_farewell,
            "order_lookup":       self.handle_order_lookup,
            "order_followup":     self.handle_order_followup,
            "general":            self.handle_general,
        }
        handler = handlers.get(intent, self.handle_general)
        return handler(message, session)

    # ------------------------------------------------------------------
    # Intent handlers
    # ------------------------------------------------------------------
    def handle_greeting(self, message: str, session: Dict) -> str:
        shop = os.getenv("SHOP_NAME", "GojoShop.et")
        is_returning = session.get("message_count", 1) > 1

        if is_returning and session.get("last_search_keyword"):
            return self.translate(
                session, "welcome_back_search",
                shop=shop, keyword=session["last_search_keyword"]
            )
        if is_returning and session.get("cart"):
            return self.translate(
                session, "welcome_back_cart",
                shop=shop, cart_len=len(session["cart"])
            )
        if is_returning:
            return self.translate(session, "welcome_back_general", shop=shop)

        greetings = [
            self.translate(session, "greeting_1", shop=shop),
            self.translate(session, "greeting_2", shop=shop),
            self.translate(session, "greeting_3", shop=shop),
        ]
        return random.choice(greetings)

    def handle_product_search(self, message: str, session: Dict) -> str:
        if self.db is None:
            return self.translate(session, "db_offline")

        filters = self._extract_product_filters(message)
        keyword = self._extract_search_keyword(message)
        if not keyword and session.get("last_search_keyword"):
            keyword = session["last_search_keyword"]
            if not filters and session.get("last_product_filters"):
                filters = dict(session["last_product_filters"])
        if not keyword:
            return self.translate(session, "product_search_prompt")

        products = self.db.search_products(keyword, limit=10, filters=filters)
        if not products:
            return self.translate(session, "product_not_found", keyword=keyword)

        exclude_ids = [int(p["id"]) for p in products if p.get("id") is not None]
        recommendations = []
        if hasattr(self.db, "get_related_products"):
            recommendations = self.db.get_related_products(keyword, exclude_ids=exclude_ids, limit=4)

        session["last_search_keyword"] = keyword
        session["last_product_filters"] = filters
        session["last_products"] = products
        session["last_product"] = products[0]
        return self._format_product_search_card(products, filters=filters, recommendations=recommendations)

    def handle_add_to_cart_id(self, message: str, session: Dict) -> str:
        """Add a specific product ID directly to cart."""
        m = re.search(r'(?:buy|add|ግዛ|ጨምር)[-_]?(\d+)', message.lower())
        if not m and message.startswith('/buy_'):
            m = re.match(r'/buy_(\d+)', message)

        if not m:
            return self.translate(session, "specify_product_id")

        pid = int(m.group(1))
        if self.db is None:
            return self.translate(session, "cart_db_offline")

        product = self.db.get_product_by_id(pid)
        if not product:
            return self.translate(session, "product_id_not_found", pid=pid)

        user_id = session.get("user_id", "default")
        self.add_to_cart(user_id, product["name"])
        session["last_product"] = product
        cart_count = len(session.get("cart", []))
        return self.translate(
            session, "cart_added_checkout_ready",
            product_name=product["name"], cart_count=cart_count
        )

    def handle_add_last_product(self, message: str, session: Dict) -> str:
        """Add the most recently viewed product to cart."""
        product = session.get("last_product")
        if not product:
            return self.translate(session, "specify_product_id")

        user_id = session.get("user_id", "default")
        self.add_to_cart(user_id, product["name"])
        cart_count = len(session.get("cart", []))
        return self.translate(
            session, "cart_added_generic",
            product_name=product["name"], cart_count=cart_count
        )

    def handle_product_followup(self, message: str, session: Dict) -> str:
        """Answer follow-up questions about the last viewed product."""
        product = session.get("last_product")
        if not product:
            return self.translate(session, "product_id_not_found", pid="")

        message_lower = message.lower()
        price = float(product.get("unit_price", 0))
        stock = product.get("current_stock", 0)
        name = product.get("name", "that item")

        if any(w in message_lower for w in ["price", "cost", "how much", "ዋጋ", "ስንት"]):
            stock_status = self.translate(session, "in_stock_msg") if stock else self.translate(session, "out_of_stock_msg")
            return self.translate(
                session, "product_price_status",
                name=name, price=f"{price:,.2f}", stock_status=stock_status
            )

        raw_details = product.get("details") or ""
        clean_desc = re.sub(r'<[^>]*>', '', raw_details).strip()
        if not clean_desc:
            shop_name = os.getenv("SHOP_NAME", "GojoShop.et")
            clean_desc = f"A quality item from {shop_name}."

        details_truncated = clean_desc[:180] + ("..." if len(clean_desc) > 180 else "")
        return self.translate(
            session, "product_details_more",
            name=name, price=f"{price:,.2f}", stock=(stock if stock is not None else 0), details=details_truncated
        )

    def handle_repeat_search(self, message: str, session: Dict) -> str:
        """Re-run the last product search."""
        keyword = session.get("last_search_keyword")
        if not keyword:
            return self.translate(session, "repeat_search_empty")
        filter_phrase = self._format_filter_phrase(session.get("last_product_filters", {}))
        return self.handle_product_search(f"search {keyword} {filter_phrase}", session)

    def handle_shipping(self, message: str, session: Dict) -> str:
        return self.translate(session, "shipping_info")

    def handle_returns(self, message: str, session: Dict) -> str:
        return self.translate(session, "returns_info")

    def handle_payment(self, message: str, session: Dict) -> str:
        return self.translate(session, "payment_info")

    def handle_warranty(self, message: str, session: Dict) -> str:
        return self.translate(session, "warranty_info")

    def handle_checkout(self, message: str, session: Dict) -> str:
        user_id = session.get("user_id", "default")
        # Sync cart from database
        self.get_cart(user_id)
        
        if self.db is not None and hasattr(self.db, "get_cart_details"):
            details = self.db.get_cart_details(user_id)
            items = details.get("items", [])
            total_price = details.get("total_price", 0.0)
            
            if not items:
                return self.translate(session, "checkout_empty")
                
            item_lines = ""
            for item in items:
                item_lines += f"\n• {item['name']} × {item['quantity']}  —  {item['subtotal']:,.2f} ETB"
                
            return self.translate(
                session, "checkout_summary",
                item_lines=item_lines, total_price=f"{total_price:,.2f}"
            )
            
        cart_items = session.get("cart", [])
        if not cart_items:
            return self.translate(session, "checkout_empty")
        return self.translate(session, "checkout_count", cart_len=len(cart_items))

    def handle_help(self, message: str, session: Dict) -> str:
        return self.translate(session, "help_info")

    def handle_human_support(self, message: str, session: Dict) -> str:
        """Hand off to a human support agent."""
        user_id = session.get("user_id", "unknown")
        already_requested = session.get("human_support_requested", False)
        self.log_support_request(user_id, message, session)

        shop = os.getenv("SHOP_NAME", "GojoShop.et")
        if already_requested:
            intro_keys = [
                "human_support_already_requested_1",
                "human_support_already_requested_2",
                "human_support_already_requested_3"
            ]
        else:
            intro_keys = [
                "human_support_request_1",
                "human_support_request_2",
                "human_support_request_3"
            ]
        intro = self.translate(session, random.choice(intro_keys))

        context_note = ""
        if session.get("last_order_id"):
            context_note = self.translate(session, "human_support_order_note", order_id=session['last_order_id'])
        elif session.get("last_search_keyword"):
            context_note = self.translate(session, "human_support_search_note", keyword=session['last_search_keyword'])

        return intro + context_note + "\n\n" + self._format_support_card(shop, session)

    def _format_support_card(self, shop: str, session: Dict) -> str:
        """Rich support card with contact options."""
        email = os.getenv("SHOP_SUPPORT_EMAIL", "support@gojoshop.et")
        phone = os.getenv("SHOP_SUPPORT_PHONE", "+251911234567")
        hours = os.getenv("SHOP_SUPPORT_HOURS", "Mon–Sat, 9:00 AM – 6:00 PM EAT")
        note = self.translate(session, "human_support_note")

        return (
            "━━━ HUMAN SUPPORT ━━━\n"
            f"Shop: {shop}\n"
            f"Email: {email}\n"
            f"Phone: {phone}\n"
            f"Hours: {hours}\n"
            f"Note: {note}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
    def handle_farewell(self, message: str, session: Dict) -> str:
        shop = os.getenv("SHOP_NAME", "GojoShop.et")
        if self._is_negative(message.lower().strip()):
            farewells_neg = [
                self.translate(session, "farewell_negative_1"),
                self.translate(session, "farewell_negative_2"),
                self.translate(session, "farewell_negative_3"),
            ]
            return random.choice(farewells_neg)
        farewells = [
            self.translate(session, "farewell_1", shop=shop),
            self.translate(session, "farewell_2", shop=shop),
            self.translate(session, "farewell_3", shop=shop),
        ]
        return random.choice(farewells)

    def handle_general(self, message: str, session: Dict) -> str:
        if session.get("last_search_keyword"):
            kw = session["last_search_keyword"]
            return self.translate(session, "general_search_kw", kw=kw)
        if session.get("last_order_id"):
            return self.translate(session, "general_order_context", order_id=session['last_order_id'])
        if session.get("cart"):
            return self.translate(session, "general_cart_items", cart_len=len(session['cart']))
        return self.translate(session, "general_help")

    # ------------------------------------------------------------------
    # Order lookup handlers
    # ------------------------------------------------------------------

    def handle_order_lookup(self, message: str, session: Dict) -> str:
        """Look up an order by ID from the database."""
        # Extract order ID from message
        order_id_raw = self._extract_order_id(message)

        if not order_id_raw:
            return self.translate(session, "order_lookup_prompt")

        if self.db is None:
            return self.translate(session, "order_lookup_db_offline")

        order = self.db.get_order(order_id_raw)

        if order is None:
            return self.translate(session, "order_lookup_not_found", order_id=order_id_raw.upper())

        # Store in session for follow-ups
        session["last_order_id"] = order["id"]

        items = self.db.get_order_items(order["id"])
        return self._format_order_card(order, items, session)

    def handle_order_followup(self, message: str, session: Dict) -> str:
        """Handle follow-up questions about the last looked-up order."""
        order_id = session.get("last_order_id")
        if not order_id or self.db is None:
            return self.translate(session, "order_lookup_prompt")

        order = self.db.get_order(order_id)
        if not order:
            return self.translate(session, "order_lookup_not_found", order_id=order_id)

        items = self.db.get_order_items(order_id)
        return self._format_order_card(order, items, session)

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def _extract_order_id(self, message: str) -> str | None:
        """
        Pull an order ID out of free text.
        Accepts: ORD-1001 / ord 1001 / #1001 / 1001
        Returns the raw matched string (normalised by DatabaseManager).
        """
        patterns = [
            r'\b(ORD[-_\s]?\d+)\b',   # ORD-1001 or ORD 1001
            r'#(\d{4,})',             # #1001
            r'\b(\d{4,})\b',         # bare 4+ digit number
        ]
        for pattern in patterns:
            m = re.search(pattern, message, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _status_emoji(status: str) -> str:
        return {
            "pending":    "🕐",
            "processing": "⚙️",
            "shipped":    "🚚",
            "delivered":  "✅",
            "cancelled":  "❌",
            "canceled":   "❌",
        }.get(status, "📦")

    def _format_order_card(self, order: dict, items: list, session: Dict) -> str:
        """Format order info as a rich text card for the chat bubble."""
        status      = order.get("order_status", order.get("status", "unknown"))
        emoji       = self._status_emoji(status)
        total       = order.get("order_amount", order.get("total_amount", 0))
        tracking    = order.get("tracking_number") or "Not yet assigned"
        address     = order.get("shipping_address", order.get("delivery_address", "N/A"))
        customer    = order.get("customer_name", "Customer")
        phone       = order.get("customer_phone", "N/A")
        email       = order.get("customer_email", "N/A")
        payment     = order.get("payment_method", "N/A")
        pay_status  = order.get("payment_status", "N/A")
        created     = order.get("created_at")
        updated     = order.get("updated_at")
        created_str = created.strftime("%b %d, %Y %I:%M %p") if created else "N/A"
        updated_str = updated.strftime("%b %d, %Y %I:%M %p") if updated else "N/A"
        order_note  = order.get("order_note", "N/A")
        expected_delivery = order.get("expected_delivery_date")
        expected_str = expected_delivery.strftime("%b %d, %Y") if expected_delivery else "N/A"
        transaction_ref = order.get("transaction_ref", "N/A")
        seller_info = order.get("seller_is", "N/A")
        
        # Cancellation info
        cancel_reason = order.get("cancel_reason", "N/A")
        cancel_cause = order.get("cancel_cause", "N/A")
        
        item_lines = ""
        for it in items:
            subtotal = float(it["unit_price"]) * int(it["quantity"])
            item_delivery_status = it.get("delivery_status", "pending")
            item_emoji = self._status_emoji(item_delivery_status)
            product_id = it.get("product_id", "N/A")
            variant = it.get("variant", "N/A")
            item_lines += f"\n  • {it['product_name']} × {it['quantity']}  —  {subtotal:,.2f} ETB {item_emoji}"
            if product_id != "N/A":
                item_lines += f" (ID: {product_id})"
            if variant != "N/A":
                item_lines += f" [Variant: {variant}]"

        card = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Order #{order['id']}\n"
            f"👤 {customer}\n"
            f"📱 {phone}\n"
            f"📧 {email}\n"
            f"📅 Placed: {created_str}\n"
            f"🔄 Updated: {updated_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Status: {emoji} {status.upper()}\n"
            f"Tracking: {tracking}\n"
            f"Expected: {expected_str}\n"
            f"Delivery to: {address}\n"
            f"📝 Note: {order_note}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛍️ Items:{item_lines}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 Payment: {payment}  [{pay_status}]\n"
            f"🔢 Transaction: {transaction_ref}\n"
            f"💰 Total: {float(total):,.2f} ETB\n"
            f"🏢 Seller: {seller_info}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        )

        # Add cancellation info if applicable
        if status in ("canceled", "cancelled"):
            card += f"❌ Cancellation Reason: {cancel_reason}\n"
            if cancel_cause != "N/A":
                card += f"🔍 Cancel Cause ID: {cancel_cause}\n"
            card += self.translate(session, "refund_note")

        # Add status-specific message
        status_norm = "cancelled" if status in ("cancelled", "canceled") else status
        status_key = f"order_status_{status_norm}"
        card += self.translate(session, status_key)
        return card

    # ------------------------------------------------------------------
    # Product search helpers
    # ------------------------------------------------------------------

    def _extract_search_keyword(self, message: str) -> str | None:
        """Extract a product search keyword from the message."""
        message_lower = message.lower().strip()

        # Strip common filler phrases to isolate the keyword
        filler = [
            r"^(show me|search for|find|i'm looking for|looking for|i want to buy|want to buy|i want|i need to buy|need to buy|do you have|"
            r"can i get|i need|buy|get me|what about|tell me about|ፈልግ|አሳይ|እፈልጋለሁ|ግዛ)\s+",
            r"\s+(please|pls|now|today|asap)$",
            r"\b(a|an|the|some|any)\b\s*",
        ]
        kw = message_lower
        for pat in filler:
            kw = re.sub(pat, "", kw, flags=re.IGNORECASE).strip()

        # Remove filter phrases so they don't pollute the keyword
        kw = re.sub(
            r"\b(under|below|above|over|max|min|cheaper than|more than|less than|"
            r"in stock|available|cheapest|newest|sort by|price asc|price desc)\b.*",
            "", kw, flags=re.IGNORECASE
        ).strip()
        kw = re.sub(r"\s{2,}", " ", kw).strip()

        # Must be at least 2 characters and not a pure number
        if len(kw) >= 2 and not kw.isdigit():
            return kw
        return None

    def _extract_product_filters(self, message: str) -> dict:
        """Extract price / stock / sort filters from the message."""
        filters: dict = {}
        message_lower = message.lower()

        # Price filters: "under 500", "below 1000", "max 2000"
        m = re.search(r"\b(?:under|below|less than|max(?:imum)?|ቢበዛ)\s*(\d+[\d,]*)", message_lower)
        if m:
            filters["max_price"] = float(m.group(1).replace(",", ""))

        m = re.search(r"\b(?:above|over|more than|min(?:imum)?|at least|ቢያንስ)\s*(\d+[\d,]*)", message_lower)
        if m:
            filters["min_price"] = float(m.group(1).replace(",", ""))

        # Stock filter
        if re.search(r"\b(in stock|available|ክምችት ላይ|available now)\b", message_lower):
            filters["in_stock"] = True

        # Sort filter
        if re.search(r"\b(cheapest|lowest price|cheapest first|price asc|ርካሽ)\b", message_lower):
            filters["sort"] = "price_asc"
        elif re.search(r"\b(most expensive|highest price|price desc|ውድ)\b", message_lower):
            filters["sort"] = "price_desc"
        elif re.search(r"\b(newest|latest|new arrivals|አዲስ)\b", message_lower):
            filters["sort"] = "newest"

        return filters

    def _format_filter_phrase(self, filters: dict) -> str:
        """Convert a filters dict back into a natural language phrase for re-search."""
        parts = []
        if "min_price" in filters:
            parts.append(f"above {filters['min_price']:.0f}")
        if "max_price" in filters:
            parts.append(f"under {filters['max_price']:.0f}")
        if filters.get("in_stock"):
            parts.append("in stock")
        if filters.get("sort") == "price_asc":
            parts.append("cheapest")
        elif filters.get("sort") == "price_desc":
            parts.append("most expensive")
        elif filters.get("sort") == "newest":
            parts.append("newest")
        return " ".join(parts)

    def _format_product_search_card(
        self, products: list, filters: dict = None, recommendations: list = None
    ) -> str:
        """Format product search results as a structured card string for the frontend."""
        filters = filters or {}
        recommendations = recommendations or []

        filter_parts = []
        if "min_price" in filters:
            filter_parts.append(f"min_price={filters['min_price']:.0f}")
        if "max_price" in filters:
            filter_parts.append(f"max_price={filters['max_price']:.0f}")
        if filters.get("in_stock"):
            filter_parts.append("in_stock=true")
        if "sort" in filters:
            filter_parts.append(f"sort={filters['sort']}")
        filters_str = ";".join(filter_parts) if filter_parts else "none"

        def product_block(p):
            price = p.get("unit_price", p.get("price", 0))
            try:
                price_fmt = f"{float(price):,.2f} ETB"
            except (TypeError, ValueError):
                price_fmt = str(price)
            stock = p.get("current_stock", p.get("stock", 0))
            image = p.get("thumbnail", p.get("image", "def.png"))
            details = re.sub(r"<[^>]*>", "", str(p.get("description", p.get("details", "")))).strip()
            return (
                f"Product ID: {p.get('id', '')}\n"
                f"Name: {p.get('name', '')}\n"
                f"Price: {price_fmt}\n"
                f"Stock: {stock}\n"
                f"Image: {image}\n"
                f"Details: {details[:200]}"
            )

        blocks = "\n---\n".join(product_block(p) for p in products)
        card = f"PRODUCT SEARCH\nFilters: {filters_str}\n{blocks}"

        if recommendations:
            rec_blocks = "\n---\n".join(product_block(p) for p in recommendations)
            card += f"\nRECOMMENDATIONS\n{rec_blocks}"

        return card

    # ------------------------------------------------------------------
    # Cart helpers
    # ------------------------------------------------------------------

    def add_to_cart(self, user_id: str, product: str) -> str:
        """Add product to user's cart (auto-creates session if needed)."""
        self._ensure_session(user_id)
        if self.db is not None and hasattr(self.db, "add_item_to_cart"):
            success = self.db.add_item_to_cart(user_id, product)
            if success:
                # Sync session in-memory state
                if hasattr(self.db, "get_cart_items_by_user"):
                    self.user_sessions[user_id]["cart"] = self.db.get_cart_items_by_user(user_id)
                return f"Added {product} to your cart! 🛒"
        
        self.user_sessions[user_id]["cart"].append(product)
        return f"Added {product} to your cart! 🛒"

    def get_cart(self, user_id: str) -> List[str]:
        """Get user's cart items (auto-creates session if needed)."""
        self._ensure_session(user_id)
        if self.db is not None and hasattr(self.db, "get_cart_items_by_user"):
            cart_items = self.db.get_cart_items_by_user(user_id)
            self.user_sessions[user_id]["cart"] = cart_items
            return cart_items
        return self.user_sessions[user_id]["cart"]
