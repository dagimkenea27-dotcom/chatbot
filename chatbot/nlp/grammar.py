# chatbot/nlp/grammar.py
"""
Lightweight rule-based grammar analysis for intent disambiguation.

The keyword scanner in :mod:`chatbot.nlp.intent_detector` matches topics by
vocabulary alone, which makes sentences ambiguous when the same word can play
different grammatical roles:

* "show me iphone in stock"  -- "in stock" is a *filter* on a product search
* "is it in stock"           -- "in stock" is the *focus* of a yes/no question
* "genuine iphone"           -- "genuine" is an *attributive adjective*
* "is this genuine"          -- "genuine" is a *predicate complement*
* "buy a gift for my mom"    -- "gift" is the object being searched
* "do you offer gift wrap"   -- "gift" names the *service/topic* itself

This module decides "which is which" using small grammar rules:

* **Utterance type** -- yes/no, wh-, imperative or declarative (based on the
  sentence-initial auxiliary / question word / base verb).
* **Pre-nominal adjective** -- a topic word that immediately precedes a product
  noun is a modifier, so the message is a *product search*.
* **Predicate complement** -- a topic word following the copula/auxiliary with a
  pronoun subject is the focus of the sentence, so it stays a *topic*.
* **Prepositional phrases** -- "in stock", "as a gift", "in installments",
  "to the USA" carry the grammatical role of the topic word.

The analyzer is intentionally dependency-free (pure ``re``) so it stays fast
and easy to test.
"""
from __future__ import annotations

import re
from typing import Any, Optional, Tuple

# ---------------------------------------------------------------------------
# Utterance classification
# ---------------------------------------------------------------------------

#: Sentence-initial auxiliaries that mark a yes/no question.
#: e.g. "is it in stock", "do you sell wholesale", "can you wrap it".
_YES_NO_START_RE: re.Pattern = re.compile(
    r"^(?:is|are|was|were|do|does|did|can|could|will|would|should|"
    r"may|might|have|has|had)\s+\w",
    re.IGNORECASE,
)

#: Sentence-initial question words that mark a wh-question.
#: e.g. "how do i pay", "when will it be back in stock", "where is my order".
_WH_START_RE: re.Pattern = re.compile(
    r"^(?:what|which|who|whom|whose|where|when|why|how)\b",
    re.IGNORECASE,
)

#: Base verbs that, sentence-initially, mark an imperative (request/command).
#: e.g. "show me iphones", "find sneakers", "tell me about shipping".
_IMPERATIVE_VERBS: Tuple[str, ...] = (
    "show", "find", "tell", "give", "get", "list", "recommend", "buy",
    "order", "cancel", "return", "search", "look", "add", "help", "let",
    "send", "check", "explain",
)
_IMPERATIVE_START_RE: re.Pattern = re.compile(
    r"^(?:" + "|".join(re.escape(v) for v in _IMPERATIVE_VERBS) + r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Product nouns used to decide whether a topic word is a modifier.
# ---------------------------------------------------------------------------

#: Specific product nouns (English, Amharic, transliterated). Generic words
#: such as "product"/"item" are intentionally excluded so that questions like
#: "are your products authentic" still resolve to the authenticity topic.
_PRODUCT_NOUNS: Tuple[str, ...] = (
    "phone", "iphone", "samsung", "galaxy", "pixel", "laptop", "macbook",
    "computer", "tablet", "ipad", "shirt", "dress", "jeans", "jacket",
    "shoe", "sneaker", "boot", "bag", "handbag", "purse", "backpack",
    "sofa", "table", "chair", "bed", "furniture", "teddy", "toy",
    "watch", "necklace", "ring", "earring", "bracelet", "headphone",
    "speaker", "tv", "camera", "airpods", "charger", "cable", "monitor",
    "keyboard", "mouse",
    "ልብስ", "ጫማ", "ሸሚዝ", "ቦርሳ", "ሰዓት", "ኮምፒውተር", "አይፎን",
    "libs", "chama", "shemiz", "borsa", "telifon", "kompyuter", "miret",
)
#: Matches a product noun, optionally pluralised (via trailing word chars).
_PRODUCT_NOUN_RE: re.Pattern = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _PRODUCT_NOUNS) + r")\w*\b",
    re.IGNORECASE,
)

#: Product-action verbs that make a topic word a *filter* rather than the focus.
_PRODUCT_ACTION_VERBS: Tuple[str, ...] = (
    "show", "find", "looking", "want", "buy", "need", "get", "recommend",
    "search", "price",
)

