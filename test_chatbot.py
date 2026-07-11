# test_chatbot.py
import unittest
from pathlib import Path
from chatbot_service import GojoShopChatbot


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

    def search_products(self, query, limit=5, filters=None):
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
        return results[:limit]

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

    def search_products(self, query, limit=5, filters=None):
        self.calls.append((query, limit, filters))
        return super().search_products(query, limit=limit, filters=filters)


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

    def test_chat_template_and_helper_use_real_utf8_emojis(self):
        template_path = Path(__file__).with_name("templates") / "chatbot.html"
        helper_path = Path(__file__).with_name("_inline_check.js")

        for path in (template_path, helper_path):
            content = path.read_text(encoding="utf-8")
            self.assertIn("🛍️", content)
            self.assertIn("📦", content)
            self.assertNotIn("âœ¦", content)
            self.assertNotIn("â€”", content)
            self.assertNotIn("ðŸ", content)

if __name__ == '__main__':
    unittest.main()
