import logging
import uuid
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

from services.ai_review import AICodeReviewEngine
from models.review import CodeReviewResponse

logger = logging.getLogger(__name__)

class ChatMessage(BaseModel):
    """Represents a single chat message"""
    role: str  # 'user' or 'assistant'
    message: str
    timestamp: datetime

class ChatSession(BaseModel):
    """Represents a chat session for a review"""
    review_id: str
    review_data: CodeReviewResponse
    messages: List[ChatMessage]
    created_at: datetime
    last_activity: datetime
    full_files: Optional[List[Dict[str, Any]]] = None  # Complete content of files being reviewed

class ChatbotService:
    """Service for handling chatbot conversations about code reviews"""

    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        self.ai_engine = AICodeReviewEngine()
        # Session expires after 24 hours of inactivity
        self.session_ttl_hours = 24

    def store_review_for_chat(self, review_response: CodeReviewResponse, full_files: Optional[List[Dict[str, Any]]] = None, review_id: Optional[str] = None) -> str:
        """Store a review response and return a unique review ID for chat"""
        # Use provided review_id or generate one if not provided
        if not review_id:
            review_id = str(uuid.uuid4())

        session = ChatSession(
            review_id=review_id,
            review_data=review_response,
            messages=[],
            created_at=datetime.now(),
            last_activity=datetime.now(),
            full_files=full_files
        )

        self.sessions[review_id] = session
        logger.info(f"Stored review session: {review_id} with {len(full_files) if full_files else 0} full files")
        return review_id

    def send_message(self, review_id: str, message: str) -> Optional[str]:
        """Send a message to the chatbot and get a response"""
        if review_id not in self.sessions:
            return None

        session = self.sessions[review_id]

        # Add user message to conversation
        user_message = ChatMessage(
            role="user",
            message=message,
            timestamp=datetime.now()
        )
        session.messages.append(user_message)
        session.last_activity = datetime.now()

        # Generate AI response
        response = self._generate_chat_response(session, message)

        # Add assistant response to conversation
        assistant_message = ChatMessage(
            role="assistant",
            message=response,
            timestamp=datetime.now()
        )
        session.messages.append(assistant_message)

        return response

    def get_conversation_history(self, review_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get the conversation history for a review"""
        if review_id not in self.sessions:
            return None

        session = self.sessions[review_id]
        return [
            {
                "role": msg.role,
                "message": msg.message,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in session.messages
        ]

    def _generate_chat_response(self, session: ChatSession, user_message: str) -> str:
        """Generate a response from the AI based on the review data and conversation"""

        # Prepare context from review data
        review_summary = session.review_data.summary
        files = session.review_data.files
        overall_feedback = session.review_data.overall_feedback

        # Build conversation history for context
        conversation_context = ""
        if session.messages:
            # Include last few messages for context (limit to prevent token overflow)
            recent_messages = session.messages[-6:]  # Last 3 exchanges
            conversation_context = "\n".join([
                f"{msg.role.title()}: {msg.message}"
                for msg in recent_messages
            ])

        # Create prompt for the AI
        categories_str = ', '.join([f"{k}: {v}" for k, v in review_summary.categories_breakdown.items()])
        files_str = chr(10).join([f"- {file.file_path} ({file.language or 'unknown'}): {len(file.comments)} comments" for file in files])
        
        # Build file content section if available
        file_content_section = ""
        if session.full_files:
            file_lines = [f"=== {f.get('path', 'unknown')} ===\n{f.get('content', '')}" for f in session.full_files]
            file_content_section = "COMPLETE FILE CONTENT (for detailed analysis):\n" + chr(10).join(file_lines) + "\n\n"
        
        prompt = f"""You are an expert code review assistant helping developers understand and improve their code based on an AI-powered review.

REVIEW FINDINGS:
{overall_feedback}

FILES ANALYZED:
{files_str}

{file_content_section}
RECENT CONVERSATION:
{conversation_context}

USER QUESTION: {user_message}

Please provide a helpful, detailed response that:
1. Directly addresses the user's question
2. References specific findings from the review when relevant
3. Provides actionable advice when appropriate
4. Uses the review data as context but doesn't just repeat it
5. Is conversational and easy to understand

If the user asks about specific issues, reference the actual comments and suggestions from the review.
"""

        try:
            # Use the AI engine's client directly for more control
            response = self.ai_engine.client.chat.completions.create(
                model=self.ai_engine.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert code review assistant helping developers understand and improve their code. Be conversational, helpful, and provide detailed explanations when asked."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,  # More creative for conversational responses
                max_tokens=1000
            )

            # Extract response text
            if response and response.choices:
                return response.choices[0].message.content
            else:
                return "I apologize, but I encountered an issue generating a response. Please try rephrasing your question."

        except Exception as e:
            logger.error(f"Error generating chat response: {e}")
            return "I apologize, but I encountered an error while processing your question. Please try again."

    def _cleanup_expired_sessions(self):
        """Remove expired chat sessions"""
        cutoff_time = datetime.now() - timedelta(hours=self.session_ttl_hours)
        expired_ids = [
            review_id for review_id, session in self.sessions.items()
            if session.last_activity < cutoff_time
        ]

        for review_id in expired_ids:
            del self.sessions[review_id]
            logger.info(f"Cleaned up expired chat session: {review_id}")

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired chat sessions")


# Global chatbot service instance
chatbot_service = ChatbotService()