#: Words that, combined with "gift", describe the *gift service* rather than
#: a gift being shopped for.
_GIFT_SERVICE_TERMS: Tuple[str, ...] = (
    "wrap", "wrapping", "wrapped", "gift wrap", "gift card", "package",
    "packaging", "presentation",
)

#: Words that describe the *installment / credit* payment scheme.
_INSTALLMENT_TERMS: Tuple[str, ...] = (
    "installment", "installments", "payment plan", "payment plans",
    "monthly payment", "hire purchase", "buy on credit", "on credit",
)

#: Destination / international-delivery markers.
_INTERNATIONAL_TERMS: Tuple[str, ...] = (
    "international", "internationally", "abroad", "overseas", "outside ethiopia",
    "diaspora", "worldwide", "export", "another country", "other countries",
    "to the usa", "to usa", "to the us", "to us", "to uk", "to europe",
    "to america", "to canada", "to dubai",
)

#: Verbs that modify an existing order vs. verbs that only inspect it.
_ORDER_MODIFY_VERBS: Tuple[str, ...] = (
    "change", "modify", "edit", "update", "alter", "adjust", "replace",
)
_ORDER_INQUIRE_VERBS: Tuple[str, ...] = (
    "track", "check", "status", "where", "find",
)

#: Verbs that request a document (invoice / receipt) vs. generic payment.
_DOCUMENT_REQUEST_VERBS: Tuple[str, ...] = (
    "need", "want", "get", "give", "send", "receive", "have",
)


def _normalize(text: str) -> str:
    return text.lower().strip()


