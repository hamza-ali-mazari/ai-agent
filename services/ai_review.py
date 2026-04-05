import os
import json
import logging
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime
from openai import AzureOpenAI
from dotenv import load_dotenv
from models.review import (
    CodeReviewRequest,
    CodeReviewResponse,
    FileReview,
    ReviewComment,
    ReviewSummary,
    ReviewCategory,
    ReviewSeverity,
    CodeLocation,
    ReviewConfig
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Validate environment variables
required_env_vars = [
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT"
]

for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Environment variable {var} is not set")

class AICodeReviewEngine:
    """Professional AI-powered code review engine."""

    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.model = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        self.cache = {}  # Simple in-memory cache

    def _get_cache_key(self, diff: str, config: ReviewConfig) -> str:
        """Generate cache key for review requests."""
        content = f"{diff}:{config.json()}"
        return hashlib.md5(content.encode()).hexdigest()

    def _parse_diff_files(self, diff: str) -> List[Dict[str, Any]]:
        """Parse git diff to extract file information."""
        files = []
        current_file = None
        lines = diff.split('\n')

        for line in lines:
            if line.startswith('diff --git'):
                if current_file:
                    files.append(current_file)

                # Extract file path
                parts = line.split()
                if len(parts) >= 3:
                    file_path = parts[2][2:]  # Remove 'b/'
                    current_file = {
                        'path': file_path,
                        'changes': [],
                        'language': self._detect_language(file_path)
                    }
            elif current_file and (line.startswith('+') or line.startswith('-')):
                current_file['changes'].append(line)

        if current_file:
            files.append(current_file)

        return files

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext_map = {
            # Python
            '.py': 'python',
            '.pyw': 'python',
            '.pyx': 'python',
            '.pxd': 'python',

            # JavaScript/TypeScript
            '.js': 'javascript',
            '.mjs': 'javascript',
            '.cjs': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.d.ts': 'typescript',

            # Java
            '.java': 'java',
            '.jsp': 'java',
            '.jar': 'java',

            # C/C++
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.hxx': 'cpp',

            # C#
            '.cs': 'csharp',
            '.csx': 'csharp',

            # Go
            '.go': 'go',

            # Rust
            '.rs': 'rust',

            # PHP
            '.php': 'php',
            '.phtml': 'php',
            '.php3': 'php',
            '.php4': 'php',
            '.php5': 'php',
            '.php7': 'php',

            # Ruby
            '.rb': 'ruby',
            '.rbw': 'ruby',

            # Swift
            '.swift': 'swift',

            # Kotlin
            '.kt': 'kotlin',
            '.kts': 'kotlin',

            # Scala
            '.scala': 'scala',
            '.sc': 'scala',

            # R
            '.r': 'r',
            '.rmd': 'r',

            # Perl
            '.pl': 'perl',
            '.pm': 'perl',
            '.t': 'perl',

            # Shell scripts
            '.sh': 'shell',
            '.bash': 'shell',
            '.zsh': 'shell',
            '.fish': 'shell',
            '.ps1': 'powershell',

            # Web technologies
            '.html': 'html',
            '.htm': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.less': 'less',

            # Configuration files
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.ini': 'ini',
            '.cfg': 'ini',

            # Database
            '.sql': 'sql',

            # Other languages
            '.lua': 'lua',
            '.dart': 'dart',
            '.hs': 'haskell',
            '.ml': 'ocaml',
            '.fs': 'fsharp',
            '.vb': 'vbnet',
            '.clj': 'clojure',
            '.elm': 'elm',
            '.ex': 'elixir',
            '.exs': 'elixir'
        }

        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return 'unknown'

    def _generate_review_prompt(self, file_info: Dict[str, Any], config: ReviewConfig) -> str:
        """Generate sophisticated review prompt for AI."""
        language = file_info.get('language', 'unknown')
        changes = '\n'.join(file_info.get('changes', []))

        categories = [cat.value for cat in config.enabled_categories]

        prompt = f"""You are an expert senior software engineer conducting a professional code review for a pull request.

FILE: {file_info['path']}
LANGUAGE: {language}

REVIEW REQUIREMENTS:
Analyze the following code changes and provide detailed, actionable feedback. You are reviewing code in {language.upper()}, so consider language-specific best practices, idioms, and common pitfalls.

Focus on these categories: {', '.join(categories)}

For each issue found, provide:
1. CATEGORY: One of {', '.join(categories)}
2. SEVERITY: critical/high/medium/low/info
3. TITLE: Brief, descriptive title
4. DESCRIPTION: Detailed explanation of the issue, considering {language} best practices
5. LOCATION: Line numbers if applicable (be precise about which lines the issue affects)
6. SUGGESTION: Clear, actionable suggestion for how to fix it, appropriate for {language}
7. INLINE_SUGGESTION: The exact replacement code that should replace the problematic lines. This should be the corrected version of the code that can be applied directly as a suggestion in the PR. Include proper indentation and formatting for {language}.
8. CODE_EXAMPLE: Additional code example showing the fix in context (use only if the inline suggestion needs more context)

CODE CHANGES:
```diff
{changes}
```

LANGUAGE-SPECIFIC GUIDANCE:
- For compiled languages (Java, C++, C#, Go, Rust): Focus on performance, memory management, type safety
- For interpreted languages (Python, JavaScript, PHP, Ruby): Focus on runtime errors, code clarity, maintainability
- For web technologies (HTML, CSS, JavaScript): Focus on accessibility, browser compatibility, security
- For scripts (Shell, PowerShell): Focus on error handling, portability, security
- For configuration files (JSON, YAML, XML): Focus on syntax correctness, structure, maintainability

RESPONSE FORMAT:
Return a JSON object with the following structure:
{{
  "summary": "Brief overall assessment of the file changes",
  "comments": [
    {{
      "category": "bugs",
      "severity": "high",
      "title": "Brief title",
      "description": "Detailed description",
      "location": {{"line_start": 10, "line_end": 15}},
      "suggestion": "How to fix",
      "inline_suggestion": "    corrected_code_line_1\\n    corrected_code_line_2",
      "code_example": "```python\\n# Full example if needed\\nprint('example')\\n```"
    }}
  ],
  "metrics": {{
    "complexity_score": 5,
    "maintainability_index": 75
  }}
}}

IMPORTANT: For INLINE_SUGGESTION, provide the exact replacement code that should replace the problematic lines. This should be ready to apply as a direct code suggestion in the PR interface. Include proper indentation matching the original code and follow {language} conventions.

Be thorough but concise. Focus on real issues and improvements specific to {language}."""

        return prompt

    def _call_ai_model(self, prompt: str) -> Dict[str, Any]:
        """Call Azure OpenAI with retry logic."""
        try:
            logger.info("Sending request to Azure OpenAI")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert code reviewer. Always respond with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Lower temperature for more consistent reviews
                max_tokens=4000,
                response_format={"type": "json_object"}
            )

            result = response.choices[0].message.content
            logger.info("Received response from Azure OpenAI")

            # Parse JSON response
            return json.loads(result)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            return {"summary": "Error parsing AI response", "comments": [], "metrics": {}}
        except Exception as e:
            logger.error(f"Error calling AI model: {str(e)}")
            return {"summary": "Error analyzing code", "comments": [], "metrics": {}}

    def _create_review_comment(self, comment_data: Dict[str, Any], file_path: str) -> ReviewComment:
        """Create a ReviewComment from AI response data."""
        try:
            location = None
            if 'location' in comment_data and comment_data['location']:
                loc_data = comment_data['location']
                location = CodeLocation(
                    file_path=file_path,
                    line_start=loc_data.get('line_start'),
                    line_end=loc_data.get('line_end'),
                    column_start=loc_data.get('column_start'),
                    column_end=loc_data.get('column_end')
                )

            return ReviewComment(
                id=f"{file_path}_{hash(str(comment_data))}",
                category=ReviewCategory(comment_data.get('category', 'best_practices')),
                severity=ReviewSeverity(comment_data.get('severity', 'info')),
                title=comment_data.get('title', 'Code Review Comment'),
                description=comment_data.get('description', ''),
                location=location,
                suggestion=comment_data.get('suggestion'),
                inline_suggestion=comment_data.get('inline_suggestion'),
                code_example=comment_data.get('code_example'),
                references=comment_data.get('references', [])
            )
        except Exception as e:
            logger.error(f"Error creating review comment: {e}")
            return ReviewComment(
                id=f"{file_path}_error",
                category=ReviewCategory.BEST_PRACTICES,
                severity=ReviewSeverity.INFO,
                title="Review Comment",
                description=str(comment_data)
            )

    def review_code(self, request: CodeReviewRequest) -> CodeReviewResponse:
        """
        Perform comprehensive AI-powered code review.

        Args:
            request: CodeReviewRequest containing diff and metadata

        Returns:
            CodeReviewResponse with structured review results
        """
        config = ReviewConfig(**(request.config or {}))

        # Check cache first
        cache_key = self._get_cache_key(request.diff, config)
        if cache_key in self.cache:
            logger.info("Returning cached review result")
            return self.cache[cache_key]

        # Parse diff into files
        files_info = self._parse_diff_files(request.diff)
        file_reviews = []

        all_comments = []

        for file_info in files_info:
            logger.info(f"Analyzing file: {file_info['path']}")

            # Generate prompt and call AI
            prompt = self._generate_review_prompt(file_info, config)
            ai_response = self._call_ai_model(prompt)

            # Parse AI response
            comments_data = ai_response.get('comments', [])
            comments = [
                self._create_review_comment(comment, file_info['path'])
                for comment in comments_data
            ]

            # Limit comments per file
            comments = comments[:config.max_comments_per_file]

            file_review = FileReview(
                file_path=file_info['path'],
                language=file_info.get('language'),
                summary=ai_response.get('summary', 'No summary provided'),
                comments=comments,
                metrics=ai_response.get('metrics', {})
            )

            file_reviews.append(file_review)
            all_comments.extend(comments)

        # Calculate summary statistics
        severity_counts = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'info': 0
        }

        category_counts = {cat.value: 0 for cat in ReviewCategory}

        for comment in all_comments:
            severity_counts[comment.severity.value] += 1
            category_counts[comment.category.value] += 1

        # Calculate overall score (simple algorithm)
        weights = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1, 'info': 0}
        penalty_score = sum(severity_counts[sev] * weight for sev, weight in weights.items())
        overall_score = max(0, 100 - penalty_score)

        summary = ReviewSummary(
            overall_score=overall_score,
            total_comments=len(all_comments),
            critical_issues=severity_counts['critical'],
            high_issues=severity_counts['high'],
            medium_issues=severity_counts['medium'],
            low_issues=severity_counts['low'],
            info_suggestions=severity_counts['info'],
            categories_breakdown=category_counts
        )

        # Generate overall feedback
        overall_feedback = self._generate_overall_feedback(summary, file_reviews)

        # Generate recommendations
        recommendations = self._generate_recommendations(summary, file_reviews)

        response = CodeReviewResponse(
            review_id=f"review_{datetime.now().isoformat()}",
            summary=summary,
            files=file_reviews,
            overall_feedback=overall_feedback,
            recommendations=recommendations,
            metadata={
                'repository_url': request.repository_url,
                'branch': request.branch,
                'commit_sha': request.commit_sha,
                'author': request.author,
                'analyzed_at': datetime.now().isoformat()
            }
        )

        # Cache the result
        self.cache[cache_key] = response

        return response

    def _generate_overall_feedback(self, summary: ReviewSummary, files: List[FileReview]) -> str:
        """Generate overall feedback based on review results."""
        score = summary.overall_score

        if score >= 90:
            feedback = "Excellent work! The code changes are of high quality with minimal issues."
        elif score >= 80:
            feedback = "Good job! The code changes are solid with some minor improvements needed."
        elif score >= 70:
            feedback = "Decent work, but there are several areas that need attention."
        elif score >= 60:
            feedback = "The code changes have significant issues that should be addressed."
        else:
            feedback = "The code changes require substantial improvements before merging."

        critical_high = summary.critical_issues + summary.high_issues
        if critical_high > 0:
            feedback += f" There are {critical_high} critical/high priority issues that must be fixed."

        return feedback

    def _generate_recommendations(self, summary: ReviewSummary, files: List[FileReview]) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        if summary.critical_issues > 0:
            recommendations.append("Fix all critical issues before merging")

        if summary.high_issues > 0:
            recommendations.append("Address high-priority issues")

        if summary.medium_issues > 3:
            recommendations.append("Consider breaking down the changes into smaller PRs")

        # Language-specific recommendations
        languages = set(f.language for f in files if f.language != 'unknown')
        for lang in languages:
            if lang == 'python':
                recommendations.append("Ensure Python code follows PEP 8 style guidelines")
            elif lang in ['javascript', 'typescript']:
                recommendations.append("Consider adding TypeScript types for better type safety")

        if summary.total_comments > 20:
            recommendations.append("The PR is quite large - consider splitting into multiple focused changes")

        return recommendations


# Global instance
review_engine = AICodeReviewEngine()


def analyze_code_diff(request: CodeReviewRequest) -> CodeReviewResponse:
    """
    Analyze a code diff using the AI review engine.

    Args:
        request: CodeReviewRequest with diff and metadata

    Returns:
        CodeReviewResponse with structured analysis
    """
    return review_engine.review_code(request)