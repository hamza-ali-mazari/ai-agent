"""
GitHub Integration Example for AI Code Review Engine

This module demonstrates how to integrate the AI Code Review Engine
with GitHub webhooks and API for automated pull request reviews.
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

class GitHubWebhookPayload(BaseModel):
    action: str
    pull_request: Optional[Dict[str, Any]] = None
    repository: Dict[str, Any]
    sender: Dict[str, Any]

class GitHubIntegration:
    """GitHub integration for AI Code Review Engine."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET")

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature."""
        if not self.webhook_secret:
            return True  # Skip verification if no secret configured

        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(f"sha256={expected_signature}", signature)

    async def handle_pull_request_event(self, payload: GitHubWebhookPayload) -> None:
        """Handle GitHub pull request events."""
        if payload.action not in ["opened", "synchronize", "reopened"]:
            return

        pr = payload.pull_request
        if not pr:
            return

        repo_full_name = payload.repository["full_name"]
        pr_number = pr["number"]

        logger.info(f"Processing PR #{pr_number} in {repo_full_name}")

        try:
            # Get PR diff
            diff_content = self.get_pull_request_diff(repo_full_name, pr_number)
            if not diff_content:
                logger.warning(f"No diff content for PR #{pr_number}")
                return

            # Get all files changed in PR for comprehensive analysis
            pr_files = self.get_pull_request_files(repo_full_name, pr_number)

            # Get file contents for deeper analysis (optional - can be expensive)
            file_contents = {}
            if os.getenv("GITHUB_DEEP_ANALYSIS", "false").lower() == "true":
                file_contents = await self.get_pr_file_contents(repo_full_name, pr_number, pr_files)

            # Prepare review request
            review_request = {
                "diff": diff_content,
                "repository_url": payload.repository["html_url"],
                "branch": pr["head"]["ref"],
                "commit_sha": pr["head"]["sha"],
                "author": pr["user"]["login"],
                "files_changed": pr_files,
                "config": {
                    "enabled_categories": ["bugs", "security", "performance", "maintainability", "style", "best_practices"],
                    "severity_threshold": "low",
                    "max_comments_per_file": 5,
                    "include_code_examples": True
                }
            }

            # Add file contents if deep analysis is enabled
            if file_contents:
                review_request["file_contents"] = file_contents

            # Call AI review engine
            review_response = await self.call_review_engine(review_request)

            # Post review comments to GitHub
            await self.post_review_comments(repo_full_name, pr_number, review_response)

            # Post overall review summary
            await self.post_review_summary(repo_full_name, pr_number, review_response)

        except Exception as e:
            logger.error(f"Error processing PR #{pr_number}: {str(e)}")

    def get_pull_request_files(self, repo_full_name: str, pr_number: int) -> List[str]:
        """Get all files changed in the PR."""
        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/files"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                files_data = response.json()
                return [file["filename"] for file in files_data]
            else:
                logger.warning(f"Failed to get PR files: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting PR files: {str(e)}")
            return []

    async def get_pr_file_contents(self, repo_full_name: str, pr_number: int, file_paths: List[str]) -> Dict[str, str]:
        """Get contents of files changed in PR for deeper analysis."""
        file_contents = {}
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        # Limit to first 10 files to avoid API limits
        for file_path in file_paths[:10]:
            try:
                # Get file content from the PR head commit
                url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}"
                params = {"ref": f"refs/pull/{pr_number}/head"}
                response = requests.get(url, headers=headers, params=params)

                if response.status_code == 200:
                    file_data = response.json()
                    if file_data.get("type") == "file" and file_data.get("content"):
                        import base64
                        content = base64.b64decode(file_data["content"]).decode("utf-8")
                        file_contents[file_path] = content
                else:
                    logger.debug(f"Could not get content for {file_path}: {response.status_code}")

            except Exception as e:
                logger.debug(f"Error getting content for {file_path}: {str(e)}")

        return file_contents

    async def review_entire_repository(self, repo_full_name: str, branch: str = "main") -> Dict[str, Any]:
        """Review all code files in an entire repository."""
        logger.info(f"Starting comprehensive review of {repo_full_name}")

        try:
            # Get all code files in repository
            all_files = await self.get_repository_files(repo_full_name, branch)

            # Filter to code files only
            code_files = [f for f in all_files if self._is_code_file(f)]

            # Get contents of code files (limit to reasonable number)
            file_contents = {}
            for file_path in code_files[:50]:  # Limit to 50 files for performance
                try:
                    content = await self.get_file_content(repo_full_name, file_path, branch)
                    if content:
                        file_contents[file_path] = content
                except Exception as e:
                    logger.debug(f"Error getting content for {file_path}: {str(e)}")

            # Create a synthetic diff from all files
            synthetic_diff = self._create_synthetic_diff(file_contents)

            # Prepare review request
            review_request = {
                "diff": synthetic_diff,
                "repository_url": f"https://github.com/{repo_full_name}",
                "branch": branch,
                "files_changed": list(file_contents.keys()),
                "config": {
                    "enabled_categories": ["bugs", "security", "performance", "maintainability", "style", "best_practices"],
                    "severity_threshold": "info",
                    "max_comments_per_file": 3,  # Fewer comments per file for repo review
                    "include_code_examples": True
                }
            }

            # Call AI review engine
            review_response = await self.call_review_engine(review_request)

            return review_response

        except Exception as e:
            logger.error(f"Error reviewing repository {repo_full_name}: {str(e)}")
            return {"error": str(e)}

    async def get_repository_files(self, repo_full_name: str, branch: str = "main") -> List[str]:
        """Get all files in a repository."""
        url = f"https://api.github.com/repos/{repo_full_name}/git/trees/{branch}"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        params = {"recursive": "true"}

        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                tree_data = response.json()
                return [item["path"] for item in tree_data.get("tree", []) if item["type"] == "blob"]
            else:
                logger.error(f"Failed to get repository files: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting repository files: {str(e)}")
            return []

    def _is_code_file(self, file_path: str) -> bool:
        """Check if a file is a code file that should be reviewed."""
        code_extensions = {
            '.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.php', '.rb',
            '.go', '.rs', '.swift', '.kt', '.scala', '.clj', '.hs', '.ml'
        }
        return any(file_path.endswith(ext) for ext in code_extensions)

    async def get_file_content(self, repo_full_name: str, file_path: str, branch: str = "main") -> Optional[str]:
        """Get content of a specific file."""
        url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        params = {"ref": branch}

        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                file_data = response.json()
                if file_data.get("type") == "file" and file_data.get("content"):
                    import base64
                    return base64.b64decode(file_data["content"]).decode("utf-8")
            return None
        except Exception as e:
            logger.debug(f"Error getting file content: {str(e)}")
            return None

    def _create_synthetic_diff(self, file_contents: Dict[str, str]) -> str:
        """Create a synthetic diff from file contents for repository review."""
        diff_lines = []

        for file_path, content in file_contents.items():
            diff_lines.extend([
                f"diff --git a/{file_path} b/{file_path}",
                f"index 0000000..0000000 100644",
                f"--- a/{file_path}",
                f"+++ b/{file_path}",
            ])

            # Add file content as additions
            for i, line in enumerate(content.split('\n'), 1):
                diff_lines.append(f"+{line}")

        return '\n'.join(diff_lines)

    def get_pull_request_diff(self, repo_full_name: str, pr_number: int) -> Optional[str]:
        """Get diff content from GitHub PR."""
        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3.diff"
        }

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        else:
            logger.error(f"Failed to get PR diff: {response.status_code}")
            return None

    async def call_review_engine(self, review_request: Dict[str, Any]) -> Dict[str, Any]:
        """Call the AI review engine API."""
        url = f"{self.base_url}/review"
        response = requests.post(url, json=review_request)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Review engine error: {response.status_code}")

    async def post_review_comments(self, repo_full_name: str, pr_number: int, review_response: Dict[str, Any]) -> None:
        """Post individual review comments to GitHub PR."""
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        for file_review in review_response.get("files", []):
            for comment in file_review.get("comments", []):
                # Post comments for issues that have inline suggestions or are high severity
                has_inline_suggestion = bool(comment.get("inline_suggestion"))
                is_significant = comment.get("severity") in ["critical", "high", "medium"]

                if has_inline_suggestion or is_significant:
                    # Create review comment
                    comment_data = {
                        "body": self.format_comment_body(comment, file_review["file_path"]),
                        "path": file_review["file_path"],
                        "line": comment.get("location", {}).get("line_start"),
                        "side": "RIGHT"
                    }

                    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/comments"
                    response = requests.post(url, json=comment_data, headers=headers)

                    if response.status_code not in [201, 200]:
                        logger.error(f"Failed to post comment: {response.status_code}")

    async def post_review_summary(self, repo_full_name: str, pr_number: int, review_response: Dict[str, Any]) -> None:
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

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        comment_data = {"body": body}
        url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"

        response = requests.post(url, json=comment_data, headers=headers)
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
        """Format a review comment for GitHub with inline suggestions."""
        severity_emojis = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
            "info": "ℹ️"
        }

        emoji = severity_emojis.get(comment.get("severity", "info"), "ℹ️")
        category = comment.get("category", "general").replace("_", " ").title()

        # Detect language for code block syntax highlighting
        language = self._detect_language(file_path) if file_path else "python"

        body = f"""**{emoji} {comment.get('title', 'Review Comment')}**

