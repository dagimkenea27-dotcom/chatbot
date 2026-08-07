# telegram_bot.py
import re

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from chatbot import GojoShopChatbot
from database import db
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

def _strip_bold(text: str) -> str:
    """Convert **bold** markers into plain text (Telegram-safe)."""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        # Share the app's DatabaseManager so carts/orders/sessions persist
        self.chatbot = GojoShopChatbot(db_manager=db)
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

    def _format_cart_card(self, text: str, lang: str) -> str:
        """Render a [CART] card as friendly plain text."""
        items, total, prompt, msg = [], "", "", ""
        # The web bot may prefix the card with a natural intro line that
        # carries a "Msg: ..." note on the same line (e.g. "Sure! Msg: ...").
        marker = text.find("Msg:")
        if marker != -1:
            msg = text[marker + len("Msg:"):].splitlines()[0].strip()
        start = text.find("[CART]")
        body = text[start + len("[CART]"):] if start != -1 else text
        for line in body.splitlines():
            t = line.strip()
            if t.startswith("Item:"):
                items.append(t[len("Item:"):].strip())
            elif t.startswith("Total:"):
                total = t[len("Total:"):].strip()
            elif t.startswith("Prompt:"):
                prompt = t[len("Prompt:"):].strip()

        header = "ጋሪዎ" if lang == "am" else "Your Cart"
        lines = []
        if msg:
            lines.append(_strip_bold(msg))
        lines.append(f"🛒 {header}")
        lines += [f"• {it}" for it in items] or ["• —"]
        if total:
            lines.append(f"\n💰 Total: {total}")
        if prompt:
            lines.append(f"\n{_strip_bold(prompt)}")
        return "\n".join(lines)

    def _format_checkout_card(self, text: str, lang: str) -> str:
        """Render a [CHECKOUT] review card as friendly plain text."""
        data = {"name": "", "phone": "", "address": "", "payment": "",
                "total": "", "prompt": "", "items": []}
        for line in text.splitlines():
            t = line.strip()
            if t.startswith("Step:"):
                continue
            for key in ("Name", "Phone", "Address", "Payment", "Total", "Prompt"):
                if t.startswith(key + ":"):
                    data[key.lower()] = t[len(key) + 1:].strip()
                    break
            else:
                if t.startswith("Item:"):
                    data["items"].append(t[len("Item:"):].strip())

        header = "ትዕዛዝ ማረጋገጫ" if lang == "am" else "Checkout Review"
        lines = [f"📋 {header}"]
        if data["name"]:
            lines.append(f"👤 Name: {data['name']}")
        if data["phone"]:
            lines.append(f"📞 Phone: {data['phone']}")
        if data["address"]:
            lines.append(f"📍 Address: {data['address']}")
        if data["payment"]:
            lines.append(f"💳 Payment: {data['payment']}")
        if data["items"]:
            lines.append("")
            lines += [f"• {it}" for it in data["items"]]
        if data["total"]:
            lines.append(f"\n💰 Total: {data['total']}")
        if data["prompt"]:
            lines.append(f"\n{_strip_bold(data['prompt'])}")
        return "\n".join(lines)

    def _format_response(self, response: str, lang: str) -> str:
        """Convert structured cards / heavy markers into clean Telegram text."""
        if "[CART]" in response:
            return self._format_cart_card(response, lang)
        if response.startswith("[CHECKOUT]"):
            return self._format_checkout_card(response, lang)

        # General cleanup for plain-text cards (search / order / promo / faq).
        cleaned = []
        for line in response.splitlines():
            s = line.strip()
            # Drop structured-card noise that only matters to the web renderer.
            if (s.startswith("Product ID:") or s.startswith("Filters:")
                    or s.startswith("HasMore:") or s.startswith("Image:")
                    or s.startswith("Step:")):
                continue
            # Strip inline card markers (they can follow a personality intro).
            s = re.sub(r"\b(PROMO|RECOMMENDATIONS|PRODUCT SEARCH)\b", "", s)
            s = re.sub(r"\s{2,}", " ", s).strip()
            if s == "---":
                s = ""
            # Replace heavy box-drawing separators.
            s = re.sub(r"━+", "—", s)
            cleaned.append(s)

        text = "\n".join(cleaned)
        # Collapse 3+ consecutive blank lines down to one blank line.
        text = re.sub(r"\n{3,}", "\n\n", text)
        return _strip_bold(text)

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
        """Handle /cart command — reuse the show_cart intent for a [CART] card."""
        user_id = str(update.effective_user.id)
        lang = _get_lang(user_id)
        self.chatbot._ensure_session(user_id)
        response = self.chatbot.get_response(user_id, "cart")
        await update.message.reply_text(self._format_response(response, lang))

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user messages"""
        user_id = str(update.effective_user.id)
        message = update.message.text
        lang = _get_lang(user_id)

        # Ensure language set in chatbot session matches Telegram language pref
        self.chatbot._ensure_session(user_id)
        self.chatbot.user_sessions[user_id]["language"] = lang

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

        # Route support-mode marker to a human-friendly note.
        if response == "[SUPPORT_MODE]":
            note = ("የድጋፍ ቡድናችን ምላሽ ይሰጥዎታል። እባክዎ ይጠብቁ። 🙏"
                    if lang == "am" else
                    "Your message has been passed to our support team. They will get back to you soon. 🙏")
            await update.message.reply_text(note)
            return

        await update.message.reply_text(self._format_response(response, lang))

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
