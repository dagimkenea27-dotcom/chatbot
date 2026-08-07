# chatbot/services/cart_service.py
from typing import List


class CartService:
    """Manages shopping cart operations."""
    
    def __init__(self, db_manager=None):
        self.db = db_manager
    
    def get_cart(self, user_id: str) -> List[str]:
        """Get user's cart items."""
        if self.db and hasattr(self.db, "get_cart_items_by_user"):
            try:
                return self.db.get_cart_items_by_user(user_id)
            except Exception as e:
                print(f"Error getting cart: {e}")
        return []
    
    def add_item(self, user_id: str, product: str) -> bool:
        """Add item to cart."""
        if self.db and hasattr(self.db, "add_item_to_cart"):
            try:
                return self.db.add_item_to_cart(user_id, product)
            except Exception as e:
                print(f"Error adding to cart: {e}")
                return False
        return False

    def remove_item(self, user_id: str, product: str) -> bool:
        """Remove an item (whole line) from the user's cart."""
        if self.db and hasattr(self.db, "remove_item_from_cart"):
            try:
                return self.db.remove_item_from_cart(user_id, product)
            except Exception as e:
                print(f"Error removing from cart: {e}")
                return False
        return False
    
    def clear_cart(self, user_id: str) -> bool:
        """Clear user's cart."""
        if self.db and hasattr(self.db, "clear_cart"):
            try:
                self.db.clear_cart(user_id)
                return True
            except Exception as e:
                print(f"Error clearing cart: {e}")
                return False
        return False