class GrammarAnalyzer:
    """Rule-based sentence analysis used to disambiguate conflicting topics.

    Parameters
    ----------
    entity_extractor:
        Optional :class:`~chatbot.nlp.entity_extractor.EntityExtractor`.
        Kept for API symmetry with :class:`IntentDetector`; product detection
        uses the built-in noun list so behaviour is fully deterministic.
    product_hints:
        Extra product words (e.g. :data:`PRODUCT_NAME_HINTS`) merged into the
        built-in product-noun list.
    """

    def __init__(self, entity_extractor: Any = None,
                 product_hints: Tuple[str, ...] = ()) -> None:
        self.entity_extractor: Any = entity_extractor
        terms: Tuple[str, ...] = tuple(dict.fromkeys(_PRODUCT_NOUNS + tuple(product_hints)))
        self._product_re = re.compile(
            r"\b(?:" + "|".join(re.escape(w) for w in terms) + r")\w*\b",
            re.IGNORECASE,
        )

    # ====================================================================
    # Utterance classification
    # ====================================================================

    def utterance_type(self, message: str) -> str:
        """Classify the sentence as ``yes_no``, ``wh``, ``imperative`` or
        ``declarative`` based on its grammatical opener."""
        msg = _normalize(message)
        if not msg:
            return "declarative"
        # "please" is a politeness marker, not part of the grammatical opener.
        msg = re.sub(r"^please[\s,]+", "", msg)
        if _YES_NO_START_RE.match(msg):
            return "yes_no"
        if _WH_START_RE.match(msg):
            return "wh"
        if _IMPERATIVE_START_RE.match(msg):
            return "imperative"
        return "declarative"

    def is_yes_no(self, message: str) -> bool:
        return self.utterance_type(message) == "yes_no"

    def is_wh(self, message: str) -> bool:
        return self.utterance_type(message) == "wh"

    def is_imperative(self, message: str) -> bool:
        return self.utterance_type(message) == "imperative"

    def is_declarative(self, message: str) -> bool:
        return self.utterance_type(message) == "declarative"

    # ====================================================================
    # Grammatical role helpers
    # ====================================================================

    def has_product_noun(self, message: str) -> bool:
        """True when a specific product noun appears in the message.

        The topic word is then likely an *attributive modifier* of that
        product (e.g. "genuine iphone") rather than the sentence focus.
        """
        return bool(self._product_re.search(message))

    def is_predicate_complement(self, message: str, term: str) -> bool:
        """True when ``term`` follows a copula/auxiliary with a pronoun subject.

        e.g. "is this genuine", "are these real", "is it original".
        In this position the topic word is the *focus*, so the topic intent
        (not a product search) should win.
        """
        msg = _normalize(message)
        return bool(
            re.search(
                rf"\b(is|are|was|were)\s+(this|that|it|these|those|they|"
                rf"your products?|my products?|items?)\s+(?:an?\s+)?{re.escape(term)}\b",
                msg,
                re.IGNORECASE,
            )
        )

    # ====================================================================
    # Topic resolution rules (return the winning intent, or ``None`` to keep
    # the keyword-based default).
    # ====================================================================

    def resolve_stock(self, message: str) -> str:
        """Distinguish a *stock filter* on a product search from a *stock
        availability question*.

        Grammar rule:
        * product-action verb + product noun -> the phrase is a filter
          ("show me iphone in stock") -> ``product_search``;
        * yes/no question or wh-question about availability -> the phrase is
          the focus ("is it in stock", "when will it be back in stock") ->
          ``stock``;
        * bare noun phrase + "in stock" ("iphone in stock") -> ``product_search``;
        * otherwise (e.g. just "in stock") -> ``stock``.
        """
        msg = _normalize(message)
        has_product = self.has_product_noun(msg)
        if has_product and any(v in msg for v in _PRODUCT_ACTION_VERBS):
            return "product_search"
        if self.is_yes_no(msg) or self.is_wh(msg):
            return "stock"
        if has_product:
            return "product_search"
        return "stock"

    def resolve_gift(self, message: str) -> str:
        """Distinguish the *gift service* topic from *shopping for a gift*.

        Grammar rule: "gift" + a service noun/verb (wrap, wrapping, card,
        package) names the topic; otherwise "gift" is the object being
        searched ("buy a gift for my mom") -> ``product_search``.
        """
        msg = _normalize(message)
        if any(w in msg for w in _GIFT_SERVICE_TERMS):
            return "gift"
        if "gift" in msg:
            return "product_search"
        return "gift"

    def resolve_authenticity(self, message: str) -> str:
        """Distinguish an *authenticity modifier* from an *authenticity
        question*.

        Grammar rule: when a specific product noun is present the topic word
        is an attributive adjective ("genuine iphone") -> ``product_search``;
        when it sits as a predicate complement ("is this genuine",
        "are your products authentic") it is the focus -> ``authenticity``.
        """
        msg = _normalize(message)
        if self.has_product_noun(msg):
            return "product_search"
        return "authenticity"

    def resolve_wholesale(self, message: str) -> str:
        """Distinguish a *bulk discount question* from a *bulk-price product
        search*.

        Grammar rule: bulk/wholesale + product noun + buy/price verb
        ("bulk price for iphone") -> ``product_search``; otherwise the
        question is about the wholesale service itself -> ``wholesale``.
        """
        msg = _normalize(message)
        if self.has_product_noun(msg) and any(v in msg for v in (
                "buy", "want", "need", "get", "price")):
            return "product_search"
        return "wholesale"

    def resolve_installment(self, message: str) -> str:
        """Choose between the ``installment`` and generic ``payment`` topics.

        Grammar rule: installment/plan/credit terms (as noun phrase or
        prepositional phrase, e.g. "payment plans", "pay in installments")
        -> ``installment``; otherwise -> ``payment``.
        """
        msg = _normalize(message)
        if any(w in msg for w in _INSTALLMENT_TERMS):
            return "installment"
        return "payment"

    def resolve_invoice(self, message: str) -> str:
        """Choose between the ``invoice`` and generic ``payment`` topics.

        Grammar rule: a document noun (invoice/receipt/bill) as the object of
        a request verb -> ``invoice``; otherwise -> ``payment``.
        """
        msg = _normalize(message)
        if any(d in msg for d in ("invoice", "invoices", "receipt", "bill",
                                  "tax invoice", "vat invoice", "ደረሰኝ", "deresen")):
            return "invoice"
        return "payment"

    def resolve_international(self, message: str) -> str:
        """Choose between the ``international`` and generic ``shipping`` topics.

        Grammar rule: a destination marker (country prepositional phrase,
        "abroad", "overseas", "diaspora") -> ``international``; otherwise
        the message is about generic shipping -> ``shipping``.
        """
        msg = _normalize(message)
        if any(w in msg for w in _INTERNATIONAL_TERMS):
            return "international"
        return "shipping"

    def resolve_order(self, message: str) -> str:
        """Choose between the ``order_change`` and ``order_lookup`` intents.

        Grammar rule: a modification verb governing "order"/"address"/
        "quantity" ("change my address") -> ``order_change``; an inquiry verb
        ("track my order", "check status") -> ``order_lookup``.
        """
        msg = _normalize(message)
        order_obj = "order" in msg or "address" in msg or "quantity" in msg
        if any(v in msg for v in _ORDER_MODIFY_VERBS) and order_obj:
            return "order_change"
        if any(v in msg for v in _ORDER_INQUIRE_VERBS) and "order" in msg:
            return "order_lookup"
        return "order_change"
