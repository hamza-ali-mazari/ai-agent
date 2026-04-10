"""Token usage tracking for AI API calls."""
import json
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TokenTracker:
    """Track token usage across API calls for monitoring and billing."""

    def __init__(self):
        """Initialize token tracker."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.analyses_count = 0
        self.start_time = datetime.now()

    def record_analysis(self, response: Dict[str, Any]) -> None:
        """Record token usage from an analysis response."""
        try:
            # Handle both dict and Pydantic model responses
            if hasattr(response, 'token_usage'):
                token_usage = response.token_usage
            elif isinstance(response, dict) and 'token_usage' in response:
                token_usage = response['token_usage']
            else:
                token_usage = None
            
            if token_usage:
                # Handle both dict and object access
                prompt = token_usage.get('prompt_tokens', 0) if isinstance(token_usage, dict) else getattr(token_usage, 'prompt_tokens', 0)
                completion = token_usage.get('completion_tokens', 0) if isinstance(token_usage, dict) else getattr(token_usage, 'completion_tokens', 0)
                total = token_usage.get('total_tokens', 0) if isinstance(token_usage, dict) else getattr(token_usage, 'total_tokens', 0)
                
                self.total_prompt_tokens += prompt
                self.total_completion_tokens += completion
                self.total_tokens += total
                logger.info(f"Token tracker: +{total} tokens (prompt: {prompt}, completion: {completion})")
            
            self.analyses_count += 1
        except Exception as e:
            logger.warning(f"Error recording token usage: {e}")
            self.analyses_count += 1

    def get_cumulative_stats(self) -> Dict[str, Any]:
        """Get cumulative token usage statistics."""
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "analyses_count": self.analyses_count,
            "average_tokens_per_analysis": (
                self.total_tokens // self.analyses_count if self.analyses_count > 0 else 0
            ),
            "session_start": self.start_time.isoformat()
        }

    def format_analysis_report(self, response: Dict[str, Any]) -> str:
        """Format token usage for a single analysis."""
        try:
            if hasattr(response, 'token_usage') and response.token_usage:
                tokens = response.token_usage
                return (
                    f"📊 **Token Usage:**\n"
                    f"- Prompt tokens: {tokens.prompt_tokens}\n"
                    f"- Completion tokens: {tokens.completion_tokens}\n"
                    f"- Total: {tokens.total_tokens}"
                )
            return "📊 **Token Usage:** Data not available"
        except Exception as e:
            logger.warning(f"Error formatting analysis report: {e}")
            return "📊 **Token Usage:** Unable to calculate"

    def format_cumulative_report(self) -> str:
        """Format cumulative token usage report."""
        stats = self.get_cumulative_stats()
        return (
            f"📈 **Cumulative Token Usage:**\n"
            f"- Total tokens: {stats['total_tokens']:,}\n"
            f"- Prompt tokens: {stats['prompt_tokens']:,}\n"
            f"- Completion tokens: {stats['completion_tokens']:,}\n"
            f"- Analyses: {stats['analyses_count']}\n"
            f"- Average per analysis: {stats['average_tokens_per_analysis']:,}\n"
            f"- Session start: {stats['session_start']}"
        )


# Global token tracker instance
token_tracker = TokenTracker()

__all__ = ['TokenTracker', 'token_tracker']
