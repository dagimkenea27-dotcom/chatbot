# chatbot/nlp/transliteration.py
"""Transliterated-Amharic (Latin script) to Ethiopic script normalization.

Ethiopian users frequently type Amharic using Latin letters (e.g. "felige
neber" for "ፈልጌ ነበር"). This module maps the most common transliterated
shopping phrases back to their Ethiopic equivalents so the existing Amharic
detection paths (intent matching, search-keyword stripping, language switch)
work unchanged.

Design notes
------------
* Replacement is greedy: longest phrases are tried first so "felige neber"
  is matched before "felige" alone.
* Matches are word-boundary aware so "gari" does not corrupt "gariya".
* The map deliberately targets Ethiopic script rather than English so that
  ``contains_amharic()`` also flips the session language to Amharic.
"""
from __future__ import annotations

import re
from typing import Dict, Tuple

#: Transliterated Amharic phrase -> canonical Ethiopic phrase.
#: Ordered longest-first (longer phrases must win over their sub-prefixes).
_TRANSLITERATION_MAP: Dict[str, str] = {
    # ---- search / browse verbs -------------------------------------------
    "felige neber": "ፈልጌ ነበር",          # I was looking for
    "feligegne": "ፈልጌኝ",                # I am looking for
    "felige": "ፈልጌ",                     # I searched (for)
    "efeligalehu": "እፈልጋለሁ",            # I want / I am looking for
    "efeligallu": "እፈልጋለሁ",
    "efelgalew": "እፈልጋለሁ",
    "felge": "ፈልግ",                      # search!
    "felig": "ፈልግ",
    "filge": "ፈልግ",
    "asayen": "አሳየኝ",                    # show me
    "asayegn": "አሳየኝ",
    "asay": "አሳይ",                        # show
    "asaya": "አሳይ",
    "gizene": "ግዛኝ",                      # buy me
    "giza": "ግዛ",                          # buy
    "gize": "ግዛ",
    "megzat": "መግዛት",                    # to buy
    "megizat": "መግዛት",
    "megza": "መግዛት",
    "maginet": "ማግኘት",                    # to get / find
    "meginet": "ማግኘት",
    "miret": "ምርት",                        # product
    "mert": "ምርት",
    "waga": "ዋጋ",                          # price
    "sint new": "ስንት ነው",               # how much is it
    "sint neber": "ስንት ነው",
    "wagaw sint new": "ዋጋው ስንት ነው",
    # ---- cart -------------------------------------------------------------
    "gariyen asay": "ጋሪዬን አሳይ",        # show my cart
    "gariye asay": "ጋሪዬ አሳይ",
    "gariye": "ጋሪዬ",                     # my cart
    "gariyeni": "ጋሪዬን",
    "gari": "ጋሪ",                          # cart
    "gar": "ጋሪ",
    # ---- cart removal -----------------------------------------------------
    "kegariye aswegid": "ከጋሪዬ አስወግድ", # remove from my cart
    "kegari aswegid": "ከጋሪ አስወግድ",
    "kegariye atfa": "ከጋሪዬ አጥፋ",
    "kegari atfa": "ከጋሪ አጥፋ",
    "kegariye": "ከጋሪዬ",
    "kegari": "ከጋሪ",
    "ke gari": "ከጋሪ",
    "aswegiden": "አስወግደኝ",             # remove (for me)
    "aswegid": "አስወግድ",                  # remove
    "atfa": "አጥፋ",                        # delete / discard
    "awred": "አውርድ",                       # take down / remove
    "siyawel": "ሲያወግድ",                  # removing
    # ---- orders / tracking ------------------------------------------------
    "yene tizaz": "የእኔ ትዕዛዝ",           # my order
    "tizaze": "ትዕዛዜ",                    # my order
    "tizaz": "ትዕዛዝ",                      # order
    "huneta": "ሁኔታ",                      # status
    "meche yederesal": "መቼ ይደርሳል",     # when will it arrive
    "meche yedresal": "መቼ ይደርሳል",
    "meche": "መቼ",                        # when
    "deresal": "ደርሷል",                    # (it) has arrived
    # ---- support / help ---------------------------------------------------
    "sew gar": "ሰው ጋር",                  # with a person
    "ewnetegna sew": "እውነተኛ ሰው",      # real person
    "wekil": "ወኪል",                       # agent
    "kesew": "ከሰው",                       # from a person
    "erdata": "እርዳታ",                    # help
    "egeza": "እገዛ",                       # help
    "chigir": "ችግር",                      # problem
    "chiger": "ችግር",
    # ---- payments / delivery ----------------------------------------------
    "kefya": "ክፍያ",                       # payment
    "mekefel": "መክፈል",                    # to pay
    "maderes": "ማድረስ",                    # delivery
    "madires": "ማድረስ",
    "akarbot": "አቅርቦት",                  # delivery / supply
    "akababi": "አካባቢ",                   # area
    # ---- greetings / courtesy ---------------------------------------------
    "endemin aleh": "እንደምን አለህ",       # how are you
    "endemin aderk": "እንደምን አደርክ",
    "endemin alachu": "እንደምን አላችሁ",
    "dehna neh": "ደህና ነህ",               # are you well
    "ameseginalehu": "አመሰግናለሁ",        # thank you
    "amesegnalehu": "አመሰግናለሁ",
    "dehna hun": "ደህና ሁን",               # goodbye (be well)
    "badeyna": "በደህና",
    "chaw": "ቻው",
    "selam": "ሰላም",                       # hello / peace
    "salam": "ሰላም",
    "tenastelign": "ተናስተልኝ",             # how are you (formal)
    # ---- FAQs / topics -----------------------------------------------------
    "wastena": "ዋስትና",                   # warranty
    "wassetna": "ዋስትና",
    "mamech": "መመለስ",                    # return
    "mameles": "መመለስ",
    "telebir": "ቴሌብር",                   # Telebirr
    "tele birr": "ቴሌብር",
    "amole": "አሞሌ",                        # Amole
    "salk": "ስልክ",                          # phone
    "adrasha": "አድራሻ",                    # address
    "kibrit": "ክብረት",                    # (rare)
    "se'at": "ሰዓት",                        # time / hours
    "sehat": "ሰዓት",
    "seriz": "ሰርዝ",                        # cancel
    "siriz": "ስርዝ",
    "kinash": "ቅናሽ",                      # discount
    "nib": "ነጥብ",                          # loyalty points
    "libs": "ልብስ",                          # clothes
    "chama": "ጫማ",                          # shoes
    "shemiz": "ሸሚዝ",                        # shirt
    "borsa": "ቦርሳ",                        # bag
    "telifon": "ቴሊፎን",                    # phone (device)
    "kompyuter": "ኮምፒውተር",              # computer
    "kamera": "ካሜራ",                       # camera
}

