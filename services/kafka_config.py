"""
Kafka Configuration Handler for AI Code Review Engine

Optimized message suggestions and event streaming for code review workflows.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ReviewEventType(str, Enum):
    REVIEW_STARTED = "review:started"
    ANALYSIS_COMPLETE = "review:analysis_complete"
    SECURITY_ISSUE_FOUND = "review:security_issue"
    APPROVAL_READY = "review:approval_ready"
    MERGE_REQUESTED = "review:merge_requested"
    REVIEW_FAILED = "review:failed"


class KafkaConfigHandler:
    """Handles Kafka event streaming and optimized message suggestions."""

    def __init__(self, broker_url: Optional[str] = None):
        self.broker_url = broker_url or "localhost:9092"
        self.topic_prefix = "code-review"
        self.events = []

    def create_review_event(
        self,
        event_type: ReviewEventType,
        review_id: str,
        pr_id: int,
        workspace: str,
        repo_slug: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create an optimized Kafka event for code review workflow."""
        event = {
            "event_type": event_type.value,
            "review_id": review_id,
            "pr_id": pr_id,
            "workspace": workspace,
            "repo_slug": repo_slug,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
            "version": "1.0"
        }
        self.events.append(event)
        logger.info(f"Created Kafka event: {event_type.value} for PR #{pr_id}")
        return event

    def create_review_started_event(
        self,
        review_id: str,
        pr_id: int,
        workspace: str,
        repo_slug: str,
        branch: str,
        files_count: int
    ) -> Dict[str, Any]:
        """Event when review analysis starts."""
        return self.create_review_event(
            ReviewEventType.REVIEW_STARTED,
            review_id,
            pr_id,
            workspace,
            repo_slug,
            {
                "branch": branch,
                "files_count": files_count,
                "status": "analyzing"
            }
        )

    def create_analysis_complete_event(
        self,
        review_id: str,
        pr_id: int,
        workspace: str,
        repo_slug: str,
        summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Event when analysis is complete."""
        return self.create_review_event(
            ReviewEventType.ANALYSIS_COMPLETE,
            review_id,
            pr_id,
            workspace,
            repo_slug,
            {
                "overall_score": summary.get("overall_score"),
                "total_comments": summary.get("total_comments"),
                "critical_issues": summary.get("critical_issues"),
                "status": "complete"
            }
        )

    def create_approval_ready_event(
        self,
        review_id: str,
        pr_id: int,
        workspace: str,
        repo_slug: str,
        destination_branch: str,
        can_merge: bool
    ) -> Dict[str, Any]:
        """Event when code is ready for approval/merge."""
        return self.create_review_event(
            ReviewEventType.APPROVAL_READY,
            review_id,
            pr_id,
            workspace,
            repo_slug,
            {
                "destination_branch": destination_branch,
                "can_merge": can_merge,
                "allowed_branches": ["master", "sit"],
                "status": "ready_for_approval"
            }
        )

    def create_security_issue_event(
        self,
        review_id: str,
        pr_id: int,
        workspace: str,
        repo_slug: str,
        issue: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Event when security issue is detected."""
        return self.create_review_event(
            ReviewEventType.SECURITY_ISSUE_FOUND,
            review_id,
            pr_id,
            workspace,
            repo_slug,
            {
                "severity": issue.get("severity"),
                "title": issue.get("title"),
                "file": issue.get("file_path"),
                "line": issue.get("line_start")
            }
        )

    def generate_optimized_suggestion(
        self,
        comment: Dict[str, Any],
        file_language: str
    ) -> str:
        """Generate optimized code suggestion for Kafka event."""
        suggestion = f"""
[{comment.get('severity', 'info').upper()}] {comment.get('title', 'Code Issue')}

File: {comment.get('location', {}).get('file_path', 'unknown')}
Line: {comment.get('location', {}).get('line_start', 'N/A')}

Issue: {comment.get('description', 'See details in review')}

Fix: {comment.get('suggestion', 'Apply inline suggestion')}

Inline Fix:
```{file_language}
{comment.get('inline_suggestion', 'N/A')}
```

Reference: {', '.join(comment.get('references', []))}
"""
        return suggestion.strip()

    def get_pending_events(self) -> List[Dict[str, Any]]:
        """Get all pending Kafka events."""
        return self.events.copy()

    def clear_events(self) -> None:
        """Clear pending events after publishing."""
        self.events.clear()

    def should_allow_approval(
        self,
        destination_branch: str,
        allowed_branches: List[str] = None
    ) -> bool:
        """Check if approval/merge is allowed for destination branch."""
        allowed = allowed_branches or ["master", "sit"]
        branch_name = destination_branch.lower().split('/')[-1]
        return branch_name in allowed

    def get_approval_status(
        self,
        pr_destination_branch: str,
        analysis_complete: bool,
        has_critical_issues: bool
    ) -> Dict[str, Any]:
        """Get current approval/merge status for PR."""
        is_valid_branch = self.should_allow_approval(pr_destination_branch)
        can_approve = analysis_complete and not has_critical_issues and is_valid_branch

        return {
            "can_approve": can_approve,
            "can_merge": can_approve,
            "destination_branch": pr_destination_branch,
            "analysis_complete": analysis_complete,
            "has_blocking_issues": has_critical_issues,
            "is_valid_destination": is_valid_branch,
            "allowed_destinations": ["master", "sit"],
            "reason": self._get_approval_reason(
                analysis_complete, has_critical_issues, is_valid_branch
            )
        }

    def _get_approval_reason(
        self,
        analysis_complete: bool,
        has_critical_issues: bool,
        is_valid_branch: bool
    ) -> str:
        """Generate human-readable reason for approval status."""
        if not analysis_complete:
            return "Analysis in progress - approval unavailable until complete"
        if has_critical_issues:
            return "Critical issues found - cannot approve until resolved"
        if not is_valid_branch:
            return "Merge only allowed to 'master' or 'sit' branches"
        return "Code ready for approval and merge"
