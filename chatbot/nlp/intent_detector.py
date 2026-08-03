# chatbot/nlp/intent_detector.py
"""
Multilingual intent detection for the GojoShop chatbot.

Recognises user intent in three script styles:
  * English               ("show me iPhone under 1000")
  * Amharic               ("አይፎን አሳየኝ")
  * transliterated Amharic ("iphone asayen", "felge", "megzat", "tizaze")

Every detection path returns an :class:`IntentResult` carrying a confidence
score in ``[0, 1]`` so callers can decide whether to act, clarify or fall
back to a generic response.

Design notes
------------
* Order detection never fires on product searches: a bare 4+ digit number,
  ``ORD-...``/``#...`` tokens or a number inside explicit order *context*
  words are required. Phone numbers and price filters are excluded.
* Product search detection supports *product-name-only* queries (e.g. just
  "iphone") via the optional :class:`~chatbot.nlp.entity_extractor.EntityExtractor`.
* Follow-up handling is context aware but degrades gracefully when no
  follow-up state has been set.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .grammar import GrammarAnalyzer

# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------


@dataclass
class IntentResult:
    """A detected intent together with a confidence score."""

    intent: str
    confidence: float = 0.0
    entities: Dict[str, Any] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Vocabulary: English, Amharic and transliterated Amharic
# ---------------------------------------------------------------------------

#: Exact affirmative answers.
AFFIRMATIVES: frozenset = frozenset({
    # English
    "yes", "yeah", "yep", "yup", "y", "sure", "ok", "okay", "k", "alright",
    "alrite", "correct", "right", "exactly", "definitely", "absolutely",
    "indeed", "fine", "sure thing",
    # Amharic
    "አዎ", "አዎን", "አዎንታዊ", "እሺ", "አው", "ትክክል", "በእርግጥ", "እሺ ነው",
    # transliterated Amharic
    "ao", "awo", "awon", "esh", "eshi", "ehe", "bikirgin", "be'irgig",
})

#: Affirmative phrases (substring match, slightly lower confidence).
AFFIRMATIVE_PHRASES: Tuple[str, ...] = (
    "that's right", "that is right", "that's correct", "that's true",
    "you're right", "you are right", "i agree", "yes please", "yeah sure",
    "sounds good", "go ahead", "please do", "sure thing",
    # Amharic
    "ትክክል ነው", "አዎ ነው", "አዎ እሺ", "እሺ ነው",
)

#: Exact negative answers.
NEGATIVES: frozenset = frozenset({
    # English
    "no", "nope", "nah", "n", "not", "never", "no way", "nahh",
    "no thanks", "no thank you", "not really", "not at all",
    # Amharic
    "አይ", "አይደለም", "አይሆንም", "አይደል", "አይስማማም", "በጭራሽ", "ፈጽሞ",
    # transliterated Amharic
    "ay", "aydelem", "ayhonem", "ayidel", "bechorash",
})

#: Negative phrases (substring match, slightly lower confidence).
NEGATIVE_PHRASES: Tuple[str, ...] = (
    "no thanks", "no thank you", "i don't think so", "i do not think so",
    "i disagree", "that's wrong", "that is wrong", "that's incorrect",
    "not correct", "not really", "no way", "absolutely not", "definitely not",
    # Amharic
    "ተሳስተሃል", "አይደለም ነው",
)

#: Words/phrases that indicate an *order lookup* (noun sense only).
ORDER_CONTEXT_TERMS: Tuple[str, ...] = (
    "order", "orders", "order status", "my order", "track", "tracking",
    "tracked", "shipment", "delivery status", "where is my", "status of",
    # Amharic
    "ትዕዛዝ", "ትእዛዜ", "ትዕዛዜ", "የእኔ ትዕዛዝ", "ትዕዛዝ ሁኔታ", "መቼ ይደርሳል",
    "የት ነው", "ሁኔታ",
    # transliterated Amharic
    "tizaz", "tizaze", "yene tizaz", "huneta", "deresal", "meche yederesal",
)

#: Contexts in which a long number is almost certainly NOT an order id.
NON_ORDER_NUMBER_TERMS: Tuple[str, ...] = (
    "phone", "mobile", "call", "contact", "tel", "telebirr", "amole", "card",
    "pin", "cvv", "account",
    # Amharic / transliterated
    "ስልክ", "ስልክ ቁጥር", "ካርድ", "ቴሌብር", "አሞሌ", "salk", "telebir", "amole",
)

#: Product/price phrasing that should suppress order-id extraction.
PRODUCT_INDICATORS: Tuple[str, ...] = (
    "buy", "purchase", "search", "find", "looking", "show", "price", "cost",
    "cheap", "expensive", "under", "below", "over", "above", "browse",
    # Amharic
    "ግዛ", "ፈልግ", "አሳይ", "ዋጋ", "ምርት",
    # transliterated Amharic
    "felge", "mayet", "megzat", "waga", "giza", "miret",
)

#: Words that trigger an explicit product search.
PRODUCT_ACTION_TERMS: Tuple[str, ...] = (
    "buy", "purchase", "price", "cost", "search", "find", "looking for",
    "recommend", "show me", "show", "need", "want", "get", "order",
    # Amharic
    "ግዛ", "ፈልግ", "አሳይ", "እፈልጋለሁ", "ምርት", "መግዛት",
    # transliterated Amharic
    "felge", "mayet", "megzat", "giza", "efeligalehu", "waga", "asay",
)

#: Fallback product-name hints when no EntityExtractor is available.
PRODUCT_NAME_HINTS: Tuple[str, ...] = (
    "phone", "iphone", "samsung", "galaxy", "pixel", "laptop", "macbook",
    "computer", "tablet", "ipad", "shirt", "dress", "jeans", "jacket",
    "shoe", "sneaker", "boot", "bag", "handbag", "purse", "backpack",
    "sofa", "table", "chair", "bed", "furniture", "teddy", "toy",
    "watch", "necklace", "ring", "earring", "bracelet", "headphone",
    "speaker", "tv", "camera", "airpods",
    # Amharic / transliterated
    "ልብስ", "ጫማ", "ምርት", "ሸሚዝ", "ቦርሳ", "ሰዓት", "ኮምፒውተር",
    "libs", "chama", "shemiz", "borsa", "telifon", "kompyuter", "miret",
)

#: Complaint patterns (English, Amharic, transliterated Amharic).
COMPLAINT_PATTERNS: Tuple[re.Pattern, ...] = (
    # --- delays ---------------------------------------------------------
    re.compile(r"\b(weeks?|months?|days?|hours?)\s+(ago|late|delay|delayed|wait)\b", re.IGNORECASE),
    re.compile(r"\b(is|was|it's)\s+(late|delayed|delayed)\b", re.IGNORECASE),
    # --- non-arrival ----------------------------------------------------
    re.compile(r"(hasn't|haven't|has not|have not|didn't|did not|never)\s+(arrived|come|shown up|showed up|delivered|sent)", re.IGNORECASE),
    re.compile(r"(not|never)\s+(received|got|get)\b", re.IGNORECASE),
    # --- damaged / defective ---------------------------------------------
    re.compile(r"\b(broken|damaged|defective|faulty|malfunctioning|not working|doesn't work|does not work|won't work|will not work)\b", re.IGNORECASE),
    re.compile(r"\b(wrong item|wrong product|missing item|missing part|incomplete order)\b", re.IGNORECASE),
    # --- bad experience --------------------------------------------------
    re.compile(r"\b(frustrating|annoying|upset|angry|disappointed|terrible|horrible|awful|disgusting|unacceptable|ridiculous)\b", re.IGNORECASE),
    re.compile(r"\b(rip.?off|scam|scammed|cheated|refund me)\b", re.IGNORECASE),
    # --- Amharic ---------------------------------------------------------
    re.compile(r"(ዘግይቷል|ተሰበረ|ተጎዳ|ጉድለት|ተበሳጨሁ|አልደረሰም|አልመጣም|አልተሰራም|አስከፊ|መጥፎ|ስህተት|የተሳሳተ|አልመዘዘው)", re.IGNORECASE),
    # --- transliterated Amharic -------------------------------------------
    re.compile(r"\b(zegitoal|tesebre|tesebara|tegoda|gudlet|tebesachu|alderesem|almetam|alteseram|metfo|askefi|sehitat)\b", re.IGNORECASE),
)

#: Words that route a damage complaint toward returns/warranty instead of
#: immediately escalating to a human.
RETURN_WARRANTY_TERMS: Tuple[str, ...] = (
    "return", "returns", "refund", "exchange", "warranty", "repair", "policy",
    "ቀይር", "መመለስ", "ተመላሽ", "ዋስትና", "ጥገና", "ተመላሽ ገንዘብ",
    "mamech", "wastena", "gudlet", "refund",
)

#: Phrases requesting human support.
HUMAN_SUPPORT_PHRASES: Tuple[str, ...] = (
    # English
    "human", "real person", "real human", "speak to someone", "talk to someone",
    "talk to a human", "speak to a human", "talk to a person", "speak to a person",
    "live agent", "human support", "customer service agent", "representative",
    "not a bot", "transfer me", "connect me to", "get me a human", "agent please",
    "supervisor", "escalate", "talk to staff", "a real person", "someone real",
    # Amharic
    "ከሰው", "ሰው ጋር", "ወኪል", "አገናኝ", "ሰው", "እውነተኛ ሰው", "አገናኘኝ",
    "ያናግሩኝ", "የሰው ድጋፍ",
    # transliterated Amharic
    "sew gar", "wekil", "kesew", "ewnetegna sew", "yewesenegn", "agent",
)

#: Order-change phrases, checked BEFORE the generic order-lookup step so that
#: "modify my order" / "change my address" do not fall into the plain
#: "please give me your order id" path.
_ORDER_CHANGE_RE: re.Pattern = re.compile(
    r"\b(change my order|change order|modify my order|edit order|edit my order|"
    r"change my address|change address|update address|update my address|"
    r"delivery address|change quantity|change my quantity|"
    r"አድራሻ ቀይር|ትዕዛዝ ቀይር|አድራሻ አሻሽል|ትዕዛዝ አሻሽል|"
    r"adrasha keyir|tizaz keyir|adrasha ashejel|tizaz ashejel)\b",
    re.IGNORECASE,
)

#: Action verbs that, combined with an "order" mention, name a specific FAQ
#: topic. Checked before the generic order-lookup step so that "how do i pay
#: for my order" / "i want to cancel my order" do not fall into the plain
#: "please give me your order id" path.
_ORDER_ACTION_TOPICS: Tuple[Tuple[str, str], ...] = (
    ("cancel", "cancellation"),
    ("return", "returns"),
    ("refund", "returns"),
    ("exchange", "returns"),
    ("pay", "payment"),
    ("payment", "payment"),
    ("invoice", "invoice"),
    ("receipt", "invoice"),
)

#: FAQ / support-topic keyword patterns mapped to intents.
#: Ordered so that the most specific topics match first (e.g. international
#: shipping must win over the generic "shipping" topic; invoice/installment
#: must beat the generic "payment" topic). "help" is generic and therefore
#: always last.
TOPIC_PATTERNS: Tuple[Tuple[re.Pattern, str], ...] = (
    # --- international / overseas delivery (most specific) ----------------
    (re.compile(
        r"\b(?:international|internationally|abroad|overseas|outside ethiopia|"
        r"diaspora|worldwide|export|another country|other countries|"
        r"ship to (?:the )?(?:usa|us|uk|europe|america|canada|dubai|qatar|saudi)|"
        r"deliver to (?:the )?(?:usa|us|uk|europe|america|canada|dubai|qatar|saudi)|"
        r"send to (?:the )?(?:usa|us|uk|europe|america|canada|dubai|qatar|saudi)|"
        r"ውጭ አገር|ከኢትዮጵያ ውጭ|ወደ ውጭ|wech agar)\b",
        re.IGNORECASE), "international"),
    # --- order changes (must beat generic "shipping"/"order lookup") ------
    (_ORDER_CHANGE_RE, "order_change"),
    # --- installment / buy-now-pay-later (must beat generic "payment") ----
    (re.compile(
        r"\b(installment|installments|monthly payment|payment plan|payment plans|"
        r"hire purchase|buy on credit|"
        r"ወርሃዊ ክፍያ|በክፍል መግዛት|ክሬዲት|werhawi kefya)\b",
        re.IGNORECASE), "installment"),
    # --- invoice / receipt (must beat generic "payment") -------------------
    (re.compile(
        r"\b(invoice|invoices|receipt|tax invoice|vat invoice|bill|"
        r"ደረሰኝ|ኢንቮይስ|ግብር ደረሰኝ|deresen)\b",
        re.IGNORECASE), "invoice"),
    # --- shipping & delivery ----------------------------------------------
    (re.compile(r"\b(shipping|ship|delivery|deliver|arrive|arrival|courier|ማድረስ|ማድረሻ|አቅርቦት|መቼ ይደርሳል|maderes|akarbot|mechen yederesal)\b", re.IGNORECASE), "shipping"),
    # --- payment ----------------------------------------------------------
    (re.compile(r"\b(pay|payment|payments|telebirr|amole|mpesa|card|cash|ክፍያ|ቴሌብር|አሞሌ|kefya|telebir|amole|መክፈያ)\b", re.IGNORECASE), "payment"),
    # --- returns / exchanges ----------------------------------------------
    (re.compile(r"\b(return|returns|refund|exchange|defective|policy|መመለስ|ተመላሽ|ቀይር|መልስ|mamech|refund)\b", re.IGNORECASE), "returns"),
    # --- warranty ---------------------------------------------------------
    (re.compile(r"\b(warranty|repair|broken|damage|damaged|ጥገና|ዋስትና|የተሰበረ|wastena|gudlet)\b", re.IGNORECASE), "warranty"),
    # --- cancellation -----------------------------------------------------
    (re.compile(r"\b(cancel|cancellation|cancel order|ሰርዝ|ስርዝ|seriz|siriz)\b", re.IGNORECASE), "cancellation"),
    # --- checkout ---------------------------------------------------------
    (re.compile(r"\b(checkout|check out|purchase now|buy now|ክፍያ አጠናቅ|ቼክአውት)\b", re.IGNORECASE), "checkout"),
    # --- stock / availability (guarded: see _match_topic) -----------------
    (re.compile(r"\b(stock|in stock|out of stock|available|availability|restock|back in stock|ክምችት|በክምችት|ክምችት ላይ|stok)\b", re.IGNORECASE), "stock"),
    # --- product authenticity ---------------------------------------------
    (re.compile(r"\b(genuine|authentic|authenticity|original product|real product|counterfeit|fake|ትክክለኛ|ኦሪጂናል|ዋና|jarida|tin)\b", re.IGNORECASE), "authenticity"),
    # --- wholesale / bulk -------------------------------------------------
    (re.compile(r"\b(wholesale|bulk|bulk order|bulk price|dealer|reseller|retailer|የጅምላ|ጅምላ|lemagi)\b", re.IGNORECASE), "wholesale"),
    # --- gift / wrapping --------------------------------------------------
    (re.compile(r"\b(gift|gifts|gift card|gift wrap|wrapping|wrapped|ስጦታ|የስጦታ|መጠቅለያ)\b", re.IGNORECASE), "gift"),
    # --- contact ----------------------------------------------------------
    (re.compile(r"\b(contact|email|phone|call|reach|address|location|support email|support phone|customer service|ያናግሩ|ኢሜይል|ስልክ|አድራሻ|salk|adrasha)\b", re.IGNORECASE), "contact"),
    # --- business hours ----------------------------------------------------
    (re.compile(r"\b(hours|open|close|business hours|opening|closing|ሰዓት|ሰዓቶች|ስራ ሰዓት|se'at)\b", re.IGNORECASE), "hours"),
    # --- promotions / discounts --------------------------------------------
    (re.compile(
        r"\b(promo|promos|promotion|promotions|discount|discounts|deal|deals|"
        r"offer|offers|sale|sales|coupon|coupons|voucher|vouchers|code|codes|"
        r"ቅናሽ|ዋጋ ቅናሽ|diskount|promoshin)\b",
        re.IGNORECASE), "promotions"),
    # --- loyalty -----------------------------------------------------------
    (re.compile(r"\b(loyalty|points|rewards|membership|ነጥብ|ታማኝ|ሽልማት|nib)\b", re.IGNORECASE), "loyalty"),
    # --- generic help (always last) ----------------------------------------
    (re.compile(r"\b(help|support|assist|assistance|problem|issue|how do i|how do we|እርዳታ|እገዛ|ችግር|erdata|egeza|chigir)\b", re.IGNORECASE), "help"),
)

#: Greetings (English, Amharic, transliterated).
GREETING_TERMS: Tuple[str, ...] = (
    "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
    "selam", "salam", "salem", "yo", "what's up", "sup",
    "ሰላም", "ሠላም", "እንደምን", "እንደምን አደርክ", "እንደምን አለህ", "እንደምን አላችሁ",
    "selam alekum", "salam alekum",
)

#: Farewells (English, Amharic, transliterated). "thanks" is handled by
#: small talk so the bot can reply with a friendly "you're welcome".
FAREWELL_TERMS: Tuple[str, ...] = (
    "bye", "goodbye", "see you", "see ya", "later", "take care", "good night",
    "ግልግል", "ቻው", "ደህና ሁን", "ደህና እደር", "በደህና", "bye bye",
    "dehna hun", "chaw", "ba dehna",
)

#: Small-talk phrases (English, Amharic, transliterated).
SMALL_TALK_PHRASES: Tuple[str, ...] = (
    "how are you", "how's it going", "how is it going", "how's your day",
    "how's the weather", "what's up", "what's new", "how's work",
    "how's family", "what are you doing", "what can you do", "who are you",
    "are you a robot", "are you a bot", "what is your name", "your name",
    "thanks", "thank you", "thanks a lot", "thank you very much", "thanks for",
    "እንደምን አለህ", "ሰላም", "እንደምን አደርክ", "እንደምን አላችሁ", "ደህና ነህ",
    "አመሰግናለሁ", "አመሰግናለሁ", "ብዙ አመሰግናለሁ",
    "endemin aleh", "endemin aderk", "dehna neh", "ameseginalehu",
)

#: Words that suppress the shopping-intent guard inside small-talk checks.
SHOPPING_TERMS: Tuple[str, ...] = (
    "buy", "purchase", "order", "price", "shop", "ምርት", "ግዛ", "ፈልግ", "አሳይ",
    "megzat", "felge", "waga",
)

#: Compiled patterns used by :meth:`IntentDetector.references_last_item`.
_REFERENCE_PHRASES: Tuple[str, ...] = (
    "that one", "this one", "that item", "this item", "the first", "first one",
    "second one", "third one", "add it", "buy it", "get it", "purchase it",
    "order it", "how much is it", "how much for it", "tell me more",
    "more about it", "about that", "about this", "want it", "i'll take it",
    "i will take it", "put it in the cart", "add to cart",
    # Amharic
    "እሱን", "ይህንን", "ያንን", "ጨምረው", "ጨምሪው", "ግዛው", "ዋጋው ስንት ነው",
    "ስለዚህ ንገረኝ", "ስለዚህ", "ይህን አክል", "እነዚህን",
    # transliterated Amharic
    "isu", "yehin", "yanin", "gizaw", "chemerew", "wagaw sint new",
)

#: Bare pronouns that count as references to the last shown product.
_REFERENCE_PRONOUNS: frozenset = frozenset({
    "it", "that", "this", "these", "those", "them", "one",
    "እሱ", "ይሄ", "ይህ", "ያ", "እነዚህ", "እነዚያ",
    "isu", "yih", "ya",
})

#: Short non-product words that must never be treated as a product search.
_NON_PRODUCT_WORDS: frozenset = frozenset({
    "yes", "no", "ok", "okay", "sure", "please", "thanks", "thank", "hello",
    "hi", "hey", "bye", "yep", "nah", "yeah", "nope", "good", "great", "hmm",
    "what", "who", "when", "where", "why", "how", "selam", "ሰላም", "አዎ", "አይ",
})

#: Explicit order-id tokens (e.g. ``ORD-12345``, ``ORDER 12345``).
_EXPLICIT_ORDER_ID_RE: re.Pattern = re.compile(
    r"\b(?:ORD|ORDER)[-_\s]?\d{3,}\b", re.IGNORECASE)
#: Hashtag order ids (e.g. ``#12345``).
_HASHTAG_ID_RE: re.Pattern = re.compile(r"#(\d{4,})")

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Lowercase and trim a message for matching."""
    return text.lower().strip()


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    """Return True if any of ``terms`` appears as a substring of ``text``."""
    return any(term in text for term in terms)


