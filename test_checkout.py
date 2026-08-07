# test_checkout.py
import unittest

from chatbot.chatbot_core import GojoShopChatbot


class CheckoutFakeDB:
    """FakeDB with full cart + order persistence for the checkout flow."""

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

    def __init__(self):
        self.users = {}
        self.carts = {}
        self.orders = {}
        self.order_details = {}
        self.sessions = {}
        self._order_seq = 100
        self.next_user_id = 9000

    def get_or_create_user(self, user_id):
        if user_id not in self.users:
            self.next_user_id += 1
            self.users[user_id] = {
                "id": self.next_user_id,
                "name": user_id,
                "email": f"{user_id}@guest.gojo.et",
                "phone": "0000000000",
            }
            self.carts[user_id] = []
        return self.users[user_id]

    def search_products(self, query, limit=5, filters=None, offset=0):
        filters = filters or {}
        query = query.lower()
        results = [p for p in self.products if all(w in p["name"].lower() for w in query.split())]
        return results[offset:offset + limit]

    def get_related_products(self, keyword, exclude_ids=None, limit=4):
        exclude_ids = set(exclude_ids or [])
        return [p for p in self.products if p["id"] not in exclude_ids][:limit]

    def get_product_by_id(self, product_id):
        return next((p for p in self.products if p["id"] == product_id), None)

    def add_item_to_cart(self, user_id, product_name, quantity=1):
        product = next((p for p in self.products if p["name"] == product_name), None)
        if not product:
            return False
        user = self.get_or_create_user(user_id)
        self.carts.setdefault(user_id, [])
        for it in self.carts[user_id]:
            if it["name"] == product_name:
                it["quantity"] += quantity
                return True
        self.carts[user_id].append({
            "product_id": product["id"],
            "name": product["name"],
            "quantity": quantity,
            "price": product["unit_price"],
            "slug": product["slug"],
            "thumbnail": product["thumbnail"],
            "seller_id": 1,
        })
        return True

    def get_cart_items_by_user(self, user_id):
        user = self.get_or_create_user(user_id)
        return [it["name"] for it in self.carts.get(user_id, [])]

    def get_cart_details(self, user_id):
        user = self.get_or_create_user(user_id)
        items = []
        total = 0.0
        for it in self.carts.get(user_id, []):
            subtotal = it["price"] * it["quantity"]
            items.append({
                "id": it["product_id"],
                "name": it["name"],
                "quantity": it["quantity"],
                "price": it["price"],
                "subtotal": subtotal,
                "slug": it["slug"],
                "thumbnail": it["thumbnail"],
            })
            total += subtotal
        return {"items": items, "total_price": total}

    def clear_cart(self, user_id):
        self.carts[user_id] = []
        return True

    def remove_item_from_cart(self, user_id, product_name):
        """Remove one product line from the cart. Returns True if removed."""
        cart = self.carts.get(user_id, [])
        pn = product_name.lower()
        for i, it in enumerate(cart):
            if it["name"].lower() == pn:
                cart.pop(i)
                return True
        for i, it in enumerate(cart):
            if pn in it["name"].lower() or it["name"].lower() in pn:
                cart.pop(i)
                return True
        return False

    def create_order(self, user_id, checkout_data):
        user = self.get_or_create_user(user_id)
        items = self.get_cart_details(user_id)["items"]
        if not items:
            return None
        self._order_seq += 1
        order_id = self._order_seq
        total = sum(it["subtotal"] for it in items)
        order = {
            "id": order_id,
            "order_id": str(order_id),
            "customer_id": str(user["id"]),
            "customer_name": checkout_data.get("name") or user["name"],
            "customer_phone": checkout_data.get("phone") or "",
            "customer_email": user["email"],
            "order_status": "pending",
            "order_amount": total,
            "payment_method": checkout_data.get("payment_method", "Cash on Delivery"),
            "payment_status": "unpaid",
            "shipping_address_data": '{"address": "%s"}' % checkout_data.get("address", ""),
            "order_group_id": f"{user['id']}-TEST",
            "seller_is": "admin",
        }
        self.orders[order_id] = order
        self.order_details[order_id] = [
            {
                "product_id": it["id"],
                "product_name": it["name"],
                "quantity": it["quantity"],
                "unit_price": it["price"],
            }
            for it in items
        ]
        self.carts[user_id] = []
        return order

    def get_order(self, order_id):
        try:
            return self.orders.get(int(order_id))
        except (TypeError, ValueError):
            return None

    def get_order_items(self, order_id):
        try:
            return self.order_details.get(int(order_id), [])
        except (TypeError, ValueError):
            return []

    def get_user_session(self, user_id):
        return self.sessions.get(user_id)

    def save_user_session(self, user_id, data):
        self.sessions[user_id] = data
        return True

    def delete_user_session(self, user_id):
        self.sessions.pop(user_id, None)
        return True


