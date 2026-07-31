# chatbot/models/session.py
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class Session:
    """User session data model."""
    user_id: str
    conversation_history: List[Dict] = field(default_factory=list)
    current_intent: Optional[str] = None
    last_intent: Optional[str] = None
    last_product: Optional[Dict] = None
    last_products: List[Dict] = field(default_factory=list)
    last_search_keyword: Optional[str] = None
    last_product_filters: Dict = field(default_factory=dict)
    last_order_id: Optional[str] = None
    message_count: int = 0
    human_support_requested: bool = False
    cart: List = field(default_factory=list)
    language: str = "en"
    user_name: Optional[str] = None
    user_preferences: Dict = field(default_factory=dict)
    browsing_history: List[Dict] = field(default_factory=list)
    sentiment_history: List[str] = field(default_factory=list)
    last_interaction_time: str = field(default_factory=lambda: datetime.now().isoformat())
    conversation_topics: List[str] = field(default_factory=list)
    user_mood: str = "neutral"
    personalization_data: Dict = field(default_factory=dict)
    last_viewed_category: Optional[str] = None
    promo_aware: bool = False
    loyalty_aware: bool = False
    contact_count: int = 0
    complaint_count: int = 0
    faq_topics_seen: List[str] = field(default_factory=list)
    
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any):
        setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Reconstruct Session dataclass from dictionary safely."""
        if not isinstance(data, dict):
            return cls(user_id=str(data or ""))
        from dataclasses import fields
        valid_keys = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "user_id": self.user_id,
            "conversation_history": self.conversation_history,
            "current_intent": self.current_intent,
            "last_intent": self.last_intent,
            "last_product": self.last_product,
            "last_products": self.last_products,
            "last_search_keyword": self.last_search_keyword,
            "last_product_filters": self.last_product_filters,
            "last_order_id": self.last_order_id,
            "message_count": self.message_count,
            "human_support_requested": self.human_support_requested,
            "cart": self.cart,
            "language": self.language,
            "user_name": self.user_name,
            "user_preferences": self.user_preferences,
            "browsing_history": self.browsing_history,
            "sentiment_history": self.sentiment_history,
            "last_interaction_time": self.last_interaction_time,
            "conversation_topics": self.conversation_topics,
            "user_mood": self.user_mood,
            "personalization_data": self.personalization_data,
            "last_viewed_category": self.last_viewed_category,
            "promo_aware": self.promo_aware,
            "loyalty_aware": self.loyalty_aware,
            "contact_count": self.contact_count,
            "complaint_count": self.complaint_count,
            "faq_topics_seen": self.faq_topics_seen,
        }