def _compile_terms(terms: Sequence[str]) -> re.Pattern:
    """Compile a set of words/phrases into one word-boundary regex.

    Using ``\\b`` boundaries avoids substring false positives such as ``"hi"``
    matching inside ``"shipping"`` or ``"yo"`` matching inside ``"you"``.
    """
    joined = "|".join(re.escape(term) for term in terms)
    return re.compile(rf"\b(?:{joined})\b", re.IGNORECASE)


#: Compiled word-boundary matchers for phrase-heavy vocabularies.
_GREETING_RE: re.Pattern = _compile_terms(GREETING_TERMS)
_FAREWELL_RE: re.Pattern = _compile_terms(FAREWELL_TERMS)
_SMALL_TALK_RE: re.Pattern = _compile_terms(SMALL_TALK_PHRASES)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class IntentDetector:
    """Detects user intent from a single message.

    Parameters
    ----------
    entity_extractor:
        Optional :class:`~chatbot.nlp.entity_extractor.EntityExtractor` used to
        recognise product-name-only queries. When omitted a small built-in
        keyword list is used instead.
    """

    # Confidence levels ---------------------------------------------------
    HIGH: float = 0.90
    MEDIUM: float = 0.75
    LOW: float = 0.55

    def __init__(self, entity_extractor: Any = None) -> None:
        self.entity_extractor: Any = entity_extractor
        # Grammar-based disambiguation for ambiguous topic phrases.
        self.grammar: GrammarAnalyzer = GrammarAnalyzer(
            entity_extractor=entity_extractor,
            product_hints=PRODUCT_NAME_HINTS,
        )
        # Backwards-compatible accessors.
        self.affirmative = AFFIRMATIVES
        self.negative = NEGATIVES

    # ====================================================================
    # Public API
    # ====================================================================

    def detect(self, message: str, session: Any, context: Any,
               session_service: Any = None) -> str:
        """Detect intent and return only the intent name.

        Wrapper around :meth:`detect_with_confidence` for callers that do not
        need the confidence score.
        """
        return self.detect_with_confidence(
            message, session, context, session_service
        ).intent

    def detect_with_confidence(self, message: str, session: Any, context: Any,
                               session_service: Any = None) -> IntentResult:
        """Detect intent with a confidence score and supporting reasons.

        Parameters
        ----------
        message:
            The raw user message.
        session:
            The current :class:`~chatbot.models.session.Session`.
        context:
            The current :class:`~chatbot.models.memory.ConversationContext`.
        session_service:
            Unused; accepted for API compatibility with earlier versions.
        """
        msg = _normalize(message)
        if not msg:
            return IntentResult("general", 0.0, reasons=["empty_message"])

        # 1. In-conversation follow-up answers ---------------------------
        followup = self._detect_followup(msg, session, context)
        if followup:
            return followup

        # 2. Complaints / negative escalation ----------------------------
        complaint = self._detect_complaint(msg, session, context)
        if complaint:
            return complaint

        # 3. Human support -------------------------------------------------
        if self._detect_human_support(msg, session):
            return IntentResult(
                "human_support", self.HIGH,
                reasons=["human_support_requested"],
            )

        # 4. Buy-by-product-id (e.g. "/buy_5" or "buy5") -------------------
        if self._is_buy_by_id(msg):
            return IntentResult("add_to_cart_id", self.HIGH,
                                reasons=["buy_by_id"])

        # 5. Contextual yes/no follow-through ------------------------------
        contextual = self._detect_contextual_answer(msg, session)
        if contextual:
            return contextual

        # 6. Product references ---------------------------------------------
        if session.last_products and self.references_last_item(msg):
            if _contains_any(msg, ("add", "buy", "get", "purchase", "order",
                                   "ጨምር", "ግዛ", "እዘዝ", "cart",
                                   "chemere", "giza", "ezh")):
                return IntentResult("add_last_product", self.HIGH,
                                    entities={"products": session.last_products},
                                    reasons=["add_last_product"])
            return IntentResult("product_followup", self.MEDIUM,
                                entities={"products": session.last_products},
                                reasons=["product_reference"])

        # 7. Repeat search ---------------------------------------------------
        if session.last_search_keyword and _contains_any(msg, (
                "show more", "more options", "anything else", "see more",
                "again", "ተጨማሪ", "ሌላ", "tesemari", "lela")):
            return IntentResult("repeat_search", self.MEDIUM,
                                reasons=["repeat_search"])

        # 8. Order change (specific, so it beats the generic order lookup) ----
        if _ORDER_CHANGE_RE.search(msg):
            return IntentResult("order_change", self.MEDIUM,
                                reasons=["topic:order_change"])

        # 9. Order-related action requests ("pay/return/cancel my order") -----
        order_action = self._detect_order_action(msg)
        if order_action:
            return IntentResult(order_action, self.MEDIUM,
                                reasons=[f"order_action:{order_action}"])

        # 10. Order lookup ----------------------------------------------------
        order_result = self._detect_order(msg, session)
        if order_result:
            return order_result

        # 11. FAQ / support topics ---------------------------------------------
        topic = self._match_topic(msg)
        if topic:
            return IntentResult(topic, self.MEDIUM,
                                reasons=[f"topic:{topic}"])

        # 12. Greetings --------------------------------------------------------
        if _GREETING_RE.search(msg):
            return IntentResult("greeting", self.HIGH,
                                reasons=["greeting"])

        # 13. Farewells ---------------------------------------------------------
        if _FAREWELL_RE.search(msg):
            return IntentResult("farewell", self.HIGH,
                                reasons=["farewell"])

        # 14. Small talk ----------------------------------------------------------
        if self.is_small_talk(msg):
            return IntentResult("small_talk", self.MEDIUM,
                                reasons=["small_talk"])

        # 15. Product search (explicit wording or name-only) -----------------------
        if _contains_any(msg, PRODUCT_ACTION_TERMS) or self._is_product_query(msg):
            return IntentResult("product_search", self.MEDIUM,
                                reasons=["product_search"])

        # 16. Fallback ---------------------------------------------------------------
        return IntentResult("general", self.LOW, reasons=["no_match"])

    # ====================================================================
    # Detection helpers
    # ====================================================================

    def _detect_followup(self, msg: str, session: Any,
                         context: Any) -> Optional[IntentResult]:
        """Resolve a reply to a pending question the bot asked earlier."""
        if not context or not getattr(context, "awaiting_followup", False):
            return None

        question_type = getattr(context, "last_question_type", None)
        aff_conf = self._affirmative_confidence(msg)
        neg_conf = self._negative_confidence(msg)

        if question_type in ("search", "order", "help"):
            if aff_conf > neg_conf:
                if question_type == "order":
                    return IntentResult("order_lookup", aff_conf,
                                        reasons=["order_followup_yes"])
                if question_type == "search" and session.last_search_keyword:
                    return IntentResult("product_search", aff_conf,
                                        entities={"keyword": session.last_search_keyword},
                                        reasons=["search_followup_yes"])
                return IntentResult("help", aff_conf,
                                    reasons=["help_followup_yes"])
            if neg_conf > aff_conf:
                return IntentResult("farewell", neg_conf,
                                    reasons=["followup_no"])

        # The user ignored the question and typed new information.
        if question_type == "order":
            order_id = self.extract_order_id(msg)
            if order_id:
                session.last_order_id = order_id
                return IntentResult("order_lookup", self.HIGH,
                                    entities={"order_id": order_id},
                                    reasons=["order_id_provided"])
        if question_type == "search" and self._is_product_query(msg):
            return IntentResult("product_search", self.MEDIUM,
                                reasons=["search_term_provided"])
        return None

    def _detect_complaint(self, msg: str, session: Any,
                          context: Any) -> Optional[IntentResult]:
        """Detect complaints and route them to order/FAQ/human handling."""
        is_complaint = any(p.search(msg) for p in COMPLAINT_PATTERNS)
        has_order_mention = _contains_any(
            msg, ("order", "ትዕዛዝ", "tizaz", "my order", "purchase"))
        negative_mood = getattr(session, "user_mood", "neutral") == "negative"

        if not (is_complaint or (has_order_mention and negative_mood)):
            return None

        # Damage complaints that ask about policy are better served by FAQ.
        if is_complaint and _contains_any(msg, RETURN_WARRANTY_TERMS):
            topic = self._match_topic(msg)
            if topic in ("returns", "warranty"):
                return IntentResult(topic, self.MEDIUM,
                                    reasons=["complaint_to_faq"])

        order_id = self.extract_order_id(msg)
        if order_id:
            session.last_order_id = order_id
            return IntentResult("order_lookup", self.HIGH,
                                entities={"order_id": order_id},
                                reasons=["complaint_order_id"])
        if getattr(session, "last_order_id", None):
            return IntentResult("order_followup", self.MEDIUM,
                                reasons=["complaint_order_followup"])

        return IntentResult("human_support", self.HIGH,
                            reasons=["complaint_no_context"])

    def _detect_human_support(self, msg: str, session: Any) -> bool:
        """Detect explicit requests to speak with a human agent."""
        if _contains_any(msg, HUMAN_SUPPORT_PHRASES):
            return True
        # A prior request + a yes answer confirms it.
        if getattr(session, "human_support_requested", False):
            return self._affirmative_confidence(msg) > 0.0
        return False

    def _is_buy_by_id(self, msg: str) -> bool:
        """Match explicit product-id purchase commands (e.g. ``/buy_5``)."""
        if msg.startswith("/buy_") and re.match(r"/buy_\d+", msg):
            return True
        return bool(re.search(r"\b(?:buy|add|ግዛ|ጨምር)[-_]?\d+\b", msg))

    def _detect_contextual_answer(self, msg: str,
                                  session: Any) -> Optional[IntentResult]:
        """Handle yes/no replies following the previous bot intent."""
        aff_conf = self._affirmative_confidence(msg)
        neg_conf = self._negative_confidence(msg)
        last_intent = session.last_intent or session.current_intent

        if aff_conf > neg_conf:
            if last_intent == "checkout" and session.cart:
                return IntentResult("checkout", aff_conf,
                                    reasons=["checkout_yes"])
            if last_intent == "order_lookup" and not session.last_order_id:
                return IntentResult("order_lookup", aff_conf,
                                    reasons=["order_lookup_yes"])
            if last_intent == "product_search" and session.last_search_keyword:
                return IntentResult("product_search", aff_conf,
                                    entities={"keyword": session.last_search_keyword},
                                    reasons=["product_search_yes"])
            if session.last_order_id:
                return IntentResult("order_followup", aff_conf,
                                    reasons=["order_followup_yes"])

        if neg_conf > aff_conf:
            return IntentResult("farewell", neg_conf,
                                reasons=["negative_answer"])
        return None

    def _detect_order_action(self, msg: str) -> Optional[str]:
        """Map an order-related action request to its FAQ topic.

        Grammar rule: when an action verb ("pay", "return", "cancel",
        "refund", "exchange") governs the object "order", the sentence is a
        *topic request* ("how do i pay for my order") rather than an order
        lookup, so it must not fall into the generic order-id prompt.
        """
        if "order" not in msg and "ትዕዛዝ" not in msg and "tizaz" not in msg:
            return None
        for verb, topic in _ORDER_ACTION_TOPICS:
            if verb in msg:
                return topic
        return None

    def _detect_order(self, msg: str, session: Any) -> Optional[IntentResult]:
        """Detect order lookups without misfiring on product searches."""
        order_id = self.extract_order_id(msg)

        # Explicit ID in a recognised format is a very strong signal.
        if order_id and _EXPLICIT_ORDER_ID_RE.search(msg) or _HASHTAG_ID_RE.search(msg):
            session.last_order_id = order_id
            return IntentResult("order_lookup", self.HIGH,
                                entities={"order_id": order_id},
                                reasons=["explicit_order_id"])

        # A bare numeric message is probably an order id (no product words).
        if order_id and re.match(r"^\d{4,}$", msg):
            session.last_order_id = order_id
            return IntentResult("order_lookup", self.MEDIUM,
                                entities={"order_id": order_id},
                                reasons=["bare_order_id"])

        # Order *context* words with an id, e.g. "track order 1234".
        if order_id:
            session.last_order_id = order_id
            return IntentResult("order_lookup", self.MEDIUM,
                                entities={"order_id": order_id},
                                reasons=["context_order_id"])

        # Order phrasing without an id yet -> prompt for the id.
        if _contains_any(msg, ORDER_CONTEXT_TERMS):
            return IntentResult("order_lookup", self.LOW,
                                reasons=["order_context_no_id"])

        # Following up on an already-known order.
        if session.last_order_id and _contains_any(msg, (
                "status", "arrive", "when", "delivery", "update", "delayed",
                "ሁኔታ", "መቼ", "አድራሻ", "huneta", "meche", "adrasha")):
            return IntentResult("order_followup", self.MEDIUM,
                                entities={"order_id": session.last_order_id},
                                reasons=["order_followup_keywords"])
        return None

    def _match_topic(self, msg: str) -> Optional[str]:
        """Return the FAQ topic that best fits the message.

        All keyword matches are collected first; then grammar rules resolve
        "which is which" when a topic word is really a product modifier
        (e.g. "in stock", "genuine iphone", "a gift for my mom") or when a
        specific topic competes with a generic one (installment vs payment,
        international vs shipping, invoice vs payment).
        """
        candidates = [intent for pattern, intent in TOPIC_PATTERNS
                      if pattern.search(msg)]
        if not candidates:
            return None
        return self._resolve_topic_grammar(msg, candidates)

    def _resolve_topic_grammar(self, msg: str,
                               candidates: List[str]) -> Optional[str]:
        """Apply grammar rules to a list of keyword-matched topics."""
        g = self.grammar

        # 1. Topic words that are really product modifiers collapse to a
        #    product search (handled later in the detection pipeline).
        if "stock" in candidates:
            if g.resolve_stock(msg) == "product_search":
                candidates = [c for c in candidates if c != "stock"]
        if "gift" in candidates and g.resolve_gift(msg) == "product_search":
            candidates = [c for c in candidates if c != "gift"]
        if "authenticity" in candidates \
                and g.resolve_authenticity(msg) == "product_search":
            candidates = [c for c in candidates if c != "authenticity"]
        if "wholesale" in candidates \
                and g.resolve_wholesale(msg) == "product_search":
            candidates = [c for c in candidates if c != "wholesale"]

        if not candidates:
            return None

        # 2. Specific topic vs generic topic pairs.
        if {"installment", "payment"} <= set(candidates):
            decision = g.resolve_installment(msg)
            if decision in ("installment", "payment"):
                candidates = [decision]
        elif {"invoice", "payment"} <= set(candidates):
            decision = g.resolve_invoice(msg)
            if decision in ("invoice", "payment"):
                candidates = [decision]
        elif {"international", "shipping"} <= set(candidates):
            decision = g.resolve_international(msg)
            if decision in ("international", "shipping"):
                candidates = [decision]
        elif {"gift", "payment"} <= set(candidates):
            # "gift card" mentions the gift-card service, not a payment method.
            if g.resolve_gift(msg) == "gift":
                candidates = ["gift"]
            else:
                candidates = [c for c in candidates if c != "gift"]

        # 3. Precedence order from TOPIC_PATTERNS breaks any remaining tie.
        return candidates[0]

    def _is_product_query(self, msg: str) -> bool:
        """True when a short message is likely a product-name-only search."""
        if msg in _NON_PRODUCT_WORDS:
            return False
        words = msg.split()
        if len(words) > 6:
            return False
        # Brand/product hints are always a safe trigger.
        if _contains_any(msg, PRODUCT_NAME_HINTS):
            return True
        if self.entity_extractor is not None:
            return bool(self.entity_extractor.extract_search_keyword(msg))
        return False

    # ====================================================================
    # Answer helpers
    # ====================================================================

    def _affirmative_confidence(self, message: str) -> float:
        """Return a confidence in ``[0, 1]`` that the message is a 'yes'."""
        msg = _normalize(message)
        if msg in AFFIRMATIVES:
            return 0.95
        if any(phrase in msg for phrase in AFFIRMATIVE_PHRASES):
            return 0.85
        if re.match(r"^(yeah|yep|yes|yup|ok|okay|sure|alright)[\s,!.]+", msg):
            return 0.80
        return 0.0

    def _negative_confidence(self, message: str) -> float:
        """Return a confidence in ``[0, 1]`` that the message is a 'no'."""
        msg = _normalize(message)
        if msg in NEGATIVES:
            return 0.95
        if any(phrase in msg for phrase in NEGATIVE_PHRASES):
            return 0.85
        if re.match(r"^(no|nope|nah|not)[\s,!.]+", msg):
            return 0.80
        return 0.0

    # ====================================================================
    # Public boolean helpers (kept for backward compatibility)
    # ====================================================================

    def is_affirmative(self, message: str) -> bool:
        """True when the message is a 'yes'-type answer."""
        return self._affirmative_confidence(message) > 0.0

    def is_negative(self, message: str) -> bool:
        """True when the message is a 'no'-type answer."""
        return self._negative_confidence(message) > 0.0

    def is_small_talk(self, message: str) -> bool:
        """Detect casual small talk, ignoring shopping-related phrases."""
        msg = _normalize(message)
        if _contains_any(msg, SHOPPING_TERMS):
            return False
        return bool(_SMALL_TALK_RE.search(msg))

    def wants_human_support(self, message: str) -> bool:
        """Detect when the user explicitly wants to reach a human."""
        return _contains_any(_normalize(message), HUMAN_SUPPORT_PHRASES)

    def references_last_item(self, message: str) -> bool:
        """True when the message refers to the previously shown product."""
        msg = _normalize(message)
        if any(phrase in msg for phrase in _REFERENCE_PHRASES):
            return True
        return msg in _REFERENCE_PRONOUNS

    # ====================================================================
    # Order-id extraction
    # ====================================================================

    def extract_order_id(self, message: str) -> Optional[str]:
        """Extract an order id from a message, or ``None``.

        Rules, in order of precedence:
          1. ``ORD-1234`` / ``ORD 1234`` / ``#1234`` explicit tokens.
          2. A message that is *entirely* 4+ digits (bare order id).
          3. A 4+ digit number appearing alongside order *context* words.

        Product searches, price filters and phone numbers never match.
        """
        text = message.strip()
        msg = _normalize(text)

        # 1. Explicit order-id tokens are always accepted.
        m = _EXPLICIT_ORDER_ID_RE.search(text)
        if m:
            return m.group(0)
        m = _HASHTAG_ID_RE.search(text)
        if m:
            return m.group(1)

        # 2. Product/price wording must never be treated as an order id.
        if _contains_any(msg, PRODUCT_INDICATORS):
            return None

        # 3. Phone numbers, payment refs etc. are not order ids.
        if _contains_any(msg, NON_ORDER_NUMBER_TERMS):
            return None

        # 4. A bare 4+ digit number is treated as an order id.
        if re.match(r"^\d{4,}$", text):
            return text

        # 5. A 4+ digit number inside explicit order context.
        if _contains_any(msg, ORDER_CONTEXT_TERMS):
            m = re.search(r"\b(\d{4,})\b", text)
            if m:
                return m.group(1)

        return None
