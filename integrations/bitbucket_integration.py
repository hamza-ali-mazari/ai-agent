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
    eventKey: Optional[str] = None
    pullrequest: Optional[Dict[str, Any]] = None  # Bitbucket uses lowercase
    push: Optional[Dict[str, Any]] = None
    repository: Dict[str, Any]
    actor: Dict[str, Any]

    model_config = {"validate_assignment": True}

class BitbucketIntegration:
    """Bitbucket integration for AI Code Review Engine."""

    def __init__(self, base_url: str = "http://localhost:8000", is_server: bool = False, kafka_handler: Optional[Any] = None):
        self.base_url = base_url
        self.kafka_handler = kafka_handler
        self.bitbucket_username = os.getenv("BITBUCKET_USERNAME")
        self.bitbucket_token = os.getenv("BITBUCKET_TOKEN")  # App password or access token
        self.bitbucket_app_password = os.getenv("BITBUCKET_APP_PASSWORD")
        self.bitbucket_oauth_token = os.getenv("BITBUCKET_OAUTH_TOKEN")
        self.webhook_secret = os.getenv("BITBUCKET_WEBHOOK_SECRET")
        self.is_server = is_server  # True for Bitbucket Server/Data Center

        # API base URLs
        self.api_base = "https://api.bitbucket.org/2.0" if not is_server else os.getenv("BITBUCKET_SERVER_URL", "")

    def get_auth_headers(self) -> Dict[str, str]:
        """Return authentication headers for Bitbucket API requests."""
        headers: Dict[str, str] = {}

        if self.bitbucket_oauth_token:
            headers["Authorization"] = f"Bearer {self.bitbucket_oauth_token}"
        elif self.bitbucket_token and not self.bitbucket_username:
            headers["Authorization"] = f"Bearer {self.bitbucket_token}"

        return headers

    def get_auth(self) -> Optional[tuple]:
        """Return auth tuple for Bitbucket Cloud Basic Auth if username/token are configured."""
        if self.bitbucket_oauth_token:
            return None

        if self.bitbucket_username and (self.bitbucket_token or self.bitbucket_app_password):
            return (self.bitbucket_username, self.bitbucket_token or self.bitbucket_app_password)

        return None

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Bitbucket webhook signature."""
        if not self.webhook_secret:
            return True  # Skip verification if no secret configured

        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Bitbucket sends signature as "sha256=hexdigest"
        if signature.startswith("sha256="):
            return signature[7:] == expected_signature
        else:
            return signature == expected_signature

        return hmac.compare_digest(f"sha256={expected_signature}", signature)

    async def handle_pull_request_event(self, payload: BitbucketWebhookPayload, event_key: str = None) -> None:
        """Handle Bitbucket pull request events."""
        logger.info(f"Received event: {event_key}")

        event_actions = [
            "pullrequest:created",
            "pullrequest:updated",
            "pullrequest:reopened"
        ]

        if event_key not in event_actions:
            logger.info(f"Ignoring event {event_key}")
            return

        pr = payload.pullrequest
        if not pr:
            logger.info(f"No pullrequest data in payload for event {event_key}")
            return

        repo = payload.repository
        logger.info(f"Repository data: {repo}")
        workspace = repo.get("workspace", {}).get("slug") or repo.get("owner", {}).get("username")
        repo_slug = repo.get("slug") or repo.get("name", "unknown")
        pr_id = pr["id"]
        destination_branch = pr.get("destination", {}).get("branch", {}).get("name", "master")

        logger.info(f"Processing PR #{pr_id} in {workspace}/{repo_slug}")

        # Emit review started event
        if self.kafka_handler:
            try:
                self.kafka_handler.create_review_event(
                    pr_id=pr_id,
                    repository=f"{workspace}/{repo_slug}",
                    event_type="review:started"
                )
                logger.info(f"Emitted review:started event for PR#{pr_id}")
            except Exception as e:
                logger.warning(f"Failed to emit review:started event: {str(e)}")

        try:
            # Get PR diff
            logger.info(f"Getting diff for PR #{pr_id}")
            diff_content = self.get_pull_request_diff(workspace, repo_slug, pr_id)
            if not diff_content:
                logger.warning(f"No diff content for PR #{pr_id}")
                return
            logger.info(f"Got diff content, length: {len(diff_content)}")

            # Get all files in PR (for comprehensive review)
            logger.info(f"Getting PR files for PR #{pr_id}")
            pr_files = self.get_pull_request_files(workspace, repo_slug, pr_id)
            logger.info(f"Got {len(pr_files)} files in PR")

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
            logger.info(f"Calling AI review engine for PR #{pr_id}")
            review_response = await self.call_review_engine(review_request)
            logger.info(f"AI review completed for PR #{pr_id}")

            # Emit analysis complete event
            summary = review_response.get("summary", {})
            has_critical = summary.get("critical_issues", 0) > 0
            if self.kafka_handler:
                try:
                    self.kafka_handler.create_analysis_complete_event(
                        pr_id=pr_id,
                        repository=f"{workspace}/{repo_slug}",
                        analysis_complete=True,
                        has_critical_issues=has_critical,
                        summary=summary
                    )
                    logger.info(f"Emitted review:analysis_complete event for PR#{pr_id}")
                except Exception as e:
                    logger.warning(f"Failed to emit analysis_complete event: {str(e)}")

            # Emit security issue events for critical/high issues
            if self.kafka_handler:
                for file_review in review_response.get("files", []):
                    for comment in file_review.get("comments", []):
                        if comment.get("category") == "security" and comment.get("severity") in ["critical", "high"]:
                            try:
                                self.kafka_handler.create_security_issue_event(
                                    pr_id=pr_id,
                                    repository=f"{workspace}/{repo_slug}",
                                    file_path=file_review.get("file_path"),
                                    severity=comment.get("severity"),
                                    title=comment.get("title"),
                                    description=comment.get("description", "")
                                )
                            except Exception as e:
                                logger.warning(f"Failed to emit security event: {str(e)}")

            # Post review comments to Bitbucket
            logger.info(f"Posting review comments for PR #{pr_id}")
            await self.post_review_comments(workspace, repo_slug, pr_id, review_response)
            logger.info(f"Review comments posted for PR #{pr_id}")

            # Post review summary
            logger.info(f"Posting review summary for PR #{pr_id}")
            await self.post_review_summary(workspace, repo_slug, pr_id, review_response)
            logger.info(f"Review summary posted for PR #{pr_id}")

            # Emit approval ready event (if destination is master or sit and no critical issues)
            if self.kafka_handler and destination_branch.lower() in ["master", "sit"] and not has_critical:
                try:
                    self.kafka_handler.create_approval_ready_event(
                        pr_id=pr_id,
                        repository=f"{workspace}/{repo_slug}",
                        destination_branch=destination_branch,
                        reviewer_comments=f"Analysis complete. Overall score: {summary.get('overall_score', 0)}/100"
                    )
                    logger.info(f"Emitted review:approval_ready event for PR#{pr_id}")
                except Exception as e:
                    logger.warning(f"Failed to emit approval_ready event: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing PR #{pr_id}: {str(e)}")
            # Emit failure event
            if self.kafka_handler:
                try:
                    self.kafka_handler.create_review_event(
                        pr_id=pr_id,
                        repository=f"{workspace}/{repo_slug}",
                        event_type="review:failed"
                    )
                except Exception as ex:
                    logger.warning(f"Failed to emit review:failed event: {str(ex)}")

    def get_pull_request_diff(self, workspace: str, repo_slug: str, pr_id: int) -> Optional[str]:
        """Get diff content from Bitbucket PR."""
        url = f"{self.api_base}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diff"
        headers = self.get_auth_headers()
        auth = self.get_auth()

        response = requests.get(url, headers=headers, auth=auth)
        if response.status_code == 200:
            return response.text
        else:
            message = response.text.strip() or response.reason
            logger.error(
                f"Failed to get PR diff: {response.status_code} (workspace={workspace} repo={repo_slug} pr={pr_id}) - {message}"
            )
            if response.status_code == 401:
                logger.error(
                    "Authentication failure when fetching PR diff. "
                    "Check BITBUCKET_USERNAME, BITBUCKET_TOKEN, BITBUCKET_APP_PASSWORD, BITBUCKET_OAUTH_TOKEN, and BITBUCKET_SERVER_TOKEN."
                )
            return None

    def get_pull_request_files(self, workspace: str, repo_slug: str, pr_id: int) -> List[str]:
        """Get all files changed in the PR."""
        url = f"{self.api_base}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diffstat"
        headers = self.get_auth_headers()
        auth = self.get_auth()

        try:
            response = requests.get(url, headers=headers, auth=auth)
            if response.status_code == 200:
                data = response.json()
                return [item["new"]["path"] for item in data.get("values", []) if item.get("new")]
            else:
                message = response.text.strip() or response.reason
                logger.warning(
                    f"Failed to get PR files: {response.status_code} (workspace={workspace} repo={repo_slug} pr={pr_id}) - {message}"
                )
                if response.status_code == 401:
                    logger.error(
                        "Authentication failure when fetching PR files. "
                        "Check Bitbucket credentials and permissions."
                    )
                return []
        except Exception as e:
            logger.error(f"Error getting PR files: {str(e)}")
            return []

    async def call_review_engine(self, review_request: Dict[str, Any]) -> Dict[str, Any]:
        """Call the AI review engine directly."""
        try:
            # Import the AI review engine
            from services.ai_review import analyze_code_diff
            from models.review import CodeReviewRequest

            # Convert the request dict to CodeReviewRequest model
            code_review_request = CodeReviewRequest(**review_request)

            # Call the AI review engine directly
            result = analyze_code_diff(code_review_request)

            # Convert the result back to dict for compatibility
            return result.dict()

        except Exception as e:
            logger.error(f"Error calling AI review engine: {str(e)}")
            raise Exception(f"AI review engine error: {str(e)}")

    async def post_review_comments(self, workspace: str, repo_slug: str, pr_id: int, review_response: Dict[str, Any]) -> None:
        """Post individual review comments to Bitbucket PR."""
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"
        auth = self.get_auth()

        for file_review in review_response.get("files", []):
            for comment in file_review.get("comments", []):
                # Post comments for issues that have inline suggestions or are high severity
                has_inline_suggestion = bool(comment.get("inline_suggestion"))
                is_significant = comment.get("severity") in ["critical", "high", "medium"]

                if has_inline_suggestion or is_significant:
                    # Create review comment
                    comment_data = {
                        "content": {
                            "raw": self.format_comment_body(comment, file_review["file_path"])
                        },
                        "inline": {
                            "path": file_review["file_path"],
                            "from": comment.get("location", {}).get("line_start"),
                            "to": comment.get("location", {}).get("line_end", comment.get("location", {}).get("line_start"))
                        }
                    }

                    url = f"{self.api_base}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
                    response = requests.post(url, json=comment_data, headers=headers, auth=auth)

                    if response.status_code not in [201, 200]:
                        logger.error(f"Failed to post comment: {response.status_code}")

    async def post_review_summary(self, workspace: str, repo_slug: str, pr_id: int, review_response: Dict[str, Any]) -> None:
        """Post overall review summary as a comment."""
        summary = review_response.get("summary", {})
        overall_feedback = review_response.get("overall_feedback", "")
        recommendations = review_response.get("recommendations", [])

        # Calculate security metrics across all files
        total_security_score = 0
        total_vulnerabilities = 0
        file_count = 0
        analysis_errors = 0

        for file_review in review_response.get("files", []):
            metrics = file_review.get("metrics", {})
            if "security_score" in metrics:
                # Only count files that were actually analyzed
                if metrics.get("analysis_error"):
                    analysis_errors += 1
                else:
                    total_security_score += metrics["security_score"]
                    total_vulnerabilities += metrics.get("vulnerability_count", 0)
                    file_count += 1

        avg_security_score = total_security_score / file_count if file_count > 0 else 0

        # Security status indicator
        if analysis_errors > 0:
            security_status = "❌ Analysis Failed"
        elif avg_security_score >= 90:
            security_status = "🛡️ Secure"
        elif avg_security_score >= 70:
            security_status = "⚠️ Needs Attention"
        else:
            security_status = "🚨 Critical Issues"

        body = f"""## 🤖 AI Code Review Summary

