# chatbot/utils/config.py
import os
from typing import Dict, Any


class Config:
    """Configuration manager."""
    
    def __init__(self):
        self._config = {
            "shop_name": os.getenv("SHOP_NAME", "GojoShop.et"),
            "support_email": os.getenv("SHOP_SUPPORT_EMAIL", "support@gojoshop.et"),
            "support_phone": os.getenv("SHOP_SUPPORT_PHONE", "+251988664488"),
            "support_hours": os.getenv("SHOP_SUPPORT_HOURS", "Mon–Sat, 9:00 AM – 6:00 PM EAT"),
            "language": os.getenv("DEFAULT_LANGUAGE", "en"),
            "max_history": int(os.getenv("MAX_HISTORY", "20")),
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value."""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set config value."""
        self._config[key] = value