#: Compiled word-boundary matchers, longest phrase first.
_TRANSLIT_ENTRIES: Tuple[Tuple[re.Pattern, str], ...] = tuple(
    (re.compile(rf"(?<!\w){re.escape(latin)}(?!\w)", re.IGNORECASE), ethiopic)
    for latin, ethiopic in sorted(
        _TRANSLITERATION_MAP.items(),
        key=lambda kv: len(kv[0].split()),
        reverse=True,
    )
)


def normalize_transliteration(message: str) -> str:
    """Replace transliterated Amharic phrases with their Ethiopic form.

    Unmatched text (English, product names, Ethiopic already present) is
    passed through unchanged.
    """
    if not message:
        return message
    result = message
    for pattern, ethiopic in _TRANSLIT_ENTRIES:
        result = pattern.sub(ethiopic, result)
    return result


#: Ethiopic product-name aliases -> Latin so Ethiopic removal keywords can be
#: matched back to the Latin names stored in the cart/DB. Longest first.
_ETHIOPIC_ALIASES: Dict[str, str] = {
    "አይፎን ፕሮ ማክስ": "iPhone Pro Max",
    "አይፎን ፕሮ": "iPhone Pro",
    "አይፎን": "iPhone",
    "ማክቡክ ፕሮ": "MacBook Pro",
    "ማክቡክ": "MacBook",
    "ሳምሰንግ": "Samsung",
    "ኖክያ": "Nokia",
    "ስልክ": "phone",
    "ጫማ": "shoe",
    "ሸሚዝ": "shirt",
    "ቲሸርት": "T-shirt",
    "ሰዓት": "watch",
    "ኮምፒውተር": "computer",
    "ማስጫ": "charger",
    "ሄድፎን": "headphone",
    "ኢራሰር": "earphone",
}

_ETHIOPIC_ALIAS_ENTRIES: Tuple[Tuple[re.Pattern, str], ...] = tuple(
    (re.compile(rf"(?<!\w){re.escape(ethiopic)}(?!\w)"), latin)
    for ethiopic, latin in sorted(
        _ETHIOPIC_ALIASES.items(),
        key=lambda kv: len(kv[0]),
        reverse=True,
    )
)


def to_latin(message: str) -> str:
    """Best-effort Ethiopic -> Latin mapping for known product-name aliases.

    Returns a copy of ``message`` with recognized Ethiopic product words
    replaced by their Latin equivalents (e.g. "አይፎን" -> "iPhone"). Unmapped
    text is passed through unchanged.
    """
    if not message:
        return message
    result = message
    for pattern, latin in _ETHIOPIC_ALIAS_ENTRIES:
        result = pattern.sub(latin, result)
    return result
