from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import logging
import json
import os
from typing import Optional, List, Dict, Any
import requests
from services.ai_review import AICodeReviewEngine, analyze_code_diff, CodeReviewRequest, CodeReviewResponse
from services.kafka_config import KafkaConfigHandler
from services.token_tracker import token_tracker
from services.chatbot_service import chatbot_service
from models.review import ReviewConfig
from integrations.bitbucket_integration import BitbucketIntegration, BitbucketWebhookPayload

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Code Review Engine",
    description="Professional AI-powered code review engine for Bitbucket with Kafka-driven event architecture and deep dependency analysis",
    version="2.0.0"
)

# Initialize integrations and services
kafka_handler = KafkaConfigHandler()
bitbucket_integration = BitbucketIntegration(kafka_handler=kafka_handler)

@app.on_event("startup")
async def startup_health_check():
    """Validate Azure OpenAI connectivity when the app starts."""
    app.state.azure_openai_available = False
    app.state.azure_openai_health_message = "Not checked"

    # Skip health check in testing environment
    if os.getenv("TESTING", "").lower() in ("true", "1", "yes"):
        app.state.azure_openai_available = True
        app.state.azure_openai_health_message = "Skipped during testing"
        logger.info("Azure OpenAI health check skipped during testing")
        return

    logger.info("Performing Azure OpenAI startup health check")
    try:
        engine = AICodeReviewEngine()
        model_name = engine.model
        if not model_name:
            raise ValueError("AZURE_OPENAI_MODEL or AZURE_OPENAI_DEPLOYMENT is not configured")

        # Validate Azure OpenAI access and deployment availability
        response = engine.client.chat.completions.create(
            model=model_name,
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
    # In testing environment, always return healthy
    if os.getenv("TESTING", "").lower() in ("true", "1", "yes"):
        return JSONResponse(status_code=200, content={
            "status": "healthy",
            "version": "2.0.0",
            "azure_openai_available": True,
            "azure_openai_health_message": "Skipped during testing"
        })

    azure_ok = getattr(app.state, "azure_openai_available", False)
    health_msg = getattr(app.state, "azure_openai_health_message", "Not checked")
    status_code = 200 if azure_ok else 503
    status = "healthy" if azure_ok else "degraded"
    return JSONResponse(status_code=status_code, content={
        "status": status,
        "version": "2.0.0",
        "azure_openai_available": azure_ok,
        "azure_openai_health_message": health_msg
    })

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "AI Code Review Engine API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "chat_ui": "/chat",
        "endpoints": {
            "review": "/review",
            "legacy_review": "/review/legacy",
            "webhook": "/webhook/bitbucket",
            "approval": "/bitbucket/approval/{workspace}/{repo_slug}/{pr_id}",
            "token_stats": "/stats/tokens",
            "token_report": "/stats/tokens/report",
            "chat": "/chat/{review_id}",
            "chat_history": "/chat/{review_id}/history",
            "chat_ui": "/chat (HTML interface)"
        }
    }

@app.get("/chat")
async def chat_ui():
    """Serve the interactive chat UI for code review chatbot"""
    chat_ui_path = os.path.join(os.path.dirname(__file__), "chat_ui.html")
    if os.path.exists(chat_ui_path):
        return FileResponse(chat_ui_path, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="Chat UI not found")

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
                "repository_url": "https://bitbucket.org/workspace/repo",
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
        # Validate request first before checking service availability
        logger.info("Received code review request")
        if not request.diff.strip():
            raise HTTPException(status_code=400, detail="Diff cannot be empty")

        # Then check service availability (skip in testing)
        if not os.getenv("TESTING", "").lower() in ("true", "1", "yes"):
            if not getattr(app.state, "azure_openai_available", False):
                health_msg = getattr(app.state, "azure_openai_health_message", "Unknown error")
                raise HTTPException(
                    status_code=503,
                    detail=f"Azure OpenAI unavailable: {health_msg}"
                )

        review_request = CodeReviewRequest(**request.dict())
        result = analyze_code_diff(review_request)

        # Track token usage
        token_tracker.record_analysis(result)
        
        # Log token usage report
        token_report = token_tracker.format_analysis_report(result)
        logger.info(token_report)
        
        # Log cumulative stats (every 10 analyses)
        cumulative_stats = token_tracker.get_cumulative_stats()
        if cumulative_stats['analyses_count'] % 10 == 0:
            cumulative_report = token_tracker.format_cumulative_report()
            logger.info(cumulative_report)

        logger.info(f"Code review completed successfully - {result.summary.total_comments} comments generated")
        
        # Store review for chatbot interaction (include full files if available)
        chat_review_id = chatbot_service.store_review_for_chat(result, review_request.full_files)
        result.metadata = result.metadata or {}
        result.metadata["chat_available"] = True
        result.metadata["chat_review_id"] = chat_review_id
        
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
        # Validate request first before checking service availability
        logger.info("Received legacy code review request")
        if not request.diff.strip():
            raise HTTPException(status_code=400, detail="Diff cannot be empty")

        # Then check service availability (skip in testing)
        if not os.getenv("TESTING", "").lower() in ("true", "1", "yes"):
            if not getattr(app.state, "azure_openai_available", False):
                health_msg = getattr(app.state, "azure_openai_health_message", "Unknown error")
                raise HTTPException(
                    status_code=503,
                    detail=f"Azure OpenAI unavailable: {health_msg}"
                )

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
        health_msg = getattr(app.state, "azure_openai_health_message", "Unknown error")
        raise HTTPException(
            status_code=503,
            detail=f"Azure OpenAI unavailable: {health_msg}"
        )

    # Handle the event in background
    background_tasks.add_task(
        bitbucket_integration.handle_pull_request_event,
        webhook_payload, event_key
    )

    return {"status": "accepted"}


