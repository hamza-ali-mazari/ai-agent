from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum


class TokenUsage(BaseModel):
    """Track token usage for API calls"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    
    def __add__(self, other):
        """Allow adding token usage together"""
        if not isinstance(other, TokenUsage):
            return NotImplemented
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens
        )


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
    changed_lines_diff: Optional[str] = None  # Diff showing the problematic lines that need fixing
    suggestion: Optional[str] = None
    inline_suggestion: Optional[str] = None  # Exact replacement code for PR suggestions
    code_example: Optional[str] = None
    minimal_test: Optional[str] = None
    references: Optional[List[str]] = None
    rule_id: Optional[str] = None  # Security rule identifier (e.g., "OWASP-A01", "CWE-89")
    impact: Optional[str] = None  # Security/business impact description
    
    # For backward compatibility
    @property
    def original_code(self) -> Optional[str]:
        """Backward compatibility property."""
        return self.changed_lines_diff


class FileReview(BaseModel):
    file_path: str
    language: Optional[str] = None
    summary: str
    comments: List[ReviewComment]
    metrics: Optional[Dict[str, Any]] = None
    tokens_used: Optional[TokenUsage] = None  # Token usage for this file's analysis


class ReviewSummary(BaseModel):
    overall_score: int  # 0-100
    total_comments: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    info_suggestions: int
    categories_breakdown: Dict[str, int]
    analysis_errors: int = 0
    # Token tracking information
    tokens_used: Optional[int] = None
    estimated_cost: Optional[str] = None  # e.g., "$0.12"

class CodeReviewRequest(BaseModel):
    diff: str
    repository_url: Optional[str] = None
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    author: Optional[str] = None
    files_changed: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    # Bitbucket project context for full repository analysis
    workspace: Optional[str] = None  # Bitbucket workspace name
    repo_slug: Optional[str] = None  # Repository slug
    analyze_full_project: Optional[bool] = False  # Whether to fetch and analyze full project context

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
                "workspace": "your-workspace",
                "repo_slug": "your-repo",
                "analyze_full_project": True,
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
    token_usage: Optional[TokenUsage] = None  # Overall token usage for entire review
    project_impact_analysis: Optional[Dict[str, Any]] = None  # Full project context and impact analysis
    
    # New comprehensive analysis results
    test_coverage_analysis: Optional[Dict[str, Any]] = None  # Test coverage metrics and warnings
    breaking_changes_analysis: Optional[Dict[str, Any]] = None  # Breaking changes detection
    complexity_analysis: Optional[Dict[str, Any]] = None  # Code complexity metrics
    performance_analysis: Optional[Dict[str, Any]] = None  # Performance antipatterns
    migration_analysis: Optional[Dict[str, Any]] = None  # Database migration analysis
    code_smells_analysis: Optional[Dict[str, Any]] = None  # Code smells and anti-patterns detection
    automated_fixes: Optional[List[Dict[str, Any]]] = None  # Automated fix code suggestions


class ReviewConfig(BaseModel):
    enabled_categories: List[ReviewCategory] = [
        ReviewCategory.SECURITY,  # Security scanning enabled by default
        ReviewCategory.BUGS,
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