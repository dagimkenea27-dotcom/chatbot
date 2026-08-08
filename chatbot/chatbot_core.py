import os
import re
import random
from datetime import datetime
from typing import Dict, List, Optional, Any

from chatbot.services.conversation_service import ConversationService
from chatbot.services.session_service import SessionService
from chatbot.services.translation_service import TranslationService
from chatbot.services.personality_service import PersonalityService
from chatbot.services.product_service import ProductService
from chatbot.services.order_service import OrderService
from chatbot.services.faq_service import FAQService
from chatbot.services.support_service import SupportService
from chatbot.services.cart_service import CartService
from chatbot.services.promotion_service import PromotionService
from chatbot.nlp.intent_detector import IntentDetector
from chatbot.nlp.entity_extractor import EntityExtractor
from chatbot.nlp.sentiment import SentimentAnalyzer
from chatbot.nlp.transliteration import normalize_transliteration, to_latin
from chatbot.models.memory import ConversationMemory
from chatbot.utils.typing import calc_typing_delay


class GojoShopChatbot:
    """Main chatbot controller that orchestrates all services."""
    
    def __init__(self, db_manager=None):
        self.db = db_manager
        
        # Initialize all services
        self.translation_service = TranslationService()
        self.session_service = SessionService(db_manager)
        self.personality_service = PersonalityService()
        self.product_service = ProductService(db_manager)
        self.order_service = OrderService(db_manager)
        self.faq_service = FAQService()
        self.support_service = SupportService(db_manager)
        self.cart_service = CartService(db_manager)
        self.promotion_service = PromotionService(db_manager)
        self.conversation_service = ConversationService()
        
        # Initialize NLP components
        self.entity_extractor = EntityExtractor()
        self.intent_detector = IntentDetector(entity_extractor=self.entity_extractor)
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # Conversation memory
        self.conversation_memory = ConversationMemory()
        
        # Load data
        self.product_catalog = self.product_service.load_catalog()
        self.faq_data = self.faq_service.load_faq()
        self.translations = self.translation_service.load_translations()

    @property
    def user_sessions(self):
        return self.session_service.user_sessions

    def _ensure_session(self, user_id: str):
        return self.session_service.get_session(user_id)

    def reset_session(self, user_id: str):
        self.session_service.reset_session(user_id)
        active = self.support_service.get_active_request(user_id)
        if active:
            self.support_service.update_status(active["id"], "resolved")

    def calc_typing_delay(self, response: str) -> int:
        return calc_typing_delay(response)

    def get_cart(self, user_id: str) -> List[str]:
        session = self.session_service.get_session(user_id)
        if self.db and hasattr(self.db, "get_cart_items_by_user"):
            return self.cart_service.get_cart(user_id)
        return session.cart

    def add_to_cart(self, user_id: str, product_name: str) -> str:
        self.cart_service.add_item(user_id, product_name)
        session = self.session_service.get_session(user_id)
        if product_name not in session.cart:
            session.cart.append(product_name)
        return f"Added {product_name} to cart"

    def remove_from_cart(self, user_id: str, product_name: str) -> bool:
        """Remove a product the user added by mistake. Returns True if removed."""
        removed = self.cart_service.remove_item(user_id, product_name)
        session = self.session_service.get_session(user_id)
        session.cart = [n for n in session.cart if n != product_name]
        return removed

    def create_order_from_cart(self, user_id: str, checkout_data: dict) -> Optional[Dict]:
        """Programmatic order placement from a cart (API fallback)."""
        if self.db is None or not hasattr(self.db, "create_order"):
            return None
        order = self.db.create_order(user_id, checkout_data)
        if not order:
            return None
        session = self.session_service.get_session(user_id)
        order_id = order.get("id") or order.get("order_id")
        session.last_order_id = order_id
        session.cart = []
        return order

    def list_support_requests(self, limit: int = 50) -> List[Dict]:
        if self.db and hasattr(self.db, "list_support_requests"):
            try:
                db_reqs = self.db.list_support_requests(limit)
                if db_reqs:
                    return db_reqs
            except Exception as e:
                print(f"Error listing support requests from DB: {e}")
        return self.support_service.support_requests[-limit:]

    @property
    def support_requests(self) -> List[Dict]:
        return self.list_support_requests(200)

    def handle_human_support(self, message: str, session) -> str:
        if isinstance(session, str):
            session = self.session_service.get_session(session)
        return self._handle_human_support(message, session)

    def update_support_request_status(self, request_id: str, status: str) -> Optional[Dict]:
        return self.support_service.update_status(request_id, status)

    def add_support_chat_message(self, request_id: str, sender: str, text: str) -> Optional[Dict]:
        return self.support_service.add_message(request_id, sender, text)

    def get_active_support_request(self, user_id: str) -> Optional[Dict]:
        return self.support_service.get_active_request(user_id)

    # ============================================================
    # MAIN ENTRY POINT
    # ============================================================
    
    def get_response(self, user_id: str, message: str) -> str:
        """Main entry point for getting chatbot response."""
        # Get session
        session = self.session_service.get_session(user_id)
        
        # Normalize transliterated Amharic (Latin script) to Ethiopic so the
        # NLP pipeline (language switch, intents, keyword extraction) can
        # understand Ethiopian users typing in Latin letters ("felige neber"
        # for "ፈልጌ ነበር"). The raw message is kept for history / support.
        raw_message = message
        message = normalize_transliteration(message)
        
        # Get conversation context
        conv_context = self.conversation_memory.get_context(user_id)
        conv_context.session = session
        
        # Update session metadata
        session.last_interaction_time = datetime.now().isoformat()
        sentiment = self.sentiment_analyzer.analyze(message)
        session.user_mood = sentiment
        
        # Extract entities
        entities = self.entity_extractor.extract(message, conv_context)
        conv_context.entities.update(entities)
        
        # Extract and update topics
        topics = self.entity_extractor.extract_topics(message)
        if topics:
            session.conversation_topics.extend(topics)
            session.conversation_topics = session.conversation_topics[-20:]
        
        # Load cart
        session.cart = self.get_cart(user_id)
        session.message_count += 1
        self.session_service.record_turn(session, "user", raw_message)
        
        # Track browsing history
        keyword = self.entity_extractor.extract_search_keyword(message)
        if keyword:
            session.browsing_history.append({
                "keyword": keyword,
                "timestamp": datetime.now().isoformat()
            })
            session.browsing_history = session.browsing_history[-30:]
            session.last_viewed_category = self.entity_extractor.categorize_keyword(keyword)
        
        # Name capture
        if (session.message_count <= 2 and not session.user_name
                and not getattr(session, "checkout_pending", False)):
            name = self.entity_extractor.extract_name(message)
            if name:
                session.user_name = name
                self.session_service.save_session(user_id)
                return self._personalized_greeting(session, name)
        
        # Language switch
        lang_result = self._handle_language_switch(message, session)
        if lang_result:
            return lang_result
        
        # Auto-detect Amharic
        if self.entity_extractor.contains_amharic(message):
            session.language = "am"
        
        # Session reset
        reset_result = self._handle_session_reset(user_id, message, session)
        if reset_result:
            return reset_result
        
        # Check for active support request
        active_req = self.support_service.get_active_request(user_id)
        if active_req:
            self.support_service.add_message(active_req['id'], "user", raw_message)
            self.session_service.save_session(user_id)
            return "[SUPPORT_MODE]"
        
        # ---- INTENT DETECTION ----
        intent = self.intent_detector.detect(
            message, session, conv_context, self.session_service
        )
        session.last_intent = session.current_intent
        session.current_intent = intent
        
        # ---- ACTIVE CHECKOUT FLOW ----
        # While the checkout state machine awaits input, route every reply to
        # the checkout handler (except explicit escapes to a human / help, and
        # cart management intents — a user may want to remove a mistakenly
        # added item (or review the cart) even at the confirm step, and the
        # removal must hit the DB BEFORE the order is placed).
        if getattr(session, "checkout_pending", False) and intent not in (
            "human_support", "help", "remove_from_cart", "show_cart"
        ):
            intent = "checkout"
        
        # ---- CLARIFICATION ----
        clarification = self._generate_clarification(
            user_id, message, conv_context, entities
        )
        if clarification and intent == "general":
            self.session_service.record_turn(session, "assistant", clarification, "clarification")
            self.conversation_memory.update_flow(user_id, message, clarification, "clarification")
            self.session_service.save_session(user_id)
            return clarification
        
        # ---- GENERATE RESPONSE ----
        response = self._generate_response(intent, message, session)
        
        # ---- ENHANCE WITH PERSONALITY ----
        response = self.personality_service.apply_enhancement(
            response, session, intent, sentiment
        )
        response = self.personality_service.wrap_natural(response, session, intent)
        
        # ---- PROACTIVE FOLLOW-UP ----
        response = self.conversation_service.add_proactive_followup(
            response, session, intent, conv_context
        )
        
        # ---- RECORD AND SAVE ----
        self.session_service.record_turn(session, "assistant", response, intent)
        self.conversation_memory.update_flow(user_id, message, response, intent)
        self.session_service.save_session(user_id)
        
        return response
    
    # ============================================================
    # INTERNAL HELPERS
    # ============================================================
    
    def _personalized_greeting(self, session, name: str) -> str:
        """Generate a personalized greeting."""
        lang = session.language
        shop = os.getenv("SHOP_NAME", "GojoShop.et")
        
        if lang == "am":
            greetings = [
                f"እንኳን ደህና መጣህ/ሽ {name}! 👋 እኔ ሳሚ ነኝ። ስምህን/ሽን ስላገረኝ ደስ ብሎኛል! ዛሬ በ{shop} ልርዳህ/ሽ? 😊",
                f"ሰላም {name}! 🌟 ቆንጆ ስም ነው! እኔ ሳሚ ነኝ። ዛሬ ምን እንፈልጋለን?",
                f"እሺ {name}! ✨ እንደገና እንገናኛለን! ዛሬ በምን ልርዳህ/ሽ?"
            ]
        else:
            greetings = [
                f"Welcome, {name}! 👋 I'm Sami. It's so nice to put a name to the chat! What brings you to {shop} today? 😊",
                f"Hello {name}! 🌟 That's a lovely name! I'm Sami. What are we shopping for today?",
                f"Hey again {name}! ✨ Good to see you! How can I help you at {shop} today?"
            ]
        return random.choice(greetings)
    
    def _handle_language_switch(self, message: str, session) -> Optional[str]:
        """Handle language switching commands."""
        import re
        lang_match = re.match(r'^/(?:language|lang)\s+(en|am)\b', message.lower().strip())
        if lang_match:
            new_lang = lang_match.group(1)
            session.language = new_lang
            self.session_service.save_session(session.user_id)
            if new_lang == "am":
                return "ቋንቋ ወደ አማርኛ ተቀይሯል። እኔ ሳሚ ነኝ፣ የእርስዎ ረዳት! 😊"
            return "Language set to English. I'm Sami, your shopping assistant! 😊"
        return None
    
    def _handle_session_reset(self, user_id: str, message: str, session) -> Optional[str]:
        """Handle session reset commands."""
        if message.lower().strip() in {"exit", "reset", "stop support"}:
            active_req = self.support_service.get_active_request(user_id)
            if active_req:
                self.support_service.update_status(active_req['id'], "resolved")
                session.human_support_requested = False
                session.current_intent = "general"
                self.session_service.save_session(user_id)
                return self.translation_service.translate(session, "support_ended")
        return None
    
    def _generate_clarification(self, user_id: str, message: str, context, entities) -> Optional[str]:
        """Generate a clarification question when the bot is uncertain."""
        lang = context.session.language if context.session else "en"
        
        if context.turn_count < 1:
            if lang == "am":
                return "ይቅርታ፣ በትክክል አልገባኝም። እባክዎ ትንሽ ተጨማሪ ማብራሪያ መስጠት ይችላሉ? 😊"
            return "Sorry, I didn't quite understand that. Could you give me a bit more context? 😊"
        
        if context.awaiting_followup:
            if lang == "am":
                return "እባክዎ ለጥያቄዬ መልስ ይስጡኝ? 😊"
            return "Could you please answer my question? 😊"
        
        if entities.get("product_type") and not any(w in message.lower() for w in ["buy", "price", "show", "find", "search"]):
            if lang == "am":
                return f"ስለ {entities['product_type']} ጠይቀዋል። ምርቶችን ላሳይዎት፣ ዋጋዎችን ላንግርዎት ወይም ላረዳዎት? 🤔"
            return f"You mentioned {entities['product_type']}. Would you like me to show you products, tell you prices, or help with something else? 🤔"
        
        if message.lower().strip() in ["yes", "no", "yeah", "nope", "አዎ", "አይ"]:
            if context.last_bot_message:
                if lang == "am":
                    return "ልክ ነው! ስለ መጨረሻው ጥያቄዬ ተናገርኩ — እባክዎ መጠየቅ የሚፈልጉትን በአጠቃላይ ሊነግሩኝ ይችላሉ? 😊"
                return "Right! I was asking about the last thing I mentioned — could you tell me more specifically what you're looking for? 😊"
        return None
    
    def _generate_response(self, intent: str, message: str, session) -> str:
        """Generate response based on intent."""
        handlers = {
            "greeting": self._handle_greeting,
            "small_talk": self._handle_small_talk,
            "product_search": self._handle_product_search,
            "purchase": self._handle_product_search,
            "add_to_cart_id": self._handle_add_to_cart_id,
            "add_last_product": self._handle_add_last_product,
            "product_followup": self._handle_product_followup,
            "repeat_search": self._handle_repeat_search,
            "shipping": self._handle_shipping,
            "returns": self._handle_returns,
            "payment": self._handle_payment,
            "warranty": self._handle_warranty,
            "contact": self._handle_contact,
            "hours": self._handle_hours,
            "promotions": self._handle_promotions,
            "loyalty": self._handle_loyalty,
            "cancellation": self._handle_cancellation,
            "checkout": self._handle_checkout,
            "show_cart": self._handle_show_cart,
            "remove_from_cart": self._handle_cart_remove,
            "stock": self._handle_stock,
            "authenticity": self._handle_authenticity,
            "wholesale": self._handle_wholesale,
            "gift": self._handle_gift,
            "invoice": self._handle_invoice,
            "order_change": self._handle_order_change,
            "international": self._handle_international,
            "installment": self._handle_installment,
            "help": self._handle_help,
            "human_support": self._handle_human_support,
            "farewell": self._handle_farewell,
            "order_lookup": self._handle_order_lookup,
            "order_followup": self._handle_order_followup,
            "general": self._handle_general,
        }
        handler = handlers.get(intent, self._handle_general)
        return handler(message, session)
    
    # ============================================================
    # RESPONSE HANDLERS
    # ============================================================
    
    def _handle_greeting(self, message: str, session) -> str:
        shop = os.getenv("SHOP_NAME", "GojoShop.et")
        is_returning = session.message_count > 1
        user_name = session.user_name
        
        if user_name and is_returning:
            if session.last_search_keyword:
                return self.translation_service.translate(
                    session, "welcome_back_search",
                    shop=shop, keyword=session.last_search_keyword
                ).replace("Welcome back", f"Welcome back, {user_name}")
            if session.cart:
                return self.translation_service.translate(
                    session, "welcome_back_cart",
                    shop=shop, cart_len=len(session.cart)
                ).replace("Hey again!", f"Hey again, {user_name}!")
            if is_returning:
                return f"Welcome back, {user_name}! 👋 What can I help you with at {shop} today?"
        
        if is_returning and session.last_search_keyword:
            return self.translation_service.translate(
                session, "welcome_back_search",
                shop=shop, keyword=session.last_search_keyword
            )
        if is_returning and session.cart:
            return self.translation_service.translate(
                session, "welcome_back_cart",
                shop=shop, cart_len=len(session.cart)
            )
        if is_returning:
            return self.translation_service.translate(session, "welcome_back_general", shop=shop)
        
        name_greetings = [
            f"👋 Welcome to {shop}! I'm Sami, your personal shopping assistant. What's your name? 😊",
            f"Hey there! 🌟 I'm Sami from {shop}. Before we start, I'd love to know your name!",
            f"Hello! ✨ I'm Sami, here to help you find amazing products at {shop}. Mind telling me your name?"
        ]
        base = random.choice(name_greetings)
        promo = self.promotion_service.get_featured()
        if promo and not session.promo_aware:
            session.promo_aware = True
            base += "\n\n" + self._promo_card(promo, session, intro_key="promo_greeting_intro")
        return base

    def _promo_card(self, featured: dict, session, intro_key: str = "promo_greeting_intro",
                    intro: Optional[str] = None) -> str:
        """Build a PROMO card string for a featured promo + product."""
        promo, product = featured["promo"], featured["product"]
        if intro is None:
            name = product.get("name", "")
            discount = promo.get("discount", 0) or 0
            intro = self.translation_service.translate(
                session, intro_key, name=name, discount=f"{discount:g}"
            )
        return self.promotion_service.format_promo_card(promo, product, intro=intro)

    def featured_promo_card(self, lang: str = "en") -> Optional[str]:
        """Return the featured live promo card localized to ``lang``, or None.

        Used by the chat frontend to surface an active offer the moment the
        customer opens the chat, without waiting for them to type a greeting.
        """
        from types import SimpleNamespace

        featured = self.promotion_service.get_featured()
        if not featured:
            return None
        promo, product = featured["promo"], featured["product"]
        name = product.get("name", "")
        discount = promo.get("discount", 0) or 0
        session = SimpleNamespace(language=lang if lang in ("en", "am") else "en")
        intro = self.translation_service.translate(
            session, "promo_greeting_intro", name=name, discount=f"{discount:g}"
        )
        return self.promotion_service.format_promo_card(promo, product, intro=intro)
    
    def _handle_small_talk(self, message: str, session) -> str:
        """Handle casual small talk."""
        lang = session.language
        user_name = session.user_name or ""
        name_str = f" {user_name}" if user_name else ""
        name_str_comma = f", {user_name}" if user_name else ""
        message_lower = message.lower()
        
        if "how are you" in message_lower or "how's it going" in message_lower or "እንደምን አለህ" in message_lower:
            if lang == "am":
                responses = [
                    f"እግዚአብሔር ጥሩ ነኝ!{name_str} እርስዎስ? 😊",
                    f"በጣም ደስተኛ ነኝ! ለመርዳት ዝግጁ ነኝ።{name_str} እርስዎስ እንዴት ናቸው? 🌟",
                    f"ደህና ነኝ አመሰግናለሁ!{name_str} ዛሬ ምን አምጥቶዎታል? ☀️"
                ]
            else:
                responses = [
                    f"I'm doing great{name_str_comma}! Thanks for asking! 😊 How about you?",
                    f"I'm absolutely wonderful! I love helping people find great products. How's your day going{name_str_comma}? 🌟",
                    f"Couldn't be better{name_str_comma}! I'm so happy you're here. What's on your mind today? ☀️"
                ]
            return random.choice(responses)
        
        elif "weather" in message_lower or "የአየር" in message_lower:
            if lang == "am":
                return f"አየሩ በአዲስ አበባ በጣም ደስ የሚል ነው እሰማለሁ{name_str}! ☀️ እርስዎስ የት ነዎት?"
            else:
                return f"I hear the weather in Addis Ababa is lovely today{name_str_comma}! ☀️ How's it where you are?"
        
        elif "thank" in message_lower or "አመሰግናለሁ" in message_lower:
            if lang == "am":
                return f"ምንም አይደለም{name_str}! 😊 ሌላ የምረዳው ነገር ካለ እባክዎ ይጠይቁ!"
            else:
                return f"You're very welcome{name_str_comma}! 😊 Let me know if there's anything else I can help with!"
        
        if lang == "am":
            responses = [
                f"እሺ{name_str}! ወደ ጎጆ ሾፕ በደህና መጡ! ምን እየፈለጉ ነው? 😊",
                f"ሰላም{name_str}! ዛሬ እንደምን አለህ/ሽ? የምርት ፍለጋ ልርዳህ/ሽ? 🌟",
                f"ሰላም በሰላም{name_str}! ከእርስዎ ጋር መነጋገር ደስ ብሎኛል! ምን እንፈልጋለን? ✨"
            ]
        else:
            responses = [
                f"Hey{name_str}! 😊 So great to chat with you! What brings you to GojoShop today?",
                f"Hi{name_str}! 🌟 I'm always happy to chat. Are you looking for something specific today?",
                f"Hey there{name_str}! ✨ I love talking to our customers. What can I help you find?"
            ]
        return random.choice(responses)
    
    def _handle_product_search(self, message: str, session) -> str:
        if self.db is None:
            return self.translation_service.translate(session, "db_offline")
        
        filters = self.entity_extractor.extract_product_filters(message)
        keyword = self.entity_extractor.extract_search_keyword(message)
        if not keyword and session.last_search_keyword:
            keyword = session.last_search_keyword
            if not filters and session.last_product_filters:
                filters = dict(session.last_product_filters)
        if not keyword:
            return self.translation_service.translate(session, "product_search_prompt")
        
        products = self.product_service.search_products(keyword, limit=10, filters=filters)
        if not products:
            return self.translation_service.translate(session, "product_not_found", keyword=keyword)
        
        exclude_ids = [int(p["id"]) for p in products if p.get("id") is not None]
        recommendations = self.product_service.get_related_products(keyword, exclude_ids=exclude_ids, limit=4)
        
        session.last_search_keyword = keyword
        session.last_product_filters = filters
        session.last_products = products
        session.last_product = products[0]
        
        return self.product_service.format_search_card(
            products, filters=filters, recommendations=recommendations,
            has_more=len(products) >= 10)
    
    def _handle_add_to_cart_id(self, message: str, session) -> str:
        import re
        m = re.search(r'(?:buy|add|ግዛ|ጨምር)[-_]?(\d+)', message.lower())
        if not m and message.startswith('/buy_'):
            m = re.match(r'/buy_(\d+)', message)
        
        if not m:
            return self.translation_service.translate(session, "specify_product_id")
        
        pid = int(m.group(1))
        if self.db is None:
            return self.translation_service.translate(session, "cart_db_offline")
        
        product = self.product_service.get_product_by_id(pid)
        if not product:
            return self.translation_service.translate(session, "product_id_not_found", pid=pid)
        
        self.cart_service.add_item(session.user_id, product["name"])
        session.last_product = product
        session.cart = self.get_cart(session.user_id)
        cart_count = len(session.cart)
        
        user_name = session.user_name or ""
        base = self.translation_service.translate(
            session, "cart_added_checkout_ready",
            product_name=product["name"], cart_count=cart_count
        )
        if user_name:
            base = base.replace("🛒", f"🛒 Great choice, {user_name}!")
        return base
    
    def _handle_add_last_product(self, message: str, session) -> str:
        product = session.last_product
        if not product:
            return self.translation_service.translate(session, "specify_product_id")
        
        self.cart_service.add_item(session.user_id, product["name"])
        session.cart = self.get_cart(session.user_id)
        cart_count = len(session.cart)
        
        user_name = session.user_name or ""
        praise = random.choice(self.personality_service.personality["catchphrases"].get(
            session.language, 
            self.personality_service.personality["catchphrases"]["en"]
        ))
        
        base = self.translation_service.translate(
            session, "cart_added_generic",
            product_name=product["name"], cart_count=cart_count
        )
        if user_name:
            base = f"{praise} 🛒 {base}"
        return base
    
    def _handle_product_followup(self, message: str, session) -> str:
        product = session.last_product
        if not product:
            return self.translation_service.translate(session, "product_id_not_found", pid="")
        
        message_lower = message.lower()
        price = float(product.get("unit_price", 0))
        stock = product.get("current_stock", 0)
        name = product.get("name", "that item")
        
        if any(w in message_lower for w in ["price", "cost", "how much", "ዋጋ", "ስንት"]):
            stock_status = self.translation_service.translate(
                session, "in_stock_msg" if stock else "out_of_stock_msg"
            )
            user_name = session.user_name or ""
            rec = random.choice(self.personality_service.personality["catchphrases"].get(
                session.language,
                self.personality_service.personality["catchphrases"]["en"]
            ))
            base = self.translation_service.translate(
                session, "product_price_status",
                name=name, price=f"{price:,.2f}", stock_status=stock_status
            )
            if user_name:
                return f"{rec} {base}"
            return base
        
        raw_details = product.get("details") or ""
        clean_desc = re.sub(r'<[^>]*>', '', raw_details).strip()
        if not clean_desc:
            shop_name = os.getenv("SHOP_NAME", "GojoShop.et")
            clean_desc = f"A quality item from {shop_name}."
        
        details_truncated = clean_desc[:180] + ("..." if len(clean_desc) > 180 else "")
        return self.translation_service.translate(
            session, "product_details_more",
            name=name, price=f"{price:,.2f}", stock=stock or 0, details=details_truncated
        )
    
    def _handle_repeat_search(self, message: str, session) -> str:
        keyword = session.last_search_keyword
        if not keyword:
            return self.translation_service.translate(session, "repeat_search_empty")
        filters = session.last_product_filters or {}
        # Page 2+ of an existing search: offset past what has been shown.
        offset = len(session.last_products or [])
        products = self.product_service.search_products(
            keyword, limit=10, filters=filters, offset=offset)
        if not products:
            return self.translation_service.translate(
                session, "no_more_products", keyword=keyword)
        session.last_products = list(session.last_products or []) + products
        if session.last_product is None:
            session.last_product = products[0]
        return self.product_service.format_search_card(
            products, filters=filters, recommendations=[],
            has_more=len(products) >= 10)
    
    def _handle_shipping(self, message: str, session) -> str:
        session.faq_topics_seen.append("shipping")
        return self.translation_service.translate(session, "shipping_info")
    
    def _handle_returns(self, message: str, session) -> str:
        session.faq_topics_seen.append("returns")
        return self.translation_service.translate(session, "returns_info")
    
    def _handle_payment(self, message: str, session) -> str:
        session.faq_topics_seen.append("payment")
        return self.translation_service.translate(session, "payment_info")
    
    def _handle_warranty(self, message: str, session) -> str:
        session.faq_topics_seen.append("warranty")
        return self.translation_service.translate(session, "warranty_info")
    
    def _handle_contact(self, message: str, session) -> str:
        session.faq_topics_seen.append("contact")
        session.contact_count += 1
        return self.translation_service.translate(session, "contact_info")
    
    def _handle_hours(self, message: str, session) -> str:
        session.faq_topics_seen.append("hours")
        return self.translation_service.translate(session, "hours_info")
    
    def _handle_promotions(self, message: str, session) -> str:
        session.faq_topics_seen.append("promotions")
        session.promo_aware = True
        active = self.promotion_service.get_active()
        cards = []
        for promo in active[:3]:
            product = self.promotion_service.get_product(promo.get("product_id"))
            if product:
                cards.append(self.promotion_service.format_promo_card(promo, product))
        if cards:
            intro = self.translation_service.translate(session, "promo_deals_intro")
            return intro + "\n\n" + "\n\n".join(cards)
        return self.translation_service.translate(session, "promotions_info")
    
    def _handle_loyalty(self, message: str, session) -> str:
        session.faq_topics_seen.append("loyalty")
        session.loyalty_aware = True
        return self.translation_service.translate(session, "loyalty_info")
    
    def _handle_stock(self, message: str, session) -> str:
        session.faq_topics_seen.append("stock")
        # If the user asks about a specific product's availability, point to it.
        product_name = session.last_product.get("name") if session.last_product else None
        if product_name and not message.lower().strip().endswith(("stock", "ክምችት")):
            return self.translation_service.translate(
                session, "stock_specific", product=product_name
            )
        return self.translation_service.translate(session, "stock_info")
    
    def _handle_authenticity(self, message: str, session) -> str:
        session.faq_topics_seen.append("authenticity")
        return self.translation_service.translate(
            session, "authenticity_info",
            shop=os.getenv("SHOP_NAME", "GojoShop.et")
        )
    
    def _handle_wholesale(self, message: str, session) -> str:
        session.faq_topics_seen.append("wholesale")
        return self.translation_service.translate(session, "wholesale_info")
    
    def _handle_gift(self, message: str, session) -> str:
        session.faq_topics_seen.append("gift")
        return self.translation_service.translate(session, "gift_info")
    
    def _handle_invoice(self, message: str, session) -> str:
        session.faq_topics_seen.append("invoice")
        return self.translation_service.translate(session, "invoice_info")
    
    def _handle_order_change(self, message: str, session) -> str:
        session.faq_topics_seen.append("order_change")
        return self.translation_service.translate(session, "order_change_info")
    
    def _handle_international(self, message: str, session) -> str:
        session.faq_topics_seen.append("international")
        return self.translation_service.translate(session, "international_info")
    
    def _handle_installment(self, message: str, session) -> str:
        session.faq_topics_seen.append("installment")
        return self.translation_service.translate(session, "installment_info")
    
    def _handle_cancellation(self, message: str, session) -> str:
        lang = session.language
        user_name = session.user_name or ""
        if lang == "am":
            return (f"የትዕዛዝ መሰረዣ ፖሊሲ {user_name}\n\n"
                    f"• ትዕዛዙን ከሰጡ **ከ1 ሰዓት ውስጥ** ወይም ከመላኩ በፊት መሰረዝ ይችላሉ\n"
                    f"• ወዲያውኑ +251988664488 ወይም support@gojoshop.et ያናግሩ\n"
                    f"• ከተላከ በኋላ የመመለሻ ሂደቱን ይጠቀሙ\n\n"
                    f"ትዕዛዝ መለያ ቁጥርዎን ይጋሩ? 📦")
        return (f"Order Cancellation Policy, {user_name}\n\n"
                f"• You can cancel within **1 hour** of ordering, or before it ships\n"
                f"• Contact us at +251988664488 or support@gojoshop.et immediately\n"
                f"• Once shipped, use our return process instead\n\n"
                f"Would you like me to look up your order? 📦")
    
    def _handle_show_cart(self, message: str, session) -> str:
        """Render the user's cart as a ``[CART]`` card with items and total."""
        items = self._load_cart_items(session)
        if not items:
            return self.translation_service.translate(session, "checkout_empty")

        total = sum(sub for _, _, sub in items)
        prompt = self.translation_service.translate(session, "cart_show_prompt")
        return self._render_cart_card(items, total, prompt=prompt)

    def _load_cart_items(self, session) -> List:
        """Return cart items as ``[(name, qty, subtotal), ...]``.

        Prefers live DB pricing via ``get_cart_details``. If the DB reports no
        items, or any item has a zero subtotal, prices are resolved from the
        product catalog so the cart card never shows blank prices.
        """
        items = []
        if self.db is not None and hasattr(self.db, "get_cart_details"):
            try:
                details = self.db.get_cart_details(session.user_id)
                for it in details.get("items") or []:
                    subtotal = float(it.get("subtotal") or
                                     (it.get("price", 0) * it.get("quantity", 1)))
                    items.append((it.get("name") or "Item",
                                  it.get("quantity", 1), subtotal))
            except Exception:
                items = []
        if not items:
            items = [(n, 1, self._lookup_product_price(n))
                     for n in (session.cart or [])]
        else:
            items = [(n, q, s if s > 0 else self._lookup_product_price(n))
                     for n, q, s in items]
        return items

    def _lookup_product_price(self, name: str) -> float:
        """Best-effort live unit price for a cart item name (0.0 if unknown)."""
        if self.db is not None and hasattr(self.db, "search_products"):
            try:
                for p in self.db.search_products(name, limit=3) or []:
                    if not p:
                        continue
                    pname = str(p.get("name") or "").lower()
                    if pname and (pname == name.lower()
                                  or pname.startswith(name.lower())
                                  or name.lower() in pname):
                        return float(p.get("unit_price") or p.get("price") or 0)
            except Exception:
                return 0.0
        return 0.0

    def _render_cart_card(self, items: List, total: float,
                          prompt: Optional[str] = None,
                          msg: Optional[str] = None) -> str:
        """Build a ``[CART]`` card string (web + Telegram render it).

        ``msg`` carries a one-line note (e.g. "Removed X") shown above the
        card. Item lines use the ``Name × qty — price ETB`` format that the
        web parser splits on ``" × "`` to recover the product name.
        """
        lines = []
        if msg:
            lines.append(f"Msg: {msg}")
        lines.append("[CART]")
        lines += [f"Item: {n} × {qty} — {price:,.2f} ETB" for n, qty, price in items]
        lines.append(f"Total: {total:,.2f} ETB")
        if prompt:
            lines.append(f"Prompt: {prompt}")
        return "\n".join(lines)

    def _handle_cart_remove(self, message: str, session) -> str:
        """Remove an item the user added by mistake, then re-show the cart."""
        items = self._load_cart_items(session)
        if not items:
            return self.translation_service.translate(session, "cart_remove_empty")
        total = sum(sub for _, _, sub in items)
        prompt = self.translation_service.translate(session, "cart_show_prompt")

        def _remove_and_rerender(name: str) -> str:
            self.cart_service.remove_item(session.user_id, name)
            session.cart = [n for n in session.cart if n != name]
            new_items = self._load_cart_items(session)
            msg = self.translation_service.translate(
                session, "cart_remove_success", product=name)
            if not new_items:
                # Nothing left to order — abandon the in-flight checkout so a
                # later "yes" can't place an empty/stale order.
                self._reset_checkout(session)
                return msg
            if (getattr(session, "checkout_pending", False)
                    and session.checkout_state == "confirm"):
                # Mid-review removal: re-render the confirm card with the
                # remaining items so the placed order excludes the removed one.
                return self._checkout_summary_card(session)
            new_total = sum(sub for _, _, sub in new_items)
            return self._render_cart_card(new_items, new_total,
                                          prompt=prompt, msg=msg)

        kw = self.entity_extractor.extract_remove_keyword(message)
        if kw:
            kw_latin = to_latin(kw).lower()
            target = None
            for name, qty, sub in items:
                name_latin = to_latin(name).lower()
                if (name.lower() == kw.lower()
                        or kw.lower() in name.lower()
                        or name.lower() in kw.lower()
                        or (kw_latin and name_latin
                            and (name_latin == kw_latin
                                 or kw_latin in name_latin
                                 or name_latin in kw_latin))):
                    target = name
                    break
            if target:
                return _remove_and_rerender(target)
            return self.translation_service.translate(
                session, "cart_remove_not_found", product=kw)

        # No explicit product name — a reference word removes the last item.
        if any(w in message.lower() for w in ("last", "it", "one", "this",
                                              "በመጨረሻ", "እሱ", "ይህ")):
            return _remove_and_rerender(items[-1][0])

        names = "\n".join(f"• {n}" for n, _, _ in items)
        return self.translation_service.translate(
            session, "cart_remove_prompt", items=names)

    def _handle_checkout(self, message: str, session) -> str:
        """Multi-step in-chat checkout state machine.

        Steps: name → phone → address → payment → review/confirm → create order.
        State lives on the session (``checkout_state`` / ``checkout_step`` /
        ``checkout_data`` / ``checkout_pending``) so it survives across turns.
        """
        cart_items = self.cart_service.get_cart(session.user_id) or session.cart
        if not cart_items:
            self._reset_checkout(session)
            return self.translation_service.translate(session, "checkout_empty")

        msg = message.strip()
        msg_lower = msg.lower()

        # ---- Cancel / escape commands (any stage) -----------------------
        if self._is_checkout_cancel(msg_lower):
            self._reset_checkout(session)
            return self.translation_service.translate(session, "checkout_cancelled")

        # ---- Fresh start -------------------------------------------------
        if not session.checkout_pending:
            session.checkout_state = "details"
            session.checkout_pending = True
            session.checkout_step = 0
            session.checkout_data = {}
            if session.user_name:
                session.checkout_data["name"] = session.user_name
                session.checkout_step = 1
                return self.translation_service.translate(
                    session, "checkout_ask_phone", name=session.user_name
                )
            return self.translation_service.translate(session, "checkout_ask_name")

        # ---- Confirm stage: yes/no/retry ---------------------------------
        if session.checkout_state == "confirm":
            if self.intent_detector.is_affirmative(msg):
                return self._place_order(session)
            if self.intent_detector.is_negative(msg):
                self._reset_checkout(session)
                return self.translation_service.translate(session, "checkout_cancelled")
            return self.translation_service.translate(session, "checkout_confirm_retry")

        # ---- Details stage: process current step --------------------------
        return self._process_checkout_step(msg, msg_lower, session)

    def _is_checkout_cancel(self, msg_lower: str) -> bool:
        if msg_lower.strip() in {"cancel", "c", "stop", "quit", "never mind",
                                 "forget it", "ሰርዝ", "አቁም", "ተወው"}:
            return True
        if msg_lower.startswith("/cancel"):
            return True
        return False

    def _reset_checkout(self, session):
        session.checkout_state = None
        session.checkout_step = 0
        session.checkout_pending = False
        session.checkout_data = {}

    def _process_checkout_step(self, msg: str, msg_lower: str, session) -> str:
        step = session.checkout_step
        data = session.checkout_data

        if step == 0:
            # Name
            name = msg.strip().strip('"')
            if len(name) < 2:
                return self.translation_service.translate(session, "checkout_invalid_name")
            data["name"] = name
            session.checkout_step = 1
            return self.translation_service.translate(session, "checkout_ask_phone", name=name)

        if step == 1:
            # Phone
            digits = re.sub(r"\D", "", msg)
            if len(digits) < 9:
                return self.translation_service.translate(session, "checkout_invalid_phone")
            data["phone"] = msg.strip()
            session.checkout_step = 2
            return self.translation_service.translate(session, "checkout_ask_address")

        if step == 2:
            # Address
            address = msg.strip()
            if len(address) < 5:
                return self.translation_service.translate(session, "checkout_invalid_address")
            data["address"] = address
            session.checkout_step = 3
            return self.translation_service.translate(session, "checkout_ask_payment")

        if step == 3:
            # Payment method
            method = self._match_payment_method(msg_lower)
            if not method:
                return self.translation_service.translate(session, "checkout_unknown_payment")
            data["payment_method"] = method
            session.checkout_state = "confirm"
            return self._checkout_summary_card(session)

        return self.translation_service.translate(session, "checkout_confirm_retry")

    def _match_payment_method(self, msg_lower: str) -> Optional[str]:
        """Map a user reply (number, English or Amharic name) to a payment method."""
        if msg_lower.strip() in {"1", "1st", "first", "cod", "cash", "cash on delivery",
                                 "በጥሬ ገንዘብ", "ካሽ", "cod ክፍያ"}:
            return "Cash on Delivery"
        if msg_lower.strip() in {"2", "2nd", "second", "telebirr", "tele birr",
                                 "ቴሌብር", "ቴሌብር ክፍያ"}:
            return "Telebirr"
        if msg_lower.strip() in {"3", "3rd", "third", "cbe", "cbe birr", "cbe bir",
                                 "ሲቢኢ", "ሲቢኢ ብር"}:
            return "CBE Birr"
        if msg_lower.strip() in {"4", "4th", "fourth", "amole", "amole birr",
                                 "አሞሌ", "አሞሌ ብር"}:
            return "Amole"
        if msg_lower.strip() in {"5", "5th", "fifth", "card", "credit", "credit card",
                                 "ባንክ ካርድ"}:
            return "Credit Card"
        if "telebirr" in msg_lower or "ቴሌብር" in msg_lower:
            return "Telebirr"
        if "amole" in msg_lower or "አሞሌ" in msg_lower:
            return "Amole"
        if "cbe" in msg_lower or "ሲቢኢ" in msg_lower:
            return "CBE Birr"
        if "cash" in msg_lower or "cod" in msg_lower or "ካሽ" in msg_lower:
            return "Cash on Delivery"
        if "card" in msg_lower or "credit" in msg_lower:
            return "Credit Card"
        return None

    def _checkout_summary_card(self, session) -> str:
        """Build the [CHECKOUT] review card shown at the confirm step."""
        data = session.checkout_data
        name = data.get("name") or ""
        phone = data.get("phone") or ""
        address = data.get("address") or ""
        payment = data.get("payment_method") or ""

        items = []
        total = 0.0
        if self.db is not None and hasattr(self.db, "get_cart_details"):
            try:
                details = self.db.get_cart_details(session.user_id)
                for it in details.get("items") or []:
                    subtotal = float(it.get("subtotal") or
                                     (it.get("price", 0) * it.get("quantity", 1)))
                    items.append((it.get("name") or "Item",
                                  it.get("quantity", 1), subtotal))
                    total += subtotal
            except Exception:
                items = []
        if not items:
            # Fallback: names from the in-memory cart with no prices
            for n in (session.cart or []):
                items.append((n, 1, 0.0))
        total = total or sum(s for _, _, s in items)

        item_lines = "\n".join(
            f"Item: {n} × {qty} — {price:,.2f} ETB" for n, qty, price in items
        ) if items else "Item: (empty)"

        confirm = self.translation_service.translate(session, "checkout_confirm_prompt")
        return (
            "[CHECKOUT]\n"
            "Step: confirm\n"
            f"Name: {name}\n"
            f"Phone: {phone}\n"
            f"Address: {address}\n"
            f"Payment: {payment}\n"
            f"{item_lines}\n"
            f"Total: {total:,.2f} ETB\n"
            f"Prompt: {confirm}"
        )

    def _place_order(self, session) -> str:
        """Persist the order via the DB and render the order card."""
        if self.db is None or not hasattr(self.db, "create_order"):
            self._reset_checkout(session)
            return self.translation_service.translate(session, "checkout_db_offline")

        order = self.db.create_order(session.user_id, session.checkout_data)
        if not order:
            self._reset_checkout(session)
            return self.translation_service.translate(session, "checkout_db_offline")

        order_id = order.get("id") or order.get("order_id")
        session.last_order_id = order_id
        items = self.order_service.get_order_items(order_id)
        card = self.order_service.format_order_card(order, items, session)
        self._reset_checkout(session)
        return card
    
    def _handle_help(self, message: str, session) -> str:
        user_name = session.user_name or ""
        base = self.translation_service.translate(session, "help_info")
        if user_name:
            return f"Of course, {user_name}! {base}"
        return base
    
    def _handle_human_support(self, message: str, session) -> str:
        user_id = session.user_id
        user_name = session.user_name or ""
        already_requested = session.human_support_requested
        self.support_service.log_request(user_id, message, session)
        
        shop = os.getenv("SHOP_NAME", "GojoShop.et")
        sentiment = session.user_mood
        
        if sentiment == "negative" or already_requested:
            intro_keys = ["human_support_already_requested_1", "human_support_already_requested_2"]
        else:
            intro_keys = ["human_support_request_1", "human_support_request_2"]
        
        intro = self.translation_service.translate(session, random.choice(intro_keys))
        
        if user_name:
            empathy = {
                "en": f"I understand, {user_name}. Let me get you to someone who can help. ",
                "am": f"ተረድቻለሁ {user_name}። የሚረዳዎትን ሰው ላገኝልዎት። "
            }
            intro = empathy.get(session.language, empathy["en"]) + intro
        
        context_note = ""
        if session.last_order_id:
            context_note = self.translation_service.translate(
                session, "human_support_order_note", order_id=session.last_order_id
            )
        elif session.last_search_keyword:
            context_note = self.translation_service.translate(
                session, "human_support_search_note", keyword=session.last_search_keyword
            )
        
        return intro + context_note + "\n\n" + self._format_support_card(shop, session)
    
    def _format_support_card(self, shop: str, session) -> str:
        email = os.getenv("SHOP_SUPPORT_EMAIL", "support@gojoshop.et")
        phone = os.getenv("SHOP_SUPPORT_PHONE", "+251988664488")
        hours = os.getenv("SHOP_SUPPORT_HOURS", "Mon–Sat, 9:00 AM – 6:00 PM EAT")
        note = self.translation_service.translate(session, "human_support_note")
        user_name = session.user_name or "Customer"
        
        return (
            "━━━ HUMAN SUPPORT ━━━\n"
            f"Hello {user_name},\n"
            f"Shop: {shop}\n"
            f"Email: {email}\n"
            f"Phone: {phone}\n"
            f"Hours: {hours}\n"
            f"Note: {note}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
    
    def _handle_farewell(self, message: str, session) -> str:
        shop = os.getenv("SHOP_NAME", "GojoShop.et")
        user_name = session.user_name or ""
        
        if self.intent_detector.is_negative(message):
            farewells_neg = [
                self.translation_service.translate(session, "farewell_negative_1"),
                self.translation_service.translate(session, "farewell_negative_2"),
                self.translation_service.translate(session, "farewell_negative_3"),
            ]
            base = random.choice(farewells_neg)
            if user_name:
                return f"I understand, {user_name}. {base}"
            return base
        
        farewells = [
            self.translation_service.translate(session, "farewell_1", shop=shop),
            self.translation_service.translate(session, "farewell_2", shop=shop),
            self.translation_service.translate(session, "farewell_3", shop=shop),
        ]
        base = random.choice(farewells)
        if user_name:
            return f"Bye for now, {user_name}! {base}"
        return base
    
    def _handle_general(self, message: str, session) -> str:
        user_name = session.user_name or ""
        
        if session.last_search_keyword:
            kw = session.last_search_keyword
            base = self.translation_service.translate(session, "general_search_kw", kw=kw)
        elif session.last_order_id:
            base = self.translation_service.translate(session, "general_order_context", order_id=session.last_order_id)
        elif session.cart:
            base = self.translation_service.translate(session, "general_cart_items", cart_len=len(session.cart))
        else:
            base = self.translation_service.translate(session, "general_help")
        
        if user_name:
            if session.language == "am":
                return f"እሺ {user_name}። {base}"
            else:
                return f"Got it, {user_name}. {base}"
        return base
    
    def _handle_order_lookup(self, message: str, session) -> str:
        order_id_raw = self.intent_detector.extract_order_id(message)
        
        if not order_id_raw:
            return self.translation_service.translate(session, "order_lookup_prompt")
        
        if self.db is None:
            return self.translation_service.translate(session, "order_lookup_db_offline")
        
        order = self.order_service.get_order(order_id_raw)
        if order is None:
            user_name = session.user_name or ""
            base = self.translation_service.translate(session, "order_lookup_not_found", order_id=order_id_raw.upper())
            if user_name:
                return f"I'm sorry, {user_name}. {base}"
            return base
        
        session.last_order_id = order.get('id')
        items = self.order_service.get_order_items(order.get('id'))
        return self.order_service.format_order_card(order, items, session)
    
    def _handle_order_followup(self, message: str, session) -> str:
        order_id = session.last_order_id
        if not order_id or self.db is None:
            return self.translation_service.translate(session, "order_lookup_prompt")
        
        order = self.order_service.get_order(order_id)
        if not order:
            return self.translation_service.translate(session, "order_lookup_not_found", order_id=order_id)
        
        items = self.order_service.get_order_items(order_id)
        return self.order_service.format_order_card(order, items, session)