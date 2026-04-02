"""
Bitbucket Integration for AI Code Review Engine

This module provides integration with Bitbucket for automated pull request reviews.
Supports both Bitbucket Cloud and Bitbucket Server/Data Center.
"""

import os
import hmac
import hashlib
import json
import requests
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class BitbucketWebhookPayload(BaseModel):
    eventKey: str
    pullrequest: Optional[Dict[str, Any]] = None  # Bitbucket uses lowercase
    repository: Dict[str, Any]
    actor: Dict[str, Any]

    model_config = {"validate_assignment": True}

class BitbucketIntegration:
    """Bitbucket integration for AI Code Review Engine."""

    def __init__(self, base_url: str = "http://localhost:8000", is_server: bool = False):
        self.base_url = base_url
        self.bitbucket_username = os.getenv("BITBUCKET_USERNAME")
        self.bitbucket_token = os.getenv("BITBUCKET_TOKEN")  # API token for both Cloud and Server
        self.webhook_secret = os.getenv("BITBUCKET_WEBHOOK_SECRET")
        self.is_server = is_server  # True for Bitbucket Server/Data Center

        # API base URLs
        self.api_base = "https://api.bitbucket.org/2.0" if not is_server else os.getenv("BITBUCKET_SERVER_URL", "")

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Bitbucket webhook signature."""
        if not self.webhook_secret:
            return True  # Skip verification if no secret configured

        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(f"sha256={expected_signature}", signature)

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Bitbucket API."""
        if self.bitbucket_token:
            return {"Authorization": f"Bearer {self.bitbucket_token}"}
        else:
            raise ValueError("BITBUCKET_TOKEN is required. App passwords are deprecated - use API tokens instead.")

    async def handle_pull_request_event(self, payload: BitbucketWebhookPayload) -> None:
        """Handle Bitbucket pull request events."""
        event_actions = [
            "pullrequest:created",
            "pullrequest:updated",
            "pullrequest:reopened"
        ]

        if payload.eventKey not in event_actions:
            return

        pr = payload.pullrequest
        if not pr:
            return

        repo = payload.repository
        workspace = repo.get("workspace", {}).get("slug") or repo.get("owner", {}).get("username")
        repo_slug = repo["slug"]
        pr_id = pr["id"]

        logger.info(f"Processing PR #{pr_id} in {workspace}/{repo_slug}")

        try:
            # Get PR diff
            diff_content = self.get_pull_request_diff(workspace, repo_slug, pr_id)
            if not diff_content:
                logger.warning(f"No diff content for PR #{pr_id}")
                return

            # Get all files in PR (for comprehensive review)
            pr_files = self.get_pull_request_files(workspace, repo_slug, pr_id)

            # Prepare review request
            review_request = {
                "diff": diff_content,
                "repository_url": f"https://bitbucket.org/{workspace}/{repo_slug}",
                "branch": pr["source"]["branch"]["name"],
                "commit_sha": pr["source"]["commit"]["hash"],
                "author": pr["author"]["display_name"],
                "files_changed": pr_files,
                "config": {
                    "enabled_categories": ["bugs", "security", "performance", "maintainability"],
                    "severity_threshold": "info",
                    "max_comments_per_file": 5
                }
            }

            # Call AI review engine
            review_response = await self.call_review_engine(review_request)

            # Post review comments to Bitbucket
            await self.post_review_comments(workspace, repo_slug, pr_id, review_response)

            # Post overall review summary
            await self.post_review_summary(workspace, repo_slug, pr_id, review_response)

        except Exception as e:
            logger.error(f"Error processing PR #{pr_id}: {str(e)}")

    def get_pull_request_diff(self, workspace: str, repo_slug: str, pr_id: int) -> Optional[str]:
        """Get diff content from Bitbucket PR."""
        url = f"{self.api_base}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diff"
        headers = self.get_auth_headers()

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        else:
            logger.error(f"Failed to get PR diff: {response.status_code}")
            return None

    def get_pull_request_files(self, workspace: str, repo_slug: str, pr_id: int) -> List[str]:
        """Get all files changed in the PR."""
        url = f"{self.api_base}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diffstat"
        headers = self.get_auth_headers()

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return [item["new"]["path"] for item in data.get("values", []) if item.get("new")]
            else:
                logger.warning(f"Failed to get PR files: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting PR files: {str(e)}")
            return []

    async def call_review_engine(self, review_request: Dict[str, Any]) -> Dict[str, Any]:
        """Call the AI review engine API."""
        url = f"{self.base_url}/review"
        response = requests.post(url, json=review_request)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Review engine error: {response.status_code}")

    async def post_review_comments(self, workspace: str, repo_slug: str, pr_id: int, review_response: Dict[str, Any]) -> None:
        """Post individual review comments to Bitbucket PR."""
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"

        for file_review in review_response.get("files", []):
            for comment in file_review.get("comments", []):
                if comment.get("severity") in ["critical", "high", "medium"]:
                    # Create review comment
                    comment_data = {
                        "content": {
                            "raw": self.format_comment_body(comment)
                        },
                        "inline": {
                            "path": file_review["file_path"],
                            "from": comment.get("location", {}).get("line_start"),
                            "to": comment.get("location", {}).get("line_end", comment.get("location", {}).get("line_start"))
                        }
                    }

                    url = f"{self.api_base}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
                    response = requests.post(url, json=comment_data, headers=headers)

                    if response.status_code not in [201, 200]:
                        logger.error(f"Failed to post comment: {response.status_code}")

    async def post_review_summary(self, workspace: str, repo_slug: str, pr_id: int, review_response: Dict[str, Any]) -> None:
        """Post overall review summary as a comment."""
        summary = review_response.get("summary", {})
        overall_feedback = review_response.get("overall_feedback", "")
        recommendations = review_response.get("recommendations", [])

        body = f"""## 🤖 AI Code Review Summary

**Overall Score:** {summary.get('overall_score', 0)}/100

### Issues Found:
- 🔴 Critical: {summary.get('critical_issues', 0)}
- 🟠 High: {summary.get('high_issues', 0)}
- 🟡 Medium: {summary.get('medium_issues', 0)}
- 🟢 Low: {summary.get('low_issues', 0)}
- ℹ️ Info: {summary.get('info_suggestions', 0)}

### Feedback:
{overall_feedback}

### Recommendations:
""" + "\n".join(f"- {rec}" for rec in recommendations)

        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"

        comment_data = {
            "content": {
                "raw": body
            }
        }

        url = f"{self.api_base}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
        response = requests.post(url, json=comment_data, headers=headers)

        if response.status_code not in [201, 200]:
            logger.error(f"Failed to post summary: {response.status_code}")

    def format_comment_body(self, comment: Dict[str, Any]) -> str:
        """Format a review comment for Bitbucket."""
        severity_emojis = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
            "info": "ℹ️"
        }

        emoji = severity_emojis.get(comment.get("severity", "info"), "ℹ️")
        category = comment.get("category", "general").replace("_", " ").title()

        body = f"""**{emoji} {comment.get('title', 'Review Comment')}**

**Category:** {category}  
**Severity:** {comment.get('severity', 'info').title()}

{comment.get('description', '')}

"""

        if comment.get('suggestion'):
            body += f"**Suggestion:** {comment['suggestion']}\n\n"

        if comment.get('code_example'):
            body += f"**Example:**\n```python\n{comment['code_example']}\n```\n"

        return body


# FastAPI integration example
bitbucket_app = FastAPI()
bitbucket_integration = BitbucketIntegration()

@bitbucket_app.post("/webhook/bitbucket")
async def bitbucket_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """Handle Bitbucket webhooks."""
    # Get raw payload
    payload = await request.body()

    # Verify signature if configured
    signature = request.headers.get("X-Hub-Signature")
    if signature and not bitbucket_integration.verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        data = json.loads(payload)
        webhook_payload = BitbucketWebhookPayload(**data)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    # Handle the event in background
    background_tasks.add_task(
        bitbucket_integration.handle_pull_request_event,
        webhook_payload
    )

    return {"status": "accepted"}


if __name__ == "__main__":
    # Example usage
    import uvicorn

    # Set environment variables
    os.environ["BITBUCKET_USERNAME"] = "your_username"
    os.environ["BITBUCKET_TOKEN"] = "your_api_token"
    os.environ["BITBUCKET_WEBHOOK_SECRET"] = "your_webhook_secret"

    uvicorn.run(bitbucket_app, host="0.0.0.0", port=8003)