class TestInChatCheckout(unittest.TestCase):
    def setUp(self):
        self.db = CheckoutFakeDB()
        self.chatbot = GojoShopChatbot(db_manager=self.db)
        self.user = "checkout_user_1"
        self.chatbot.add_to_cart(self.user, "iPhone 15")
        self.chatbot.add_to_cart(self.user, "iPhone Case")

    def _cart_len(self):
        return len(self.chatbot.get_cart(self.user))

    def test_checkout_empty_cart(self):
        chatbot = GojoShopChatbot(db_manager=self.db)
        user = "empty_user_1"
        chatbot.get_response(user, "Hello")
        response = chatbot.get_response(user, "Checkout")
        self.assertIn("empty", response)

    def test_checkout_full_flow_places_order(self):
        r1 = self.chatbot.get_response(self.user, "Checkout")
        self.assertIn("Step 1", r1)
        self.assertIn("name", r1)

        r2 = self.chatbot.get_response(self.user, "Abebe Girma")
        self.assertIn("Step 2", r2)
        self.assertIn("phone", r2)

        r3 = self.chatbot.get_response(self.user, "+251 911 123 456")
        self.assertIn("Step 3", r3)
        self.assertIn("address", r3)

        r4 = self.chatbot.get_response(self.user, "Bole, Addis Ababa")
        self.assertIn("Step 4", r4)
        self.assertIn("pay", r4)

        r5 = self.chatbot.get_response(self.user, "Telebirr")
        self.assertIn("[CHECKOUT]", r5)
        self.assertIn("Abebe Girma", r5)
        self.assertIn("iPhone 15", r5)
        self.assertIn("Total:", r5)

        session = self.chatbot.user_sessions[self.user]
        self.assertEqual(session.checkout_state, "confirm")

        r6 = self.chatbot.get_response(self.user, "Yes")
        self.assertIn("Order #", r6)
        self.assertIn("Abebe Girma", r6)

        session = self.chatbot.user_sessions[self.user]
        self.assertIsNone(session.checkout_state)
        self.assertFalse(session.checkout_pending)
        self.assertEqual(self._cart_len(), 0)
        self.assertIsNotNone(session.last_order_id)

    def test_checkout_cancel_resets_and_keeps_cart(self):
        self.chatbot.get_response(self.user, "Checkout")
        self.chatbot.get_response(self.user, "Abebe Girma")
        response = self.chatbot.get_response(self.user, "cancel")
        self.assertIn("cancelled", response)

        session = self.chatbot.user_sessions[self.user]
        self.assertIsNone(session.checkout_state)
        self.assertEqual(self._cart_len(), 2)

    def test_checkout_validation_reprompts(self):
        self.chatbot.get_response(self.user, "Checkout")
        r = self.chatbot.get_response(self.user, "A")
        self.assertIn("name", r)
        r = self.chatbot.get_response(self.user, "Abebe Girma")
        self.assertIn("Step 2", r)
        r = self.chatbot.get_response(self.user, "123")
        self.assertIn("phone", r)

    def test_checkout_unknown_payment_reprompts(self):
        self.chatbot.get_response(self.user, "Checkout")
        self.chatbot.get_response(self.user, "Abebe Girma")
        self.chatbot.get_response(self.user, "+251911000000")
        self.chatbot.get_response(self.user, "Addis Ababa")
        r = self.chatbot.get_response(self.user, "bitcoin")
        self.assertIn("pay", r.lower())

    def test_checkout_no_on_confirm_cancels(self):
        self.chatbot.get_response(self.user, "Checkout")
        self.chatbot.get_response(self.user, "Abebe Girma")
        self.chatbot.get_response(self.user, "+251911000000")
        self.chatbot.get_response(self.user, "Addis Ababa")
        self.chatbot.get_response(self.user, "2")
        r = self.chatbot.get_response(self.user, "No")
        self.assertIn("cancelled", r)
        self.assertEqual(self._cart_len(), 2)

    def test_checkout_prefills_known_user_name(self):
        session = self.chatbot.user_sessions[self.user]
        session.user_name = "Sami"
        r1 = self.chatbot.get_response(self.user, "Checkout")
        self.assertIn("Step 2", r1)
        self.assertIn("Sami", r1)

    def test_checkout_db_offline(self):
        chatbot = GojoShopChatbot(db_manager=None)
        user = "offline_user_1"
        chatbot.add_to_cart(user, "iPhone 15")
        chatbot.get_response(user, "Checkout")
        chatbot.get_response(user, "Abebe Girma")
        chatbot.get_response(user, "+251911000000")
        chatbot.get_response(user, "Addis Ababa")
        r = chatbot.get_response(user, "Telebirr")
        self.assertIn("[CHECKOUT]", r)
        r = chatbot.get_response(user, "Yes")
        self.assertIn("offline", r)

    def test_payment_method_number_mapping(self):
        session = self.chatbot.user_sessions[self.user]
        self.assertEqual(
            self.chatbot._match_payment_method("2"), "Telebirr")
        self.assertEqual(
            self.chatbot._match_payment_method("3"), "CBE Birr")
        self.assertEqual(
            self.chatbot._match_payment_method("cod"), "Cash on Delivery")
        self.assertEqual(
            self.chatbot._match_payment_method("አሞሌ"), "Amole")
        self.assertIsNone(self.chatbot._match_payment_method("xyz"))
        self.assertIsNone(session.checkout_state)

    def test_show_cart_empty(self):
        chatbot = GojoShopChatbot(db_manager=self.db)
        user = "show_cart_empty_1"
        response = chatbot.get_response(user, "show my cart")
        self.assertIn("empty", response.lower())

    def test_show_cart_lists_items_and_total(self):
        response = self.chatbot.get_response(self.user, "show cart")
        self.assertIn("[CART]", response)
        self.assertIn("iPhone 15", response)
        self.assertIn("iPhone Case", response)
        self.assertIn("Total:", response)

    def test_show_cart_bare_word(self):
        response = self.chatbot.get_response(self.user, "cart")
        self.assertIn("[CART]", response)
        self.assertIn("iPhone 15", response)

    def test_show_cart_amharic(self):
        response = self.chatbot.get_response(self.user, "ጋሪ አሳይ")
        self.assertIn("[CART]", response)
        self.assertIn("iPhone 15", response)

    def test_show_cart_does_not_swallow_add_to_cart(self):
        response = self.chatbot.get_response(self.user, "add to cart")
        self.assertNotIn("[CART]", response)


