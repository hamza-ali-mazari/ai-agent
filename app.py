from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
import json
import os
from typing import Optional, List, Dict, Any
import requests
from services.ai_review import AICodeReviewEngine, analyze_code_diff, CodeReviewRequest, CodeReviewResponse
from models.review import ReviewConfig
from integrations.bitbucket_integration import BitbucketIntegration, BitbucketWebhookPayload

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Code Review Engine",
    description="Professional AI-powered code review engine for GitHub and Bitbucket integrations",
    version="2.0.0"
)

# Initialize integrations
bitbucket_integration = BitbucketIntegration()

@app.on_event("startup")
async def startup_health_check():
    """Validate Azure OpenAI connectivity when the app starts."""
    app.state.azure_openai_available = False
    app.state.azure_openai_health_message = "Not checked"

    logger.info("Performing Azure OpenAI startup health check")
    try:
        engine = AICodeReviewEngine()
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        if not deployment:
            raise ValueError("AZURE_OPENAI_DEPLOYMENT is not configured")

        # Validate Azure OpenAI access and deployment availability
        response = engine.client.chat.completions.create(
            model=deployment,
            messages=[{"role": "system", "content": "Health check."}],
            temperature=0.0,
            max_tokens=1
        )

        if not response or not getattr(response, 'choices', None):
            raise RuntimeError("Azure OpenAI returned an empty response")

        app.state.azure_openai_available = True
        app.state.azure_openai_health_message = "Azure OpenAI is available"
        logger.info("Azure OpenAI startup health check succeeded")
    except Exception as exc:
        app.state.azure_openai_available = False
        app.state.azure_openai_health_message = str(exc)
        logger.error(f"Azure OpenAI startup health check failed: {exc}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    azure_ok = getattr(app.state, "azure_openai_available", False)
    status_code = 200 if azure_ok else 503
    status = "healthy" if azure_ok else "degraded"
    return JSONResponse(status_code=status_code, content={
        "status": status,
        "version": "2.0.0",
        "azure_openai_available": azure_ok,
        "azure_openai_health_message": app.state.azure_openai_health_message
    })

class ReviewRequest(BaseModel):
    diff: str
    repository_url: Optional[str] = None
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    author: Optional[str] = None
    files_changed: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "diff": """diff --git a/example.py b/example.py
index 1234567..abcdef0 100644
--- a/example.py
+++ b/example.py
@@ -1,3 +1,5 @@
+def hello():
+    print('Hello World')
+
 def goodbye():
-    print('Goodbye')
+    print('Goodbye World')""",
                "repository_url": "https://github.com/user/repo",
                "branch": "feature/new-feature",
                "commit_sha": "abcdef0123456789",
                "author": "developer@example.com",
                "files_changed": ["example.py"],
                "config": {
                    "enabled_categories": ["bugs", "security", "performance"],
                    "severity_threshold": "low"
                }
            }
        }
    }

class LegacyReviewRequest(BaseModel):
    diff: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "diff": "+ def hello():\n+     print('Hello World')\n- def goodbye():\n-     print('Goodbye')"
            }
        }
    }

@app.post("/review", response_model=CodeReviewResponse, responses={
    200: {"description": "Successful code review"},
    400: {"description": "Bad request - empty diff"},
    500: {"description": "Internal server error"}
})
async def review_code(request: ReviewRequest):
    """
    Perform comprehensive AI-powered code review.

    Returns structured analysis with file-by-file breakdown, severity levels,
    and actionable recommendations.
    """
    try:
        if not getattr(app.state, "azure_openai_available", False):
            raise HTTPException(
                status_code=503,
                detail=f"Azure OpenAI unavailable: {app.state.azure_openai_health_message}"
            )

        logger.info("Received code review request")
        if not request.diff.strip():
            raise HTTPException(status_code=400, detail="Diff cannot be empty")

        review_request = CodeReviewRequest(**request.dict())
        result = analyze_code_diff(review_request)

        logger.info(f"Code review completed successfully - {result.summary.total_comments} comments generated")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in review_code: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/review/legacy", response_model=dict, responses={
    200: {"description": "Successful code review (legacy format)"},
    400: {"description": "Bad request - empty diff"},
    500: {"description": "Internal server error"}
})
async def review_code_legacy(request: LegacyReviewRequest):
    """
    Legacy endpoint for backward compatibility.

    Returns simple text-based review (deprecated - use /review instead).
    """
    try:
        if not getattr(app.state, "azure_openai_available", False):
            raise HTTPException(
                status_code=503,
                detail=f"Azure OpenAI unavailable: {app.state.azure_openai_health_message}"
            )

        logger.info("Received legacy code review request")
        if not request.diff.strip():
            raise HTTPException(status_code=400, detail="Diff cannot be empty")

        # Convert to new format
        review_request = CodeReviewRequest(diff=request.diff)
        result = analyze_code_diff(review_request)

        # Convert to legacy format
        legacy_response = {
            "review": result.overall_feedback,
            "details": {
                "score": result.summary.overall_score,
                "total_comments": result.summary.total_comments,
                "critical_issues": result.summary.critical_issues,
                "high_issues": result.summary.high_issues
            }
        }

        logger.info("Legacy code review completed successfully")
        return legacy_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in review_code_legacy: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/review/repository/github", response_model=CodeReviewResponse, responses={
    200: {"description": "Successful repository review"},
    400: {"description": "Bad request"},
    500: {"description": "Internal server error"}
})
async def review_github_repository(request: dict):
    """
    Review all code files in a GitHub repository.
    
    - **repo_full_name**: GitHub repository in format "owner/repo"
    - **branch**: Branch to review (default: "main")
    """
    try:
        if not getattr(app.state, "azure_openai_available", False):
            raise HTTPException(
                status_code=503,
                detail=f"Azure OpenAI unavailable: {app.state.azure_openai_health_message}"
            )

        from integrations.github_integration import GitHubIntegration
        github_integration = GitHubIntegration()

        repo_full_name = request.get("repo_full_name")
        branch = request.get("branch", "main")

        if not repo_full_name:
            raise HTTPException(status_code=400, detail="repo_full_name is required")

        logger.info(f"Starting repository review for {repo_full_name}:{branch}")
        result = await github_integration.review_entire_repository(repo_full_name, branch)

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        logger.info(f"Repository review completed for {repo_full_name}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in repository review: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/webhook/bitbucket")
async def bitbucket_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """Handle Bitbucket webhooks."""
    # Get raw payload
    payload = await request.body()

    # Verify signature if configured
    signature = request.headers.get("X-Hub-Signature-256")
    if signature and not bitbucket_integration.verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        data = json.loads(payload.decode('utf-8'))
        logger.info(f"Webhook payload keys: {list(data.keys())}")
        webhook_payload = BitbucketWebhookPayload(**data)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    # Get event key from header
    event_key = request.headers.get("X-Event-Key")
    logger.info(f"Event key from header: {event_key}")

    if not getattr(app.state, "azure_openai_available", False):
        raise HTTPException(
            status_code=503,
            detail=f"Azure OpenAI unavailable: {app.state.azure_openai_health_message}"
        )

    # Handle the event in background
    background_tasks.add_task(
        bitbucket_integration.handle_pull_request_event,
        webhook_payload, event_key
    )

    return {"status": "accepted"}