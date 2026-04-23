import os
import json
import logging
import hashlib
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from openai import AzureOpenAI
from dotenv import load_dotenv
from services.dependency_analyzer import DependencyAnalyzer
from services.project_context_analyzer import project_analyzer
from services.test_coverage_analyzer import test_coverage_analyzer
from services.breaking_changes_detector import breaking_changes_detector
from services.complexity_analyzer import complexity_analyzer
from services.performance_analyzer import performance_analyzer
from services.migration_analyzer import migration_analyzer, fix_generator
from services.code_smells_analyzer import code_smells_analyzer
from models.review import (
    CodeReviewRequest,
    CodeReviewResponse,
    FileReview,
    ReviewComment,
    ReviewSummary,
    ReviewCategory,
    ReviewSeverity,
    CodeLocation,
    ReviewConfig,
    TokenUsage
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

# Log Azure OpenAI configuration for debugging (masked sensitive info)
azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', '')
if azure_endpoint:
    # Mask the endpoint - only show domain, not full URL
    masked_endpoint = '/'.join(azure_endpoint.split('/')[:3]) + '/***'
    logger.info(f"Azure OpenAI Endpoint: {masked_endpoint}")
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

    def _generate_review_prompt(self, file_info: Dict[str, Any], config: ReviewConfig, analyze_complete: bool = False) -> str:
        """Generate sophisticated review prompt for AI."""
        language = file_info.get('language', 'unknown')
        
        # Use complete content if analyzing full files, otherwise use changes
        if analyze_complete and 'content' in file_info:
            code_to_review = file_info.get('content', '')
            analysis_scope = "COMPLETE FILE ANALYSIS"
            code_section = f"""COMPLETE FILE CONTENT (Comprehensive Review):
```{language}
{code_to_review}
```"""
        else:
            changes = '\n'.join(file_info.get('changes', []))
            analysis_scope = "CHANGED LINES ANALYSIS"
            code_section = f"""CODE CHANGES (Diff):
```diff
{changes}
```"""

        categories = [cat.value for cat in config.enabled_categories]

        prompt = f"""You are an expert senior software engineer conducting a professional code review for a pull request.

FILE: {file_info['path']}
LANGUAGE: {language}
ANALYSIS SCOPE: {analysis_scope}

REVIEW REQUIREMENTS:
Analyze the following code and provide detailed, actionable feedback. You are reviewing code in {language.upper()}, so consider language-specific best practices, idioms, and common pitfalls.

Focus on these categories: {', '.join(categories)}

COMPREHENSIVE ANALYSIS INSTRUCTIONS:
Since this is a {analysis_scope}, perform a THOROUGH review that includes:
1. **Security vulnerabilities** - hardcoded secrets, SQL injection, XSS, authentication issues
2. **Code smells** - duplicated code, long functions, deep nesting, poor naming
3. **Best practices** - proper error handling, input validation, logging
4. **Performance issues** - inefficient algorithms, memory leaks, unnecessary operations
5. **Maintainability** - code clarity, documentation, test coverage
6. **Design patterns** - use appropriate patterns, avoid anti-patterns

SECURITY SCANNING REQUIREMENTS:
Perform a comprehensive security analysis for:
- SQL Injection vulnerabilities (unsafe string concatenation in queries)
- XSS (Cross-Site Scripting) attacks (unsafe HTML output, user input in DOM)
- Hardcoded secrets (API keys, passwords, tokens, database credentials in source code)
- Unsafe API usage (deprecated functions, insecure defaults)
- Authentication/authorization issues (missing auth checks, weak auth)
- Data validation issues (missing input sanitization)
- Cryptographic weaknesses (weak algorithms, improper key management)
- Exposed configuration data (hardcoded endpoints, credentials)

For each issue found, provide:
1. CATEGORY: One of {', '.join(categories)}
2. SEVERITY: critical/high/medium/low/info
3. TITLE: Brief, descriptive title (e.g., "Missing Import Statements", "SQL Injection Risk")
4. DESCRIPTION: Detailed explanation of the issue, considering {language} best practices and security implications
5. LOCATION: Line numbers if applicable (be precise about which lines the issue affects)
6. CHANGED_LINES_DIFF: The exact diff showing the problematic lines that need to be changed
7. SUGGESTION: Clear, actionable suggestion for how to fix it, appropriate for {language}
8. INLINE_SUGGESTION: The exact replacement code that should replace the problematic lines. This should be the corrected version of the code that can be applied directly as a suggestion in the PR. Include proper indentation and formatting for {language}.
9. CODE_EXAMPLE: Additional code example showing the fix in context (use only if the inline suggestion needs more context)
10. MINIMAL_TEST: A minimal unit test or security test that validates the fix
11. REFERENCES: Security standards, OWASP guidelines, or best practices that apply

{code_section}

LANGUAGE-SPECIFIC GUIDANCE:
- For compiled languages (Java, C++, C#, Go, Rust): Focus on performance, memory management, type safety, secure coding practices
- For interpreted languages (Python, PHP, Ruby): Focus on runtime errors, code clarity, maintainability, input validation, secure API usage
- For **JavaScript/TypeScript (web)**: Focus on async/await best practices, promise handling, null safety, DOM manipulation security, event handler leaks, memory management, type safety (TS), module dependencies, XSS prevention, CSRF tokens
- For HTML/CSS: Focus on accessibility, semantic structure, browser compatibility, security (XSS, CSRF, secure headers)
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
      "changed_lines_diff": "- query = f'SELECT * FROM users WHERE id = {{user_id}}'\n+ cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
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

CHANGED_LINES_DIFF REQUIREMENTS:
- Show the problematic lines from the diff that need to be replaced
- Include the lines before and after for context
- Use proper diff format (- for old, + for new)
- Match original indentation exactly
- Show only the relevant lines that need to be changed

BITBUCKET INTEGRATION NOTES:
- Focus on Bitbucket-specific features and workflows
- Provide inline suggestions that can be directly applied in Bitbucket PRs
- Include line-specific feedback for better code review experience
- Support both Bitbucket Cloud and Server environments
- Generate comments that integrate well with Bitbucket's review interface

IMPORTANT NOTES:
- Be thorough but concise - one sentence summaries only
- Focus ONLY on real issues specific to {language}
- Prioritize SECURITY vulnerabilities (highest risk first)
- Avoid duplicate issues across separate comments
- Provide different fixes for different problems
- Make suggestions language-specific and immediately applicable
- Include both original code and suggested changes for clear before/after comparison"""

        return prompt

    def _call_ai_model(self, prompt: str) -> tuple[Dict[str, Any], TokenUsage]:
        """Call Azure OpenAI with retry logic and return response + token usage."""
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
            
            # Extract token usage from response
            token_usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
            
            logger.info(f"Token usage - Prompt: {token_usage.prompt_tokens}, Completion: {token_usage.completion_tokens}, Total: {token_usage.total_tokens}")

            # Parse JSON response
            parsed_result = json.loads(result)
            return parsed_result, token_usage

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            # Return error response with zero token usage (partial count before error)
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
            }, TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
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
            }, TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

    def _extract_original_code_from_diff(self, diff_content: str, file_path: str, line_start: int, line_end: Optional[int] = None) -> Optional[str]:
        """
        Extract original code from diff content based on line numbers.
        
        Args:
            diff_content: The full git diff content
            file_path: Path to the file in the diff
            line_start: Starting line number
            line_end: Ending line number (optional)
            
        Returns:
            Original code lines as string, or None if not found
        """
        try:
            lines = diff_content.split('\n')
            current_file = None
            current_line_num = 0
            original_lines = []
            
            i = 0
            while i < len(lines):
                line = lines[i]
                
                # Find the file we're looking for
                if line.startswith('diff --git'):
                    # Extract file path from diff line
                    parts = line.split()
                    if len(parts) >= 3:
                        diff_file_path = parts[2][2:]  # Remove 'b/'
                        if diff_file_path == file_path:
                            current_file = diff_file_path
                            current_line_num = 0
                        else:
                            current_file = None
                
                elif current_file and line.startswith('@@'):
                    # Parse hunk header like @@ -10,5 +10,5 @@
                    import re
                    match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', line)
                    if match:
                        old_start = int(match.group(1))
                        current_line_num = old_start
                
                elif current_file and (line.startswith('-') or line.startswith(' ')):
                    # This is an original line (either removed or context)
                    if current_line_num >= line_start:
                        if line_end is None or current_line_num <= line_end:
                            # Remove the diff marker and add the line
                            original_lines.append(line[1:] if line.startswith(('-', ' ')) else line)
                        elif current_line_num > line_end:
                            break
                    
                    if line.startswith(('-', ' ')):
                        current_line_num += 1
                
                i += 1
            
            return '\n'.join(original_lines).strip() if original_lines else None
            
        except Exception as e:
            logger.warning(f"Failed to extract original code from diff: {e}")
            return None

    def _create_review_comment(self, comment_data: Dict[str, Any], file_path: str, diff_content: str = None) -> ReviewComment:
        """Create a ReviewComment from AI response data with improved formatting."""
        try:
            location = None
            original_code = comment_data.get('original_code')  # AI-provided original code

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

                # Extract original code from diff if not provided by AI
                if not original_code and diff_content and location.line_start:
                    original_code = self._extract_original_code_from_diff(
                        diff_content, file_path, location.line_start, location.line_end
                    )

            # Use inline suggestion as-is without adding extra diff markers
            inline_suggestion = comment_data.get('inline_suggestion')

            return ReviewComment(
                id=f"{file_path}_{hash(str(comment_data))}",
                category=ReviewCategory(comment_data.get('category', 'best_practices')),
                severity=ReviewSeverity(comment_data.get('severity', 'info')),
                title=comment_data.get('title', 'Code Review Comment'),
                description=comment_data.get('description', ''),
                location=location,
                changed_lines_diff=comment_data.get('changed_lines_diff') or comment_data.get('original_code'),  # Handle both field names
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

        # COMPREHENSIVE ANALYSIS: Use complete file content if provided (analyzes entire files)
        # Otherwise fall back to diff-based analysis (only changed lines)
        if request.full_files and request.analyze_complete_files:
            logger.info("Analyzing COMPLETE file content (comprehensive security & code quality review)")
            files_info = request.full_files
        else:
            logger.info("Analyzing git diff (changed lines only)")
            files_info = self._parse_diff_files(request.diff)
        file_reviews = []
        all_comments = []
        total_tokens = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

        for file_info in files_info:
            logger.info(f"Analyzing file: {file_info['path']}")

            # Generate prompt and call AI
            # Pass analyze_complete flag to tell the model whether we're analyzing complete files or just diffs
            analyze_complete = request.analyze_complete_files and request.full_files is not None
            prompt = self._generate_review_prompt(file_info, config, analyze_complete=analyze_complete)
            ai_response, file_tokens = self._call_ai_model(prompt)
            
            # Accumulate tokens
            total_tokens = total_tokens + file_tokens

            # Parse AI response
            comments_data = ai_response.get('comments', [])
            comments = [
                self._create_review_comment(comment, file_info['path'], request.diff)
                for comment in comments_data
            ]

            # Limit comments per file
            comments = comments[:config.max_comments_per_file]

            # DEDUPLICATION: Remove critical/high security issues from file comments
            # These are already displayed in the overall security section to avoid repetition
            filtered_comments = [
                c for c in comments
                if not (c.category.value == 'security' and c.severity.value in ['critical', 'high'])
            ]
            comments = filtered_comments

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
                metrics=metrics,
                tokens_used=file_tokens
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

        # Calculate total tokens used
        total_tokens_used = sum(
            file_review.tokens_used.total_tokens if file_review.tokens_used else 0
            for file_review in file_reviews
        )
        
        # Estimate cost (GPT-4o pricing: ~$0.005 per 1K tokens)
        estimated_cost = f"${(total_tokens_used * 0.000005):.4f}"

        summary = ReviewSummary(
            overall_score=overall_score,
            total_comments=len(all_comments),
            critical_issues=severity_counts['critical'],
            high_issues=severity_counts['high'],
            medium_issues=severity_counts['medium'],
            low_issues=severity_counts['low'],
            info_suggestions=severity_counts['info'],
            categories_breakdown=category_counts,
            analysis_errors=analysis_errors,
            tokens_used=total_tokens_used,
            estimated_cost=estimated_cost
        )

        # Generate consolidated security analysis (one-time for all changes)
        security_analysis = self._generate_consolidated_security_analysis(all_comments)

        # ADVANCED ANALYSIS: Run comprehensive code quality and performance analyzers
        test_coverage_analysis = test_coverage_analyzer.analyze_test_coverage(files_info, all_files={})
        breaking_changes_analysis = breaking_changes_detector.detect_breaking_changes(files_info)
        complexity_analysis = complexity_analyzer.analyze_complexity(files_info)
        performance_analysis = performance_analyzer.analyze_performance(files_info)
        migration_analysis = migration_analyzer.analyze_migrations(files_info)
        code_smells_analysis = code_smells_analyzer.analyze_code_smells(files_info)

        # Generate automated fix suggestions for top issues
        top_issues = []
        if breaking_changes_analysis.get('breaking_changes'):
            top_issues.extend(breaking_changes_analysis.get('breaking_changes')[:2])
        if complexity_analysis.get('high_complexity_files'):
            top_issues.extend(complexity_analysis.get('high_complexity_files')[:2])
        if performance_analysis.get('high_priority_issues'):
            top_issues.extend(performance_analysis.get('high_priority_issues')[:2])

        automated_fixes = fix_generator.generate_fixes(top_issues)

        # Analyze project impact if full project context is requested
        # Use environment variables as fallback if not provided in request
        project_impact_analysis = None
        workspace = request.workspace or os.getenv("BITBUCKET_WORKSPACE")
        repo_slug = request.repo_slug or os.getenv("BITBUCKET_REPO_SLUG")
        
        if request.analyze_full_project and workspace and repo_slug:
            logger.info("Fetching full project context for impact analysis...")
            # Create a modified request with the resolved workspace and repo_slug
            request.workspace = workspace
            request.repo_slug = repo_slug
            project_impact_analysis = self._analyze_project_impact(request)

        # Generate review ID using UUID (prevents URL encoding issues with colons/dots)
        # Format: review_<uuid> for cleaner URL handling in chatbot
        review_id = f"review_{str(uuid.uuid4())}"
        logger.info(f"Generated review session ID: {review_id}")
        
        # Generate overall feedback (non-repetitive)
        overall_feedback = self._generate_overall_feedback(
            summary, file_reviews, security_analysis,
            test_coverage_analysis, breaking_changes_analysis,
            complexity_analysis, performance_analysis,
            migration_analysis, automated_fixes,
            project_impact_analysis, code_smells_analysis,
            review_id=review_id
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(summary, file_reviews)

        response = CodeReviewResponse(
            review_id=review_id,
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
            },
            token_usage=total_tokens,
            project_impact_analysis=project_impact_analysis,
            # New comprehensive analyses
            test_coverage_analysis=test_coverage_analysis,
            breaking_changes_analysis=breaking_changes_analysis,
            complexity_analysis=complexity_analysis,
            performance_analysis=performance_analysis,
            migration_analysis=migration_analysis,
            automated_fixes=automated_fixes,
            code_smells_analysis=code_smells_analysis
        )

        # Cache the result
        self.cache[cache_key] = response
        
        logger.info(f"Review completed with ID: {response.review_id}")
        logger.info(f"Review stored in chatbot service for interactive discussion")

        return response

    def _analyze_project_impact(self, request: CodeReviewRequest) -> Dict[str, Any]:
        """Fetch full project context and analyze impact of changes."""
        try:
            logger.info(f"Analyzing project impact for {request.workspace}/{request.repo_slug}")
            
            # Fetch all project files
            all_files = project_analyzer.fetch_project_files(
                workspace=request.workspace,
                repo_slug=request.repo_slug,
                branch=request.branch or "master"
            )
            
            logger.info(f"Fetched {len(all_files)} files from repository")
            
            # Get changed files from request
            changed_files = request.files_changed or []
            if not changed_files:
                # Try to extract from diff
                files_info = self._parse_diff_files(request.diff)
                changed_files = [f['path'] for f in files_info]
            
            # Analyze dependencies
            dependency_analysis = project_analyzer.analyze_dependencies(
                changed_files=changed_files,
                all_files=all_files
            )
            
            # Generate impact report
            impact_report = project_analyzer.generate_impact_report(
                changed_files=changed_files,
                dependency_analysis=dependency_analysis
            )
            
            affected_count = len(dependency_analysis.get('affected_files', []))
            logger.info(f"Project impact analysis complete - {affected_count} files affected out of {len(all_files)} total")
            
            return {
                "all_files_count": len(all_files),
                "changed_files": changed_files,
                "affected_files_count": affected_count,
                "dependency_analysis": dependency_analysis,
                "impact_report": impact_report
            }
            
        except Exception as e:
            logger.error(f"Error analyzing project impact: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    def _generate_consolidated_security_analysis(self, all_comments: List[ReviewComment]) -> Dict[str, Any]:
        """Generate rich, comprehensive security analysis with line-specific details and actionable insights."""
        security_comments = [c for c in all_comments if c.category.value == 'security']

        if not security_comments:
            return {
                "overall_security_posture": "🛡️ Secure - No security vulnerabilities detected",
                "critical_vulnerabilities": 0,
                "high_vulnerabilities": 0,
                "patterns": [],
                "recommendations": [],
                "risk_level": "Low",
                "summary": "✅ All security checks passed",
                "severity_breakdown": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "file_locations": [],
                "critical_findings": [],
                "high_findings": []
            }

        # Categorize by severity
        critical = [c for c in security_comments if c.severity.value == 'critical']
        high = [c for c in security_comments if c.severity.value == 'high']
        medium = [c for c in security_comments if c.severity.value == 'medium']

        # Enhanced vulnerability pattern detection with OWASP categories
        patterns = []
        categories_found = {}
        vulnerability_types = {
            'injection': ['sql injection', 'command injection', 'code injection', 'ldap injection', 'nosql injection', 'path traversal'],
            'xss': ['cross-site scripting', 'xss', 'script injection', 'html injection', 'dom-based xss'],
            'authentication': ['auth', 'login', 'password', 'credential', 'session', 'mfa', '2fa', 'weak auth'],
            'authorization': ['access control', 'permission', 'role', 'privilege escalation', 'idor', 'broken access'],
            'hardcoded': ['hardcoded', 'secret', 'key', 'token', 'password', 'api key', 'credential'],
            'validation': ['input validation', 'sanitization', 'filtering', 'trust boundary', 'deserialization', 'validate'],
            'encryption': ['encryption', 'crypto', 'hash', 'cipher', 'plaintext', 'ssl', 'tls', 'weak crypto'],
            'configuration': ['config', 'misconfiguration', 'default credentials', 'debug mode', 'exposed endpoint'],
            'data_leakage': ['information disclosure', 'sensitive data', 'privacy', 'pii', 'data exposure', 'information leak']
        }

        for comment in security_comments:
            title_lower = comment.title.lower()
            description_lower = (comment.description or '').lower()

            for vuln_type, keywords in vulnerability_types.items():
                if any(keyword in title_lower or keyword in description_lower for keyword in keywords):
                    categories_found[vuln_type] = categories_found.get(vuln_type, 0) + 1

        if categories_found:
            patterns = [f"**{cat.title()}:** {count} issue(s)" for cat, count in sorted(categories_found.items(), key=lambda x: x[1], reverse=True)]

        # Generate file locations with line numbers
        file_locations = []
        for comment in security_comments:
            if comment.location:
                location_info = {
                    "file": comment.location.file_path,
                    "line": comment.location.line_start or "N/A",
                    "severity": comment.severity.value,
                    "title": comment.title,
                    "rule_id": comment.rule_id or "N/A"
                }
                file_locations.append(location_info)

        # Critical and high findings with details
        critical_findings = []
        high_findings = []

        for comment in critical:
            finding = {
                "title": comment.title,
                "file": comment.location.file_path if comment.location else "Unknown",
                "line": comment.location.line_start if comment.location else "N/A",
                "description": comment.description,
                "suggestion": comment.suggestion,
                "rule_id": comment.rule_id or "N/A",
                "impact": comment.impact or "High security risk"
            }
            critical_findings.append(finding)

        for comment in high:
            finding = {
                "title": comment.title,
                "file": comment.location.file_path if comment.location else "Unknown",
                "line": comment.location.line_start if comment.location else "N/A",
                "description": comment.description,
                "suggestion": comment.suggestion,
                "rule_id": comment.rule_id or "N/A",
                "impact": comment.impact or "Security vulnerability"
            }
            high_findings.append(finding)

        # Enhanced risk assessment with better summaries
        total_sec_issues = len(security_comments)
        if len(critical) > 0:
            posture = f"🚨 **CRITICAL RISK** - {len(critical)} critical vulnerability/vulnerabilities found"
            risk_level = "Critical"
            summary = f"🔴 **BLOCKING:** {len(critical)} critical security issues must be fixed before merge. These pose immediate threats to application security."
        elif len(high) > 0:
            posture = f"⚠️ **HIGH RISK** - {len(high)} high-severity issue(s) found"
            risk_level = "High"
            summary = f"🟠 **REQUIRES ATTENTION:** {len(high)} high-risk security vulnerabilities detected. Address before deployment to production."
        elif len(medium) > 0:
            posture = f"🟡 **MEDIUM RISK** - {len(medium)} security concerns identified"
            risk_level = "Medium"
            summary = f"🟡 **IMPROVEMENT NEEDED:** {len(medium)} security issues found. Consider fixing before release for better security posture."
        else:
            posture = f"🛡️ **SECURE** - No significant security issues found"
            risk_level = "Low"
            summary = f"✅ **SECURE:** All security checks passed. Code follows security best practices."

        # Enhanced, actionable recommendations with priority levels
        recommendations = []
        if total_sec_issues > 0:
            if len(critical) > 0:
                recommendations.append("🚨 **URGENT (P0 - 24h):** Fix all critical vulnerabilities immediately - these are blocking deployment")
                recommendations.append("🔧 **ACTION:** Review critical findings above and implement suggested fixes within 24 hours")
            if len(high) > 0:
                recommendations.append("⚠️ **HIGH PRIORITY (P1 - 48h):** Address high-severity security issues before production deployment")
                recommendations.append("🔍 **REVIEW:** Examine high-risk findings and apply security patches within 48 hours")
            if len(medium) > 0:
                recommendations.append("🟡 **MEDIUM PRIORITY (P2 - 1 week):** Schedule fixes for medium-severity issues in next sprint")
            if patterns:
                top_patterns = [p.split(':')[0].replace('**', '') for p in patterns[:3]]
                recommendations.append(f"🎯 **FOCUS AREAS:** Prioritize fixing {', '.join(top_patterns)} patterns - highest impact fixes")
            recommendations.append("🧪 **TESTING (P3):** Add security unit tests and integration tests for vulnerable code paths")
            recommendations.append("📚 **KNOWLEDGE:** Security awareness training on " + (f"{list(categories_found.keys())[0].title()}" if categories_found else "OWASP Top 10"))
            recommendations.append("🔒 **AUTOMATION:** Implement SAST tools (SonarQube, Checkmarx) in CI/CD for continuous security scanning")

        return {
            "overall_security_posture": posture,
            "critical_vulnerabilities": len(critical),
            "high_vulnerabilities": len(high),
            "medium_vulnerabilities": len(medium),
            "low_vulnerabilities": len([c for c in security_comments if c.severity.value == 'low']),
            "total_security_issues": total_sec_issues,
            "risk_score": max(0, 100 - (len(critical) * 25 + len(high) * 15 + len(medium) * 8 + len([c for c in security_comments if c.severity.value == 'low']) * 3)),
            "patterns": patterns,
            "risk_level": risk_level,
            "action_required": "Deployment Blocked" if len(critical) > 0 else ("Fix Before Production" if len(high) > 0 else "Approved"),
            "summary": summary,
            "recommendations": recommendations,
            "severity_breakdown": {
                "critical": len(critical),
                "high": len(high),
                "medium": len(medium),
                "low": len([c for c in security_comments if c.severity.value == 'low'])
            },
            "vulnerability_matrix": {
                "injection": categories_found.get('injection', 0),
                "xss": categories_found.get('xss', 0),
                "authentication": categories_found.get('authentication', 0),
                "authorization": categories_found.get('authorization', 0),
                "hardcoded": categories_found.get('hardcoded', 0),
                "validation": categories_found.get('validation', 0),
                "encryption": categories_found.get('encryption', 0),
                "configuration": categories_found.get('configuration', 0),
                "data_leakage": categories_found.get('data_leakage', 0)
            },
            "file_locations": file_locations,
            "critical_findings": critical_findings,
            "high_findings": high_findings
        }

    def _generate_overall_feedback(
        self, 
        summary: ReviewSummary, 
        files: List[FileReview], 
        security_analysis: Dict[str, Any],
        test_coverage: Dict[str, Any] = None,
        breaking_changes: Dict[str, Any] = None,
        complexity: Dict[str, Any] = None,
        performance: Dict[str, Any] = None,
        migration_analysis: Dict[str, Any] = None,
        automated_fixes: List[Dict[str, Any]] = None,
        project_impact: Dict[str, Any] = None,
        code_smells: Dict[str, Any] = None,
        review_id: str = None
    ) -> str:
        """Generate Code Rabbit style detailed analysis with prominent token tracking."""
        if summary.analysis_errors > 0:
            return (
                "## ⚠️ Analysis Incomplete\n\n"
                "**Issue:** AI analysis failed for one or more files\n"
                "**Action:** Please verify your Azure OpenAI credentials and retry the review\n\n"
                "---"
            )

        feedback_parts = []
        
        # CODE RABBIT STYLE HEADER
        feedback_parts.append("## 📋 Code Review Analysis")
        feedback_parts.append("")
        
        # CODE QUALITY SCORECARD (Code Rabbit Style)
        feedback_parts.append("### 🎯 Code Quality Metrics")
        feedback_parts.append("")
        
        # Issue distribution
        if summary.critical_issues > 0 or summary.high_issues > 0 or summary.medium_issues > 0:
            feedback_parts.append("**Issue Distribution:**")
            if summary.critical_issues > 0:
                feedback_parts.append(f"- 🔴 **Critical:** {summary.critical_issues} issue(s)")
            if summary.high_issues > 0:
                feedback_parts.append(f"- 🟠 **High:** {summary.high_issues} issue(s)")
            if summary.medium_issues > 0:
                feedback_parts.append(f"- 🟡 **Medium:** {summary.medium_issues} issue(s)")
            if summary.low_issues > 0:
                feedback_parts.append(f"- 🔵 **Low:** {summary.low_issues} issue(s)")
            if summary.info_suggestions > 0:
                feedback_parts.append(f"- ℹ️ **Info:** {summary.info_suggestions} suggestion(s)")
            feedback_parts.append("")
        
        # Category breakdown (Code Rabbit style)
        if summary.categories_breakdown:
            feedback_parts.append("**Review by Category:**")
            sorted_categories = sorted(summary.categories_breakdown.items(), key=lambda x: x[1], reverse=True)
            category_icons = {
                'security': '🔒',
                'bugs': '🐛',
                'performance': '⚡',
                'maintainability': '🏗️',
                'style': '🎨',
                'best_practices': '✨',
                'testing': '🧪',
                'documentation': '📖'
            }
            for category, count in sorted_categories[:5]:  # Top 5
                icon = category_icons.get(category, '•')
                feedback_parts.append(f"- {icon} **{category.title()}:** {count}")
            feedback_parts.append("")
        
        # SECURITY ANALYSIS SECTION
        feedback_parts.append("---")
        feedback_parts.append("")
        security_posture = security_analysis.get('overall_security_posture', '')
        total_sec_issues = security_analysis.get('total_security_issues', 0)
        risk_score = security_analysis.get('risk_score', 100)
        
        # Ensure risk_score is realistic - if there are issues, it should not be 100
        if total_sec_issues > 0 and risk_score >= 95:
            risk_score = max(0, 100 - (total_sec_issues * 10))  # Recalculate if unrealistic
        
        # Security Status Card
        feedback_parts.append(f"### 🛡️ Security Assessment")
        feedback_parts.append(f"{security_posture}")
        feedback_parts.append("")
        
        # Risk Score Gauge with accurate percentage
        if risk_score >= 80:
            gauge = "████████████████████ (Secure)"
        elif risk_score >= 60:
            gauge = "████████████░░░░░░░░ (Acceptable)"
        elif risk_score >= 40:
            gauge = "████████░░░░░░░░░░░░ (At Risk)"
        else:
            gauge = "████░░░░░░░░░░░░░░░░ (Critical)"
        
        feedback_parts.append(f"**Risk Score:** {int(risk_score)}/100 | {gauge}")
        feedback_parts.append("")

        if total_sec_issues > 0:
            # Security patterns if available
            patterns = security_analysis.get('patterns', [])
            if patterns:
                feedback_parts.append("**Vulnerability Patterns Detected:**")
                for pattern in patterns[:3]:  # Reduced from 5 to 3 to avoid repetition
                    feedback_parts.append(f"• {pattern}")
                feedback_parts.append("")

            # Critical Findings with Line Numbers and Suggestions
            critical_findings = security_analysis.get('critical_findings', [])
            if critical_findings:
                feedback_parts.append("**🚨 Critical Security Issues (Must Fix):**")
                feedback_parts.append("")
                for i, finding in enumerate(critical_findings[:3], 1):  # Reduced from 5 to 3
                    feedback_parts.append(f"**{i}. {finding['title']}**")
                    feedback_parts.append(f"   📁 Location: `{finding['file']}:{finding['line']}`")
                    feedback_parts.append(f"   📝 Description: {finding['description']}")
                    if finding.get('impact'):
                        feedback_parts.append(f"   ⚠️ Impact: {finding['impact']}")
                    feedback_parts.append("")

            # High Findings
            high_findings = security_analysis.get('high_findings', [])
            if high_findings:
                feedback_parts.append("**⚠️ High Priority Security Issues:**")
                feedback_parts.append("")
                for i, finding in enumerate(high_findings[:2], 1):  # Reduced from 5 to 2
                    feedback_parts.append(f"**{i}. {finding['title']}**")
                    feedback_parts.append(f"   📁 Location: `{finding['file']}:{finding['line']}`")
                    feedback_parts.append(f"   📝 Description: {finding['description']}")
                    if finding.get('impact'):
                        feedback_parts.append(f"   ⚠️ Impact: {finding['impact']}")
                    feedback_parts.append("")
        else:
            feedback_parts.append("✅ **No security vulnerabilities detected** - Code follows security best practices")
            feedback_parts.append("")

        # DEPENDENCY ANALYSIS SECTION
        dep_summary = {"critical": 0, "high": 0, "medium": 0, "total": 0}

        for file in files:
            if file.metrics and 'dependency_analysis' in file.metrics:
                dep_analysis = file.metrics['dependency_analysis']
                if dep_analysis.get('issues'):
                    for issue in dep_analysis['issues']:
                        severity = issue.get('severity', 'medium')
                        dep_summary[severity] = dep_summary.get(severity, 0) + 1
                        dep_summary['total'] += 1

        if dep_summary['total'] > 0:
            feedback_parts.append("---")
            feedback_parts.append("")
            feedback_parts.append(f"### 📦 Dependency Analysis")
            feedback_parts.append(f"**Total Issues Found:** {dep_summary['total']}")
            feedback_parts.append("")
            dep_breakdown = []
            if dep_summary['critical'] > 0:
                dep_breakdown.append(f"🚨 {dep_summary['critical']} Critical")
            if dep_summary['high'] > 0:
                dep_breakdown.append(f"⚠️ {dep_summary['high']} High")
            if dep_summary['medium'] > 0:
                dep_breakdown.append(f"🟡 {dep_summary['medium']} Medium")
            if dep_breakdown:
                feedback_parts.append(f"**Severity Breakdown:** {' | '.join(dep_breakdown)}")
            feedback_parts.append("")



        # BREAKING CHANGES SECTION
        feedback_parts.append("---")
        feedback_parts.append("")
        if breaking_changes and breaking_changes.get('has_breaking_changes'):
            severity_emoji = {
                'critical': '🚨',
                'high': '⚠️',
                'medium': '🟡',
                'low': '🔵'
            }
            emoji = severity_emoji.get(breaking_changes.get('severity'), '❓')
            feedback_parts.append(f"### {emoji} Breaking Changes Detected")
            feedback_parts.append(f"**Count:** {breaking_changes.get('breaking_changes_count', 0)} breaking change(s)")
            feedback_parts.append("")

            for change in breaking_changes.get('breaking_changes', [])[:3]:
                feedback_parts.append(f"⚠️ **{change.get('type', 'Change').upper()}**")
                feedback_parts.append(f"   Name: `{change.get('name', 'Unknown')}`")
                feedback_parts.append(f"   Impact: {change.get('impact', 'Unknown')}")
                feedback_parts.append(f"   Fix: {change.get('fix', 'N/A')}")
                feedback_parts.append("")

            for rec in breaking_changes.get('recommendations', [])[:2]:
                feedback_parts.append(f"❌ {rec}")
            feedback_parts.append("")
        else:
            feedback_parts.append("### ✅ Breaking Changes Check")
            feedback_parts.append("**Status:** No breaking changes detected")
            feedback_parts.append("**Result:** Code is backward compatible")
            feedback_parts.append("")

        # COMPLEXITY ANALYSIS SECTION
        feedback_parts.append("---")
        feedback_parts.append("")
        if complexity and complexity.get('has_complexity_issues'):
            health_emoji = {'good': '✅', 'acceptable': '🟡', 'risky': '🔴'}
            emoji = health_emoji.get(complexity.get('overall_health', 'good'), '❓')
            feedback_parts.append(f"### {emoji} Code Complexity Analysis")
            feedback_parts.append(f"**Health:** {emoji} {complexity.get('overall_health', 'unknown').upper()}")
            feedback_parts.append(f"**Average Complexity:** {complexity.get('average_complexity', 0)}")
            feedback_parts.append("")

            if complexity.get('high_complexity_files'):
                feedback_parts.append("**⚠️ High Complexity Files:**")
                for cf in complexity['high_complexity_files'][:3]:
                    feedback_parts.append(f"- {cf.get('file')}: CC={cf.get('cyclomatic_complexity')} (threshold: {cf.get('threshold')})")
                    feedback_parts.append(f"  💡 {cf.get('suggestion', 'Refactor needed')}")
                feedback_parts.append("")

            for rec in complexity.get('recommendations', [])[:2]:
                feedback_parts.append(f"🔧 {rec}")
            feedback_parts.append("")
        else:
            feedback_parts.append("### ✅ Code Complexity Analysis")
            health = complexity.get('overall_health', 'good') if complexity else 'good'
            health_emoji = {'good': '✅', 'acceptable': '🟡', 'risky': '🔴'}
            emoji = health_emoji.get(health, '✅')
            feedback_parts.append(f"**Health:** {emoji} {health.upper()}")
            avg_complexity = complexity.get('average_complexity', 0) if complexity else 0
            feedback_parts.append(f"**Average Complexity:** {avg_complexity} (target: <5)")
            feedback_parts.append("**Result:** Code complexity is within healthy range")
            feedback_parts.append("")

        # PERFORMANCE ANALYSIS SECTION
        feedback_parts.append("---")
        feedback_parts.append("")
        if performance and performance.get('has_performance_issues'):
            perf_emoji = {'critical': '⛔', 'high': '⚡', 'medium': '🟡'}
            emoji = perf_emoji.get(performance.get('severity', 'medium'), '💡')
            feedback_parts.append(f"### {emoji} Performance Issues")
            feedback_parts.append(f"**Total Issues:** {performance.get('total_issues', 0)}")
            feedback_parts.append("")

            if performance.get('high_priority_issues'):
                feedback_parts.append("**High Priority Issues:**")
                for issue in performance['high_priority_issues'][:2]:
                    feedback_parts.append(f"- **{issue.get('type', 'Issue').replace('_', ' ').title()}**")
                    feedback_parts.append(f"  Impact: {issue.get('impact', 'N/A')}")
                    feedback_parts.append(f"  Fix: {issue.get('fix', 'N/A')}")
                feedback_parts.append("")

            for rec in performance.get('recommendations', [])[:2]:
                feedback_parts.append(f"⚡ {rec}")
            feedback_parts.append("")
        else:
            feedback_parts.append("### ✅ Performance Analysis")
            feedback_parts.append("**Status:** No performance antipatterns detected")
            feedback_parts.append("**Result:** Code follows performance best practices")
            feedback_parts.append("")

        # MIGRATIONS SECTION
        feedback_parts.append("---")
        feedback_parts.append("")
        if migration_analysis and migration_analysis.get('has_migrations'):
            feedback_parts.append(f"### 📊 Database Migrations")
            feedback_parts.append(f"**Migration Files:** {migration_analysis.get('total_migrations', 0)}")
            feedback_parts.append("")

            if migration_analysis.get('risky_migrations'):
                feedback_parts.append("**⚠️ Risky Operations Detected:**")
                for mig in migration_analysis['risky_migrations'][:2]:
                    feedback_parts.append(f"- {mig.get('file')}")
                    for op in mig.get('operations', [])[:2]:
                        feedback_parts.append(f"  ⚠️ {op}")
                feedback_parts.append("")

            for rec in migration_analysis.get('recommendations', [])[:2]:
                feedback_parts.append(f"📋 {rec}")
            feedback_parts.append("")
        else:
            feedback_parts.append("### ✅ Database Migrations Check")
            feedback_parts.append("**Status:** No database migrations detected")
            feedback_parts.append("**Result:** No migration-related issues")
            feedback_parts.append("")

        # CODE SMELLS ANALYSIS SECTION
        feedback_parts.append("---")
        feedback_parts.append("")
        if code_smells and code_smells.get('has_smells'):
            feedback_parts.append(f"### 👃 Code Smells & Anti-Patterns")
            feedback_parts.append(f"**Total Issues Found:** {code_smells.get('total_smells_found', 0)}")
            feedback_parts.append("")
            
            # Severity breakdown
            severity = code_smells.get('severity_breakdown', {})
            if severity.get('critical', 0) > 0 or severity.get('high', 0) > 0:
                feedback_parts.append("**Severity Breakdown:**")
                if severity.get('critical', 0) > 0:
                    feedback_parts.append(f"- 🔴 **Critical:** {severity['critical']} code smell(s)")
                if severity.get('high', 0) > 0:
                    feedback_parts.append(f"- 🟠 **High:** {severity['high']} issue(s)")
                if severity.get('medium', 0) > 0:
                    feedback_parts.append(f"- 🟡 **Medium:** {severity['medium']} issue(s)")
                if severity.get('low', 0) > 0:
                    feedback_parts.append(f"- 🔵 **Low:** {severity['low']} suggestion(s)")
                feedback_parts.append("")
            
            # Categories breakdown
            smells_by_cat = code_smells.get('smells_by_category', {})
            if smells_by_cat:
                feedback_parts.append("**Issues by Category:**")
                for category, smells_list in sorted(smells_by_cat.items(), key=lambda x: len(x[1]), reverse=True)[:5]:
                    count = len(smells_list) if isinstance(smells_list, list) else smells_list
                    feedback_parts.append(f"- **{category.replace('_', ' ').title()}:** {count}")
                feedback_parts.append("")
            
            # Critical smells if any
            critical_smells = code_smells.get('critical_smells', [])
            if critical_smells:
                feedback_parts.append("**🔴 Critical Code Smells:**")
                for smell in critical_smells[:3]:
                    feedback_parts.append(f"- **{smell.get('title', 'Issue')}** ({smell.get('type', 'unknown')})")
                    feedback_parts.append(f"  📁 Line {smell.get('line', 'unknown')}: {smell.get('description', '')}")
                    feedback_parts.append(f"  💡 Fix: {smell.get('suggestion', 'Refactor needed')}")
                feedback_parts.append("")
            
            # High smells
            high_smells = code_smells.get('high_smells', [])
            if high_smells:
                feedback_parts.append("**⚠️ High Priority Code Smells:**")
                for smell in high_smells[:2]:
                    feedback_parts.append(f"- **{smell.get('title', 'Issue')}** (Line {smell.get('line', '?')})")
                    feedback_parts.append(f"  💡 {smell.get('suggestion', 'Needs attention')}")
                feedback_parts.append("")
            
            # Recommendations (only first 2 to avoid repetition)
            recommendations_list = code_smells.get('recommendations', [])
            if recommendations_list:
                feedback_parts.append("**Recommendations:**")
                for rec in recommendations_list[:2]:
                    feedback_parts.append(f"📋 {rec}")
                feedback_parts.append("")
        else:
            feedback_parts.append("### ✅ Code Smells Check")
            feedback_parts.append("**Status:** No significant code smells detected")
            feedback_parts.append("")


        # PROJECT IMPACT ANALYSIS SECTION (ALWAYS SHOW)
        feedback_parts.append("---")
        feedback_parts.append("")
        
        if project_impact and not project_impact.get('error'):
            feedback_parts.append(f"### 🌍 Project Impact Analysis")
            all_files_count = project_impact.get('all_files_count', 0)
            affected_count = project_impact.get('affected_files_count', 0)
            changed_files = project_impact.get('changed_files', [])
            
            feedback_parts.append(f"**Repository Scope:** {all_files_count} total files analyzed")
            feedback_parts.append(f"**Your Changes:** {len(changed_files)} file(s) modified")
            feedback_parts.append("")
            
            if affected_count == 0:
                feedback_parts.append("### ✅ **NO ISSUES DETECTED**")
                feedback_parts.append("")
                feedback_parts.append("**Status:** This change is ISOLATED and does NOT affect other files")
                feedback_parts.append("")
                feedback_parts.append(f"**Your changes in:**")
                for f in changed_files[:5]:
                    feedback_parts.append(f"- {f}")
                if len(changed_files) > 5:
                    feedback_parts.append(f"- ... and {len(changed_files) - 5} more")
                feedback_parts.append("")
                feedback_parts.append("**Safe:** All other files in the project are NOT impacted")
                feedback_parts.append("")
                feedback_parts.append("### ✅ Recommendation: SAFE TO MERGE")
                feedback_parts.append("This PR can be safely merged without affecting other parts of the codebase.")
            else:
                feedback_parts.append(f"### ⚠️ **{affected_count} FILE(S) AFFECTED**")
                feedback_parts.append("")
                feedback_parts.append(f"**Status:** Your changes will affect {affected_count} other file(s)")
                feedback_parts.append("")
                feedback_parts.append("**Files Changed:**")
                for f in changed_files[:5]:
                    feedback_parts.append(f"- 📝 {f}")
                if len(changed_files) > 5:
                    feedback_parts.append(f"- ... and {len(changed_files) - 5} more")
                feedback_parts.append("")
                
                affected_files = project_impact.get('dependency_analysis', {}).get('affected_files', [])
                if affected_files:
                    feedback_parts.append("**Affected Files (may need review/update):**")
                    for i, f in enumerate(affected_files[:10], 1):
                        feedback_parts.append(f"{i}. ⚠️ {f}")
                    if len(affected_files) > 10:
                        feedback_parts.append(f"... and {len(affected_files) - 10} more files")
                    feedback_parts.append("")
                
                feedback_parts.append("### ⚠️ Recommendation: REVIEW AFFECTED FILES")
                feedback_parts.append("Before merging, please:")
                feedback_parts.append(f"1. Review the {len(changed_files)} changed file(s)")
                feedback_parts.append(f"2. Check the {affected_count} affected file(s) for compatibility")
                feedback_parts.append("3. Run tests to ensure no breaking changes")
            
            feedback_parts.append("")
        else:
            feedback_parts.append("### 🌍 Project Impact Analysis")
            feedback_parts.append("**Status:** Repository-wide analysis not performed")
            feedback_parts.append("")
            feedback_parts.append("💡 **To enable full project impact analysis:**")
            feedback_parts.append("")
            feedback_parts.append("**Option 1 - Via Request (for single review):**")
            feedback_parts.append("```json")
            feedback_parts.append("{")
            feedback_parts.append('  "analyze_full_project": true,')
            feedback_parts.append('  "workspace": "your-bitbucket-workspace",')
            feedback_parts.append('  "repo_slug": "your-repository-name"')
            feedback_parts.append("}")
            feedback_parts.append("```")
            feedback_parts.append("")
            feedback_parts.append("**Option 2 - Via Environment Variables (global):**")
            feedback_parts.append("```bash")
            feedback_parts.append("export BITBUCKET_WORKSPACE=your-workspace")
            feedback_parts.append("export BITBUCKET_REPO_SLUG=your-repo")
            feedback_parts.append("# Then set this header in next request:")
            feedback_parts.append('{"analyze_full_project": true}')
            feedback_parts.append("```")
            feedback_parts.append("")
            feedback_parts.append("**Current Status:**")
            workspace_set = bool(os.getenv("BITBUCKET_WORKSPACE"))
            repo_set = bool(os.getenv("BITBUCKET_REPO_SLUG"))
            feedback_parts.append(f"- BITBUCKET_WORKSPACE: {'✅ Set' if workspace_set else '❌ Not set'}")
            feedback_parts.append(f"- BITBUCKET_REPO_SLUG: {'✅ Set' if repo_set else '❌ Not set'}")
            feedback_parts.append(f"- BITBUCKET_TOKEN: {'✅ Set' if os.getenv('BITBUCKET_TOKEN') else '❌ Not set'}")
            feedback_parts.append("")
            feedback_parts.append("This will:")
            feedback_parts.append("- Fetch all files from your repository")
            feedback_parts.append("- Analyze which files your changes affect")
            feedback_parts.append("- Identify breaking changes across the codebase")
            feedback_parts.append("- Show affected file list in the review")
            feedback_parts.append("")
            feedback_parts.append("✅ **Requires:** Bitbucket credentials (BITBUCKET_USERNAME + BITBUCKET_APP_PASSWORD)")
            feedback_parts.append("")

        # AUTOMATED FIX SUGGESTIONS SECTION
        if automated_fixes:
            feedback_parts.append("---")
            feedback_parts.append("")
            feedback_parts.append("### 🛠️ Automated Fix Suggestions")
            feedback_parts.append("")

            for i, fix in enumerate(automated_fixes[:3], 1):
                feedback_parts.append(f"**{i}. {fix.get('title', 'Fix Suggestion')}**")
                feedback_parts.append("")
                feedback_parts.append(f"**Before:**")
                feedback_parts.append("```python")
                feedback_parts.append(fix.get('code_before', 'N/A'))
                feedback_parts.append("```")
                feedback_parts.append("")
                feedback_parts.append(f"**After:**")
                feedback_parts.append("```python")
                feedback_parts.append(fix.get('code_after', 'N/A'))
                feedback_parts.append("```")
                feedback_parts.append("")
                feedback_parts.append(f"💡 {fix.get('explanation', 'See code comparison')}")
                feedback_parts.append("")

        # No final token stats - removed to minimize output

        # Join with proper formatting
        return "\n".join(feedback_parts)

    def _generate_recommendations(self, summary: ReviewSummary, files: List[FileReview]) -> List[str]:
        """Generate rich, prioritized recommendations with visual indicators."""
        recommendations = []

        # Priority-based sections
        priority_sections = []

        # Critical/High priority section
        critical_high = []
        if summary.critical_issues > 0:
            critical_high.append("🛑 **BLOCKING:** Fix all critical issues before merging")
        if summary.high_issues > 0:
            critical_high.append("⚠️ **HIGH PRIORITY:** Address high-severity issues to reduce risk")

        if critical_high:
            priority_sections.extend(critical_high)

        # Security section
        security_issues = sum(1 for file in files for comment in file.comments
                            if comment.category.value == 'security')
        if security_issues > 0:
            priority_sections.append("🔒 **SECURITY:** Apply security fixes in order of severity (Critical → High → Medium)")

        # Size and complexity section
        complexity = []
        if summary.medium_issues > 3:
            complexity.append("💡 **REFACTOR:** Consider breaking down changes into smaller, focused PRs")
        if summary.total_comments > 20:
            complexity.append("📦 **SIZE:** Large PR detected - split into multiple focused changes for easier review")

        if complexity:
            priority_sections.extend(complexity)

        # Quality improvement section
        quality = []
        if summary.overall_score < 70:
            quality.append("📋 **FOLLOW-UP:** Schedule a follow-up review after addressing feedback")
        elif summary.overall_score >= 80:
            quality.append("✅ **APPROVED:** Code meets quality standards - ready for merge")

        if quality:
            priority_sections.extend(quality)

        # Dependency recommendations
        dep_recs = []
        for file in files:
            if file.metrics and 'dependency_analysis' in file.metrics:
                dep_analysis = file.metrics['dependency_analysis']
                if dep_analysis.get('issues'):
                    critical_deps = sum(1 for i in dep_analysis['issues'] if i.get('severity') == 'critical')
                    if critical_deps > 0:
                        dep_recs.append("📦 **DEPENDENCIES:** Update critical dependency vulnerabilities immediately")

        if dep_recs:
            priority_sections.extend(dep_recs)

        # If no specific recommendations, provide general guidance
        if not priority_sections:
            priority_sections.append("✅ **APPROVED:** No blocking issues found - code is ready for merge")

        return priority_sections


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