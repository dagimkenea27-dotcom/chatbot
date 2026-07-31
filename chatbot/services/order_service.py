# chatbot/services/order_service.py
import json
from typing import Dict, List, Optional, Any


class OrderService:
    """Manages order lookup and formatting."""
    
    def __init__(self, db_manager=None):
        self.db = db_manager
    
    def get_order(self, order_id: str) -> Optional[Dict]:
        """Get order by ID."""
        if self.db is None:
            return None
        try:
            return self.db.get_order(order_id)
        except Exception as e:
            print(f"Error getting order: {e}")
            return None
    
    def get_order_items(self, order_id: str) -> List[Dict]:
        """Get order items."""
        if self.db is None:
            return []
        try:
            return self.db.get_order_items(order_id)
        except Exception as e:
            print(f"Error getting order items: {e}")
            return []
    
    @staticmethod
    def _status_emoji(status: str) -> str:
        return {
            "pending": "🕐",
            "processing": "⚙️",
            "shipped": "🚚",
            "delivered": "✅",
            "cancelled": "❌",
            "canceled": "❌",
        }.get(status, "📦")
    
    def format_order_card(self, order: dict, items: list, session) -> str:
        """Format order as a rich text card."""
        import json as _json
        
        status = order.get("order_status", "unknown")
        emoji = self._status_emoji(status)
        order_id = order.get("id", "N/A")
        
        # Customer info
        customer = order.get("customer_name") or "N/A"
        phone = order.get("customer_phone") or order.get("order_phone") or "N/A"
        email = order.get("customer_email") or "N/A"
        
        # Timestamps
        created = order.get("created_at")
        updated = order.get("updated_at")
        created_str = created.strftime("%b %d, %Y %I:%M %p") if hasattr(created, "strftime") else str(created or "N/A")
        updated_str = updated.strftime("%b %d, %Y %I:%M %p") if hasattr(updated, "strftime") else str(updated or "N/A")
        
        # Delivery info
        tracking = order.get("tracking_number") or order.get("third_party_delivery_tracking_id") or "Not yet assigned"
        expected = order.get("expected_delivery_date")
        expected_str = expected.strftime("%b %d, %Y") if hasattr(expected, "strftime") else str(expected or "N/A")
        
        addr = "N/A"
        raw_addr_data = order.get("shipping_address_data")
        if raw_addr_data:
            try:
                addr_data = _json.loads(raw_addr_data) if isinstance(raw_addr_data, str) else raw_addr_data
                parts = [addr_data.get("name") or "", addr_data.get("address") or addr_data.get("street_address") or "",
                        addr_data.get("city") or "", addr_data.get("zip") or "", addr_data.get("country") or "",
                        addr_data.get("phone") or ""]
                addr = ", ".join(p for p in parts if p) or "N/A"
            except Exception:
                addr = str(raw_addr_data)
        elif order.get("shipping_address"):
            addr = str(order["shipping_address"])
        
        delivery_type = order.get("delivery_type") or order.get("shipping_type") or "N/A"
        delivery_service = order.get("delivery_service_name") or "N/A"
        order_note = order.get("order_note") or "—"
        
        # Payment
        payment = (order.get("payment_method") or "N/A").replace("_", " ").title()
        pay_status = order.get("payment_status") or "N/A"
        transaction = order.get("transaction_ref") or "N/A"
        total = float(order.get("order_amount") or 0)
        shipping_cost = float(order.get("shipping_cost") or 0)
        discount = float(order.get("discount_amount") or 0)
        extra_disc = float(order.get("extra_discount") or 0)
        coupon = order.get("coupon_code") or "—"
        is_free_ship = bool(order.get("is_shipping_free"))
        seller = order.get("seller_is") or "N/A"
        order_group = order.get("order_group_id") or "N/A"
        
        # Cancellation
        cancel_reason = order.get("cancel_reason") or "N/A"
        cancel_cause = order.get("cancel_cause")
        canceled_by = order.get("canceled_by_type") or "N/A"
        
        # Items
        item_lines = ""
        for it in items:
            qty = int(it.get("quantity") or it.get("qty") or 1)
            price = float(it.get("unit_price") or it.get("price") or 0)
            subtotal = price * qty
            d_status = it.get("delivery_status", "pending")
            d_emoji = self._status_emoji(d_status)
            p_status = it.get("payment_status", "")
            variant = it.get("variant") or it.get("variation") or ""
            name = it.get("product_name") or "Unknown Product"
            
            item_lines += f"\n  • {name} × {qty}  —  {subtotal:,.2f} ETB  {d_emoji}"
            if variant:
                item_lines += f"  [{variant}]"
            if p_status:
                item_lines += f"  ({p_status})"
        
        if not item_lines:
            item_lines = "\n  No items found."
        
        # Build card
        coupon_line = ""
        if coupon and coupon not in ("—", "0", "0.00"):
            coupon_line = f"🏷️  Coupon   : {coupon}\n"
        
        card = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦  Order #{order_id}\n"
            f"🗂️  Group: {order_group}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤  Customer : {customer}\n"
            f"📱  Phone    : {phone}\n"
            f"📧  Email    : {email}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅  Placed   : {created_str}\n"
            f"🔄  Updated  : {updated_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji}  Status   : {status.upper()}\n"
            f"🚚  Tracking : {tracking}\n"
            f"📆  Expected : {expected_str}\n"
            f"📍  Delivery : {delivery_type}  ({delivery_service})\n"
            f"🏠  Address  : {addr}\n"
            f"📝  Note     : {order_note}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛍️  Items:{item_lines}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💳  Payment  : {payment}  [{pay_status}]\n"
            f"🔢  Tx Ref   : {transaction}\n"
            + coupon_line +
            f"💸  Discount : {discount:,.2f} ETB"
            + (f"  +extra {extra_disc:,.2f}" if extra_disc else "") + "\n"
            f"🚚  Shipping : {'FREE ✅' if is_free_ship else f'{shipping_cost:,.2f} ETB'}\n"
            f"💰  Total    : {total:,.2f} ETB\n"
            f"🏢  Seller   : {seller}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        
        if status in ("canceled", "cancelled"):
            card += f"❌  Reason   : {cancel_reason}\n"
            if cancel_cause:
                card += f"🔍  Cause ID : {cancel_cause}\n"
            if canceled_by != "N/A":
                card += f"👁️  Cancelled by: {canceled_by}\n"
        
        return card