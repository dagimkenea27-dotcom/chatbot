# chatbot/services/translation_service.py
import json
import os
from typing import Dict


class TranslationService:
    """Manages translations and localization."""
    
    def __init__(self):
        self.translations = self.load_translations()
    
    def load_translations(self) -> Dict:
        """Load localization files with fallback defaults."""
        translations = {}
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        i18n_dir = os.path.join(base_dir, "data", "i18n")
        
        if not os.path.exists(i18n_dir):
            os.makedirs(i18n_dir, exist_ok=True)
        
        for lang in ["en", "am"]:
            path = os.path.join(i18n_dir, f"{lang}.json")
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        translations[lang] = json.load(f)
                else:
                    default = self._get_default_translations(lang)
                    translations[lang] = {"bot": default}
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump({"bot": default}, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Error loading {lang}.json: {e}")
                translations[lang] = {"bot": self._get_default_translations(lang)}
        return translations
    
    def translate(self, session, key: str, **kwargs) -> str:
        """Get translated string with fallback."""
        lang = session.language if session else "en"
        text = self.translations.get(lang, {}).get("bot", {}).get(key)
        if text is None:
            text = self.translations.get("en", {}).get("bot", {}).get(key)
        if text is None:
            text = key
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError, TypeError):
            return text
    
    def _get_default_translations(self, lang: str) -> Dict:
        """Return default translations."""
        # ... (copy from original _get_default_translations method)
        return {}