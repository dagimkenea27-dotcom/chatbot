# chatbot/nlp/entity_extractor.py
import re
from typing import Dict, List, Optional


class EntityExtractor:
    """Extracts entities from user messages."""
    
    def extract(self, message: str, context) -> Dict:
        """Extract entities from message."""
        entities = {}
        message_lower = message.lower()
        
        # Extract product names
        product_patterns = [
            r'(phone|iphone|samsung|galaxy|pixel|macbook|dell|hp|laptop|computer)',
            r'(shirt|dress|jeans|jacket|shoe|boot|sneaker|handbag|bag|purse)',
            r'(sofa|table|chair|bed|furniture|decor|vase|lamp|rug|coaster)',
            r'(earring|necklace|bracelet|ring|jewelry|accessory)',
            r'(teddy bear|bear|stuffed animal|toy)',
        ]
        
        for pattern in product_patterns:
            match = re.search(pattern, message_lower)
            if match:
                entities["product_type"] = match.group(1)
                break
        
        # Extract order ID
        order_match = re.search(r'(ORD[-\s]?\d+|#\d{4,})', message, re.IGNORECASE)
        if order_match:
            entities["order_id"] = order_match.group(1)
        else:
            if any(w in message_lower for w in ["order", "track", "ትዕዛዝ", "ትእዛዜ", "ትዕዛዜ", "ትእዛዝ"]):
                num_match = re.search(r'\b(\d{4,})\b', message)
                if num_match:
                    entities["order_id"] = num_match.group(1)
        
        # Extract price filters
        price_match = re.search(r'(under|below|less than|max|over|above|more than|min)\s*(\d+)', message_lower)
        if price_match:
            if not any(w in message_lower for w in ["order", "track", "ትዕዛዝ","ትእዛዜ", "ትዕዛዜ", "ትእዛዝ"]):
                entities["price_filter"] = {
                    "operator": price_match.group(1),
                    "value": int(price_match.group(2))
                }
        
        # Detect if user is asking a question
        if "?" in message:
            entities["is_question"] = True
            question_types = ["how", "what", "where", "when", "why", "can"]
            for qt in question_types:
                if qt in message_lower:
                    entities["question_type"] = qt
                    break
        
        # Detect references
        if any(phrase in message_lower for phrase in ["it", "that", "this", "those", "these", "one", "them"]):
            entities["has_reference"] = True
        
        return entities
    
    def extract_search_keyword(self, message: str) -> Optional[str]:
        """Extract search keyword from message."""
        message_lower = message.lower().strip()
        
        non_product_phrases = [
            # Order / support topics (never product searches)
            "track my order", "track order", "my order", "order status", "order number",
            "shipping", "delivery", "payment", "contact", "hours", "help", "support",
            "return policy", "warranty", "cancel order", "cancellation", "human support",
            "ትዕዛዜ", "ትዕዛዝ", "ትእዛዜ", "ትእዛዝ", "tizaze", "tizaz", "huneta",
            # Greetings / small talk
            "how are you", "how's it going", "how is it going", "how's your day",
            "what's up", "what's new", "good morning", "good afternoon",
            "good evening", "thanks", "thank you", "thank you very much",
            "እንደምን", "ሰላም", "አመሰግናለሁ", "እንደምን አደርክ",
            # Questions about the bot / site
            "who are you", "what is your name", "what's your name", "what can you do",
            "are you a robot", "are you a bot", "what is sami", "who is sami",
            "how do you work", "where are you",
            # Miscellaneous non-product queries
            "hello", "hi there", "bye", "see you", "exit", "reset", "stop",
        ]
        if any(phrase in message_lower for phrase in non_product_phrases):
            return None
        
        filler = [
            r"^(show me|show|search for|search|find|looking for|i'm looking for|"
            r"i want to buy|want to buy|i want to get|i would like|i'd like|would like|"
            r"i want|want to buy|i need to buy|need to buy|do you have|can i get|"
            r"i need|need|buy|get me|recommend|tell me about|what about|show me some|"
            r"ፈልግ|አሳይ|እፈልጋለሁ|ግዛ|መግዛት|felge|asay|efeligalehu|giza|megzat|mayet)\s+",
            r"\s+(please|pls|now|today|asap|right now)$",
            r"\b(a|an|the|some|any)\b\s*",
        ]
        kw = message_lower
        for pat in filler:
            kw = re.sub(pat, "", kw, flags=re.IGNORECASE).strip()
        
        # A leftover bare question word ("what", "how", ...) is not a product.
        if re.match(r"^(what|what's|who|when|where|why|how|can|could|do|does)\b", kw):
            return None
        
        kw = re.sub(
            r"\b(under|below|above|over|max|min|cheaper than|more than|less than|"
            r"in stock|available|cheapest|newest|sort by|price asc|price desc)\b.*",
            "", kw, flags=re.IGNORECASE
        ).strip()
        kw = re.sub(r"\s{2,}", " ", kw).strip()
        
        if len(kw) >= 2 and not kw.isdigit():
            return kw
        return None
    
    def extract_product_filters(self, message: str) -> dict:
        """Extract product filters from message."""
        filters = {}
        message_lower = message.lower()
        
        m = re.search(r"\b(?:under|below|less than|max|ቢበዛ)\s*(\d+[\d,]*)", message_lower)
        if m:
            filters["max_price"] = float(m.group(1).replace(",", ""))
        
        m = re.search(r"\b(?:above|over|more than|min|at least|ቢያንስ)\s*(\d+[\d,]*)", message_lower)
        if m:
            filters["min_price"] = float(m.group(1).replace(",", ""))
        
        if re.search(r"\b(in stock|available|ክምችት ላይ)\b", message_lower):
            filters["in_stock"] = True
        
        if re.search(r"\b(cheapest|lowest price|price asc|ርካሽ)\b", message_lower):
            filters["sort"] = "price_asc"
        elif re.search(r"\b(most expensive|highest price|price desc|ውድ)\b", message_lower):
            filters["sort"] = "price_desc"
        elif re.search(r"\b(newest|latest|new arrivals|አዲስ)\b", message_lower):
            filters["sort"] = "newest"
        
        return filters
    
    def format_filter_phrase(self, filters: dict) -> str:
        """Format filters as a natural language phrase."""
        parts = []
        if "min_price" in filters:
            parts.append(f"above {filters['min_price']:.0f}")
        if "max_price" in filters:
            parts.append(f"under {filters['max_price']:.0f}")
        if filters.get("in_stock"):
            parts.append("in stock")
        if filters.get("sort") == "price_asc":
            parts.append("cheapest")
        elif filters.get("sort") == "price_desc":
            parts.append("most expensive")
        elif filters.get("sort") == "newest":
            parts.append("newest")
        return " ".join(parts)
    
    def extract_topics(self, message: str) -> List[str]:
        """Extract conversation topics."""
        topics = []
        message_lower = message.lower()
        
        topic_keywords = {
            "shopping": ["buy", "purchase", "shop", "order", "checkout", "ግዛ", "ገዛ", "እዘዝ"],
            "electronics": ["phone", "laptop", "tablet", "camera", "tv", "computer", "ኤሌክትሮኒክስ"],
            "clothing": ["shirt", "dress", "jeans", "jacket", "shoe", "boot", "ልብስ", "ጫማ"],
            "home": ["furniture", "kitchen", "decor", "sofa", "table", "chair", "ቤት"],
            "delivery": ["shipping", "delivery", "track", "arrive", "ማድረሻ", "አቅርቦት", "መቼ"],
            "payment": ["pay", "payment", "cash", "card", "telebirr", "amole", "ክፍያ", "ቴሌብር"],
            "support": ["help", "support", "assist", "problem", "issue", "እርዳታ", "ችግር"]
        }
        
        for topic, keywords in topic_keywords.items():
            if any(kw in message_lower for kw in keywords):
                topics.append(topic)
        return topics
    
    def categorize_keyword(self, keyword: str) -> Optional[str]:
        """Categorize a search keyword."""
        keyword_lower = keyword.lower()
        categories = {
            "electronics": [
                "phone", "iphone", "samsung", "galaxy", "pixel", "laptop", "macbook",
                "tablet", "ipad", "camera", "tv", "computer", "speaker", "headphone",
                "airpods", "charger", "ቴሊፎን", "ኮምፒውተር", "ላፕቶፕ",
                "telifon", "kompyuter", "laptop", "kamera",
            ],
            "clothing": [
                "shirt", "dress", "jeans", "jacket", "suit", "skirt", "top", "trousers",
                "pants", "ልብስ", "ሸሚዝ", "ቀሚስ", "ሱሪ", "libs", "shemiz", "kemis", "suri",
            ],
            "shoes": [
                "shoe", "boot", "sneaker", "sandal", "heel", "slipper", "ጫማ", "ብስኬት",
                "chama", "sneaker",
            ],
            "bags": [
                "bag", "handbag", "purse", "backpack", "wallet", "ቦርሳ", "ቻንታ",
                "borsa", "chanta",
            ],
            "accessories": [
                "earring", "necklace", "bracelet", "ring", "watch", "belt", "sunglasses",
                "የጆሮ", "ሀብል", "ቀለበት", "ክሎች", "earring", "habl", "kelebet", "se'at",
            ],
            "home": [
                "sofa", "table", "chair", "bed", "furniture", "decor", "vase", "lamp",
                "rug", "curtain", "ቤት", "ሶፋ", "ጠረጴዛ", "ወንበር", "አልጋ", "sofa", "tesrepiza",
                "wonber", "alga",
            ],
            "toys": [
                "teddy", "bear", "toy", "doll", "game", "puzzle", "አሻንጉሊት", "ሀብታም",
                "ashangulit",
            ],
            "kitchen": [
                "cookware", "utensil", "appliance", "pot", "pan", "knife", "kettle",
                "blender", "ኩሽና", "ፓን", "knife", "kitchen",
            ],
        }
        for category, keywords in categories.items():
            if any(kw in keyword_lower for kw in keywords):
                return category
        return None
    
    def extract_name(self, message: str) -> Optional[str]:
        """Extract user name from message."""
        match = re.match(r"^(?:my name is|i am|i'm|call me|name is)\s+([a-zA-Z\u1200-\u137f\s]+)", message.lower())
        if match:
            return match.group(1).strip()
        return None
    
    def contains_amharic(self, message: str) -> bool:
        """Check if message contains Amharic characters."""
        return bool(re.search(r'[\u1200-\u137f]', message))