class TestCartRemove(unittest.TestCase):
    def setUp(self):
        self.db = CheckoutFakeDB()
        self.chatbot = GojoShopChatbot(db_manager=self.db)
        self.user = "remove_user_1"
        self.chatbot.add_to_cart(self.user, "iPhone 15")
        self.chatbot.add_to_cart(self.user, "iPhone Case")

    def _cart_len(self):
        return len(self.chatbot.get_cart(self.user))

    def test_remove_from_cart_service(self):
        self.assertEqual(self._cart_len(), 2)
        self.assertTrue(self.chatbot.remove_from_cart(self.user, "iPhone 15"))
        self.assertEqual(self._cart_len(), 1)
        self.assertIn("iPhone Case", self.chatbot.get_cart(self.user))

    def test_remove_missing_product_returns_false(self):
        self.assertFalse(self.chatbot.remove_from_cart(self.user, "Headphones"))
        self.assertEqual(self._cart_len(), 2)

    def test_remove_english_keyword(self):
        response = self.chatbot.get_response(self.user, "remove iPhone 15 from my cart")
        self.assertIn("[CART]", response)
        self.assertIn("Item: iPhone Case", response)
        self.assertNotIn("Item: iPhone 15", response)
        self.assertEqual(self._cart_len(), 1)

    def test_remove_amharic_keyword(self):
        response = self.chatbot.get_response(self.user, "አይፎን ከጋሪዬ አስወግድ")
        self.assertIn("Item: iPhone Case", response)
        self.assertNotIn("Item: iPhone 15", response)
        self.assertEqual(self._cart_len(), 1)

    def test_remove_transliterated_keyword(self):
        response = self.chatbot.get_response(self.user, "kegariye aswegid iPhone Case")
        self.assertIn("Item: iPhone 15", response)
        self.assertNotIn("Item: iPhone Case", response)
        self.assertEqual(self._cart_len(), 1)

    def test_remove_reference_last_item(self):
        response = self.chatbot.get_response(self.user, "remove the last one")
        self.assertIn("Item: iPhone 15", response)
        self.assertNotIn("Item: iPhone Case", response)
        self.assertEqual(self._cart_len(), 1)

    def test_remove_unknown_product_prompts(self):
        response = self.chatbot.get_response(self.user, "remove headphones from cart")
        self.assertIn("isn't", response.lower())
        self.assertEqual(self._cart_len(), 2)

    def test_remove_bare_prompt_lists_items(self):
        response = self.chatbot.get_response(self.user, "remove")
        self.assertIn("iPhone 15", response)
        self.assertIn("iPhone Case", response)
        self.assertEqual(self._cart_len(), 2)

    def test_remove_from_empty_cart(self):
        self.chatbot.cart_service.clear_cart(self.user)
        response = self.chatbot.get_response(self.user, "remove iPhone 15")
        self.assertIn("empty", response.lower())

    def test_remove_last_item_says_removed(self):
        self.chatbot.remove_from_cart(self.user, "iPhone Case")
        response = self.chatbot.get_response(self.user, "remove iPhone 15")
        self.assertIn("removed", response.lower())
        self.assertEqual(self._cart_len(), 0)

    def test_remove_msg_line_in_card(self):
        response = self.chatbot.get_response(self.user, "remove iPhone 15")
        self.assertIn("Msg:", response)
        self.assertIn("Removed", response)


