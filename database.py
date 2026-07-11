# database.py
"""
GojoShop.et — Database Manager
Handles MySQL connections via PyMySQL.
Reads config from .env (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME).
Degrades gracefully if MySQL is unreachable.
"""

import pymysql
import pymysql.cursors
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.config = {
            "host":     os.getenv("DB_HOST", "localhost"),
            "port":     int(os.getenv("DB_PORT", 3306)),
            "user":     os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "db":       os.getenv("DB_NAME", "gojoshop"),
            "charset":  "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
            "connect_timeout": 5,
        }

    def _get_connection(self):
        """Open a fresh connection (short-lived, safe for Flask threading)."""
        return pymysql.connect(**self.config)

    def health_check(self) -> bool:
        """Returns True if DB is reachable."""
        try:
            conn = self._get_connection()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"DB health check failed: {e}")
            return False

    def get_order(self, order_id: str) -> dict | None:
        """
        Fetch a single order by order_id (e.g. 'ORD-1001').
        Returns a dict with order fields, or None if not found / DB down.
        """
        # Normalise: accept '1001', '#1001', 'ORD-1001' → 'ORD-1001'
        order_id = self._normalise_order_id(order_id)
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM orders WHERE order_id = %s LIMIT 1",
                    (order_id,)
                )
                row = cur.fetchone()
            conn.close()
            return row
        except Exception as e:
            logger.error(f"get_order error: {e}")
            return None

    def get_order_items(self, order_id: str) -> list[dict]:
        """
        Fetch all items belonging to an order.
        Returns a list of dicts, or [] on failure.
        """
        order_id = self._normalise_order_id(order_id)
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT product_name, quantity, unit_price "
                    "FROM order_items WHERE order_id = %s",
                    (order_id,)
                )
                rows = cur.fetchall()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"get_order_items error: {e}")
            return []

    def search_products(self, query: str, limit: int = 5, filters: dict | None = None) -> list[dict]:
        """
        Search active products by matching each word against name, details, or meta_description.
        Every word must appear in at least one of those fields.
        Returns a list of dicts with product details, or [] on failure.
        """
        filters = filters or {}
        words = [w.strip() for w in query.split() if w.strip()]
        if not words:
            return []

        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                word_conditions = []
                params = []
                for word in words:
                    term = f"%{word}%"
                    word_conditions.append(
                        "(name LIKE %s OR details LIKE %s OR meta_description LIKE %s)"
                    )
                    params.extend([term, term, term])

                filter_conditions = []
                min_price = filters.get("min_price")
                max_price = filters.get("max_price")
                if min_price is not None:
                    filter_conditions.append("unit_price >= %s")
                    params.append(min_price)
                if max_price is not None:
                    filter_conditions.append("unit_price <= %s")
                    params.append(max_price)
                if filters.get("in_stock"):
                    filter_conditions.append("current_stock > 0")

                where_parts = ["status = 1", *word_conditions, *filter_conditions]
                order_by = {
                    "price_asc": "unit_price ASC",
                    "price_desc": "unit_price DESC",
                    "newest": "id DESC",
                }.get(filters.get("sort"), "(name LIKE %s) DESC, (details LIKE %s) DESC")

                sql = (
                    "SELECT id, name, unit_price, current_stock, details, thumbnail, slug "
                    "FROM products "
                    f"WHERE {' AND '.join(where_parts)} "
                    f"ORDER BY {order_by} "
                    "LIMIT %s"
                )
                broad_term = f"%{query}%"
                if filters.get("sort") not in {"price_asc", "price_desc", "newest"}:
                    params.extend([broad_term, broad_term])
                params.append(limit)
                cur.execute(sql, params)
                rows = cur.fetchall()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"search_products error: {e}")
            return []

    def get_related_products(self, keyword: str, exclude_ids: list[int] | None = None, limit: int = 4) -> list[dict]:
        """
        Return lightweight recommendations near a keyword, excluding products already shown.
        """
        words = [w.strip() for w in keyword.split() if len(w.strip()) > 2]
        if not words:
            return []

        exclude_ids = exclude_ids or []
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                clauses = []
                params = []
                for word in words[:3]:
                    term = f"%{word}%"
                    clauses.append("(name LIKE %s OR details LIKE %s OR meta_description LIKE %s)")
                    params.extend([term, term, term])

                exclude_sql = ""
                if exclude_ids:
                    placeholders = ", ".join(["%s"] * len(exclude_ids))
                    exclude_sql = f" AND id NOT IN ({placeholders})"
                    params.extend(exclude_ids)

                sql = (
                    "SELECT id, name, unit_price, current_stock, details, thumbnail, slug "
                    "FROM products "
                    f"WHERE status = 1 AND ({' OR '.join(clauses)}){exclude_sql} "
                    "ORDER BY current_stock > 0 DESC, id DESC "
                    "LIMIT %s"
                )
                params.append(limit)
                cur.execute(sql, params)
                rows = cur.fetchall()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"get_related_products error: {e}")
            return []

    def get_product_by_id(self, product_id: int) -> dict | None:
        """Fetch a single active product by ID."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, unit_price, current_stock, details, thumbnail, slug "
                    "FROM products WHERE id = %s AND status = 1",
                    (product_id,)
                )
                row = cur.fetchone()
            conn.close()
            return row
        except Exception as e:
            logger.error(f"get_product_by_id error: {e}")
            return None

    @staticmethod
    def _normalise_order_id(raw: str) -> str:
        """
        Convert user input to canonical order ID format.
        '1001'     → 'ORD-1001'
        '#1001'    → 'ORD-1001'
        'ORD-1001' → 'ORD-1001'
        'ord-1001' → 'ORD-1001'
        """
        raw = raw.strip().upper().lstrip("#")
        if not raw.startswith("ORD-"):
            raw = f"ORD-{raw}"
        return raw


# Singleton used across the app
db = DatabaseManager()
