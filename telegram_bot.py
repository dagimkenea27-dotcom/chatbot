# telegram_bot.py
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from chatbot_service import GojoShopChatbot
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.chatbot = GojoShopChatbot()
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup bot command and message handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("cart", self.cart_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        keyboard = [
            ['🛍️ Shop', '🔍 Search'],
            ['🛒 Cart', '📦 Orders'],
            ['❓ Help', '📞 Contact']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        welcome_message = """Welcome to GojoShop.et! 🛍️

Your one-stop shop for quality products in Ethiopia.

I'm here to help you find products, answer questions, and assist with your shopping needs.

What can I help you with today?"""
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """🆘 How can I help you?

Commands:
/start - Start the bot
/help - Show this help message
/cart - View your cart
/search [product] - Search for products

I can also help with:
• Product recommendations
• Order tracking
• Returns and refunds
• Payment methods
• Shipping information

Just type your question!"""
        
        await update.message.reply_text(help_text)
    
    async def cart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cart command"""
        user_id = str(update.effective_user.id)
        cart = self.chatbot.get_cart(user_id)
        
        if not cart:
            await update.message.reply_text("🛒 Your cart is empty. Start shopping! 🛍️")
        else:
            cart_items = "\n".join([f"• {item}" for item in cart])
            await update.message.reply_text(f"🛒 Your Cart:\n\n{cart_items}\n\nTotal: Calculate at checkout")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user messages"""
        user_id = str(update.effective_user.id)
        message = update.message.text
        user_name = update.effective_user.first_name
        
        # Get response from chatbot
        response = self.chatbot.get_response(user_id, message)
        await update.message.reply_text(response)
    
    def run(self):
        """Start the bot"""
        print("🤖 GojoShop Telegram Bot is running...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN not set in .env file!")
    print(f"🤖 GojoShop Telegram Bot starting...")
    bot = TelegramBot(TOKEN)
    bot.run()
    