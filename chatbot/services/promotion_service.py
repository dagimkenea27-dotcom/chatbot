# chatbot/services/promotion_service.py
import json
import os
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any


class PromotionService:
    """Manages scheduled product promotions for the marketing team.

    Promotions are stored in a JSON file (``chatbot/data/promotions.json``) so
    they can be fully managed through the admin dashboard without DB migrations.
    A promotion is *live* when ``active`` is true AND the current time falls
    inside its start/end window (an empty/absent ``end`` means it runs forever).
    """

    def __init__(self, db_manager=None, path: Optional[str] = None):
        self.db = db_manager
        self.path = path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "promotions.json",
        )
        self.promotions: List[Dict] = []
        self._last_mtime: Optional[float] = None
        self.load()

    # ── Persistence ─────────────────────────────────────────────
    def load(self) -> List[Dict]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.promotions = data if isinstance(data, list) else []
            self._last_mtime = os.path.getmtime(self.path)
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            print(f"PromotionService: could not load {self.path}: {e}")
            self.promotions = []
        return self.promotions

    def _reload_if_changed(self) -> None:
        """Reload the JSON file if it changed on disk (another worker/process
        may have written it). Keeps delete/update consistent across processes."""
        try:
            mtime = os.path.getmtime(self.path)
        except OSError:
            return
        if mtime != self._last_mtime:
            self.load()

    def save(self) -> bool:
        """Atomically persist promotions so a crash or concurrent reader never
        sees a half-written file."""
        try:
            tmp_path = self.path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.promotions, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)
            self._last_mtime = os.path.getmtime(self.path)
            return True
        except Exception as e:
            print(f"PromotionService: could not save {self.path}: {e}")
            return False

    # ── Query helpers ────────────────────────────────────────────
    def _now(self) -> datetime:
        return datetime.now()

    def _window_open(self, promo: Dict, now: Optional[datetime] = None) -> bool:
        now = now or self._now()
        start = self._parse_dt(promo.get("start"))
        end = self._parse_dt(promo.get("end"))
        if start and now < start:
            return False
        if end and now > end:
            return False
        return True

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

    def list_all(self) -> List[Dict]:
        """Return every promotion with a computed status label."""
        self._reload_if_changed()
        now = self._now()
        out = []
        for promo in self.promotions:
            row = dict(promo)
            row["status"] = self.get_status(promo, now)
            row["product"] = self.get_product(promo.get("product_id"))
            out.append(row)
        return out

    def get_status(self, promo: Dict, now: Optional[datetime] = None) -> str:
        now = now or self._now()
        if not promo.get("active"):
            return "paused"
        start = self._parse_dt(promo.get("start"))
        end = self._parse_dt(promo.get("end"))
        if start and now < start:
            return "scheduled"
        if end and now > end:
            return "expired"
        return "active"

    def get(self, promo_id: str) -> Optional[Dict]:
        self._reload_if_changed()
        for promo in self.promotions:
            if promo.get("id") == promo_id:
                return promo
        return None

    def get_active(self, now: Optional[datetime] = None) -> List[Dict]:
        self._reload_if_changed()
        return [p for p in self.promotions
                if p.get("active") and self._window_open(p, now)]

    def get_featured(self, now: Optional[datetime] = None) -> Optional[Dict]:
        """Return the first live promotion with its resolved product row."""
        for promo in self.get_active(now):
            product = self.get_product(promo.get("product_id"))
            if product:
                return {"promo": promo, "product": product}
        return None

    def get_product(self, product_id: Any) -> Optional[Dict]:
        if self.db is None or product_id in (None, ""):
            return None
        try:
            return self.db.get_product_by_id(int(product_id))
        except Exception as e:
            print(f"PromotionService: get_product error: {e}")
            return None

    # ── CRUD ─────────────────────────────────────────────────────
    def create(self, data: Dict) -> Optional[Dict]:
        self._reload_if_changed()
        product_id = data.get("product_id")
        if product_id in (None, ""):
            return None
        promo = {
            "id": "promo-" + uuid.uuid4().hex[:8],
            "product_id": int(product_id),
            "title": (data.get("title") or "").strip(),
            "message": (data.get("message") or "").strip(),
            "discount": self._coerce_number(data.get("discount"), 0),
            "start": (data.get("start") or "").strip() or None,
            "end": (data.get("end") or "").strip() or None,
            "active": bool(data.get("active", True)),
            "created_at": self._now().isoformat(timespec="seconds"),
        }
        self.promotions.append(promo)
        if not self.save():
            self.load()
            return None
        return dict(promo)

    def update(self, promo_id: str, data: Dict) -> Optional[Dict]:
        self._reload_if_changed()
        promo = self.get(promo_id)
        if not promo:
            return None
        if "product_id" in data and data["product_id"] not in (None, ""):
            promo["product_id"] = int(data["product_id"])
        for field in ("title", "message", "start", "end"):
            if field in data:
                promo[field] = (data[field] or "").strip() or None
        if "discount" in data:
            promo["discount"] = self._coerce_number(data["discount"], promo.get("discount", 0))
        if "active" in data:
            promo["active"] = bool(data["active"])
        if not self.save():
            self.load()
            return None
        return dict(promo)

    def delete(self, promo_id: str) -> bool:
        self._reload_if_changed()
        before = len(self.promotions)
        self.promotions = [p for p in self.promotions if p.get("id") != promo_id]
        if len(self.promotions) == before:
            return False
        if not self.save():
            self.load()
            return False
        return True

    @staticmethod
    def _coerce_number(value: Any, default: float = 0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    # ── Card formatting ──────────────────────────────────────────
    def format_promo_card(self, promo: Dict, product: Dict,
                          intro: Optional[str] = None) -> str:
        """Build a structured PROMO card the frontend renders as a styled card."""
        name = product.get("name", "")
        price = product.get("unit_price", product.get("price", 0))
        try:
            price_fmt = f"{float(price):,.2f} ETB"
        except (TypeError, ValueError):
            price_fmt = str(price)
        image = product.get("thumbnail", product.get("image", "def.png"))
        details = product.get("details", product.get("description", ""))
        details = re.sub(r"<[^>]*>", "", str(details)).strip()[:200]
        title = (promo.get("title") or "").strip()
        message = (promo.get("message") or "").strip()
        discount = promo.get("discount", 0) or 0

        lines = ["PROMO"]
        if intro:
            lines.append(f"Intro: {intro}")
        if title:
            lines.append(f"Title: {title}")
        lines.append(f"Name: {name}")
        lines.append(f"Price: {price_fmt}")
        if discount:
            lines.append(f"Discount: {discount:g}% off")
        if message:
            lines.append(f"Details: {message}")
        elif details:
            lines.append(f"Details: {details}")
        lines.append(f"Image: {image}")
        lines.append(f"Id: {product.get('id', '')}")
        return "\n".join(lines)