**Category:** {category}
**Severity:** {comment.get('severity', 'info').title()}

{comment.get('description', '')}

"""

        if comment.get('suggestion'):
            body += f"**Suggestion:** {comment['suggestion']}\n\n"

        # Add inline suggestion if available
        if comment.get('inline_suggestion'):
            body += f"```suggestion\n{comment['inline_suggestion']}\n```\n\n"

        if comment.get('code_example') and not comment.get('inline_suggestion'):
            # Replace the generic python code block with the detected language
            code_example = comment['code_example'].replace('```python', f'```{language}')
            body += f"**Example:**\n{code_example}\n"

        return body


# FastAPI integration example
github_app = FastAPI()
github_integration = GitHubIntegration()

@github_app.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """Handle GitHub webhooks."""
    # Get raw payload
    payload = await request.body()

    # Verify signature if configured
    signature = request.headers.get("X-Hub-Signature-256")
    if signature and not github_integration.verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        data = json.loads(payload)
        webhook_payload = GitHubWebhookPayload(**data)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    # Handle the event in background
    background_tasks.add_task(
        github_integration.handle_pull_request_event,
        webhook_payload
    )

    return {"status": "accepted"}


if __name__ == "__main__":
    # Example usage
    import uvicorn

    # Set environment variables
    os.environ["GITHUB_TOKEN"] = "your_github_token"
    os.environ["GITHUB_WEBHOOK_SECRET"] = "your_webhook_secret"

    uvicorn.run(github_app, host="0.0.0.0", port=8001)