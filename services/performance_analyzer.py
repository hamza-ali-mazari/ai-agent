"""
Performance Antipatterns Detector

Identifies common performance issues:
- N+1 queries
- Inefficient loops
- Memory leaks
- Synchronous operations that should be async
- Unoptimized algorithms
"""

import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """Detects performance antipatterns in code."""

    def __init__(self):
        """Initialize performance analyzer."""
        self.antipatterns = {
            'n_plus_one': {
                'description': 'N+1 query problem',
                'severity': 'high',
                'pattern': r'for\s+\w+\s+in\s+.*?:\s*.*?(?:query|select|db\.|execute)',
                'fix': 'Use JOIN or batch queries instead of loop queries'
            },
            'blocking_io': {
                'description': 'Blocking I/O in loop',
                'severity': 'high',
                'pattern': r'for\s+.*?in.*?:\s*.*?(?:requests\.|open\(|socket)',
                'fix': 'Use async/await or thread pool for concurrent I/O'
            },
            'sleep_in_loop': {
                'description': 'Sleep in tight loop',
                'severity': 'medium',
                'pattern': r'while\s*\(|for\s+.*?:\s*.*?sleep\(|Thread\.sleep\(',
                'fix': 'Use event-driven or async approach instead'
            },
            'unoptimized_list': {
                'description': 'List operation in loop',
                'severity': 'medium',
                'pattern': r'for.*?in.*?:\s*.*?(?:list|array)\.(?:append|insert|remove)',
                'fix': 'Pre-allocate array or use set/dict for containment checks'
            },
            'string_concat_loop': {
                'description': 'String concatenation in loop',
                'severity': 'medium',
                'pattern': r'for.*?in.*?:\s*.*?(?:\+=|\.concat|\.join)\s*["\']',
                'fix': 'Use list.join() or StringBuilder instead'
            }
        }

    def analyze_performance(
        self,
        changed_files: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze code for performance antipatterns.

        Args:
            changed_files: List of changed files with content

        Returns:
            Dictionary with performance issues
        """
        analysis = {
            "has_performance_issues": False,
            "performance_issues": [],
            "high_priority_issues": [],
            "memory_leak_risks": [],
            "optimization_opportunities": [],
            "total_issues": 0,
            "severity": "none",  # none, low, medium, high, critical
            "warnings": [],
            "recommendations": []
        }

        for changed_file in changed_files:
            file_path = changed_file.get('path', '')
            content = changed_file.get('content', '')

            if not content or not self._is_code_file(file_path):
                continue

            # Detect various performance issues
            issues = self._detect_antipatterns(file_path, content)
            analysis["performance_issues"].extend(issues)

            # Detect memory issues
            memory_issues = self._detect_memory_issues(file_path, content)
            analysis["memory_leak_risks"].extend(memory_issues)

            # Find optimization opportunities
            opportunities = self._find_optimizations(file_path, content)
            analysis["optimization_opportunities"].extend(opportunities)

        # Categorize issues
        analysis["high_priority_issues"] = [
            i for i in analysis["performance_issues"]
            if i.get('severity') in ['critical', 'high']
        ]

        analysis["total_issues"] = len(analysis["performance_issues"])
        analysis["has_performance_issues"] = analysis["total_issues"] > 0

        # Determine overall severity
        if analysis["memory_leak_risks"]:
            analysis["severity"] = "critical"
        elif analysis["high_priority_issues"]:
            analysis["severity"] = "high"
        elif any(i.get('severity') == 'medium' for i in analysis["performance_issues"]):
            analysis["severity"] = "medium"

        # Generate warnings
        if analysis["severity"] == "critical":
            analysis["warnings"].append(f"⛔ CRITICAL: Memory leak risks detected")
        elif analysis["severity"] == "high":
            analysis["warnings"].append(
                f"⚠️ {len(analysis['high_priority_issues'])} high-priority performance issues found"
            )
        elif analysis["total_issues"] > 0:
            analysis["warnings"].append(
                f"⚡ {analysis['total_issues']} performance optimization opportunity/opportunities"
            )

        # Generate recommendations
        if analysis["memory_leak_risks"]:
            analysis["recommendations"].append("🚨 ACTION: Review and fix memory leak risks immediately")

        if analysis["high_priority_issues"]:
            analysis["recommendations"].append("⚡ OPTIMIZE: High-performance impact issues should be fixed")

        if analysis["optimization_opportunities"]:
            analysis["recommendations"].append(
                f"💡 {len(analysis['optimization_opportunities'])} optimization opportunity/opportunities available"
            )

        if not analysis["has_performance_issues"]:
            analysis["recommendations"].append("✅ CLEAN: No obvious performance issues detected")

        return analysis

    def _is_code_file(self, file_path: str) -> bool:
        """Check if file is a code file."""
        code_extensions = {
            '.py', '.js', '.ts', '.java', '.cs', '.cpp', '.c', '.rb', '.go',
            '.php', '.swift', '.kt', '.rs', '.scala', '.jsx', '.tsx'
        }
        return any(file_path.endswith(ext) for ext in code_extensions)

    def _detect_antipatterns(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """Detect common performance antipatterns."""
        issues = []
        language = self._detect_language(file_path)

        # N+1 Query Detection
        n_plus_one = self._detect_n_plus_one(content, language)
        for issue in n_plus_one:
            issues.append({
                "type": "n_plus_one_query",
                "file": file_path,
                "line": issue.get('line', 'N/A'),
                "severity": "high",
                "description": "N+1 query detected: queries inside loops cause performance issues",
                "impact": "Exponential database load (N queries instead of 1)",
                "fix": "Use JOIN or batch queries to fetch all data in one query",
                "example": "❌ for user_id in user_ids: user = db.query(user_id)  # N queries\n✅ users = db.query(id__in=user_ids)  # 1 query"
            })

        # Blocking I/O Detection
        blocking = self._detect_blocking_io(content, language)
        for issue in blocking:
            issues.append({
                "type": "blocking_io",
                "file": file_path,
                "line": issue.get('line', 'N/A'),
                "severity": "high",
                "description": "Blocking I/O in loop: requests/file I/O inside loops",
                "impact": "Sequential operations cause severe latency",
                "fix": "Use async/await, thread pools, or concurrent requests",
                "example": "❌ for url in urls: response = requests.get(url)  # Sequential\n✅ responses = asyncio.gather(*[aiohttp.get(u) for u in urls])  # Concurrent"
            })

        # String Concatenation in Loop
        string_concat = self._detect_string_concatenation_loop(content, language)
        for issue in string_concat:
            issues.append({
                "type": "string_concatenation_loop",
                "file": file_path,
                "line": issue.get('line', 'N/A'),
                "severity": "medium",
                "description": "String concatenation in loop: creates new strings repeatedly",
                "impact": "O(n²) complexity instead of O(n)",
                "fix": "Use list and join() for Python, StringBuilder for Java",
                "example": "❌ result = ''; [result += str(x) for x in items]  # O(n²)\n✅ result = ''.join(str(x) for x in items)  # O(n)"
            })

        # List mutations in loop
        list_mutations = self._detect_list_mutations(content, language)
        for issue in list_mutations:
            issues.append({
                "type": "inefficient_list_mutation",
                "file": file_path,
                "line": issue.get('line', 'N/A'),
                "severity": "medium",
                "description": "List mutation in loop: resizing array repeatedly",
                "impact": "Costly memory reallocations",
                "fix": "Use pre-allocated arrays or different data structures",
                "example": "❌ result = []; [result.append(x) for x in items]  # Resizing\n✅ result = [None] * len(items); result[i] = x  # Pre-allocated"
            })

        # Sleep in loop
        sleep_issues = self._detect_sleep_in_loop(content, language)
        for issue in sleep_issues:
            issues.append({
                "type": "sleep_in_loop",
                "file": file_path,
                "line": issue.get('line', 'N/A'),
                "severity": "medium",
                "description": "Sleep/delay in loop: blocks execution",
                "impact": "Linear increase in execution time",
                "fix": "Use async delays or event-driven approach",
                "example": "❌ for item in items: time.sleep(1); process(item)  # Days of execution\n✅ Use asyncio.sleep() and concurrent processing"
            })

        return issues

    def _detect_n_plus_one(self, content: str, language: str) -> List[Dict]:
        """Detect N+1 query patterns."""
        issues = []

        # Pattern: for loop with query inside
        patterns = [
            r'for\s+\w+\s+in\s+[\w\.]+:\s*(?:[^}]*?)(query|execute|select|find|get|fetch)[\s\(]',
            r'\.map\s*\(\s*async?\s*\([\w]*\)\s*=>\s*(?:[^}]*?)(?:query|execute|select)',
        ]

        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                # Find line number
                line_num = 1 + content[:content.find(re.search(pattern, content, re.IGNORECASE | re.MULTILINE).group(0) or '')].count('\n')
                issues.append({'line': line_num})

        return issues

    def _detect_blocking_io(self, content: str, language: str) -> List[Dict]:
        """Detect blocking I/O in loops."""
        issues = []

        # Patterns: requests, file operations inside loops
        patterns = [
            r'for\s+[\w]*\s+in\s+[\w\.]+:\s*(?:[^}]*?)(requests\.|open\(|socket|fetch|axios)',
            r'\.forEach\s*\(\s*async?\s*\([\w]*\)\s*=>\s*(?:[^}]*?)requests\.',
        ]

        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                line_num = 1 + content[:content.find(re.search(pattern, content, re.IGNORECASE | re.MULTILINE).group(0) or '')].count('\n')
                issues.append({'line': line_num})

        return issues

    def _detect_string_concatenation_loop(self, content: str, language: str) -> List[Dict]:
        """Detect string concatenation in loops."""
        issues = []

        # Pattern: string += in loop
        pattern = r'for\s+[\w]*\s+in\s+[\w\.]+:[^}]*?(\s*\w+\s*\+=\s*["\']|\+=\s*str\()'

        if re.search(pattern, content, re.MULTILINE):
            line_num = 1 + content[:content.find(re.search(pattern, content, re.MULTILINE).group(0) or '')].count('\n')
            issues.append({'line': line_num})

        return issues

    def _detect_list_mutations(self, content: str, language: str) -> List[Dict]:
        """Detect inefficient list mutations."""
        issues = []

        # Pattern: append in comprehension/loop
        patterns = [
            r'for\s+[\w]*\s+in\s+[\w\.]+:\s*(?:[^}]*?)(\.append\(|\.insert\(|\.remove\()',
            r'\[\s*\w+\s+for\s+[\w]*\s+in\s+[\w\.]+\s*\]',  # List comprehension is OK
        ]

        if re.search(patterns[0], content, re.IGNORECASE | re.MULTILINE):
            line_num = 1 + content[:content.find(re.search(patterns[0], content, re.IGNORECASE | re.MULTILINE).group(0) or '')].count('\n')
            issues.append({'line': line_num})

        return issues

    def _detect_sleep_in_loop(self, content: str, language: str) -> List[Dict]:
        """Detect sleep/delays in loops."""
        issues = []

        # Pattern: sleep inside loop
        pattern = r'(?:for|while)\s*[\(\w\s:]+\s*:\s*(?:[^}]*?)(sleep\(|Thread\.sleep|delay\(|setTimeout)'

        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            line_num = 1 + content[:content.find(re.search(pattern, content, re.IGNORECASE | re.MULTILINE).group(0) or '')].count('\n')
            issues.append({'line': line_num})

        return issues

    def _detect_memory_issues(self, file_path: str, content: str) -> List[Dict]:
        """Detect potential memory leaks."""
        issues = []

        # Detect global state accumulation
        if re.search(r'global\s+\w+.*?(?:\+=|\.append)', content):
            issues.append({
                "type": "global_accumulation",
                "file": file_path,
                "severity": "high",
                "description": "Global variable accumulation can cause memory leaks",
                "suggestion": "Use local scopes or clear data periodically"
            })

        # Detect unclosed resources
        open_count = len(re.findall(r'open\(|connect\(|socket\(', content))
        close_count = len(re.findall(r'close\(|disconnect\(|shutdown\(', content))
        if open_count > close_count:
            issues.append({
                "type": "unclosed_resources",
                "file": file_path,
                "severity": "medium",
                "description": f"{open_count - close_count} resource(s) opened without guaranteed closure",
                "suggestion": "Use context managers (with statement) or try/finally"
            })

        # Detect circular references
        if re.search(r'self\.\w+\s*=\s*.*?self|this\.\w+\s*=\s*.*?this', content):
            issues.append({
                "type": "potential_circular_reference",
                "file": file_path,
                "severity": "low",
                "description": "Possible circular reference that could leak memory",
                "suggestion": "Use weak references if needed"
            })

        return issues

    def _find_optimizations(self, file_path: str, content: str) -> List[Dict]:
        """Find optimization opportunities."""
        opportunities = []

        # Missing caching
        if re.search(r'(?:def|function|public)\s+\w+.*?(?:query|fetch|calculate|compute)', content) and not re.search(r'cache|memo|@lru_cache', content):
            opportunities.append({
                "type": "missing_caching",
                "file": file_path,
                "severity": "low",
                "description": "Expensive operations could benefit from caching",
                "suggestion": "Add memoization or caching (redis, lru_cache, etc.)"
            })

        # Inefficient algorithms
        if re.search(r'for\s+[\w]*\s+in\s+.*?:\s*for\s+[\w]*\s+in', content):
            opportunities.append({
                "type": "nested_loops",
                "file": file_path,
                "severity": "low",
                "description": "Nested loops have O(n²) complexity",
                "suggestion": "Consider using sets, dicts, or sorting for O(n log n) or O(n)"
            })

        # Unoptimized regex
        if content.count('re.search') > 3 or content.count('re.match') > 3:
            opportunities.append({
                "type": "regex_compilation",
                "file": file_path,
                "severity": "low",
                "description": f"Compiling regex multiple times is inefficient",
                "suggestion": "Pre-compile regex patterns: pattern = re.compile(...)"
            })

        return opportunities[:3]  # Return top 3

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        if file_path.endswith('.py'):
            return 'python'
        elif file_path.endswith(('.js', '.ts')):
            return 'javascript'
        elif file_path.endswith('.java'):
            return 'java'
        return 'python'

    def get_performance_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Get actionable performance recommendations."""
        recommendations = []

        if analysis["severity"] == "critical":
            recommendations.append("🔥 CRITICAL: Memory leak risks must be fixed before merge")

        elif analysis["severity"] == "high":
            recommendations.append("⚡ OPTIMIZE: High-impact performance issues should be addressed")

        if analysis["high_priority_issues"]:
            issue_type = analysis["high_priority_issues"][0]["type"].replace('_', ' ').title()
            recommendations.append(f"🎯 PRIORITY: Fix {issue_type} first")

        if analysis["optimization_opportunities"]:
            recommendations.append("💡 TIP: Consider the optimization opportunities listed")

        if not analysis["has_performance_issues"]:
            recommendations.append("✅ FAST: No performance antipatterns detected")

        return recommendations


# Global instance
performance_analyzer = PerformanceAnalyzer()
