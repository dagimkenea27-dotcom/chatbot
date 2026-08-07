# test_telegram_bot.py
import unittest

from telegram_bot import TelegramBot, _strip_bold


class TelegramBotFormatterTests(unittest.TestCase):
    def setUp(self):
        self.bot = TelegramBot.__new__(TelegramBot)

    def test_strip_bold(self):
        self.assertEqual(_strip_bold("Say **checkout** now"), "Say checkout now")

    def test_format_cart_card_en(self):
        card = (
            "[CART]\n"
            "Item: iPhone 15 × 1 — 45,000.00 ETB\n"
            "Total: 45,000.00 ETB\n"
            "Prompt: Ready to buy? Say **checkout** to place your order."
        )
        out = self.bot._format_response(card, "en")
        self.assertIn("🛒 Your Cart", out)
        self.assertIn("• iPhone 15 × 1", out)
        self.assertIn("💰 Total: 45,000.00 ETB", out)
        self.assertIn("checkout", out)
        self.assertNotIn("**", out)
        self.assertNotIn("[CART]", out)

    def test_format_cart_card_am(self):
        card = "[CART]\nItem: ስልክ × 1 — 850.00 ETB\nTotal: 850.00 ETB\nPrompt: **checkout** ይበሉ"
        out = self.bot._format_response(card, "am")
        self.assertIn("ጋሪዎ", out)
        self.assertIn("💰 Total: 850.00 ETB", out)

    def test_format_cart_card_with_msg_after_intro(self):
        card = (
            "Sure! 😊 Msg: ✅ Removed **iPhone Case** from your cart.\n"
            "[CART]\n"
            "Item: iPhone 15 × 1 — 45,000.00 ETB\n"
            "Total: 45,000.00 ETB\n"
            "Prompt: Ready to buy? Say **checkout** to place your order."
        )
        out = self.bot._format_response(card, "en")
        self.assertIn("Removed iPhone Case from your cart", out)
        self.assertIn("🛒 Your Cart", out)
        self.assertIn("• iPhone 15 × 1", out)
        self.assertIn("💰 Total: 45,000.00 ETB", out)
        self.assertNotIn("**", out)
        self.assertNotIn("[CART]", out)

    def test_format_checkout_card(self):
        card = (
            "[CHECKOUT]\n"
            "Step: confirm\n"
            "Name: Abebe Girma\n"
            "Phone: +251911123456\n"
            "Address: Bole, Addis Ababa\n"
            "Payment: Telebirr\n"
            "Item: iPhone 15 × 1 — 45,000.00 ETB\n"
            "Total: 45,000.00 ETB\n"
            "Prompt: Reply **Yes** to confirm."
        )
        out = self.bot._format_response(card, "en")
        self.assertIn("📋 Checkout Review", out)
        self.assertIn("👤 Name: Abebe Girma", out)
        self.assertIn("📞 Phone: +251911123456", out)
        self.assertIn("💳 Payment: Telebirr", out)
        self.assertIn("• iPhone 15 × 1", out)
        self.assertIn("💰 Total: 45,000.00 ETB", out)
        self.assertNotIn("Step:", out)
        self.assertNotIn("**", out)

    def test_format_plain_text_strips_markers(self):
        text = (
            "Great! 🌟 PRODUCT SEARCH\n"
            "Name: iPhone 15\n"
            "Price: 45,000.00 ETB\n"
            "Image: def.png\n"
            "---\n"
            "Name: iPhone Case\n"
            "Price: 500.00 ETB"
        )
        out = self.bot._format_response(text, "en")
        self.assertNotIn("PRODUCT SEARCH", out)
        self.assertNotIn("Image:", out)
        self.assertIn("Name: iPhone 15", out)
        self.assertIn("Name: iPhone Case", out)

    def test_format_order_card_separators(self):
        text = (
            "━━━━━━━━━━━━━━\n"
            "📦 Order #123\n"
            "━━━━━━━━━━━━━━\n"
            "💰 Total: 1,700.00 ETB\n"
            "━━━━━━━━━━━━━━"
        )
        out = self.bot._format_response(text, "en")
        self.assertNotIn("━", out)
        self.assertIn("📦 Order #123", out)
        self.assertIn("💰 Total: 1,700.00 ETB", out)


if __name__ == '__main__':
    unittest.main()
