# chatbot/models/memory.py
from typing import Dict, List, Optional, Any
from datetime import datetime


class ConversationContext:
    """Conversation context for a user."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.topic_history: List[Dict] = []
        self.current_topic: Optional[str] = None
        self.last_user_message: Optional[str] = None
        self.last_bot_message: Optional[str] = None
        self.entities: Dict = {}
        self.pending_questions: List[str] = []
        self.turn_count: int = 0
        self.clarification_needed: bool = False
        self.last_topic_switch: Optional[str] = None
        self.user_intent: Optional[str] = None
        self.conversation_flow: List[Dict] = []
        self.conversation_mode: str = "idle"
        self.last_search_results: Optional[List] = None
        self.awaiting_followup: bool = False
        self.conversation_stage: str = "greeting"
        self.last_question_type: Optional[str] = None
        self.session = None


class ConversationMemory:
    """Manages conversation memory for all users."""
    
    def __init__(self):
        self._contexts: Dict[str, ConversationContext] = {}
    
    def get_context(self, user_id: str) -> ConversationContext:
        """Get or create conversation context for a user."""
        if user_id not in self._contexts:
            self._contexts[user_id] = ConversationContext(user_id)
        return self._contexts[user_id]
    
    def update_flow(self, user_id: str, message: str, response: str, intent: str):
        """Update conversation flow."""
        context = self.get_context(user_id)
        context.turn_count += 1
        context.last_user_message = message
        context.last_bot_message = response
        
        if intent != context.current_topic:
            context.last_topic_switch = context.current_topic
            context.current_topic = intent
        
        # Update conversation mode
        mode_map = {
            "product_search": "searching",
            "product_followup": "searching",
            "add_last_product": "searching",
            "order_lookup": "ordering",
            "order_followup": "ordering",
            "greeting": "chatting",
            "small_talk": "chatting",
            "farewell": "idle"
        }
        context.conversation_mode = mode_map.get(intent, context.conversation_mode)
        
        context.topic_history.append({
            "turn": context.turn_count,
            "user": message[:100],
            "bot": response[:100],
            "intent": intent,
            "mode": context.conversation_mode,
            "timestamp": datetime.now().isoformat()
        })
        
        if len(context.topic_history) > 50:
            context.topic_history = context.topic_history[-50:]
    
    def clear_context(self, user_id: str):
        """Clear conversation context for a user."""
        if user_id in self._contexts:
            del self._contexts[user_id]