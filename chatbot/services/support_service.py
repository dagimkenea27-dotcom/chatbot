# chatbot/services/support_service.py
import random
from datetime import datetime
from typing import Dict, List, Optional


class SupportService:
    """Manages human support requests."""
    
    def __init__(self, db_manager=None):
        self.db = db_manager
        self.support_requests: List[Dict] = []
    
    def log_request(self, user_id: str, message: str, session) -> Dict:
        """Record a human-support handoff."""
        metadata = {
            "last_intent": session.current_intent,
            "last_order_id": session.last_order_id,
            "last_search_keyword": session.last_search_keyword,
            "cart": list(session.cart),
            "user_name": session.user_name,
            "conversation_topics": session.conversation_topics,
            "user_mood": session.user_mood
        }
        
        entry = None
        try:
            if self.db and hasattr(self.db, "create_support_request"):
                req_id = f"SUP-{random.randint(10000, 99999)}"
                entry = self.db.create_support_request(req_id, user_id, message, metadata)
        except Exception as e:
            print(f"Error creating support request: {e}")
        
        if not entry:
            entry = {
                "id": f"SUP-{len(self.support_requests) + 1:05d}",
                "status": "open",
                "user_id": user_id,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata,
                "messages": [{"sender": "user", "text": message, "timestamp": datetime.now().isoformat()}],
            }
        
        self.support_requests.append(entry)
        if len(self.support_requests) > 200:
            self.support_requests = self.support_requests[-200:]
        session.human_support_requested = True
        return entry
    
    def get_active_request(self, user_id: str) -> Optional[Dict]:
        """Get active support request for user."""
        try:
            if self.db and hasattr(self.db, "get_active_support_request"):
                db_req = self.db.get_active_support_request(user_id)
                if db_req:
                    return db_req
        except Exception as e:
            print(f"Error getting active support request: {e}")
        
        for req in reversed(self.support_requests):
            if req.get("user_id") == user_id and req.get("status") in {"open", "in_progress"}:
                return req
        return None
    
    def add_message(self, request_id: str, sender: str, text: str) -> Optional[Dict]:
        """Add message to support chat."""
        try:
            if self.db and hasattr(self.db, "add_support_message"):
                db_msg = self.db.add_support_message(request_id, sender, text)
                if db_msg:
                    for req in self.support_requests:
                        if req.get("id") == request_id:
                            req.setdefault("messages", []).append(db_msg)
                    return db_msg
        except Exception as e:
            print(f"Error adding support message: {e}")
        
        for req in self.support_requests:
            if req.get("id") == request_id:
                msg = {"sender": sender, "text": text, "timestamp": datetime.now().isoformat()}
                req.setdefault("messages", []).append(msg)
                return msg
        return None
    
    def update_status(self, request_id: str, status: str) -> Optional[Dict]:
        """Update support request status."""
        if status not in {"open", "in_progress", "resolved"}:
            return None
        
        try:
            if self.db and hasattr(self.db, "update_support_request_status"):
                self.db.update_support_request_status(request_id, status)
        except Exception as e:
            print(f"Error updating support request status: {e}")
        
        for req in self.support_requests:
            if req.get("id") == request_id:
                req["status"] = status
                req["updated_at"] = datetime.now().isoformat()
                return req
        return None