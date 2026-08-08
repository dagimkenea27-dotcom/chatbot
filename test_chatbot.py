# test_chatbot.py
import unittest
from pathlib import Path
from chatbot.chatbot_core import GojoShopChatbot


class FakeDB:
    products = [
        {
            "id": 1,
            "name": "iPhone 15",
            "unit_price": 45000,
            "current_stock": 3,
            "details": "Apple smartphone",
            "thumbnail": "iphone.jpg",
            "slug": "iphone-15",
        },
        {
            "id": 2,
            "name": "iPhone Case",
            "unit_price": 500,
            "current_stock": 12,
            "details": "Protective phone case",
            "thumbnail": "case.jpg",
            "slug": "iphone-case",
        }
    ]

    def search_products(self, query, limit=5, filters=None, offset=0):
        filters = filters or {}
        query = query.lower()
        results = [p for p in self.products if all(word in p["name"].lower() for word in query.split())]
        if filters.get("min_price") is not None:
            results = [p for p in results if p["unit_price"] >= filters["min_price"]]
        if filters.get("max_price") is not None:
            results = [p for p in results if p["unit_price"] <= filters["max_price"]]
        if filters.get("in_stock"):
            results = [p for p in results if p["current_stock"] > 0]
        if filters.get("sort") == "price_asc":
            results = sorted(results, key=lambda p: p["unit_price"])
        return results[offset:offset + limit]

    def get_related_products(self, keyword, exclude_ids=None, limit=4):
        exclude_ids = set(exclude_ids or [])
        return [p for p in self.products if p["id"] not in exclude_ids][:limit]

    def get_product_by_id(self, product_id):
        return next((p for p in self.products if p["id"] == product_id), None)

    def get_order(self, order_id):
        return None

    def get_order_items(self, order_id):
        return []


class RecordingDB(FakeDB):
    def __init__(self):
        super().__init__()
        self.calls = []

    def search_products(self, query, limit=5, filters=None, offset=0):
        self.calls.append((query, limit, filters, offset))
        return super().search_products(query, limit=limit, filters=filters, offset=offset)


class PagedDB(FakeDB):
    """FakeDB with more products than one page, to exercise pagination."""
    products = [
        {
            "id": i,
            "name": f"iPhone {i}",
            "unit_price": 1000 + i,
            "current_stock": 5,
            "details": "Apple smartphone",
            "thumbnail": f"iphone{i}.jpg",
            "slug": f"iphone-{i}",
        }
        for i in range(1, 26)
    ]


