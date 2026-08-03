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
from queue import Queue, Empty
import threading

load_dotenv()

logger = logging.getLogger(__name__)


class PyMySQLConnectionPool:
    def __init__(self, pool_size=10, **config):
        self.config = config
        self.pool_size = pool_size
        self.pool = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self._created_connections = 0

    def _create_connection(self):
        return pymysql.connect(**self.config)

    def get_connection(self):
        try:
            return self.pool.get_nowait()
        except Empty:
            with self.lock:
                if self._created_connections < self.pool_size:
                    self._created_connections += 1
                    return self._create_connection()
            return self.pool.get(block=True, timeout=5)

    def release_connection(self, conn):
        try:
            conn.ping(reconnect=True)
            self.pool.put_nowait(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            with self.lock:
                self._created_connections -= 1


class DatabaseManager:
    def __init__(self):
        self.config = {
            "host":     os.getenv("DB_HOST", "localhost"),
            "port":     int(os.getenv("DB_PORT")) if os.getenv("DB_PORT", "").strip().isdigit() else 3306,
            "user":     os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "db":       os.getenv("DB_NAME", "gojoshopchat"),
            "charset":  "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
            "connect_timeout": 5,
        }
        self._pool = PyMySQLConnectionPool(pool_size=15, **self.config)

    def _get_connection(self):
        """Lease a connection from the connection pool (thread-safe)."""
        conn = self._pool.get_connection()
        original_close = conn.close
        
        def release_to_pool():
            # Restore the original close method and release back to pool
            conn.close = original_close
            self._pool.release_connection(conn)
            
        conn.close = release_to_pool
        return conn


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
        Fetch a single order by order_id, JOINed with the users table so
        customer name / email / phone are always populated from the real DB.
        Returns a dict with order + customer fields, or None if not found.
        """
        order_id = self._normalise_order_id(order_id)
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        o.id,
                        o.customer_id,
                        o.order_status,
                        o.order_amount,
                        o.payment_method,
                        o.payment_status,
                        o.transaction_ref,
                        o.shipping_address,
                        o.shipping_address_data,
                        o.shipping_cost,
                        o.is_shipping_free,
                        o.shipping_type,
                        o.delivery_type,
                        o.delivery_service_name,
                        o.third_party_delivery_tracking_id AS tracking_number,
                        o.expected_delivery_date,
                        o.order_note,
                        o.seller_is,
                        o.cancel_reason,
                        o.cancel_cause,
                        o.canceled_by_type,
                        o.customer_phone        AS order_phone,
                        o.coupon_code,
                        o.discount_amount,
                        o.extra_discount,
                        o.shipping_cost,
                        o.deliveryman_charge,
                        o.order_group_id,
                        o.created_at,
                        o.updated_at,
                        -- Customer fields from users table
                        COALESCE(u.name,
                                 CONCAT_WS(' ', NULLIF(u.f_name,''), NULLIF(u.l_name,'')),
                                 'N/A')              AS customer_name,
                        COALESCE(u.phone, o.customer_phone, 'N/A') AS customer_phone,
                        COALESCE(u.email, 'N/A')    AS customer_email
                    FROM orders o
                    LEFT JOIN users u
                        ON CONVERT(CAST(u.id AS CHAR) USING utf8mb4) COLLATE utf8mb4_general_ci
                         = CONVERT(o.customer_id USING utf8mb4) COLLATE utf8mb4_general_ci
                    WHERE o.id = %s
                    LIMIT 1
                    """,
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
        Fetch all items belonging to an order from order_details.
        Extracts product name from the product_details JSON blob.
        Returns a list of dicts with all useful fields, or [] on failure.
        """
        order_id = self._normalise_order_id(order_id)
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        od.id,
                        od.product_id,
                        COALESCE(
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(od.product_details, '$.name')), 'null'),
                            'Unknown Product'
                        )                           AS product_name,
                        JSON_UNQUOTE(JSON_EXTRACT(od.product_details, '$.thumbnail')) AS thumbnail,
                        od.qty                      AS quantity,
                        od.price                    AS unit_price,
                        od.discount,
                        od.tax,
                        od.tax_model,
                        od.variant,
                        od.variation,
                        od.discount_type,
                        od.delivery_status,
                        od.payment_status,
                        od.refund_request
                    FROM order_details od
                    WHERE od.order_id = %s
                    """,
                    (order_id,)
                )
                rows = cur.fetchall()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"get_order_items error: {e}")
            return []

    def search_products(self, query: str, limit: int = 5, filters: dict | None = None,
                        offset: int = 0) -> list[dict]:
        """
        Search active products by matching each word against name, details, or meta_description.
        Every word must appear in at least one of those fields.
        Returns a list of dicts with product details, or [] on failure.

        ``offset`` supports pagination for "show more" style follow-up requests.
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
                    "LIMIT %s OFFSET %s"
                )
                broad_term = f"%{query}%"
                if filters.get("sort") not in {"price_asc", "price_desc", "newest"}:
                    params.extend([broad_term, broad_term])
                params.extend([limit, offset])
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

    def get_or_create_user(self, user_id: str) -> dict | None:
        """
        Look up user by ID (for numeric ID), telegram_id (for Telegram bot user_id),
        or email (for web guest users). Create if it doesn't exist.
        """
        import random
        import string
        
        if not user_id:
            return None
            
        try:
            conn = self._get_connection()
            user = None
            with conn.cursor() as cur:
                # 1. Try numeric user_id as either PK or telegram_id
                try:
                    num_id = int(user_id)
                    cur.execute("SELECT * FROM users WHERE telegram_id = %s LIMIT 1", (num_id,))
                    user = cur.fetchone()
                    if not user:
                        cur.execute("SELECT * FROM users WHERE id = %s LIMIT 1", (num_id,))
                        user = cur.fetchone()
                except ValueError:
                    # 2. String user_id - check by guest email format
                    guest_email = f"{user_id}@guest.gojo.et"
                    cur.execute("SELECT * FROM users WHERE email = %s LIMIT 1", (guest_email,))
                    user = cur.fetchone()
                
                # 3. If user doesn't exist, create one
                if not user:
                    if user_id.isdigit():
                        num_id = int(user_id)
                        email = f"tg_{user_id}@gojo.org.et"
                        phone = f"TG-{user_id}"
                        name = f"Telegram User {user_id}"
                        cur.execute(
                            "INSERT INTO users (telegram_id, name, f_name, l_name, phone, email, password, is_active) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, 1)",
                            (num_id, name, "Telegram", "User", phone, email, "tg_pass")
                        )
                        conn.commit()
                        cur.execute("SELECT * FROM users WHERE telegram_id = %s LIMIT 1", (num_id,))
                        user = cur.fetchone()
                    else:
                        guest_email = f"{user_id}@guest.gojo.et"
                        phone = "0000000000"
                        cur.execute(
                            "INSERT INTO users (name, f_name, l_name, phone, email, password, is_active) "
                            "VALUES (%s, 'Guest', 'User', %s, %s, 'guest_pass', 1)",
                            (user_id, phone, guest_email)
                        )
                        conn.commit()
                        cur.execute("SELECT * FROM users WHERE email = %s LIMIT 1", (guest_email,))
                        user = cur.fetchone()
            conn.close()
            return user
        except Exception as e:
            logger.error(f"get_or_create_user error: {e}")
            return None

    def add_item_to_cart(self, user_id: str, product_name: str, quantity: int = 1) -> bool:
        """
        Resolve the user, resolve the product, get/generate cart_group_id,
        and insert/update cart item in DB.
        """
        import time
        import random
        import string

        user = self.get_or_create_user(user_id)
        if not user:
            return False

        customer_id = user["id"]
        is_guest = 1 if not str(user_id).isdigit() else 0

        try:
            conn = self._get_connection()
            product = None
            with conn.cursor() as cur:
                # 1. Resolve product details
                cur.execute(
                    "SELECT id, name, unit_price, slug, thumbnail, user_id "
                    "FROM products WHERE name = %s AND status = 1 LIMIT 1",
                    (product_name,)
                )
                product = cur.fetchone()

                if not product:
                    # Try fuzzy search
                    cur.execute(
                        "SELECT id, name, unit_price, slug, thumbnail, user_id "
                        "FROM products WHERE name LIKE %s AND status = 1 LIMIT 1",
                        (f"%{product_name}%",)
                    )
                    product = cur.fetchone()

                if not product:
                    conn.close()
                    logger.warning(f"Product '{product_name}' not found in database.")
                    return False

                # 2. Get existing cart_group_id or generate a new one
                cur.execute(
                    "SELECT cart_group_id FROM carts WHERE customer_id = %s LIMIT 1",
                    (customer_id,)
                )
                row = cur.fetchone()
                if row and row["cart_group_id"]:
                    cart_group_id = row["cart_group_id"]
                else:
                    rand_suffix = "".join(random.choices(string.ascii_letters, k=5))
                    timestamp = int(time.time())
                    prefix = "guest" if is_guest else str(customer_id)
                    cart_group_id = f"{prefix}-{rand_suffix}-{timestamp}"

                # 3. Check if product already in cart
                cur.execute(
                    "SELECT id, quantity FROM carts WHERE customer_id = %s AND product_id = %s LIMIT 1",
                    (customer_id, product["id"])
                )
                existing = cur.fetchone()

                if existing:
                    new_qty = existing["quantity"] + quantity
                    cur.execute(
                        "UPDATE carts SET quantity = %s, price = %s, updated_at = NOW() WHERE id = %s",
                        (new_qty, product["unit_price"], existing["id"])
                    )
                else:
                    cur.execute(
                        "INSERT INTO carts (customer_id, cart_group_id, product_id, quantity, price, "
                        "tax, discount, slug, name, thumbnail, seller_id, is_guest, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s, 0, 0, %s, %s, %s, %s, %s, NOW(), NOW())",
                        (
                            customer_id,
                            cart_group_id,
                            product["id"],
                            quantity,
                            product["unit_price"],
                            product["slug"],
                            product["name"],
                            product["thumbnail"] or "def.png",
                            product["user_id"],
                            is_guest
                        )
                    )
                conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"add_item_to_cart error: {e}")
            return False

    def get_cart_items_by_user(self, user_id: str) -> list[str]:
        """Fetch list of product names in the user's cart."""
        user = self.get_or_create_user(user_id)
        if not user:
            return []

        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM carts WHERE customer_id = %s", (user["id"],))
                rows = cur.fetchall()
            conn.close()
            return [row["name"] for row in rows]
        except Exception as e:
            logger.error(f"get_cart_items_by_user error: {e}")
            return []

    def get_cart_details(self, user_id: str) -> dict:
        """Fetch cart items with pricing, and the total amount."""
        user = self.get_or_create_user(user_id)
        if not user:
            return {"items": [], "total_price": 0.0}

        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, quantity, price, slug, thumbnail "
                    "FROM carts WHERE customer_id = %s",
                    (user["id"],)
                )
                rows = cur.fetchall()
            conn.close()

            items = []
            total_price = 0.0
            for row in rows:
                subtotal = float(row["price"]) * int(row["quantity"])
                items.append({
                    "id": row["id"],
                    "name": row["name"],
                    "quantity": row["quantity"],
                    "price": float(row["price"]),
                    "subtotal": subtotal,
                    "slug": row["slug"],
                    "thumbnail": row["thumbnail"]
                })
                total_price += subtotal

            return {"items": items, "total_price": total_price}
        except Exception as e:
            logger.error(f"get_cart_details error: {e}")
            return {"items": [], "total_price": 0.0}

    def clear_cart(self, user_id: str) -> bool:
        """Delete all items in user's cart."""
        user = self.get_or_create_user(user_id)
        if not user:
            return False

        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM carts WHERE customer_id = %s", (user["id"],))
                conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"clear_cart error: {e}")
            return False

    def get_user_session(self, user_id: str) -> dict | None:
        """Fetch session data from database."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT session_data FROM user_sessions WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
            conn.close()
            if row and row["session_data"]:
                if isinstance(row["session_data"], str):
                    import json
                    return json.loads(row["session_data"])
                return row["session_data"]
            return None
        except Exception as e:
            logger.error(f"get_user_session error: {e}")
            return None

    def save_user_session(self, user_id: str, session_data: dict) -> bool:
        """Save session data to database."""
        try:
            import json
            serialized = json.dumps(session_data)
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO user_sessions (user_id, session_data) "
                    "VALUES (%s, %s) ON DUPLICATE KEY UPDATE session_data = %s",
                    (user_id, serialized, serialized)
                )
                conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"save_user_session error: {e}")
            return False

    def delete_user_session(self, user_id: str) -> bool:
        """Delete session data from database."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM user_sessions WHERE user_id = %s", (user_id,))
                conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"delete_user_session error: {e}")
            return False

    def get_active_support_request(self, user_id: str) -> dict | None:
        """Fetch current active support request for user."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM support_requests WHERE user_id = %s AND status IN ('open', 'in_progress') "
                    "ORDER BY created_at DESC LIMIT 1",
                    (user_id,)
                )
                row = cur.fetchone()
            conn.close()
            if row:
                import json
                if row.get("messages") and isinstance(row["messages"], str):
                    row["messages"] = json.loads(row["messages"])
                if row.get("metadata") and isinstance(row["metadata"], str):
                    row["metadata"] = json.loads(row["metadata"])
                return row
            return None
        except Exception as e:
            logger.error(f"get_active_support_request error: {e}")
            return None

    def create_support_request(self, request_id: str, user_id: str, message: str, metadata: dict) -> dict | None:
        """Create a new support request in database."""
        try:
            import json
            from datetime import datetime
            
            initial_msg = {
                "sender": "user",
                "text": message,
                "timestamp": datetime.now().isoformat()
            }
            messages_json = json.dumps([initial_msg])
            metadata_json = json.dumps(metadata)
            
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO support_requests (id, status, user_id, message, metadata, messages) "
                    "VALUES (%s, 'open', %s, %s, %s, %s)",
                    (request_id, user_id, message, metadata_json, messages_json)
                )
                conn.commit()
            conn.close()
            
            return {
                "id": request_id,
                "status": "open",
                "user_id": user_id,
                "message": message,
                "metadata": metadata,
                "messages": [initial_msg],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"create_support_request error: {e}")
            return None

    def add_support_message(self, request_id: str, sender: str, text: str) -> dict | None:
        """Add a message to a support request's chat history."""
        try:
            import json
            from datetime import datetime
            
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT messages FROM support_requests WHERE id = %s", (request_id,))
                row = cur.fetchone()
                if not row:
                    conn.close()
                    return None
                
                messages = []
                if row["messages"]:
                    if isinstance(row["messages"], str):
                        messages = json.loads(row["messages"])
                    elif isinstance(row["messages"], list):
                        messages = row["messages"]
                
                new_msg = {
                    "sender": sender,
                    "text": text,
                    "timestamp": datetime.now().isoformat()
                }
                messages.append(new_msg)
                
                cur.execute(
                    "UPDATE support_requests SET messages = %s WHERE id = %s",
                    (json.dumps(messages), request_id)
                )
                conn.commit()
            conn.close()
            return new_msg
        except Exception as e:
            logger.error(f"add_support_message error: {e}")
            return None

    def list_support_requests(self, limit: int = 50) -> list[dict]:
        """List the last N support requests."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM support_requests ORDER BY created_at DESC LIMIT %s",
                    (limit,)
                )
                rows = cur.fetchall()
            conn.close()
            
            import json
            for row in rows:
                if row.get("messages") and isinstance(row["messages"], str):
                    row["messages"] = json.loads(row["messages"])
                if row.get("metadata") and isinstance(row["metadata"], str):
                    row["metadata"] = json.loads(row["metadata"])
                if row.get("created_at"):
                    # Format datetime objects as strings for JSON API
                    row["timestamp"] = row["created_at"].isoformat()
            return rows
        except Exception as e:
            logger.error(f"list_support_requests error: {e}")
            return []

    def update_support_request_status(self, request_id: str, status: str) -> dict | None:
        """Update status of a support request."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE support_requests SET status = %s WHERE id = %s",
                    (status, request_id)
                )
                conn.commit()
                
                cur.execute("SELECT * FROM support_requests WHERE id = %s LIMIT 1", (request_id,))
                row = cur.fetchone()
            conn.close()
            
            if row:
                import json
                if row.get("messages") and isinstance(row["messages"], str):
                    row["messages"] = json.loads(row["messages"])
                if row.get("metadata") and isinstance(row["metadata"], str):
                    row["metadata"] = json.loads(row["metadata"])
                if row.get("created_at"):
                    row["timestamp"] = row["created_at"].isoformat()
                return row
            return None
        except Exception as e:
            logger.error(f"update_support_request_status error: {e}")
            return None

    @staticmethod
    def _normalise_order_id(raw) -> str:
        """
        Convert user input to canonical order ID format.
        For numeric IDs (current schema): '100001' → '100001'
        For string IDs (legacy): 'ORD-1001' → 'ORD-1001'
        Handles both string and integer inputs.
        """
        # Convert to string if it's not already
        if not isinstance(raw, str):
            raw = str(raw)
        raw = raw.strip().upper().lstrip("#")
        # Try to convert to integer - if successful, return as string
        try:
            int(raw)
            return raw
        except ValueError:
            # If it's not numeric, keep the original logic for string-based IDs
            if not raw.startswith("ORD-"):
                raw = f"ORD-{raw}"
            return raw


# Singleton used across the app
db = DatabaseManager()

