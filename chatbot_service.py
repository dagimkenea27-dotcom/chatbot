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

    def _ensure_session(self, user_id: str):
        """Initialize session if it doesn't exist yet."""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
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
                "cart": []
            }
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
            "yes", "yeah", "yep", "sure", "ok", "okay", "please", "y", "correct", "right"
        }

    def _is_negative(self, message: str) -> bool:
        return message.lower().strip() in {"no", "nope", "nah", "not really", "n"}

    def _references_last_item(self, message: str) -> bool:
        message_lower = message.lower()
        return any(
            phrase in message_lower
            for phrase in [
                "that one", "this one", "the first", "first one", "second one",
                "add it", "buy it", "get it", "purchase it", "order it",
                "how much is it", "tell me more", "more about it", "about that",
            ]
        ) or message_lower.strip() in {"it", "that", "this"}

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

        # Check for command to exit support mode
        if message.lower().strip() in {"exit", "reset", "stop support"}:
            active_req = self.get_active_support_request(user_id)
            if active_req:
                active_req["status"] = "resolved"
                active_req["updated_at"] = datetime.now().isoformat()
                session["human_support_requested"] = False
                return "Support session ended. AI Chatbot is back! How can I help you now?"

        # Check if user is actively in a live support request session
        active_req = self.get_active_support_request(user_id)
        if active_req:
            # Add message to support chat history
            self.add_support_chat_message(active_req["id"], "user", message)
            # Return special token to indicate support mode
            return "[SUPPORT_MODE]"

        intent = self.detect_intent(message, session)
        session["last_intent"] = session.get("current_intent")
        session["current_intent"] = intent

        response = self.generate_response(intent, message, session)
        response = self._wrap_natural(response, session, intent)
        self._record_turn(session, "assistant", response, intent)
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
            if any(w in message_lower for w in ["add", "buy", "get", "purchase", "order"]):
                return "add_last_product"
            return "product_followup"

        if session.get("last_search_keyword") and any(
            phrase in message_lower
            for phrase in ["show more", "more options", "anything else", "other options", "see more"]
        ):
            return "repeat_search"

        if session.get("last_order_id") and any(
            w in message_lower for w in ["status", "arrive", "when", "delivery", "update", "still", "delayed", "where is it"]
        ):
            return "order_followup"

        # --- Human support / escalation ---
        if self._wants_human_support(message_lower):
            return "human_support"
        if session.get("human_support_requested") and self._is_affirmative(message_lower):
            return "human_support"

        # --- Direct buy / add to cart commands (e.g. /buy_85 or buy 85) ---
        if re.search(r'\b(buy|add)[-_\s]?(\d+)\b', message_lower) or message_lower.startswith('/buy_'):
            return "add_to_cart_id"

        if self._extract_product_filters(message_lower) and self._extract_search_keyword(message_lower):
            return "product_search"

        # --- Order lookup ---
        # Explicit order ID pattern: ORD-XXXX, #XXXX, or bare digits 4+
        if re.search(r'\b(ord[-\s]?\d+|#\d{4,}|\d{4,})\b', message_lower):
            return "order_lookup"
        # Order-related phrases (with prior order context = follow-up)
        if any(w in message_lower for w in ["my order", "order status", "track", "tracking", "where is my", "order number"]):
            return "order_lookup"
        # Follow-up on previously looked-up order
        if session.get("last_order_id") and any(
            w in message_lower for w in ["status", "arrive", "when", "delivery", "update", "still", "delayed"]
        ):
            return "order_followup"

        # --- Payment (before checkout to avoid collision) ---
        if any(w in message_lower for w in ["telebirr", "amole"]):
            return "payment"

        # --- Product search and buy intents ---
        if any(w in message_lower for w in ["buy", "purchase", "order", "price", "cost", "search", "find", "looking for", "recommend", "show me"]):
            return "product_search"
        if any(w in message_lower for w in ["cart", "checkout"]):
            return "checkout"

        # --- Support ---
        if any(w in message_lower for w in ["shipping", "delivery", "arrive"]):
            return "shipping"
        if any(w in message_lower for w in ["return", "refund", "exchange", "defective"]):
            return "returns"
        if any(w in message_lower for w in ["payment", "pay", "card", "visa", "mastercard"]):
            return "payment"
        if any(w in message_lower for w in ["warranty", "repair", "broken", "damage"]):
            return "warranty"

        # --- General ---
        if any(w in message_lower for w in ["help", "support", "assist", "problem"]):
            return "help"
        if any(w in message_lower for w in ["hello", "hi", "hey", "good morning", "selam"]):
            return "greeting"
        if any(w in message_lower for w in ["bye", "goodbye", "see you", "thanks", "thank"]):
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
        ]
        return any(phrase in message_lower for phrase in phrases)

    def log_support_request(self, user_id: str, message: str, session: Dict) -> Dict:
        """Record a human-support handoff for follow-up."""
        entry = {
            "id": f"SUP-{len(self.support_requests) + 1:05d}",
            "status": "open",
            "user_id": user_id,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "last_intent": session.get("current_intent"),
            "last_order_id": session.get("last_order_id"),
            "last_search_keyword": session.get("last_search_keyword"),
            "cart": list(session.get("cart", [])),
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
        for req in reversed(self.support_requests):
            if req.get("user_id") == user_id and req.get("status") in {"open", "in_progress"}:
                return req
        return None

    def add_support_chat_message(self, request_id: str, sender: str, text: str) -> Optional[Dict]:
        """Add a message to the support chat history."""
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


    def update_support_request_status(self, request_id: str, status: str) -> Dict | None:
        """Update an in-memory support request status for the admin page."""
        if status not in {"open", "in_progress", "resolved"}:
            return None
        for request in self.support_requests:
            if request.get("id") == request_id:
                request["status"] = status
                request["updated_at"] = datetime.now().isoformat()
                return request
        return None

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
            return (
                f"Welcome back to {shop}! 👋\n"
                f"Still thinking about **{session['last_search_keyword']}**, or looking for something else?"
            )
        if is_returning and session.get("cart"):
            return (
                f"Hey again! 👋 You still have **{len(session['cart'])} item(s)** in your cart. "
                "Want to keep shopping or head to checkout?"
            )
        if is_returning:
            return f"Hey, welcome back to {shop}! 👋 What can I help you with today?"

        greetings = [
            f"👋 Hello! Welcome to {shop}! I'm here to help you find products, track orders, or answer any questions.",
            f"ሰላም! Welcome to {shop}! What are you shopping for today?",
            f"Hey there! 👋 I'm your {shop} assistant. Tell me what you're looking for and I'll help you out.",
        ]
        return random.choice(greetings)

    def handle_product_search(self, message: str, session: Dict) -> str:
        if self.db is None:
            return "⚠️ Live product database is currently offline. Please try again later."

        filters = self._extract_product_filters(message)
        keyword = self._extract_search_keyword(message)
        if not keyword and session.get("last_search_keyword"):
            keyword = session["last_search_keyword"]
            if not filters and session.get("last_product_filters"):
                filters = dict(session["last_product_filters"])
        if not keyword:
            return (
                "🔍 What kind of products are you looking for?\n"
                "We have an extensive catalog including Teddy Bears, handmade earrings, leather bags, coasters, and baby shoes!"
            )

        products = self.db.search_products(keyword, limit=10, filters=filters)
        if not products:
            return (
                f"🔍 I couldn't find anything matching **\"{keyword}\"** right now.\n"
                "You could try \"bear\", \"earring\", \"bag\", or \"shoes\" — or describe what you need in your own words."
            )

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
        m = re.search(r'(?:buy|add)[-_]?(\d+)', message.lower())
        if not m and message.startswith('/buy_'):
            m = re.match(r'/buy_(\d+)', message)

        if not m:
            return "Which product would you like to add? Please specify the product ID or search for it."

        pid = int(m.group(1))
        if self.db is None:
            return "⚠️ Database offline. Cannot add item by ID."

        product = self.db.get_product_by_id(pid)
        if not product:
            return f"❌ Sorry, I couldn't find a product with ID {pid}."

        user_id = session.get("user_id", "default")
        self.add_to_cart(user_id, product["name"])
        session["last_product"] = product
        cart_count = len(session.get("cart", []))
        return (
            f"🛒 **{product['name']}** is in your cart now! "
            f"You have {cart_count} item(s). Say **checkout** whenever you're ready."
        )

    def handle_add_last_product(self, message: str, session: Dict) -> str:
        """Add the most recently viewed product to cart."""
        product = session.get("last_product")
        if not product:
            return "Which product did you mean? Search for something first, or tell me the product ID."

        user_id = session.get("user_id", "default")
        self.add_to_cart(user_id, product["name"])
        cart_count = len(session.get("cart", []))
        return (
            f"🛒 Added **{product['name']}** to your cart! "
            f"That's {cart_count} item(s) so far. Ready to checkout?"
        )

    def handle_product_followup(self, message: str, session: Dict) -> str:
        """Answer follow-up questions about the last viewed product."""
        product = session.get("last_product")
        if not product:
            return "I'm not sure which product you mean — could you search for it again or share the name?"

        message_lower = message.lower()
        price = float(product.get("unit_price", 0))
        stock = product.get("current_stock", 0)
        name = product.get("name", "that item")

        if any(w in message_lower for w in ["price", "cost", "how much"]):
            return (
                f"**{name}** is **{price:,.2f} ETB**. "
                f"{'We have it in stock!' if stock else 'It may be out of stock right now.'} "
                f"Want me to add it to your cart?"
            )

        raw_details = product.get("details") or ""
        clean_desc = re.sub(r'<[^>]*>', '', raw_details).strip()
        if not clean_desc:
            clean_desc = f"A quality item from {os.getenv('SHOP_NAME', 'GojoShop.et')}."

        return (
            f"Here's more on **{name}**:\n"
            f"• Price: {price:,.2f} ETB\n"
            f"• Stock: {stock if stock is not None else 0}\n"
            f"• {clean_desc[:180]}{'...' if len(clean_desc) > 180 else ''}\n\n"
            f"Say **add it** if you'd like it in your cart."
        )

    def handle_repeat_search(self, message: str, session: Dict) -> str:
        """Re-run the last product search."""
        keyword = session.get("last_search_keyword")
        if not keyword:
            return "What should I search for? Tell me the product type or name you're interested in."
        filter_phrase = self._format_filter_phrase(session.get("last_product_filters", {}))
        return self.handle_product_search(f"search {keyword} {filter_phrase}", session)

    def _extract_product_filters(self, message: str) -> Dict:
        """Extract product filters from natural language."""
        text = message.lower()
        filters: Dict = {}

        under = re.search(r'\b(?:under|below|less than|max|maximum)\s*(?:etb|birr)?\s*(\d+(?:\.\d+)?)', text)
        over = re.search(r'\b(?:over|above|more than|min|minimum)\s*(?:etb|birr)?\s*(\d+(?:\.\d+)?)', text)
        between = re.search(r'\bbetween\s*(\d+(?:\.\d+)?)\s*(?:and|-|to)\s*(\d+(?:\.\d+)?)', text)
        if between:
            low, high = sorted([float(between.group(1)), float(between.group(2))])
            filters["min_price"] = low
            filters["max_price"] = high
        else:
            if under:
                filters["max_price"] = float(under.group(1))
            if over:
                filters["min_price"] = float(over.group(1))

        if any(phrase in text for phrase in ["in stock", "available only", "available now", "not sold out"]):
            filters["in_stock"] = True

        if any(phrase in text for phrase in ["cheapest", "lowest price", "price low", "low to high"]):
            filters["sort"] = "price_asc"
        elif any(phrase in text for phrase in ["expensive", "highest price", "price high", "high to low"]):
            filters["sort"] = "price_desc"
        elif any(phrase in text for phrase in ["newest", "latest", "recent"]):
            filters["sort"] = "newest"

        return filters

    def _extract_search_keyword(self, message: str) -> str:
        """Extract the core search keyword from user message."""
        text = message.lower()
        text = re.sub(r'\bbetween\s*\d+(?:\.\d+)?\s*(?:and|-|to)\s*\d+(?:\.\d+)?', ' ', text)
        text = re.sub(r'\b(?:under|below|less than|max|maximum|over|above|more than|min|minimum)\s*(?:etb|birr)?\s*\d+(?:\.\d+)?', ' ', text)
        text = re.sub(r'\b(?:in stock|available only|available now|not sold out|cheapest|lowest price|price low|low to high|expensive|highest price|price high|high to low|newest|latest|recent)\b', ' ', text)
        text = re.sub(r'[^\w\s]', '', text)
        # Remove common stopwords
        stopwords = {
            "i", "want", "to", "buy", "purchase", "order", "search", "find", "looking", "for", 
            "please", "show", "me", "a", "an", "the", "need", "any", "some", "can", "you", 
            "get", "recommend", "recommendations", "have", "product", "products", "item", "items",
            "filter", "filters", "sort", "by", "only", "etb", "birr"
        }
        words = [w for w in text.split() if w not in stopwords]
        return " ".join(words) if words else ""

    def _format_filter_phrase(self, filters: Dict) -> str:
        parts = []
        if filters.get("min_price") is not None:
            parts.append(f"over {filters['min_price']:g}")
        if filters.get("max_price") is not None:
            parts.append(f"under {filters['max_price']:g}")
        if filters.get("in_stock"):
            parts.append("in stock")
        sort_labels = {
            "price_asc": "cheapest",
            "price_desc": "highest price",
            "newest": "newest",
        }
        if filters.get("sort") in sort_labels:
            parts.append(sort_labels[filters["sort"]])
        return " ".join(parts)

    def _format_filter_meta(self, filters: Dict) -> str:
        if not filters:
            return "none"
        parts = []
        if filters.get("min_price") is not None:
            parts.append(f"min_price={filters['min_price']:g}")
        if filters.get("max_price") is not None:
            parts.append(f"max_price={filters['max_price']:g}")
        if filters.get("in_stock"):
            parts.append("in_stock=true")
        if filters.get("sort"):
            parts.append(f"sort={filters['sort']}")
        return "; ".join(parts)

    def _format_product_block(self, product: Dict) -> str:
        raw_details = product.get("details") or ""
        clean_desc = re.sub(r'<[^>]*>', '', raw_details).strip()
        clean_desc = (clean_desc[:70] + "...") if len(clean_desc) > 70 else clean_desc
        if not clean_desc:
            shop_name = os.getenv("SHOP_NAME", "GojoShop.et")
            clean_desc = f"Quality product from {shop_name}."

        return (
            f"Product ID: {product['id']}\n"
            f"Name: {product['name']}\n"
            f"Price: {float(product['unit_price']):,.2f} ETB\n"
            f"Stock: {product['current_stock'] if product['current_stock'] is not None else 0}\n"
            f"Image: {product['thumbnail'] or 'def.png'}\n"
            f"Details: {clean_desc}\n"
        )

    def _format_product_search_card(
        self,
        products: List[Dict],
        filters: Dict | None = None,
        recommendations: List[Dict] | None = None,
    ) -> str:
        """Format a list of database products into a machine-parseable search card block."""
        filters = filters or {}
        recommendations = recommendations or []
        card = "━━━ PRODUCT SEARCH ━━━\n"
        card += f"Filters: {self._format_filter_meta(filters)}\n"
        for i, p in enumerate(products):
            card += self._format_product_block(p)
            if i < len(products) - 1:
                card += "---\n"
        if recommendations:
            card += "\n━━━ RECOMMENDATIONS ━━━\n"
            for i, rec in enumerate(recommendations):
                card += self._format_product_block(rec)
                if i < len(recommendations) - 1:
                    card += "---\n"
        card += "━━━━━━━━━━━━━━━━━━━━━━"
        return card

    def handle_shipping(self, message: str, session: Dict) -> str:
        return """🚚 Shipping Information:
• Standard delivery: 2-5 business days (Free over 5000 ETB)
• Express delivery: 1-2 business days (300 ETB)
• Same-day delivery available in Addis Ababa (500 ETB)
• Track your order with the tracking number sent to your email

Would you like to check delivery status for your order?"""

    def handle_returns(self, message: str, session: Dict) -> str:
        return """🔄 Return Policy:
• 30-day return window from delivery date
• Items must be unused and in original packaging
• Free returns for defective items
• Restocking fee for non-defective returns

To start a return, visit your orders page or contact our support team."""

    def handle_payment(self, message: str, session: Dict) -> str:
        return """💳 Payment Methods:
• Telebirr - Quick and easy
• Amole - Available at any branch
• Credit/Debit Cards (Visa, Mastercard)
• Cash on Delivery

All payments are secure and encrypted. Need help with a specific payment method?"""

    def handle_warranty(self, message: str, session: Dict) -> str:
        return """🔧 Warranty Information:
• 1-year manufacturer warranty on all electronics
• 6-month warranty on clothing and accessories
• Extended warranty available for purchase (up to 3 years)
• Warranty covers manufacturing defects, not accidental damage

For warranty claims, visit our store or contact support with your receipt."""

    def handle_checkout(self, message: str, session: Dict) -> str:
        user_id = session.get("user_id", "default")
        # Sync cart from database
        self.get_cart(user_id)
        
        if self.db is not None and hasattr(self.db, "get_cart_details"):
            details = self.db.get_cart_details(user_id)
            items = details.get("items", [])
            total_price = details.get("total_price", 0.0)
            
            if not items:
                return "Your cart is empty. Would you like to browse our products?"
                
            item_lines = ""
            for item in items:
                item_lines += f"\n• {item['name']} × {item['quantity']}  —  {item['subtotal']:,.2f} ETB"
                
            return (
                f"🛒 **Your Cart Summary:**\n"
                f"{item_lines}\n\n"
                f"💰 **Total Amount: {total_price:,.2f} ETB**\n\n"
                f"Would you like to proceed to checkout? I can help you with payment and delivery details."
            )
            
        cart_items = session.get("cart", [])
        if not cart_items:
            return "Your cart is empty. Would you like to browse our products?"
        return f"You have {len(cart_items)} item(s) in your cart. Proceed to checkout? I can help you with payment and delivery."

    def handle_help(self, message: str, session: Dict) -> str:
        return """🆘 How can I help you?
Here's what I can assist with:
1. 📱 Product search and recommendations
2. 🛒 Purchasing and checking out
3. 🚚 Shipping and delivery status
4. 🔄 Returns and exchanges
5. 💳 Payment methods
6. 🔧 Warranty information
7. 📦 Order tracking — just share your Order ID (e.g. ORD-1001)

If you'd rather speak with a person, just say **"talk to human"** and I'll connect you with our support team."""

    def handle_human_support(self, message: str, session: Dict) -> str:
        """Hand off to a human support agent."""
        user_id = session.get("user_id", "unknown")
        already_requested = session.get("human_support_requested", False)
        self.log_support_request(user_id, message, session)

        shop = os.getenv("SHOP_NAME", "GojoShop.et")
        if already_requested:
            intro = random.choice([
                "I've flagged your chat for our support team. ",
                "No problem — a real person can take it from here. ",
                "Understood. I'm connecting you with our team now. ",
            ])
        else:
            intro = random.choice([
                "Of course — sometimes it's better to talk to a real person. ",
                "Sure, I'll get you to our support team. ",
                "Absolutely. Let me connect you with someone from our team. ",
            ])

        context_note = ""
        if session.get("last_order_id"):
            context_note = f"\nI've noted you were asking about order **{session['last_order_id']}**."
        elif session.get("last_search_keyword"):
            context_note = f"\nI've noted you were looking at **{session['last_search_keyword']}**."

        return intro + context_note + "\n\n" + self._format_support_card(shop)

    def _format_support_card(self, shop: str) -> str:
        """Rich support card with contact options."""
        email = os.getenv("SHOP_SUPPORT_EMAIL", "support@gojoshop.et")
        phone = os.getenv("SHOP_SUPPORT_PHONE", "+251911234567")
        hours = os.getenv("SHOP_SUPPORT_HOURS", "Mon–Sat, 9:00 AM – 6:00 PM EAT")

        return (
            "━━━ HUMAN SUPPORT ━━━\n"
            f"Shop: {shop}\n"
            f"Email: {email}\n"
            f"Phone: {phone}\n"
            f"Hours: {hours}\n"
            "Note: A support agent will follow up on this chat as soon as possible.\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )

    def handle_farewell(self, message: str, session: Dict) -> str:
        shop = os.getenv("SHOP_NAME", "GojoShop.et")
        if self._is_negative(message.lower().strip()):
            return random.choice([
                "No worries at all! Let me know if you change your mind. 😊",
                "That's okay — I'm here whenever you need help.",
                "Alright! Feel free to ask if anything else comes up.",
            ])
        farewells = [
            f"Thank you for stopping by {shop}! Come back anytime! 🛍️",
            "You're welcome! Have a great day! 👋",
            f"Thanks for chatting — hope to see you again at {shop}!",
        ]
        return random.choice(farewells)

    def handle_general(self, message: str, session: Dict) -> str:
        if session.get("last_search_keyword"):
            kw = session["last_search_keyword"]
            return (
                f"I can tell you more about **{kw}**, help you add something to your cart, "
                "or answer questions about shipping, returns, and orders.\n\n"
                "What would you like to do next?"
            )
        if session.get("last_order_id"):
            return (
                f"We were just looking at order **{session['last_order_id']}**. "
                "Ask about its status, delivery, or start a new search — whatever you need."
            )
        if session.get("cart"):
            return (
                f"You have **{len(session['cart'])} item(s)** in your cart. "
                "I can help you checkout, find more products, or answer shop questions."
            )
        return """I'm here to help! You can ask me things like:
• "Show me leather bags" — product search
• "Track order ORD-1001" — order status
• "Shipping info" or "return policy"
• "Checkout" when you're ready to buy
• "Talk to human" — speak with our support team

What would you like to know?"""

    # ------------------------------------------------------------------
    # Order lookup handlers
    # ------------------------------------------------------------------

    def handle_order_lookup(self, message: str, session: Dict) -> str:
        """Look up an order by ID from the database."""
        # Extract order ID from message
        order_id_raw = self._extract_order_id(message)

        if not order_id_raw:
            return (
                "📦 Sure! Please share your Order ID to track your order.\n"
                "It looks like: **ORD-1001** (found in your confirmation email or SMS)."
            )

        if self.db is None:
            return (
                "⚠️ Order lookup is temporarily unavailable. "
                "Please contact support at support@gojoshop.et or call +251911234567."
            )

        order = self.db.get_order(order_id_raw)

        if order is None:
            return (
                f"❌ I couldn't find an order with ID **{order_id_raw.upper()}**.\n"
                "Please double-check the order ID in your confirmation email or SMS, "
                "or contact us at support@gojoshop.et."
            )

        # Store in session for follow-ups
        session["last_order_id"] = order["id"]

        items = self.db.get_order_items(order["id"])
        return self._format_order_card(order, items)

    def handle_order_followup(self, message: str, session: Dict) -> str:
        """Handle follow-up questions about the last looked-up order."""
        order_id = session.get("last_order_id")
        if not order_id or self.db is None:
            return "Could you share your Order ID? It looks like ORD-1001."

        order = self.db.get_order(order_id)
        if not order:
            return f"I'm having trouble retrieving order {order_id}. Please try again."

        items = self.db.get_order_items(order_id)
        return self._format_order_card(order, items)

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
            r'\b(ORD[-\s]?\d+)\b',   # ORD-1001 or ORD 1001
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
        }.get(status, "📦")

    def _format_order_card(self, order: dict, items: list) -> str:
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
            # Get delivery status for this item if available
            item_delivery_status = it.get("delivery_status", "pending")
            item_emoji = self._status_emoji(item_delivery_status)
            # Include product ID and variant if available
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
        if status == "canceled":
            card += f"❌ Cancellation Reason: {cancel_reason}\n"
            if cancel_cause != "N/A":
                card += f"🔍 Cancel Cause ID: {cancel_cause}\n"
            card += "Refunds are processed within 5 business days."

        # Add status-specific message
        if status == "delivered":
            card += "✅ Your order has been delivered! Enjoying your purchase? 😊"
        elif status == "shipped":
            card += "🚚 Your order is on its way! Expected delivery in 1-2 days."
        elif status == "processing":
            card += "⚙️ We're preparing your order. It will ship soon!"
        elif status == "pending":
            card += "🕐 Your order is confirmed and awaiting processing."
        elif status == "cancelled":
            card += "❌ This order was cancelled. Refunds are processed within 5 business days."

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
