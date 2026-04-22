import pytest
from services.chatbot_service import ChatbotService, ChatMessage
from models.review import CodeReviewResponse, ReviewSummary, FileReview, ReviewComment, ReviewCategory, ReviewSeverity
from datetime import datetime


class TestChatbotService:
    """Test cases for the chatbot service"""

    def setup_method(self):
        """Set up test fixtures"""
        self.chatbot = ChatbotService()

        # Create a mock review response
        self.mock_review = CodeReviewResponse(
            review_id="test-review-123",
            summary=ReviewSummary(
                overall_score=75,
                total_comments=5,
                critical_issues=1,
                high_issues=2,
                medium_issues=1,
                low_issues=1,
                info_suggestions=0,
                categories_breakdown={"security": 2, "performance": 1, "bugs": 2},
                analysis_errors=0
            ),
            files=[
                FileReview(
                    file_path="test.py",
                    language="python",
                    summary="Found security and performance issues",
                    comments=[
                        ReviewComment(
                            id="1",
                            category=ReviewCategory.SECURITY,
                            severity=ReviewSeverity.HIGH,
                            title="SQL Injection Vulnerability",
                            description="User input is directly concatenated into SQL query",
                            location=None,
                            suggestion="Use parameterized queries or prepared statements"
                        ),
                        ReviewComment(
                            id="2",
                            category=ReviewCategory.PERFORMANCE,
                            severity=ReviewSeverity.MEDIUM,
                            title="Inefficient Loop",
                            description="Loop could be optimized",
                            location=None,
                            suggestion="Consider using list comprehension"
                        )
                    ],
                    metrics=None
                )
            ],
            overall_feedback="Good code overall, but address the security vulnerability and consider performance improvements.",
            recommendations=[
                "Fix the SQL injection vulnerability immediately",
                "Optimize the loop for better performance",
                "Add input validation"
            ],
            metadata=None
        )

    def test_store_review_for_chat(self):
        """Test storing a review for chat"""
        review_id = self.chatbot.store_review_for_chat(self.mock_review)

        assert review_id is not None
        assert len(review_id) > 0
        assert review_id in self.chatbot.sessions

        session = self.chatbot.sessions[review_id]
        assert session.review_data == self.mock_review
        assert len(session.messages) == 0
        assert session.created_at is not None
        assert session.last_activity is not None
        assert session.full_files is None  # No full files provided

    def test_store_review_for_chat_with_full_files(self):
        """Test storing a review for chat with full file content"""
        full_files = [
            {"path": "test.py", "content": "def hello():\n    print('Hello World')", "language": "python"}
        ]
        
        review_id = self.chatbot.store_review_for_chat(self.mock_review, full_files)

        assert review_id is not None
        assert review_id in self.chatbot.sessions

        session = self.chatbot.sessions[review_id]
        assert session.review_data == self.mock_review
        assert session.full_files == full_files

    def test_send_message_valid_session(self):
        """Test sending a message to a valid chat session"""
        # Store review first
        review_id = self.chatbot.store_review_for_chat(self.mock_review)

        # Send a message
        user_message = "Can you explain the security issues in more detail?"
        response = self.chatbot.send_message(review_id, user_message)

        # In testing environment, AI might not be available, so response might be an error message
        # But the method should not crash
        assert response is not None
        assert isinstance(response, str)

        # Check that message was added to conversation
        session = self.chatbot.sessions[review_id]
        assert len(session.messages) == 2  # user + assistant
        assert session.messages[0].message == user_message
        assert session.messages[0].role == "user"
        assert session.messages[1].role == "assistant"

    def test_send_message_invalid_session(self):
        """Test sending a message to an invalid session"""
        response = self.chatbot.send_message("nonexistent-id", "Hello?")
        assert response is None

    def test_get_conversation_history_valid(self):
        """Test getting conversation history for a valid session"""
        # Store review and send a message
        review_id = self.chatbot.store_review_for_chat(self.mock_review)
        self.chatbot.send_message(review_id, "Test message")

        history = self.chatbot.get_conversation_history(review_id)

        assert history is not None
        assert len(history) == 2
        assert all(msg["role"] in ["user", "assistant"] for msg in history)
        assert all("message" in msg for msg in history)
        assert all("timestamp" in msg for msg in history)

    def test_get_conversation_history_invalid(self):
        """Test getting conversation history for an invalid session"""
        history = self.chatbot.get_conversation_history("nonexistent-id")
        assert history is None

    def test_cleanup_expired_sessions(self):
        """Test that expired sessions are cleaned up"""
        # Store a review
        review_id = self.chatbot.store_review_for_chat(self.mock_review)

        # Manually set the last activity to be very old
        import time
        old_time = datetime.now().timestamp() - (25 * 3600)  # 25 hours ago
        self.chatbot.sessions[review_id].last_activity = datetime.fromtimestamp(old_time)

        # Trigger cleanup
        self.chatbot._cleanup_expired_sessions()

        # Session should be removed
        assert review_id not in self.chatbot.sessions

    def test_empty_message_handling(self):
        """Test that empty messages are handled gracefully"""
        review_id = self.chatbot.store_review_for_chat(self.mock_review)

        # Send empty message
        response = self.chatbot.send_message(review_id, "")
        assert response is not None  # Should still get a response

        # Send whitespace-only message
        response = self.chatbot.send_message(review_id, "   ")
        assert response is not None