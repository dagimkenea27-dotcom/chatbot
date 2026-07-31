# telegram_bot.py
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from chatbot import GojoShopChatbot
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Per-user language store (in-memory, keyed by Telegram user ID)
_user_languages: dict[str, str] = {}

def _get_lang(user_id: str) -> str:
    return _user_languages.get(user_id, "en")

def _set_lang(user_id: str, lang: str):
    _user_languages[user_id] = lang

class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.chatbot = GojoShopChatbot()
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup bot command and message handlers"""
        self.application.add_handler(CommandHandler("start",    self.start_command))
        self.application.add_handler(CommandHandler("help",     self.help_command))
        self.application.add_handler(CommandHandler("cart",     self.cart_command))
        self.application.add_handler(CommandHandler("lang",     self.lang_command))
        self.application.add_handler(CommandHandler("language", self.lang_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    def _keyboard(self, lang: str) -> ReplyKeyboardMarkup:
        """Return reply keyboard buttons in the correct language."""
        if lang == "am":
            rows = [
                ['🛍️ ሱቅ', '🔍 ፈልግ'],
                ['🛒 ጋሪ', '📦 ትዕዛዞች'],
                ['❓ እርዳታ', '📞 አግኙን'],
            ]
        else:
            rows = [
                ['🛍️ Shop', '🔍 Search'],
                ['🛒 Cart', '📦 Orders'],
                ['❓ Help', '📞 Contact'],
            ]
        return ReplyKeyboardMarkup(rows, resize_keyboard=True)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = str(update.effective_user.id)
        lang = _get_lang(user_id)
        reply_markup = self._keyboard(lang)

        if lang == "am":
            welcome_message = (
                "ወደ GojoShop.et እንኳን ደህና መጡ! 🛍️\n\n"
                "ምርቶችን ለማስፈለግ፣ ጥያቄዎችን ለመጠየቅ "
                "እና የፈለጉትን ለማግኘት እዚህ ነኝ።\n\n"
                "ለቋንቋ ቅንብር /lang ይጠቀሙ (ለምሳሌ: /lang am).\n\n"
                "ዛሬ በምን ልርዳዎት?"
            )
        else:
            welcome_message = (
                "Welcome to GojoShop.et! 🛍️\n\n"
                "Your one-stop shop for quality products in Ethiopia.\n\n"
                "I'm here to help you find products, answer questions, and assist with your shopping needs.\n\n"
                "Use /lang to change language (e.g. /lang am for Amharic).\n\n"
                "What can I help you with today?"
            )
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    
    async def lang_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /lang [en|am] command to switch language."""
        user_id = str(update.effective_user.id)
        args = context.args
        current_lang = _get_lang(user_id)

        if not args:
            if current_lang == "am":
                await update.message.reply_text(
                    "አሁን የሚጠቀሙት ቋንቋ: አማርኛ 🇪🇹\n"
                    "ወደ እንግሊዝኛ ለመቀየር: /lang en"
                )
            else:
                await update.message.reply_text(
                    "Current language: English 🇬🇧\n"
                    "Switch to Amharic: /lang am"
                )
            return

        lang = args[0].lower()
        if lang not in ("en", "am"):
            await update.message.reply_text("Supported languages: en (English), am (አማርኛ)")
            return

        _set_lang(user_id, lang)
        # Propagate to chatbot session
        session = self.chatbot.user_sessions.get(user_id)
        if session:
            session["language"] = lang

        if lang == "am":
            await update.message.reply_text(
                "ቋንቋ ወደ አማርኛ ተቀይሯል! 🇪🇹",
                reply_markup=self._keyboard("am")
            )
        else:
            await update.message.reply_text(
                "Language switched to English! 🇬🇧",
                reply_markup=self._keyboard("en")
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = str(update.effective_user.id)
        lang = _get_lang(user_id)

        if lang == "am":
            help_text = (
                "🆘 በምን ልርዳዎት?\n\n"
                "ትዕዛዞች:\n"
                "/start - ቦቱን ጀምር\n"
                "/help - ይህን የእርዳታ መልዕክት አሳይ\n"
                "/cart - ጋሪህን/ሽን እይ\n"
                "/lang am - ወደ አማርኛ ቀይር\n"
                "/lang en - ወደ እንግሊዝኛ ቀይር\n\n"
                "እንዲሁም ልረዳ:\n"
                "• ምርት ምክሮች\n"
                "• ትዕዛዝ መከታተል\n"
                "• መመለሻ ጥያቄዎች\n"
                "• የክፍያ ዘዴዎች\n"
                "• የማድረሻ መረጃ\n\n"
                "ጥያቄዎን ይተይቡ!"
            )
        else:
            help_text = (
                "🆘 How can I help you?\n\n"
                "Commands:\n"
                "/start - Start the bot\n"
                "/help - Show this help message\n"
                "/cart - View your cart\n"
                "/lang am - Switch to Amharic\n"
                "/lang en - Switch to English\n\n"
                "I can also help with:\n"
                "• Product recommendations\n"
                "• Order tracking\n"
                "• Returns and refunds\n"
                "• Payment methods\n"
                "• Shipping information\n\n"
                "Just type your question!"
            )
        
        await update.message.reply_text(help_text)
    
    async def cart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cart command"""
        user_id = str(update.effective_user.id)
        lang = _get_lang(user_id)
        cart = self.chatbot.get_cart(user_id)
        
        if not cart:
            msg = "🛒 ጋሪዎ ባዶ ነው። ለመግዛት ይጀምሩ! 🛍️" if lang == "am" else "🛒 Your cart is empty. Start shopping! 🛍️"
            await update.message.reply_text(msg)
        else:
            cart_items = "\n".join([f"• {item}" for item in cart])
            if lang == "am":
                await update.message.reply_text(f"🛒 ጋሪዎ:\n\n{cart_items}\n\nጠቅላላ: ሂሳብ ሲከፍሉ ይሰላል")
            else:
                await update.message.reply_text(f"🛒 Your Cart:\n\n{cart_items}\n\nTotal: Calculate at checkout")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user messages"""
        user_id = str(update.effective_user.id)
        message = update.message.text

        # Ensure language set in chatbot session matches Telegram language pref
        self.chatbot._ensure_session(user_id)
        self.chatbot.user_sessions[user_id]["language"] = _get_lang(user_id)

        # Detect quick-reply button presses and map them to English commands
        button_map_am = {
            "🛍️ ሱቅ": "show products",
            "🔍 ፈልግ": "search",
            "🛒 ጋሪ": "cart",
            "📦 ትዕዛዞች": "track order",
            "❓ እርዳታ": "help",
            "📞 አግኙን": "talk to human",
        }
        if message in button_map_am:
            message = button_map_am[message]

        # Get response from chatbot (language is already in session)
        response = self.chatbot.get_response(user_id, message)

        # Strip the heavy card format markers for Telegram (plain text is fine)
        response = response.replace("━━━━━━━━━━━━━━━━━━━━━━", "—" * 10)
        response = response.replace("━━━ PRODUCT SEARCH ━━━", "🔍 ውጤቶች:" if _get_lang(user_id) == "am" else "🔍 Search Results:")
        response = response.replace("━━━ RECOMMENDATIONS ━━━", "💡 ምክሮች:" if _get_lang(user_id) == "am" else "💡 Recommendations:")
        response = response.replace("━━━ HUMAN SUPPORT ━━━", "👤 " + ("ድጋፍ:" if _get_lang(user_id) == "am" else "Support:"))
        response = response.replace("━━━━━━━━━━━━━━━━━━━━━━", "——————————")

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