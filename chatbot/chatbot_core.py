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
from chatbot.nlp.intent_detector import IntentDetector
from chatbot.nlp.entity_extractor import EntityExtractor
from chatbot.nlp.sentiment import SentimentAnalyzer
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
        self.conversation_service = ConversationService()
        
        # Initialize NLP components
        self.intent_detector = IntentDetector()
        self.entity_extractor = EntityExtractor()
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
        session.cart = self.cart_service.get_cart(user_id)
        session.message_count += 1
        self.session_service.record_turn(session, "user", message)
        
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
        if session.message_count <= 2 and not session.user_name:
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
            self.support_service.add_message(active_req['id'], "user", message)
            self.session_service.save_session(user_id)
            return "[SUPPORT_MODE]"
        
        # ---- INTENT DETECTION ----
        intent = self.intent_detector.detect(
            message, session, conv_context, self.session_service
        )
        session.last_intent = session.current_intent
        session.current_intent = intent
        
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
        return random.choice(name_greetings)
    
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
        
        return self.product_service.format_search_card(products, filters=filters, recommendations=recommendations)
    
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
        filter_phrase = self.entity_extractor.format_filter_phrase(session.last_product_filters)
        return self._handle_product_search(f"search {keyword} {filter_phrase}", session)
    
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
        return self.translation_service.translate(session, "promotions_info")
    
    def _handle_loyalty(self, message: str, session) -> str:
        session.faq_topics_seen.append("loyalty")
        session.loyalty_aware = True
        return self.translation_service.translate(session, "loyalty_info")
    
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
    
    def _handle_checkout(self, message: str, session) -> str:
        cart_items = self.cart_service.get_cart(session.user_id)
        if not cart_items:
            return self.translation_service.translate(session, "checkout_empty")
        return self.translation_service.translate(session, "checkout_count", cart_len=len(cart_items))
    
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