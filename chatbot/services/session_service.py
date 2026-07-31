from datetime import datetime
from typing import Dict, List, Optional, Any
from chatbot.models.session import Session


class SessionService:
    """Manages user sessions and conversation history."""
    
    def __init__(self, db_manager=None):
        self.db = db_manager
        self.user_sessions = {}
    
    def get_session(self, user_id: str) -> Session:
        """Get or create a user session."""
        if user_id not in self.user_sessions:
            raw_session = None
            try:
                if self.db and hasattr(self.db, "get_user_session"):
                    raw_session = self.db.get_user_session(user_id)
            except Exception as e:
                print(f"Error getting session for {user_id}: {e}")
                raw_session = None
            
            if isinstance(raw_session, dict):
                session = Session.from_dict(raw_session)
                session.user_id = user_id
            elif isinstance(raw_session, Session):
                session = raw_session
                session.user_id = user_id
            else:
                session = Session(user_id=user_id)
                try:
                    if self.db and hasattr(self.db, "save_user_session"):
                        self.db.save_user_session(user_id, session.to_dict())
                except Exception as e:
                    print(f"Error saving new session for {user_id}: {e}")
            self.user_sessions[user_id] = session
        else:
            if isinstance(self.user_sessions[user_id], Session):
                self.user_sessions[user_id].user_id = user_id
            elif isinstance(self.user_sessions[user_id], dict):
                self.user_sessions[user_id] = Session.from_dict(self.user_sessions[user_id])
                self.user_sessions[user_id].user_id = user_id
        return self.user_sessions[user_id]
    
    def save_session(self, user_id: str):
        """Persist user session to database."""
        if self.db and hasattr(self.db, "save_user_session") and user_id in self.user_sessions:
            try:
                session = self.user_sessions[user_id]
                session_dict = session.to_dict() if hasattr(session, "to_dict") else session
                self.db.save_user_session(user_id, session_dict)
            except Exception as e:
                print(f"Error saving session for {user_id}: {e}")
    
    def record_turn(self, session: Session, role: str, text: str, intent: str = None):
        """Store a structured conversation turn for context."""
        session.conversation_history.append({
            "role": role,
            "text": text,
            "intent": intent,
            "timestamp": datetime.now().isoformat(),
        })
        if len(session.conversation_history) > 20:
            session.conversation_history = session.conversation_history[-20:]
    
    def reset_session(self, user_id: str):
        """Clear conversation context for a user."""
        if self.db and hasattr(self.db, "delete_user_session"):
            try:
                self.db.delete_user_session(user_id)
            except Exception as e:
                print(f"Error deleting session for {user_id}: {e}")
        self.user_sessions.pop(user_id, None)