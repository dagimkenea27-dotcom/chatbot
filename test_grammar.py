# test_grammar.py
import unittest

from chatbot.nlp.grammar import GrammarAnalyzer
from chatbot.nlp.intent_detector import IntentDetector
from chatbot.nlp.entity_extractor import EntityExtractor
from chatbot.models.session import Session
from chatbot.models.memory import ConversationContext


class TestGrammarAnalyzerUtterance(unittest.TestCase):
    def setUp(self):
        self.g = GrammarAnalyzer()

    def test_yes_no_questions(self):
        for msg in ("is it in stock", "do you sell wholesale",
                    "can you wrap it as a gift", "are your products authentic"):
            self.assertEqual(self.g.utterance_type(msg), "yes_no", msg)
            self.assertTrue(self.g.is_yes_no(msg))

    def test_wh_questions(self):
        for msg in ("how do i pay", "when will it be back in stock",
                    "where is my order"):
            self.assertEqual(self.g.utterance_type(msg), "wh", msg)
            self.assertTrue(self.g.is_wh(msg))

    def test_imperatives(self):
        for msg in ("show me iphone in stock", "find sneakers", "tell me about shipping"):
            self.assertEqual(self.g.utterance_type(msg), "imperative", msg)
            self.assertTrue(self.g.is_imperative(msg))

    def test_declaratives(self):
        for msg in ("i want to modify my order", "genuine iphone", "thanks"):
            self.assertEqual(self.g.utterance_type(msg), "declarative", msg)
            self.assertTrue(self.g.is_declarative(msg))

    def test_declarative_after_please(self):
        self.assertEqual(self.g.utterance_type("please show me iphones"), "imperative")


class TestGrammarAnalyzerRules(unittest.TestCase):
    def setUp(self):
        self.g = GrammarAnalyzer()

    def test_stock_filter_vs_question(self):
        # "in stock" is a filter on an explicit product search.
        self.assertEqual(self.g.resolve_stock("show me iphone in stock"), "product_search")
        self.assertEqual(self.g.resolve_stock("iphone in stock"), "product_search")
        # "in stock" is the focus of an availability question.
        self.assertEqual(self.g.resolve_stock("is it in stock"), "stock")
        self.assertEqual(self.g.resolve_stock("is iphone in stock"), "stock")
        self.assertEqual(self.g.resolve_stock("when will it be back in stock"), "stock")
        self.assertEqual(self.g.resolve_stock("in stock"), "stock")

    def test_authenticity_modifier_vs_complement(self):
        # Attributive adjective before a product noun -> product search.
        self.assertEqual(self.g.resolve_authenticity("genuine iphone"), "product_search")
        self.assertEqual(self.g.resolve_authenticity("authentic samsung charger"), "product_search")
        # Predicate complement -> authenticity topic.
        self.assertEqual(self.g.resolve_authenticity("is this genuine"), "authenticity")
        self.assertEqual(self.g.resolve_authenticity("are your products authentic"), "authenticity")

    def test_gift_service_vs_shopping(self):
        self.assertEqual(self.g.resolve_gift("do you offer gift wrapping"), "gift")
        self.assertEqual(self.g.resolve_gift("gift card"), "gift")
        self.assertEqual(self.g.resolve_gift("buy a gift for my mom"), "product_search")
        self.assertEqual(self.g.resolve_gift("do you sell gifts"), "product_search")

    def test_wholesale_service_vs_product(self):
        self.assertEqual(self.g.resolve_wholesale("do you sell wholesale"), "wholesale")
        self.assertEqual(self.g.resolve_wholesale("i want to buy in bulk"), "wholesale")
        self.assertEqual(self.g.resolve_wholesale("bulk price for iphone"), "product_search")

    def test_installment_invoice_international(self):
        self.assertEqual(self.g.resolve_installment("do you have payment plans"), "installment")
        self.assertEqual(self.g.resolve_installment("how do i pay"), "payment")
        self.assertEqual(self.g.resolve_invoice("can i get an invoice"), "invoice")
        self.assertEqual(self.g.resolve_invoice("payment methods"), "payment")
        self.assertEqual(self.g.resolve_international("do you ship to the USA"), "international")
        self.assertEqual(self.g.resolve_international("how long does shipping take"), "shipping")


class TestGrammarIntegration(unittest.TestCase):
    def setUp(self):
        self.d = IntentDetector(entity_extractor=EntityExtractor())
        self.session = Session(user_id="grammar_tester")
        self.context = ConversationContext(user_id="grammar_tester")

    def detect(self, msg):
        return self.d.detect_with_confidence(msg, self.session, self.context).intent

    def test_stock_does_not_shadow_product_search(self):
        self.assertEqual(self.detect("show me iphone in stock"), "product_search")
        self.assertEqual(self.detect("is it in stock"), "stock")

    def test_authenticity_does_not_shadow_product_search(self):
        self.assertEqual(self.detect("genuine iphone"), "product_search")
        self.assertEqual(self.detect("is this genuine"), "authenticity")

    def test_gift_does_not_shadow_product_search(self):
        self.assertEqual(self.detect("buy a gift for my mom"), "product_search")
        self.assertEqual(self.detect("do you offer gift wrapping"), "gift")
        self.assertEqual(self.detect("gift card"), "gift")

    def test_order_action_beats_generic_order_lookup(self):
        self.assertEqual(self.detect("how do i pay for my order"), "payment")
        self.assertEqual(self.detect("how do i cancel my order"), "cancellation")
        self.assertEqual(self.detect("i want to return my order"), "returns")
        # Pure lookups still work.
        self.assertEqual(self.detect("track my order"), "order_lookup")
        self.assertEqual(self.detect("where is my order"), "order_lookup")

    def test_specific_topics_beat_generic(self):
        self.assertEqual(self.detect("can i get an invoice"), "invoice")
        self.assertEqual(self.detect("do you have payment plans"), "installment")
        self.assertEqual(self.detect("do you ship to the USA"), "international")
        self.assertEqual(self.detect("i want to modify my order"), "order_change")


if __name__ == '__main__':
    unittest.main()