**Overall Score:** {summary.get('overall_score', 0)}/100
**Security Score:** {avg_security_score:.1f}/100 ({security_status})

### Issues Found:
- 🔴 Critical: {summary.get('critical_issues', 0)}
- 🟠 High: {summary.get('high_issues', 0)}
- 🟡 Medium: {summary.get('medium_issues', 0)}
- 🟢 Low: {summary.get('low_issues', 0)}
- ℹ️ Info: {summary.get('info_suggestions', 0)}

### Security Analysis:
- **Total Vulnerabilities:** {total_vulnerabilities}
- **Files Analyzed:** {file_count}
- **Analysis Errors:** {analysis_errors}
- **Average Security Score:** {avg_security_score:.1f}/100

### Feedback:
{overall_feedback}

### Recommendations:
""" + "\n".join(f"- {rec}" for rec in recommendations)

        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"
        auth = self.get_auth()

        comment_data = {
            "content": {
                "raw": body
            }
        }

        url = f"{self.api_base}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
        response = requests.post(url, json=comment_data, headers=headers, auth=auth)

        if response.status_code not in [201, 200]:
            logger.error(f"Failed to post summary: {response.status_code}")

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        if not file_path:
            return 'text'

        ext_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.java': 'java',
            '.cpp': 'cpp', '.c': 'c', '.go': 'go', '.rs': 'rust', '.php': 'php',
            '.rb': 'ruby', '.cs': 'csharp', '.swift': 'swift', '.kt': 'kotlin',
            '.scala': 'scala', '.sh': 'bash', '.ps1': 'powershell', '.html': 'html',
            '.css': 'css', '.sql': 'sql', '.json': 'json', '.xml': 'xml', '.yaml': 'yaml'
        }

        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return 'text'

    def format_comment_body(self, comment: Dict[str, Any], file_path: str = None) -> str:
        """Format a review comment for Bitbucket with professional security-focused layout."""
        severity_emojis = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
            "info": "ℹ️"
        }

        emoji = severity_emojis.get(comment.get("severity", "info"), "ℹ️")
        category = comment.get("category", "general").replace("_", " ").title()
        title = comment.get('title', 'Review Comment')

        # Detect language for code block syntax highlighting
        language = self._detect_language(file_path) if file_path else "python"

        # Build professional comment body
        body_parts = []

        # Header with severity and title
        body_parts.append(f"### {emoji} {title}")

        # Severity and category
        body_parts.append(f"**Severity:** {comment.get('severity', 'info').upper()}")
        body_parts.append(f"**Category:** {category}")

        # Location if available
        if comment.get('location') and comment['location'].get('line_start'):
            loc = comment['location']
            line_info = f"{file_path}:{loc['line_start']}"
            if loc.get('line_end') and loc['line_end'] != loc['line_start']:
                line_info += f"-{loc['line_end']}"
            body_parts.append(f"**File + line:** {line_info}")

        # Rule ID if available (for security issues)
        if comment.get('rule_id'):
            body_parts.append(f"**Rule ID:** {comment['rule_id']}")

        # Description
        if comment.get('description'):
            body_parts.append("")
            body_parts.append(comment['description'])

        # Impact (for security issues)
        if comment.get('impact'):
            body_parts.append("")
            body_parts.append(f"**Impact:** {comment['impact']}")

        # Suggestion
        if comment.get('suggestion'):
            body_parts.append("")
            body_parts.append(f"**Suggestion:** {comment['suggestion']}")

        # Changed lines diff (showing before/after)
        if comment.get('changed_lines_diff') or comment.get('original_code'):
            body_parts.append("")
            body_parts.append("**Changed Lines (Diff):**")
            diff_content = comment.get('changed_lines_diff') or comment.get('original_code')
            body_parts.append(f"```diff\n{diff_content}\n```")

        # Inline suggestion (diff format)
        if comment.get('inline_suggestion'):
            body_parts.append("")
            body_parts.append("**Suggested fix:**")
            body_parts.append(f"```diff\n{comment['inline_suggestion']}\n```")

        # Code example
        if comment.get('code_example'):
            body_parts.append("")
            body_parts.append("**Example:**")
            code_example = comment['code_example'].replace('```python', f'```{language}')
            body_parts.append(code_example)

        # Minimal test
        if comment.get('minimal_test'):
            body_parts.append("")
            body_parts.append("**Minimal test:**")
            minimal_test = comment['minimal_test'].replace('```python', f'```{language}')
            body_parts.append(minimal_test)

        # References
        if comment.get('references'):
            body_parts.append("")
            body_parts.append("**References:**")
            for ref in comment['references']:
                body_parts.append(f"- {ref}")

        return "\n".join(body_parts)


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