class DegradedCartDetailsDB(CheckoutFakeDB):
    """Mimics a live DB where get_cart_details returns empty (query error)
    while item names are still resolvable — prices must not be blank."""

    def get_cart_details(self, user_id):
        return {"items": [], "total_price": 0.0}


class TestCartPricesResolved(unittest.TestCase):
    def setUp(self):
        self.db = DegradedCartDetailsDB()
        self.chatbot = GojoShopChatbot(db_manager=self.db)
        self.user = "prices_user_1"
        self.chatbot.add_to_cart(self.user, "iPhone 15")
        self.chatbot.add_to_cart(self.user, "iPhone Case")

    def test_show_cart_prices_not_blank(self):
        response = self.chatbot.get_response(self.user, "show cart")
        self.assertIn("45,000.00 ETB", response)
        self.assertIn("500.00 ETB", response)
        self.assertIn("45,500.00 ETB", response)
        self.assertNotIn("— 0.00 ETB", response)

    def test_remove_keeps_real_prices(self):
        response = self.chatbot.get_response(self.user, "remove iPhone 15")
        self.assertIn("500.00 ETB", response)
        self.assertIn("Total: 500.00 ETB", response)
        self.assertNotIn("— 0.00 ETB", response)


if __name__ == '__main__':
    unittest.main()
