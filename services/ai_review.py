import os
import json
import logging
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime
from openai import AzureOpenAI
from dotenv import load_dotenv
from services.dependency_analyzer import DependencyAnalyzer
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
    "AZURE_OPENAI_ENDPOINT"
]

for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Environment variable {var} is not set")

if not (os.getenv("AZURE_OPENAI_MODEL") or os.getenv("AZURE_OPENAI_DEPLOYMENT")):
    raise ValueError(
        "Environment variable AZURE_OPENAI_MODEL or AZURE_OPENAI_DEPLOYMENT must be set"
    )

# Log Azure OpenAI configuration for debugging
logger.info(f"Azure OpenAI Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
logger.info(f"Azure OpenAI API Version: {os.getenv('AZURE_OPENAI_API_VERSION')}")
logger.info(
    "Azure OpenAI Model: %s",
    os.getenv("AZURE_OPENAI_MODEL") or os.getenv("AZURE_OPENAI_DEPLOYMENT")
)

class AICodeReviewEngine:
    """Professional AI-powered code review engine."""

    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.model = os.getenv("AZURE_OPENAI_MODEL") or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        if not self.model:
            raise ValueError("AZURE_OPENAI_MODEL or AZURE_OPENAI_DEPLOYMENT is required")
        if os.getenv("AZURE_OPENAI_MODEL") and os.getenv("AZURE_OPENAI_DEPLOYMENT") \
                and os.getenv("AZURE_OPENAI_MODEL") != os.getenv("AZURE_OPENAI_DEPLOYMENT"):
            logger.warning(
                "Both AZURE_OPENAI_MODEL and AZURE_OPENAI_DEPLOYMENT are set; using AZURE_OPENAI_MODEL"
            )
        self.cache = {}  # Simple in-memory cache
        self.dependency_analyzer = DependencyAnalyzer()

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

SECURITY SCANNING REQUIREMENTS:
Perform a comprehensive security analysis for:
- SQL Injection vulnerabilities (unsafe string concatenation in queries)
- XSS (Cross-Site Scripting) attacks (unsafe HTML output, user input in DOM)
- Hardcoded secrets (API keys, passwords, tokens in source code)
- Unsafe API usage (deprecated functions, insecure defaults)
- Authentication/authorization issues (missing auth checks, weak auth)
- Data validation issues (missing input sanitization)
- Cryptographic weaknesses (weak algorithms, improper key management)

For each issue found, provide:
1. CATEGORY: One of {', '.join(categories)}
2. SEVERITY: critical/high/medium/low/info
3. TITLE: Brief, descriptive title (e.g., "Missing Import Statements", "SQL Injection Risk")
4. DESCRIPTION: Detailed explanation of the issue, considering {language} best practices and security implications
5. LOCATION: Line numbers if applicable (be precise about which lines the issue affects)
6. SUGGESTION: Clear, actionable suggestion for how to fix it, appropriate for {language}
7. INLINE_SUGGESTION: The exact replacement code that should replace the problematic lines. This should be the corrected version of the code that can be applied directly as a suggestion in the PR. Include proper indentation and formatting for {language}.
8. CODE_EXAMPLE: Additional code example showing the fix in context (use only if the inline suggestion needs more context)
9. MINIMAL_TEST: A minimal unit test or security test that validates the fix
10. REFERENCES: Security standards, OWASP guidelines, or best practices that apply

CODE CHANGES:
```diff
{changes}
```

LANGUAGE-SPECIFIC GUIDANCE:
- For compiled languages (Java, C++, C#, Go, Rust): Focus on performance, memory management, type safety, secure coding practices
- For interpreted languages (Python, JavaScript, PHP, Ruby): Focus on runtime errors, code clarity, maintainability, input validation, secure API usage
- For web technologies (HTML, CSS, JavaScript): Focus on accessibility, browser compatibility, security (XSS, CSRF, secure headers)
- For scripts (Shell, PowerShell): Focus on error handling, portability, security, input sanitization
- For configuration files (JSON, YAML, XML): Focus on syntax correctness, structure, maintainability, secret exposure

SECURITY ANALYSIS FRAMEWORK:
1. Input Validation: Check for proper sanitization of user inputs
2. Output Encoding: Verify safe output handling (HTML, SQL, JSON)
3. Authentication: Look for missing auth checks, weak auth mechanisms
4. Authorization: Check for proper access controls
5. Session Management: Review session handling security
6. Cryptography: Identify weak algorithms, improper key usage
7. Error Handling: Ensure errors don't leak sensitive information
8. Logging: Check for secure logging practices

METRICS CALCULATION:
- security_score: 0-100 based on vulnerability count and severity (100 = no issues, deduct 15-20 points per vulnerability, more for critical/high severity)
- vulnerability_count: Total number of security issues found
- quality_score: 0-100 based on code quality issues (100 = excellent, deduct points for style, performance, maintainability issues)
- maintainability_score: 0-100 based on code structure and readability (100 = highly maintainable, deduct for complex functions, poor naming, lack of documentation)
- complexity_score: 0-10 based on cyclomatic complexity (0 = simple, 10 = very complex)

RESPONSE FORMAT:
Return a JSON object with the following structure:
{{
  "summary": "ONE sentence assessment of this file's overall quality and main issues",
  "comments": [
    {{
      "category": "security",
      "severity": "critical",
      "title": "SQL Injection Vulnerability",
      "description": "User input is directly concatenated into SQL query without parameterization",
      "location": {{"line_start": 15, "line_end": 18}},
      "suggestion": "Use parameterized queries or prepared statements to prevent SQL injection",
      "inline_suggestion": "cursor.execute(\\"SELECT * FROM users WHERE id = %s\\", (user_id,))",
      "code_example": "```python\\nimport sqlite3\\n# Secure parameterized query\\ncursor.execute(\\"SELECT * FROM users WHERE id = ?\\", (user_id,))\\n```",
      "minimal_test": "```python\\ntest_result = query_user(\\"1 OR 1=1\\")\\nassert len(test_result) == 0\\n```",
      "references": ["OWASP SQL Injection Prevention Cheat Sheet", "CWE-89"]
    }}
  ],
  "metrics": {{
    "complexity_score": 5,
    "maintainability_index": 75,
    "security_score": 85,
    "vulnerability_count": 2,
    "quality_score": 90,
    "maintainability_score": 88
  }}
}}

INLINE_SUGGESTION REQUIREMENTS:
- Provide ONLY the corrected line(s) of code
- DO NOT include diff markers (-, +, @@ etc.)
- DO NOT include unnecessary context
- Match original indentation exactly
- Make it ready to apply directly as a code suggestion
- Include ALL required changes on one or multiple lines
- For multi-line fixes, include each line without markers

IMPORTANT NOTES:
- Be thorough but concise - one sentence summaries only
- Focus ONLY on real issues specific to {language}
- Prioritize SECURITY vulnerabilities (highest risk first)
- Avoid duplicate issues across separate comments
- Provide different fixes for different problems
- Make suggestions language-specific and immediately applicable
"""

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
                        "content": "You are an expert code reviewer and security analyst using GPT-4. Always respond with valid JSON. Focus on security vulnerabilities and code quality issues. Be precise and actionable in your suggestions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,  # Lower temperature for consistent, deterministic reviews (optimal for gpt-4o)
                max_tokens=4000,
                response_format={"type": "json_object"},
                top_p=0.9  # Ensure diverse but coherent responses
            )

            result = response.choices[0].message.content
            logger.info("Received response from Azure OpenAI")

            # Parse JSON response
            return json.loads(result)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            return {
                "summary": "Error parsing AI response - unable to complete analysis",
                "comments": [],
                "metrics": {
                    "security_score": 0,  # Unable to determine
                    "vulnerability_count": 0,
                    "quality_score": 0,
                    "maintainability_score": 0,
                    "complexity_score": 0,
                    "analysis_error": "JSON parsing failed"
                }
            }
        except Exception as e:
            logger.error(f"Error calling AI model: {str(e)}")
            return {
                "summary": "Error analyzing code - AI service unavailable",
                "comments": [],
                "metrics": {
                    "security_score": 0,  # Unable to determine
                    "vulnerability_count": 0,
                    "quality_score": 0,
                    "maintainability_score": 0,
                    "complexity_score": 0,
                    "analysis_error": "AI service unavailable"
                }
            }

    def _create_review_comment(self, comment_data: Dict[str, Any], file_path: str) -> ReviewComment:
        """Create a ReviewComment from AI response data with improved formatting."""
        try:
            location = None
            if 'location' in comment_data and comment_data['location']:
                loc_data = comment_data['location']
                
                # Helper function to safely convert to int or None
                def to_int_or_none(val):
                    if val is None:
                        return None
                    if isinstance(val, int):
                        return val
                    if isinstance(val, str):
                        if val.lower() in ('n/a', 'unknown', ''):
                            return None
                        try:
                            return int(val)
                        except ValueError:
                            return None
                    return None
                
                location = CodeLocation(
                    file_path=file_path,
                    line_start=to_int_or_none(loc_data.get('line_start')),
                    line_end=to_int_or_none(loc_data.get('line_end')),
                    column_start=to_int_or_none(loc_data.get('column_start')),
                    column_end=to_int_or_none(loc_data.get('column_end'))
                )

            # Format inline suggestion with proper diff markers
            inline_suggestion = comment_data.get('inline_suggestion')
            if inline_suggestion and not inline_suggestion.startswith(('-', '+')):
                # Add diff markers for clarity if not already present
                lines = inline_suggestion.split('\n')
                formatted_lines = []
                for line in lines:
                    if line.strip():
                        formatted_lines.append(f"+ {line}") if not line.startswith('-') else formatted_lines.append(f"- {line}")
                inline_suggestion = '\n'.join(formatted_lines)

            return ReviewComment(
                id=f"{file_path}_{hash(str(comment_data))}",
                category=ReviewCategory(comment_data.get('category', 'best_practices')),
                severity=ReviewSeverity(comment_data.get('severity', 'info')),
                title=comment_data.get('title', 'Code Review Comment'),
                description=comment_data.get('description', ''),
                location=location,
                suggestion=comment_data.get('suggestion'),
                inline_suggestion=inline_suggestion,
                code_example=comment_data.get('code_example'),
                minimal_test=comment_data.get('minimal_test'),
                references=comment_data.get('references', []),
                rule_id=comment_data.get('rule_id'),
                impact=comment_data.get('impact')
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
        Perform comprehensive AI-powered code review with consolidated security analysis.

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

            # Analyze dependencies for this file
            language = file_info.get('language', '').lower()
            changes_content = '\n'.join(file_info.get('changes', []))
            try:
                dependency_analysis = self.dependency_analyzer.analyze_file_dependencies(
                    file_info['path'],
                    changes_content,
                    language
                )
            except Exception as e:
                logger.warning(f"Dependency analysis failed for {file_info['path']}: {str(e)}")
                dependency_analysis = {}

            # Update metrics with security information
            metrics = ai_response.get('metrics', {})
            if 'security_score' not in metrics:
                # Calculate security score based on comments
                security_issues = [c for c in comments if c.category.value == 'security']
                vuln_count = len(security_issues)
                # Security score: 100 - (vulnerabilities * 20) - (high/crit * 10)
                security_score = max(0, 100 - (vuln_count * 15) - sum(20 if c.severity.value in ['critical', 'high'] else 0 for c in security_issues))
                metrics['security_score'] = security_score
                metrics['vulnerability_count'] = vuln_count

            # Add dependency analysis results to metrics
            if dependency_analysis:
                metrics['dependency_analysis'] = dependency_analysis

            # Keep summary but make it concise (not repetitive)
            file_summary = ai_response.get('summary', '')
            if len(file_summary) > 150:
                file_summary = file_summary[:150] + '...'

            file_review = FileReview(
                file_path=file_info['path'],
                language=file_info.get('language'),
                summary=file_summary,
                comments=comments,
                metrics=metrics
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

        analysis_errors = sum(
            1 for file_review in file_reviews
            if file_review.metrics and file_review.metrics.get('analysis_error')
        )

        # Calculate overall score (simple algorithm)
        weights = {'critical': 10, 'high': 5, 'medium': 2, 'low': 1, 'info': 0}
        penalty_score = sum(severity_counts[sev] * weight for sev, weight in weights.items())
        overall_score = max(0, 100 - penalty_score)

        # If the AI review failed, lower the overall score to reflect incomplete analysis
        if analysis_errors > 0:
            overall_score = 0

        summary = ReviewSummary(
            overall_score=overall_score,
            total_comments=len(all_comments),
            critical_issues=severity_counts['critical'],
            high_issues=severity_counts['high'],
            medium_issues=severity_counts['medium'],
            low_issues=severity_counts['low'],
            info_suggestions=severity_counts['info'],
            categories_breakdown=category_counts,
            analysis_errors=analysis_errors
        )

        # Generate consolidated security analysis (one-time for all changes)
        security_analysis = self._generate_consolidated_security_analysis(all_comments)

        # Generate overall feedback (non-repetitive)
        overall_feedback = self._generate_overall_feedback(summary, file_reviews, security_analysis)

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
                'analyzed_at': datetime.now().isoformat(),
                'security_analysis': security_analysis
            }
        )

        # Cache the result
        self.cache[cache_key] = response

        return response

    def _generate_consolidated_security_analysis(self, all_comments: List[ReviewComment]) -> Dict[str, Any]:
        """Generate unified security analysis across all files."""
        security_comments = [c for c in all_comments if c.category.value == 'security']
        
        if not security_comments:
            return {
                "overall_security_posture": "No security vulnerabilities detected",
                "critical_vulnerabilities": 0,
                "high_vulnerabilities": 0,
                "patterns": [],
                "recommendations": []
            }
        
        # Categorize by severity
        critical = [c for c in security_comments if c.severity.value == 'critical']
        high = [c for c in security_comments if c.severity.value == 'high']
        
        # Identify patterns
        patterns = []
        categories_found = {}
        for comment in security_comments:
            title_lower = comment.title.lower()
            for pattern in ['injection', 'xss', 'authentication', 'authorization', 'hardcoded', 'validation', 'encryption']:
                if pattern in title_lower:
                    categories_found[pattern] = categories_found.get(pattern, 0) + 1
        
        if categories_found:
            patterns = [f"{cat.title()}: {count} issue(s)" for cat, count in sorted(categories_found.items(), key=lambda x: x[1], reverse=True)]
        
        # Generate posture
        total_sec_issues = len(security_comments)
        if total_sec_issues == 0:
            posture = "Secure - No vulnerabilities found"
        elif len(critical) > 0:
            posture = f"🚨 Critical - {len(critical)} critical vulnerability/vulnerabilities found"
        elif len(high) > 0:
            posture = f"⚠️ High Risk - {len(high)} high-severity issue(s) found"
        else:
            posture = "⚡ Medium Risk - Multiple lower-severity security issues"
        
        return {
            "overall_security_posture": posture,
            "critical_vulnerabilities": len(critical),
            "high_vulnerabilities": len(high),
            "total_security_issues": total_sec_issues,
            "patterns": patterns,
            "recommendations": [
                "Apply security fixes in order of severity (Critical → High → Medium)",
                "Review security best practices for the patterns identified",
                "Consider adding security tests for validation"
            ] if total_sec_issues > 0 else []
        }

    def _generate_overall_feedback(self, summary: ReviewSummary, files: List[FileReview], security_analysis: Dict[str, Any]) -> str:
        """Generate concise, non-repetitive overall feedback."""
        if summary.analysis_errors > 0:
            return (
                "⚠️ Analysis incomplete: AI analysis failed for one or more files. "
                "Please verify your OpenAI credentials and retry the review."
            )

        score = summary.overall_score
        
        # Score-based message (single, not repetitive)
        if score >= 90:
            main_feedback = "✅ Excellent - High-quality changes with minimal issues"
        elif score >= 80:
            main_feedback = "👍 Good - Solid changes with some minor improvements needed"
        elif score >= 70:
            main_feedback = "🔍 Review needed - Several areas require attention"
        elif score >= 60:
            main_feedback = "⚠️ Issues found - Significant items need addressing before merge"
        else:
            main_feedback = "🛑 Major issues - Substantial improvements required"

        # Add count summary (not duplicate)
        details = f"Score: {score}/100. Found {summary.total_comments} issues: "
        details += f"{summary.critical_issues} critical, {summary.high_issues} high, {summary.medium_issues} medium"
        
        # Add security posture if relevant
        if security_analysis and 'overall_security_posture' in security_analysis:
            details += f". Security: {security_analysis['overall_security_posture']}"

        return f"{main_feedback}. {details}"

    def _generate_recommendations(self, summary: ReviewSummary, files: List[FileReview]) -> List[str]:
        """Generate actionable, non-repetitive recommendations."""
        recommendations = []

        # Critical/High priority
        if summary.critical_issues > 0:
            recommendations.append("🛑 Fix all critical issues before merging")
        
        if summary.high_issues > 0:
            recommendations.append("⚠️ Address high-priority issues to reduce risk")

        # Medium issues
        if summary.medium_issues > 3:
            recommendations.append("💡 Consider breaking down changes into smaller, focused PRs")
        
        # Size check
        if summary.total_comments > 20:
            recommendations.append("📦 Large PR detected - split into multiple focused changes for easier review")

        # Security recommendations
        security_issues = sum(1 for _ in [file.comments for file in files] for comment in _ 
                            if comment.category.value == 'security')
        if security_issues > 0:
            recommendations.append("🔒 Apply security fixes in order of severity")

        # Overall quality
        if summary.overall_score < 70:
            recommendations.append("📋 Schedule a follow-up review after addressing feedback")

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