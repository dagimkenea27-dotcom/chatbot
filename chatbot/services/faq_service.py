# chatbot/services/faq_service.py
from typing import Dict


class FAQService:
    """Manages FAQ data."""
    
    def load_faq(self) -> Dict:
        """Load FAQ data."""
        return {
            "shipping": {
                "question": "How long does shipping take?",
                "answer": "Standard delivery takes 2-5 business days. Express (1-2 days) costs 200 ETB. Same-day delivery in Addis Ababa (order before 12 PM) costs 500 ETB. Orders over 1,500 ETB ship FREE! We deliver nationwide across all Ethiopian regions."
            },
            "returns": {
                "question": "What is your return policy?",
                "answer": "We accept returns within 14 days of delivery. Items must be unused and in original packaging. Defective items get a FREE return + full refund. Wrong items sent get a FREE return + free replacement. Custom/personalized items are non-returnable."
            },
            "payment": {
                "question": "What payment methods do you accept?",
                "answer": "We accept Telebirr, CBE Birr, Amole, M-Pesa (mobile), plus CBE, Awash, Abyssinia, Dashen bank transfers, and Cash on Delivery. All payments are SSL-encrypted and secure."
            },
            "warranty": {
                "question": "Do you offer warranty?",
                "answer": "Yes! Electronics get 1-year manufacturer warranty. Home appliances get 6 months. Clothing & accessories get a 30-day defect warranty. Handmade products have a 14-day quality guarantee. Covers manufacturing defects, not accidental damage."
            },
            "contact": {
                "question": "How do I contact GojoShop?",
                "answer": "Email: support@gojoshop.et (24hr response). Phone/WhatsApp: +251911234567 (Mon-Sat 8AM-8PM). Store: Bole Road, Addis Ababa (near Edna Mall). Social: @GojoShopET on Telegram, Facebook, Instagram."
            },
            "hours": {
                "question": "What are your business hours?",
                "answer": "Store: Mon-Fri 8AM-9PM, Sat 9AM-8PM, Sun 10AM-6PM. Online chat: Mon-Sat 8AM-10PM, Sun 9AM-7PM. Orders placed before 2PM are processed same day."
            },
            "promotions": {
                "question": "Do you have any promotions or discounts?",
                "answer": "Yes! Free shipping on orders over 1,500 ETB. 10% off your first order (code: GOJO10). Buy 2 Get 1 Free on selected accessories. Flash sales every Friday! Seasonal deals for Ethiopian New Year, Christmas, and Timkat."
            },
            "loyalty": {
                "question": "Do you have a loyalty program?",
                "answer": "Yes! Earn 1 point per 10 ETB spent. 100 points = 50 ETB discount. Tiers: Bronze (0-499pts, 5% bonus), Silver (500-1999pts, 10% bonus + free express), Gold (2000+pts, 15% bonus + priority support). Welcome bonus: 50 points on first purchase!"
            },
            "tracking": {
                "question": "How do I track my order?",
                "answer": "Share your Order ID (e.g., #100001) here and I'll look it up instantly! You also receive a tracking number by SMS and email once your order ships."
            },
            "cancellation": {
                "question": "Can I cancel my order?",
                "answer": "You can cancel within 1 hour of placing the order, or before it ships. Contact us immediately at +251911234567 or support@gojoshop.et. Once shipped, you'll need to use our return process instead."
            },
            "stock": {
                "question": "Is a product in stock?",
                "answer": "Live stock levels are shown on each product card. In stock items ship within 1-2 business days. Out of stock items are usually restocked within 1-2 weeks."
            },
            "authenticity": {
                "question": "Are your products genuine?",
                "answer": "Yes! All products are 100% authentic, sourced directly from trusted manufacturers and authorized distributors. Every item includes original packaging and a genuine warranty."
            },
            "wholesale": {
                "question": "Do you offer wholesale or bulk pricing?",
                "answer": "Yes! We welcome bulk orders from shops, distributors and resellers. Bulk pricing starts at 10+ units. Email wholesale@gojoshop.et or call +251911234567 for a custom quote."
            },
            "gift": {
                "question": "Do you offer gift wrapping?",
                "answer": "Yes! Gift wrapping is available at checkout for 100 ETB, and gift cards start from 500 ETB. We can also deliver directly to the recipient with a personal message."
            },
            "invoice": {
                "question": "Can I get an invoice or receipt?",
                "answer": "A receipt is emailed after every order. Tax invoices are available on request with your TIN. For businesses we provide VAT invoices and delivery notes. Email support@gojoshop.et with your Order ID."
            },
            "order_change": {
                "question": "Can I change my order after placing it?",
                "answer": "You can change your delivery address within 2 hours of ordering, and adjust quantities or add items before the order is processed. Once processed or shipped, changes are not possible."
            },
            "international": {
                "question": "Do you ship internationally?",
                "answer": "Currently we ship within Ethiopia only. For international requests, contact international@gojoshop.et and we'll see what we can arrange."
            },
            "installment": {
                "question": "Do you offer installment payments?",
                "answer": "Yes, on select electronics and home appliances. Plans of 3, 6 or 12 months are available with a valid ID and a down payment starting at 20%."
            }
        }