class TestGojoShopChatbot(unittest.TestCase):
    def setUp(self):
        self.chatbot = GojoShopChatbot(db_manager=FakeDB())
        self.user_id = "test_user_123"
    
    def test_greeting(self):
        response = self.chatbot.get_response(self.user_id, "Hello")
        self.assertIn("GojoShop.et", response)
    
    def test_product_search(self):
        response = self.chatbot.get_response(self.user_id, "I want to buy an iPhone")
        self.assertIn("iPhone", response)

    def test_product_search_uses_10_results(self):
        db = RecordingDB()
        chatbot = GojoShopChatbot(db_manager=db)
        chatbot.get_response(self.user_id, "show me iPhone")
        self.assertTrue(db.calls)
        self.assertEqual(db.calls[0][1], 10)

    def test_product_search_filters(self):
        response = self.chatbot.get_response(self.user_id, "show me iPhone under 1000 cheapest in stock")
        self.assertIn("Filters:", response)
        self.assertIn("max_price=1000", response)
        self.assertIn("iPhone Case", response)
    
    def test_shipping_info(self):
        response = self.chatbot.get_response(self.user_id, "Shipping info")
        self.assertIn("Shipping", response)
    
    def test_payment_info(self):
        response = self.chatbot.get_response(self.user_id, "Payment methods")
        self.assertIn("Telebirr", response)
    
    def test_add_to_cart(self):
        result = self.chatbot.add_to_cart(self.user_id, "iPhone 15")
        self.assertIn("Added", result)
        cart = self.chatbot.get_cart(self.user_id)
        self.assertIn("iPhone 15", cart)
    
    def test_checkout_with_empty_cart(self):
        # Initialize session first, then clear the cart
        self.chatbot.get_response(self.user_id, "Hello")
        self.chatbot.user_sessions[self.user_id]["cart"] = []
        response = self.chatbot.get_response(self.user_id, "Checkout")
        self.assertIn("empty", response)

    def test_reset_session_resolves_active_support_request(self):
        self.chatbot.get_response(self.user_id, "I need human support")
        self.assertIsNotNone(self.chatbot.get_active_support_request(self.user_id))

        self.chatbot.reset_session(self.user_id)

        self.assertIsNone(self.chatbot.get_active_support_request(self.user_id))

    def test_show_more_paginates_results(self):
        chatbot = GojoShopChatbot(db_manager=PagedDB())
        user = "paged_user_1"

        first = chatbot.get_response(user, "show me iphone")
        self.assertIn("HasMore: true", first)
        self.assertEqual(first.split("RECOMMENDATIONS")[0].count("Product ID:"), 10)

        second = chatbot.get_response(user, "show more")
        self.assertIn("HasMore: true", second)
        self.assertEqual(second.count("Product ID:"), 10)

        third = chatbot.get_response(user, "show more")
        self.assertEqual(third.count("Product ID:"), 5)
        self.assertIn("HasMore: false", third)

        fourth = chatbot.get_response(user, "show more")
        self.assertIn("no_more_products" if "no_more_products" in fourth else "That's everything", fourth)

    def test_show_more_keeps_filters(self):
        chatbot = GojoShopChatbot(db_manager=PagedDB())
        user = "paged_user_2"

        chatbot.get_response(user, "show me iphone under 1200")
        next_page = chatbot.get_response(user, "show more")
        self.assertIn("max_price=1200", next_page)

    def test_chat_template_uses_real_utf8_emojis(self):
        template_path = Path(__file__).with_name("index.html")

        content = template_path.read_text(encoding="utf-8")
        self.assertIn("🛍️", content)
        self.assertIn("📦", content)
        self.assertNotIn("âœ¦", content)
        self.assertNotIn("â€”", content)
        self.assertNotIn("ðŸ", content)

    def test_db_session_and_support_persistence(self):
        class FullPersistentDB(FakeDB):
            def __init__(self):
                self.sessions = {}
                self.support_reqs = {}

            def get_user_session(self, user_id):
                return self.sessions.get(user_id)

            def save_user_session(self, user_id, data):
                self.sessions[user_id] = data
                return True

            def delete_user_session(self, user_id):
                self.sessions.pop(user_id, None)
                return True

            def create_support_request(self, request_id, user_id, message, metadata):
                req = {
                    "id": request_id,
                    "status": "open",
                    "user_id": user_id,
                    "message": message,
                    "metadata": metadata,
                    "messages": [{"sender": "user", "text": message}]
                }
                self.support_reqs[request_id] = req
                return req

            def get_active_support_request(self, user_id):
                for req in self.support_reqs.values():
                    if req["user_id"] == user_id and req["status"] in ("open", "in_progress"):
                        return req
                return None

            def add_support_message(self, request_id, sender, text):
                req = self.support_reqs.get(request_id)
                if req:
                    msg = {"sender": sender, "text": text}
                    req["messages"].append(msg)
                    return msg
                return None

            def list_support_requests(self, limit=50):
                return list(self.support_reqs.values())[-limit:]

            def update_support_request_status(self, request_id, status):
                req = self.support_reqs.get(request_id)
                if req:
                    req["status"] = status
                    return req
                return None

        pdb = FullPersistentDB()
        chatbot = GojoShopChatbot(db_manager=pdb)
        user = "persistent_user_456"

        # 1. Test Session persistence
        chatbot.get_response(user, "Hello")
        self.assertIn(user, pdb.sessions)

        # 2. Test Support request DB persistence
        res = chatbot.get_response(user, "Talk to human")
        self.assertIn("HUMAN SUPPORT", res)
        active = chatbot.get_active_support_request(user)
        self.assertIsNotNone(active)
        self.assertEqual(active["user_id"], user)

        # 3. Test list and update support requests
        reqs = chatbot.list_support_requests()
        self.assertEqual(len(reqs), 1)

        updated = chatbot.update_support_request_status(active["id"], "resolved")
        self.assertEqual(updated["status"], "resolved")


class TestTransliteratedAmharic(unittest.TestCase):
    """Amharic typed in Latin letters (e.g. "felige neber") must work."""

    def setUp(self):
        self.chatbot = GojoShopChatbot(db_manager=FakeDB())
        self.user_id = "test_translit_user"

    def test_transliterated_search_returns_products(self):
        response = self.chatbot.get_response(self.user_id, "iphone felige neber")
        self.assertIn("iPhone", response)

    def test_transliterated_search_switches_language(self):
        self.chatbot.get_response(self.user_id, "iphone felige neber")
        session = self.chatbot.user_sessions[self.user_id]
        self.assertEqual(session["language"], "am")

    def test_conjugated_amharic_search_uses_clean_keyword(self):
        db = RecordingDB()
        chatbot = GojoShopChatbot(db_manager=db)
        chatbot.get_response(self.user_id, "አይፎን ፈልጌ ነበር")
        self.assertTrue(db.calls)
        query = db.calls[0][0]
        self.assertIn("አይፎን", query)
        self.assertNotIn("ፈልጌ", query)
        self.assertNotIn("ነበር", query)

    def test_conjugated_verb_without_product_prompts(self):
        response = self.chatbot.get_response(self.user_id, "ፈልጌ ነበር")
        self.assertIn("ምርቶችን", response)
        self.assertNotIn("couldn't find anything", response.lower())

    def test_transliterated_show_cart(self):
        response = self.chatbot.get_response(self.user_id, "gari asayen")
        self.assertIn("ባዶ", response)

    def test_transliterated_pure_buy_prompts_for_keyword(self):
        response = self.chatbot.get_response(self.user_id, "gizene")
        self.assertIn("ምርቶችን", response)
        self.assertNotIn("couldn't find anything", response.lower())

    def test_transliteration_word_boundaries(self):
        from chatbot.nlp.transliteration import normalize_transliteration
        self.assertEqual(normalize_transliteration("gari"), "ጋሪ")
        self.assertEqual(normalize_transliteration("gariya"), "gariya")
        self.assertEqual(
            normalize_transliteration("iphone felige neber"), "iphone ፈልጌ ነበር"
        )


if __name__ == '__main__':
    unittest.main()
