# app.py
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from chatbot.chatbot_core import GojoShopChatbot
from database import db
from dotenv import load_dotenv
import uuid
import os

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

# Configure CORS dynamically from .env
cors_origins = os.getenv('CORS_ORIGIN', '*')
if cors_origins == '*' or not cors_origins.strip():
    CORS(app)
else:
    origins_list = [o.strip() for o in cors_origins.split(',') if o.strip()]
    CORS(app, origins=origins_list)

# Initialize chatbot — inject DB manager
chatbot = GojoShopChatbot(db_manager=db)

# Log DB status on startup
if db.health_check():
    print("[GojoShop] MySQL connected — order lookup enabled")
else:
    print("[GojoShop] WARNING: MySQL unavailable — order lookup disabled")


@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception:
        return render_template('chatbot.html')


@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route('/admin/support')
def support_admin():
    """Human support request dashboard."""
    return render_template('support_admin.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint for API integration"""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    message = (data.get('message') or '').strip()
    lang = data.get('lang')

    if not user_id:
        user_id = str(uuid.uuid4())

    if not message:
        return jsonify({'error': 'Message is required'}), 400

    chatbot._ensure_session(user_id)
    if lang:
        chatbot.user_sessions[user_id]["language"] = lang

    response = chatbot.get_response(user_id, message)
    current_lang = chatbot.user_sessions[user_id].get('language', 'en')

    if response == "[SUPPORT_MODE]":
        return jsonify({
            'user_id': user_id,
            'response': "",
            'intent': 'human_support',
            'typing_delay_ms': 0,
            'needs_human': True,
            'in_support_mode': True,
            'lang': current_lang
        })

    delay = chatbot.calc_typing_delay(response)

    return jsonify({
        'user_id': user_id,
        'response': response,
        'intent': chatbot.user_sessions[user_id]['current_intent'],
        'typing_delay_ms': delay,
        'needs_human': chatbot.user_sessions[user_id].get('human_support_requested', False),
        'lang': current_lang
    })


@app.route('/api/translations/<lang>', methods=['GET'])
def get_translations(lang):
    """Retrieve UI translations for frontend consumption."""
    if lang not in chatbot.translations:
        return jsonify({'error': 'Language not supported'}), 404
    return jsonify(chatbot.translations.get(lang, {}).get("ui", {}))


@app.route('/api/support/requests', methods=['GET'])
def list_support_requests():
    """List pending human-support requests (for admin/staff use)."""
    return jsonify({'requests': chatbot.list_support_requests(50)})


@app.route('/api/support/request', methods=['POST'])
def request_support():
    """Explicitly request human assistance."""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    message = data.get('message', 'User requested human support from chat UI')

    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400

    chatbot._ensure_session(user_id)
    session = chatbot.user_sessions[user_id]
    response = chatbot.handle_human_support(message, session)

    return jsonify({
        'user_id': user_id,
        'request': chatbot.support_requests[-1] if chatbot.support_requests else None,
        'response': response,
        'needs_human': True,
    })


@app.route('/api/support/requests/<request_id>', methods=['PATCH'])
def update_support_request(request_id):
    """Update support request status."""
    data = request.get_json(silent=True) or {}
    updated = chatbot.update_support_request_status(request_id, data.get('status'))
    if not updated:
        return jsonify({'error': 'Request not found or invalid status'}), 404
    return jsonify({'request': updated})


@app.route('/api/support/requests/<request_id>/messages', methods=['GET'])
def get_support_messages(request_id):
    """Retrieve chat history for a support request."""
    for req in chatbot.support_requests:
        if req.get("id") == request_id:
            return jsonify({'messages': req.get("messages", [])})
    return jsonify({'error': 'Request not found'}), 404


@app.route('/api/support/requests/<request_id>/messages', methods=['POST'])
def send_support_message(request_id):
    """Send a message from the support agent/admin."""
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Message text is required'}), 400

    msg = chatbot.add_support_chat_message(request_id, "agent", text)
    if not msg:
        return jsonify({'error': 'Request not found'}), 404
    return jsonify({'message': msg})


@app.route('/api/support/requests/active/<user_id>', methods=['GET'])
def get_active_support_request(user_id):
    """Check if the user has an active support request and return messages."""
    req = chatbot.get_active_support_request(user_id)
    if req:
        return jsonify({
            'status': 'active',
            'request_id': req['id'],
            'status_label': req['status'],
            'messages': req.get('messages', [])
        })
    return jsonify({'status': 'inactive'})


@app.route('/api/session/reset', methods=['POST'])
def reset_session():
    """Reset conversation context for a user and resolve any active support ticket."""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400

    # Auto-resolve any open/in_progress support ticket so AI becomes active again
    active_req = chatbot.get_active_support_request(user_id)
    if active_req:
        chatbot.update_support_request_status(active_req['id'], 'resolved')

    chatbot.reset_session(user_id)
    return jsonify({'message': 'Session reset', 'user_id': user_id})


@app.route('/api/order/<order_id>', methods=['GET'])
def get_order(order_id):
    """Direct order status API endpoint"""
    order = db.get_order(order_id)
    if not order:
        return jsonify({'error': f'Order {order_id} not found'}), 404
    items = db.get_order_items(order_id)
    # Convert datetime objects to strings for JSON serialisation
    if order.get('created_at'):
        order['created_at'] = order['created_at'].isoformat()
    if order.get('updated_at'):
        order['updated_at'] = order['updated_at'].isoformat()
    return jsonify({'order': order, 'items': items})


@app.route('/api/cart/<user_id>', methods=['GET'])
def get_cart(user_id):
    """Get user's cart"""
    cart = chatbot.get_cart(user_id)
    return jsonify({'cart': cart})


@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    """Add item to cart"""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    product = data.get('product')

    if not user_id or not product:
        return jsonify({'error': 'User ID and product required'}), 400

    response = chatbot.add_to_cart(user_id, product)
    # Return updated cart count from DB if available
    cart_count = len(chatbot.get_cart(user_id))
    return jsonify({'message': response, 'cart_count': cart_count})


@app.route('/api/cart/details/<user_id>', methods=['GET'])
def get_cart_details(user_id):
    """Get cart with full pricing details and grand total"""
    if hasattr(db, 'get_cart_details'):
        details = db.get_cart_details(user_id)
        return jsonify(details)
    # Fallback: plain list
    cart = chatbot.get_cart(user_id)
    return jsonify({'items': [{'name': p} for p in cart], 'total_price': 0.0})


@app.route('/api/cart/clear', methods=['POST'])
def clear_cart():
    """Clear all items from a user's cart"""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400

    if hasattr(db, 'clear_cart'):
        db.clear_cart(user_id)
        # Sync session cart too
        chatbot._ensure_session(user_id)
        chatbot.user_sessions[user_id]['cart'] = []
    return jsonify({'message': 'Cart cleared', 'user_id': user_id})


@app.route('/api/products', methods=['GET'])
def get_products():
    """Get product catalog"""
    return jsonify(chatbot.product_catalog)


@app.route('/api/faq', methods=['GET'])
def get_faq():
    """Get FAQ data"""
    return jsonify(chatbot.faq_data)


@app.route('/api/promotions', methods=['GET'])
def list_promotions():
    """List all promotions (with status + product info) for the marketing dashboard."""
    return jsonify({'promotions': chatbot.promotion_service.list_all()})


@app.route('/api/promotions', methods=['POST'])
def create_promotion():
    """Create a new promotion campaign."""
    data = request.get_json(silent=True) or {}
    if not data.get('product_id'):
        return jsonify({'error': 'product_id is required'}), 400
    promo = chatbot.promotion_service.create(data)
    if not promo:
        return jsonify({'error': 'Could not create promotion'}), 400
    return jsonify({'promotion': promo}), 201


@app.route('/api/promotions/<promo_id>', methods=['PATCH'])
def update_promotion(promo_id):
    """Update a promotion (title, message, discount, dates, active toggle)."""
    data = request.get_json(silent=True) or {}
    promo = chatbot.promotion_service.update(promo_id, data)
    if not promo:
        return jsonify({'error': 'Promotion not found'}), 404
    return jsonify({'promotion': promo})


@app.route('/api/promotions/<promo_id>', methods=['DELETE'])
def delete_promotion(promo_id):
    """Delete a promotion."""
    if not chatbot.promotion_service.delete(promo_id):
        return jsonify({'error': 'Promotion not found'}), 404
    return jsonify({'message': 'Promotion deleted'})


@app.route('/api/promotions/products', methods=['GET'])
def search_promo_products():
    """Product picker search for the marketing dashboard."""
    q = (request.args.get('q') or '').strip()
    limit = min(int(request.args.get('limit', 8)), 20)
    if not q:
        return jsonify({'products': []})
    products = db.search_products(q, limit=limit)
    return jsonify({'products': products})


@app.route('/api/promotions/featured', methods=['GET'])
def featured_promotion():
    """Return the featured live promo card (localized) shown when chat opens."""
    lang = request.args.get('lang', 'en')
    user_id = request.args.get('user_id')
    card = chatbot.featured_promo_card(lang)
    if not card:
        return jsonify({'promo': None})
    if user_id:
        chatbot._ensure_session(user_id)
        chatbot.user_sessions[user_id].promo_aware = True
    return jsonify({'promo': {'card': card}})


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'db_connected': db.health_check()
    })


if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('PORT')) if os.getenv('PORT', '').strip().isdigit() else 5000
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Dynamically find the primary local IP address to print nice instructions
    local_ip = '127.0.0.1'
    if host == '0.0.0.0':
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = '127.0.0.1'
        finally:
            s.close()

    print(f"[GojoShop] Chatbot starting...")
    print(f"  - Local:           http://127.0.0.1:{port}")
    if host == '0.0.0.0' and local_ip != '127.0.0.1':
        print(f"  - Local Network:   http://{local_ip}:{port}")
    
    app.run(host=host, debug=debug, port=port)

