# chatbot/services/product_service.py
import re
from typing import Dict, List, Optional, Any


class ProductService:
    """Manages product catalog and search."""
    
    def __init__(self, db_manager=None):
        self.db = db_manager
    
    def load_catalog(self) -> Dict:
        """Load product catalog."""
        return {
            "electronics": {
                "phones": ["iPhone 15", "Samsung Galaxy S24", "Google Pixel 8"],
                "laptops": ["MacBook Pro", "Dell XPS 13", "HP Spectre"],
                "accessories": ["AirPods", "Chargers", "Phone Cases"]
            },
            "clothing": {
                "men": ["T-shirts", "Jeans", "Jackets", "Suits"],
                "women": ["Dresses", "Tops", "Skirts", "Handbags"],
                "kids": ["T-shirts", "Shorts", "Shoes"]
            },
            "home": {
                "furniture": ["Sofas", "Tables", "Chairs", "Beds"],
                "kitchen": ["Cookware", "Utensils", "Appliances"],
                "decor": ["Wall Art", "Vases", "Rugs", "Lamps"]
            }
        }
    
    def search_products(self, keyword: str, limit: int = 10, filters: dict = None,
                        offset: int = 0) -> List[Dict]:
        """Search products by keyword with filters."""
        if self.db is None:
            return []
        try:
            return self.db.search_products(
                keyword, limit=limit, filters=filters or {}, offset=offset)
        except Exception as e:
            print(f"Error searching products: {e}")
            return []
    
    def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        """Get product by ID."""
        if self.db is None:
            return None
        try:
            return self.db.get_product_by_id(product_id)
        except Exception as e:
            print(f"Error getting product: {e}")
            return None
    
    def get_related_products(self, keyword: str, exclude_ids: List[int], limit: int = 4) -> List[Dict]:
        """Get related products."""
        if self.db is None or not hasattr(self.db, "get_related_products"):
            return []
        try:
            return self.db.get_related_products(keyword, exclude_ids=exclude_ids, limit=limit)
        except Exception as e:
            print(f"Error getting related products: {e}")
            return []
    
    def format_search_card(self, products: list, filters: dict = None,
                           recommendations: list = None,
                           has_more: bool = False) -> str:
        """Format product search results as a structured card.

        ``has_more`` tells the frontend whether a "Show more" button should be
        shown (i.e. whether another page of results may exist).
        """
        filters = filters or {}
        recommendations = recommendations or []

        filter_parts = []
        if "min_price" in filters:
            filter_parts.append(f"min_price={filters['min_price']:.0f}")
        if "max_price" in filters:
            filter_parts.append(f"max_price={filters['max_price']:.0f}")
        if filters.get("in_stock"):
            filter_parts.append("in_stock=true")
        if "sort" in filters:
            filter_parts.append(f"sort={filters['sort']}")
        filters_str = ";".join(filter_parts) if filter_parts else "none"
        has_more_str = "true" if has_more else "false"
        
        def product_block(p):
            price = p.get("unit_price", p.get("price", 0))
            try:
                price_fmt = f"{float(price):,.2f} ETB"
            except (TypeError, ValueError):
                price_fmt = str(price)
            stock = p.get("current_stock", p.get("stock", 0))
            image = p.get("thumbnail", p.get("image", "def.png"))
            details = re.sub(r"<[^>]*>", "", str(p.get("description", p.get("details", "")))).strip()
            return (
                f"Product ID: {p.get('id', '')}\n"
                f"Name: {p.get('name', '')}\n"
                f"Price: {price_fmt}\n"
                f"Stock: {stock}\n"
                f"Image: {image}\n"
                f"Details: {details[:200]}"
            )
        
        blocks = "\n---\n".join(product_block(p) for p in products)
        card = f"PRODUCT SEARCH\nFilters: {filters_str}\nHasMore: {has_more_str}\n{blocks}"
        
        if recommendations:
            rec_blocks = "\n---\n".join(product_block(p) for p in recommendations)
            card += f"\nRECOMMENDATIONS\n{rec_blocks}"
        
        return card