@app.post("/bitbucket/approval/{workspace}/{repo_slug}/{pr_id}")
async def get_approval_status(
    workspace: str,
    repo_slug: str,
    pr_id: int,
    body: Optional[dict] = None
):
    """
    Get approval and merge status for a Bitbucket PR.
    
    Approval is only allowed when:
    1. Analysis is complete
    2. No critical security issues exist
    3. Destination branch is 'master' or 'sit'
    
    Returns {can_approve, can_merge, allowed_destinations, reason}
    """
    try:
        if not getattr(app.state, "azure_openai_available", False):
            health_msg = getattr(app.state, "azure_openai_health_message", "Unknown error")
            raise HTTPException(
                status_code=503,
                detail=f"Azure OpenAI unavailable: {health_msg}"
            )

        request_body = body or {}
        analysis_complete = request_body.get("analysis_complete", False)
        has_critical_issues = request_body.get("has_critical_issues", False)
        destination_branch = request_body.get("destination_branch", "master")

        logger.info(
            f"Approval check for {workspace}/{repo_slug}#{pr_id} "
            f"(analysis_complete={analysis_complete}, has_critical={has_critical_issues}, dest_branch={destination_branch})"
        )

        # Get approval status from Kafka handler
        approval_status = kafka_handler.get_approval_status(
            pr_destination_branch=destination_branch,
            analysis_complete=analysis_complete,
            has_critical_issues=has_critical_issues
        )

        logger.info(f"Approval status for PR#{pr_id}: {approval_status}")
        return approval_status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking approval status for PR#{pr_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/stats/tokens")
async def get_token_stats():
    """
    Get cumulative token usage statistics for all analyses performed.
    
    Returns metrics including:
    - Total tokens consumed across all reviews
    - Average tokens per analysis/file/comment
    - Total number of analyses performed
    """
    try:
        stats = token_tracker.get_cumulative_stats()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        logger.error(f"Error retrieving token stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/stats/tokens/report")
async def get_token_report():
    """
    Get a formatted token usage report for all analyses.
    
    Returns a formatted text report with detailed statistics.
    """
    try:
        report = token_tracker.format_cumulative_report()
        return {
            "status": "success",
            "report": report
        }
    except Exception as e:
        logger.error(f"Error generating token report: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
@app.get("/config/default")
async def get_default_config():
    """
    Get default review configuration.
    
    Returns the default configuration used for code reviews when no custom config is provided.
    """
    default_config = {
        "enabled_categories": [
            "bugs",
            "security",
            "performance",
            "maintainability",
            "style",
            "best_practices"
        ],
        "severity_threshold": "info",
        "max_comments_per_file": 10,
        "include_code_suggestions": True,
        "include_explanations": True,
        "max_tokens_per_review": 4000,
        "timeout_seconds": 120,
        "cache_enabled": True,
        "cache_ttl_seconds": 3600
    }
    return default_config


# Chatbot endpoints
class ChatMessageRequest(BaseModel):
    message: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Can you explain the security issues in more detail?"
            }
        }
    }


@app.post("/chat/{review_id}", response_model=Dict[str, Any], responses={
    200: {"description": "Successful chatbot response"},
    404: {"description": "Review session not found"},
    500: {"description": "Internal server error"}
})
async def chat_with_review(review_id: str, request: ChatMessageRequest):
    """
    Send a message to the chatbot about a specific code review.

    The chatbot can answer questions about the review findings, provide clarifications,
    explain technical concepts, and offer additional advice.
    """
    try:
        logger.info(f"Received chat message for review: {review_id}")

        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        response = chatbot_service.send_message(review_id, request.message)

        if response is None:
            raise HTTPException(status_code=404, detail="Review session not found or expired")

        return {
            "review_id": review_id,
            "response": response,
            "status": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/chat/{review_id}/history", response_model=Dict[str, Any], responses={
    200: {"description": "Conversation history retrieved"},
    404: {"description": "Review session not found"},
    500: {"description": "Internal server error"}
})
async def get_chat_history(review_id: str):
    """
    Get the conversation history for a specific review chat session.

    Returns all messages exchanged with the chatbot for this review.
    """
    try:
        logger.info(f"Retrieving chat history for review: {review_id}")

        history = chatbot_service.get_conversation_history(review_id)

        if history is None:
            raise HTTPException(status_code=404, detail="Review session not found or expired")

        return {
            "review_id": review_id,
            "history": history,
            "message_count": len(history),
            "status": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")