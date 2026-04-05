from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum


class ReviewSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReviewCategory(str, Enum):
    BUGS = "bugs"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    STYLE = "style"
    BEST_PRACTICES = "best_practices"
    TESTING = "testing"
    DOCUMENTATION = "documentation"


class CodeLocation(BaseModel):
    file_path: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    column_start: Optional[int] = None
    column_end: Optional[int] = None


class ReviewComment(BaseModel):
    id: str
    category: ReviewCategory
    severity: ReviewSeverity
    title: str
    description: str
    location: Optional[CodeLocation] = None
    suggestion: Optional[str] = None
    inline_suggestion: Optional[str] = None  # Exact replacement code for PR suggestions
    code_example: Optional[str] = None
    minimal_test: Optional[str] = None
    references: Optional[List[str]] = None


class FileReview(BaseModel):
    file_path: str
    language: Optional[str] = None
    summary: str
    comments: List[ReviewComment]
    metrics: Optional[Dict[str, Any]] = None


class ReviewSummary(BaseModel):
    overall_score: int  # 0-100
    total_comments: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    info_suggestions: int
    categories_breakdown: Dict[str, int]


class CodeReviewRequest(BaseModel):
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


class CodeReviewResponse(BaseModel):
    review_id: str
    summary: ReviewSummary
    files: List[FileReview]
    overall_feedback: str
    recommendations: List[str]
    metadata: Optional[Dict[str, Any]] = None


class ReviewConfig(BaseModel):
    enabled_categories: List[ReviewCategory] = [
        ReviewCategory.BUGS,
        ReviewCategory.SECURITY,
        ReviewCategory.PERFORMANCE,
        ReviewCategory.MAINTAINABILITY,
        ReviewCategory.STYLE,
        ReviewCategory.BEST_PRACTICES
    ]
    severity_threshold: ReviewSeverity = ReviewSeverity.INFO
    max_comments_per_file: int = 10
    include_code_examples: bool = True
    language_specific_rules: Optional[Dict[str, Dict[str, Any]]] = None
    custom_rules: Optional[List[Dict[str, Any]]] = None