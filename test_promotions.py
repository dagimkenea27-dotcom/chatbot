# test_promotions.py
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta

from chatbot.chatbot_core import GojoShopChatbot
from chatbot.services.promotion_service import PromotionService


class PromoFakeDB:
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

    def get_product_by_id(self, product_id):
        return next((p for p in self.products if p["id"] == product_id), None)

    def search_products(self, query, limit=5, filters=None, offset=0):
        filters = filters or {}
        query = query.lower()
        results = [p for p in self.products if all(w in p["name"].lower() for w in query.split())]
        return results[offset:offset + limit]

    def get_related_products(self, keyword, exclude_ids=None, limit=4):
        exclude_ids = set(exclude_ids or [])
        return [p for p in self.products if p["id"] not in exclude_ids][:limit]

    def get_order(self, order_id):
        return None

    def get_order_items(self, order_id):
        return []


class TestPromotionService(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "promotions.json")
        self.db = PromoFakeDB()
        self.service = PromotionService(db_manager=self.db, path=self.path)

    def _ts(self, dt):
        return dt.strftime("%Y-%m-%dT%H:%M")

    def _create_active(self, **overrides):
        data = {
            "product_id": 1,
            "title": "Summer Sale",
            "message": "Get it now!",
            "discount": 15,
            "start": self._ts(datetime.now() - timedelta(days=1)),
            "end": self._ts(datetime.now() + timedelta(days=7)),
            "active": True,
        }
        data.update(overrides)
        return self.service.create(data)

    def test_crud(self):
        promo = self._create_active()
        self.assertIsNotNone(promo)
        self.assertTrue(promo["id"].startswith("promo-"))

        loaded = self.service.list_all()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["product"]["name"], "iPhone 15")

        updated = self.service.update(promo["id"], {"discount": 20, "active": False})
        self.assertEqual(updated["discount"], 20)
        self.assertFalse(updated["active"])

        self.assertTrue(self.service.delete(promo["id"]))
        self.assertEqual(self.service.list_all(), [])

    def test_active_window_filtering(self):
        self._create_active()  # live now
        self._create_active(product_id=2, title="Scheduled",
                            start=self._ts(datetime.now() + timedelta(days=2)))
        self._create_active(title="Paused", active=False)
        self._create_active(title="Expired",
                            end=self._ts(datetime.now() - timedelta(days=1)))

        active = self.service.get_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["title"], "Summer Sale")

        statuses = {p["title"]: p["status"] for p in self.service.list_all()}
        self.assertEqual(statuses["Summer Sale"], "active")
        self.assertEqual(statuses["Scheduled"], "scheduled")
        self.assertEqual(statuses["Paused"], "paused")
        self.assertEqual(statuses["Expired"], "expired")

    def test_no_end_means_runs_forever(self):
        promo = self._create_active(start=self._ts(datetime.now() - timedelta(days=1)), end="")
        self.assertEqual(len(self.service.get_active()), 1)
        self.assertEqual(self.service.get_status(promo), "active")

    def test_reloads_after_external_file_change(self):
        self._create_active()
        self.assertEqual(len(self.service.get_active()), 1)

        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([], f)

        self.assertEqual(self.service.list_all(), [])
        self.assertEqual(self.service.get_active(), [])
        self.assertIsNone(self.service.get_featured())

    def test_delete_clears_file_and_in_memory(self):
        promo = self._create_active()
        self.assertTrue(self.service.delete(promo["id"]))

        with open(self.path, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), [])

        self.assertEqual(self.service.list_all(), [])
        self.assertIsNone(self.service.get_featured())

    def test_get_featured_resolves_product(self):
        self._create_active()
        featured = self.service.get_featured()
        self.assertIsNotNone(featured)
        self.assertEqual(featured["product"]["name"], "iPhone 15")
        self.assertEqual(featured["promo"]["discount"], 15)

    def test_get_featured_none_without_active(self):
        self.assertIsNone(self.service.get_featured())

    def test_format_promo_card(self):
        promo = self._create_active()
        product = self.db.get_product_by_id(1)
        card = self.service.format_promo_card(promo, product, intro="Hello deal!")
        self.assertIn("PROMO", card)
        self.assertIn("Intro: Hello deal!", card)
        self.assertIn("Name: iPhone 15", card)
        self.assertIn("Price: 45,000.00 ETB", card)
        self.assertIn("Discount: 15% off", card)
        self.assertIn("Id: 1", card)


class TestPromoChatbotIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "promotions.json")
        self.db = PromoFakeDB()
        self.service = PromotionService(db_manager=self.db, path=self.path)
        self.chatbot = GojoShopChatbot(db_manager=self.db)
        self.chatbot.promotion_service = self.service

    def _seed(self, **overrides):
        data = {
            "product_id": 1,
            "title": "Summer Sale",
            "message": "Get it now!",
            "discount": 15,
            "start": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "end": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"),
            "active": True,
        }
        data.update(overrides)
        return self.service.create(data)

    def test_greeting_shows_promo_card_once(self):
        self._seed()
        first = self.chatbot.get_response("promo_user_1", "Hello")
        self.assertIn("PROMO", first)
        self.assertIn("iPhone 15", first)
        self.assertIn("15% off", first)

        second = self.chatbot.get_response("promo_user_1", "Hi again")
        self.assertNotIn("PROMO", second)

    def test_greeting_no_promo_when_none_active(self):
        response = self.chatbot.get_response("promo_user_2", "Hello")
        self.assertNotIn("PROMO", response)

    def test_promotions_intent_shows_live_deals(self):
        self._seed()
        response = self.chatbot.get_response("promo_user_3", "what promotions do you have")
        self.assertIn("PROMO", response)
        self.assertIn("iPhone 15", response)

    def test_promotions_intent_fallback_when_no_deals(self):
        response = self.chatbot.get_response("promo_user_4", "what promotions do you have")
        self.assertIn("promotions_info" if "promotions_info" in response else "Current Promotions", response)

    def test_promo_card_stays_clean_through_pipeline(self):
        self._seed()
        response = self.chatbot.get_response("promo_user_5", "what promotions do you have")
        self.assertIn("PROMO", response)
        self.assertNotIn("PROMO", response.replace("PROMO", ""))

    def test_featured_promo_card_localized(self):
        self._seed()
        card = self.chatbot.featured_promo_card("en")
        self.assertIsNotNone(card)
        self.assertIn("PROMO", card)
        self.assertIn("iPhone 15", card)
        self.assertIn("15% off", card)
        am_card = self.chatbot.featured_promo_card("am")
        self.assertIsNotNone(am_card)
        self.assertIn("PROMO", am_card)

    def test_featured_promo_card_none_without_active(self):
        self.assertIsNone(self.chatbot.featured_promo_card("en"))

    def test_featured_promo_card_marks_session_aware(self):
        self._seed()
        card = self.chatbot.featured_promo_card("en")
        self.assertIsNotNone(card)
        session = self.chatbot.session_service.get_session("aware_user_1")
        session.promo_aware = True
        greeting = self.chatbot.get_response("aware_user_1", "Hello")
        self.assertNotIn("PROMO", greeting)


if __name__ == "__main__":
    unittest.main()
