"""
Code Complexity Metrics Analyzer

Calculates cyclomatic complexity, cognitive complexity, and maintainability index.
Warns when complexity exceeds healthy thresholds.
"""

import re
import logging
from typing import Dict, List, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class ComplexityAnalyzer:
    """Analyzes code complexity metrics."""

    def __init__(self):
        """Initialize complexity analyzer."""
        # Complexity thresholds
        self.thresholds = {
            'cyclomatic': {'ideal': 5, 'acceptable': 10, 'risky': 15},
            'cognitive': {'ideal': 5, 'acceptable': 10, 'risky': 15},
            'maintainability': {'ideal': 70, 'acceptable': 50, 'risky': 40},
            'lines_of_code': {'ideal': 300, 'acceptable': 500, 'risky': 1000}
        }

    def analyze_complexity(
        self,
        changed_files: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze code complexity metrics for changed files.

        Args:
            changed_files: List of changed files with content

        Returns:
            Dictionary with complexity analysis
        """
        analysis = {
            "has_complexity_issues": False,
            "files_analyzed": 0,
            "high_complexity_files": [],
            "cognitive_complexity_files": [],
            "maintainability_issues": [],
            "average_complexity": 0,
            "overall_health": "good",  # good, acceptable, risky
            "warnings": [],
            "recommendations": []
        }

        all_metrics = []

        for changed_file in changed_files:
            file_path = changed_file.get('path', '')
            content = changed_file.get('content', '')

            if not content or not self._is_code_file(file_path):
                continue

            analysis["files_analyzed"] += 1

            # Calculate metrics for this file
            metrics = self._calculate_metrics(file_path, content)
            all_metrics.append(metrics)

            # Check for complexity issues
            if metrics['cyclomatic'] > self.thresholds['cyclomatic']['risky']:
                analysis["high_complexity_files"].append({
                    "file": file_path,
                    "cyclomatic_complexity": metrics['cyclomatic'],
                    "threshold": self.thresholds['cyclomatic']['risky'],
                    "functions": metrics['high_complexity_functions'],
                    "severity": "critical",
                    "suggestion": "Refactor: Break into smaller functions or extract helper methods"
                })

            elif metrics['cyclomatic'] > self.thresholds['cyclomatic']['acceptable']:
                analysis["high_complexity_files"].append({
                    "file": file_path,
                    "cyclomatic_complexity": metrics['cyclomatic'],
                    "threshold": self.thresholds['cyclomatic']['acceptable'],
                    "functions": metrics['high_complexity_functions'],
                    "severity": "high",
                    "suggestion": "Consider refactoring for better maintainability"
                })

            # Check cognitive complexity
            if metrics['cognitive'] > self.thresholds['cognitive']['risky']:
                analysis["cognitive_complexity_files"].append({
                    "file": file_path,
                    "cognitive_complexity": metrics['cognitive'],
                    "threshold": self.thresholds['cognitive']['risky'],
                    "complex_sections": metrics['complex_sections'],
                    "severity": "high",
                    "suggestion": "Too many nested conditions - refactor logic flow"
                })

            # Track maintainability
            if metrics['maintainability_index'] < self.thresholds['maintainability']['risky']:
                analysis["maintainability_issues"].append({
                    "file": file_path,
                    "index": metrics['maintainability_index'],
                    "threshold": self.thresholds['maintainability']['risky'],
                    "factors": metrics['maintainability_factors'],
                    "suggestion": "Code is difficult to maintain - prioritize refactoring"
                })

        # Calculate summary metrics
        if all_metrics:
            avg_complexity = sum(m['cyclomatic'] for m in all_metrics) / len(all_metrics)
            analysis["average_complexity"] = round(avg_complexity, 2)

            # Determine overall health
            if len(analysis["high_complexity_files"]) > 0:
                analysis["overall_health"] = "risky"
            elif avg_complexity > self.thresholds['cyclomatic']['acceptable']:
                analysis["overall_health"] = "acceptable"
            else:
                analysis["overall_health"] = "good"

        analysis["has_complexity_issues"] = len(analysis["high_complexity_files"]) > 0

        # Generate warnings and recommendations
        if analysis["has_complexity_issues"]:
            analysis["warnings"].append(
                f"⚠️ {len(analysis['high_complexity_files'])} file(s) exceed complexity thresholds"
            )
            analysis["recommendations"].append("🔧 REFACTOR: Break complex functions into smaller units")
            analysis["recommendations"].append("💡 TIP: Aim for cyclomatic complexity < 10")

        if analysis["cognitive_complexity_files"]:
            analysis["warnings"].append(
                f"🧠 {len(analysis['cognitive_complexity_files'])} file(s) have high cognitive complexity"
            )
            analysis["recommendations"].append("📚 SIMPLIFY: Reduce nesting and conditional branches")

        if analysis["maintainability_issues"]:
            analysis["warnings"].append(
                f"⚙️ {len(analysis['maintainability_issues'])} file(s) have low maintainability"
            )
            analysis["recommendations"].append("🎯 PRIORITY: Focus refactoring on low maintainability files")

        if analysis["overall_health"] == "good":
            analysis["recommendations"].append("✅ HEALTHY: Complexity metrics are within acceptable range")

        return analysis

    def _is_code_file(self, file_path: str) -> bool:
        """Check if file is a code file."""
        code_extensions = {
            '.py', '.js', '.ts', '.java', '.cs', '.cpp', '.c', '.rb', '.go',
            '.php', '.swift', '.kt', '.rs', '.scala', '.jsx', '.tsx'
        }
        return any(file_path.endswith(ext) for ext in code_extensions)

    def _calculate_metrics(self, file_path: str, content: str) -> Dict[str, Any]:
        """Calculate all complexity metrics for a file."""
        metrics = {
            'file': file_path,
            'cyclomatic': self._calculate_cyclomatic_complexity(content),
            'cognitive': self._calculate_cognitive_complexity(content),
            'maintainability_index': self._calculate_maintainability_index(content),
            'maintainability_factors': self._get_maintainability_factors(content),
            'high_complexity_functions': self._find_complex_functions(content, file_path),
            'complex_sections': self._find_complex_sections(content),
            'lines_of_code': len(content.split('\n')),
            'functions_count': len(re.findall(r'^\s*(?:def|function|public\s+\w+)\s+\w+', content, re.MULTILINE))
        }
        return metrics

    def _calculate_cyclomatic_complexity(self, content: str) -> int:
        """
        Calculate cyclomatic complexity using decision point counting.
        CC = decision points + 1
        """
        # Decision points: if, for, while, case, catch, logical operators
        decision_points = 0

        # Count control structures
        decision_points += len(re.findall(r'\bif\b', content, re.IGNORECASE))
        decision_points += len(re.findall(r'\belif\b|\belse if\b', content, re.IGNORECASE))
        decision_points += len(re.findall(r'\bfor\b', content, re.IGNORECASE))
        decision_points += len(re.findall(r'\bwhile\b', content, re.IGNORECASE))
        decision_points += len(re.findall(r'\bcase\b', content, re.IGNORECASE))
        decision_points += len(re.findall(r'\bcatch\b', content, re.IGNORECASE))
        decision_points += len(re.findall(r'\btry\b', content, re.IGNORECASE))

        # Count logical operators (each adds complexity)
        decision_points += len(re.findall(r'\s+and\s+|\s+or\s+|\s*\&\&\s*|\s*\|\|\s*', content))

        # Add ternary operators
        decision_points += len(re.findall(r'\?\s*.*?\s*:', content))

        return max(1, decision_points + 1)

    def _calculate_cognitive_complexity(self, content: str) -> int:
        """
        Calculate cognitive complexity (harder to understand).
        Similar to cyclomatic but weights nesting higher.
        """
        complexity = 0
        nesting_level = 0

        for line in content.split('\n'):
            stripped = line.strip()

            # Increase nesting for block starters
            if any(kw in stripped for kw in ['if ', 'for ', 'while ', 'try:', 'def ', 'class ']):
                nesting_level += 1
                # Add base complexity plus nesting weight
                complexity += 1 + (nesting_level * 0.5)

            # Decrease nesting for block enders
            if any(pattern in stripped for pattern in ['}', 'except:', 'finally:', 'else:']):
                nesting_level = max(0, nesting_level - 1)

            # Extra weight for deeply nested conditions
            if nesting_level > 3:
                complexity += nesting_level * 0.5

        return int(complexity)

    def _calculate_maintainability_index(self, content: str) -> float:
        """
        Calculate maintainability index (0-100, higher is better).
        Based on: LOC, cyclomatic complexity, comments
        """
        lines = len(content.split('\n'))
        cc = self._calculate_cyclomatic_complexity(content)
        comments = len(re.findall(r'#|//|/\*|\*/', content))

        # Simplified maintainability formula
        # MI = 171 - 5.2 * ln(Halstead Volume) - 0.23 * CC - 16.2 * ln(LOC) + 50 * sqrt(2.4 * Comments%)
        if lines < 2 or cc < 1:
            return 100

        comment_ratio = comments / max(1, lines / 100)
        mi = 171 - (5.2 * (lines * 0.5)) - (0.23 * cc) - (16.2 * (lines / 100))
        mi += (50 * (comment_ratio ** 0.5)) if comment_ratio > 0 else 0

        return max(0, min(100, mi))

    def _get_maintainability_factors(self, content: str) -> List[str]:
        """Get factors affecting maintainability."""
        factors = []

        lines = len(content.split('\n'))
        if lines > self.thresholds['lines_of_code']['risky']:
            factors.append("Large file (>1000 LOC)")
        elif lines > self.thresholds['lines_of_code']['acceptable']:
            factors.append("Medium-sized file (>500 LOC)")

        cc = self._calculate_cyclomatic_complexity(content)
        if cc > self.thresholds['cyclomatic']['risky']:
            factors.append("High cyclomatic complexity")

        comments = len(re.findall(r'#|//|/\*|\*/', content)) / max(1, len(content.split('\n')))
        if comments < 0.02:
            factors.append("Low comment ratio (<2%)")

        # Check for long functions
        functions = re.findall(r'(?:def|function|public)\s+\w+.*?(?=\n(?:def|function|public)|$)', content, re.DOTALL)
        for func in functions[:3]:  # Check first 3
            func_lines = len(func.split('\n'))
            if func_lines > 50:
                factors.append("Long function detected")
                break

        # Check for duplicate code patterns
        lines_list = [l.strip() for l in content.split('\n') if l.strip()]
        if len(lines_list) > 10:
            duplicates = len([l for l in lines_list if lines_list.count(l) > 2])
            if duplicates > len(lines_list) * 0.1:
                factors.append("Possible code duplication")

        return factors

    def _find_complex_functions(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Find functions with high complexity."""
        complex_funcs = []

        # Extract functions with their content
        patterns = [
            (r'def\s+(\w+)\s*\([^)]*\):[^}]*?(?=\ndef|\Z)', 'python'),
            (r'function\s+(\w+)\s*\([^)]*\)\s*\{[^}]*\}', 'js'),
            (r'public\s+(?:\w+\s+)?(\w+)\s*\([^)]*\)\s*\{[^}]*\}', 'java'),
        ]

        for pattern, lang in patterns:
            for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                func_name = match.group(1)
                func_content = match.group(0)

                cc = self._calculate_cyclomatic_complexity(func_content)
                if cc > self.thresholds['cyclomatic']['acceptable']:
                    complex_funcs.append({
                        "name": func_name,
                        "complexity": cc,
                        "lines": len(func_content.split('\n')),
                        "suggestion": f"Refactor `{func_name}()` - complexity is {cc}"
                    })

        return complex_funcs[:5]  # Return top 5

    def _find_complex_sections(self, content: str) -> List[Dict[str, Any]]:
        """Find complex code sections (nested conditions, loops, etc)."""
        sections = []
        lines = content.split('\n')
        nesting_depth = 0
        max_nesting = 0
        nesting_start = 0

        for i, line in enumerate(lines, 1):
            # Track nesting depth
            opening = line.count('{') + line.count('[') + line.count('(')
            closing = line.count('}') + line.count(']') + line.count(')')

            if opening > closing and nesting_depth == 0:
                nesting_start = i

            nesting_depth = max(0, nesting_depth + opening - closing)

            if nesting_depth > max_nesting:
                max_nesting = nesting_depth

            if nesting_depth > 3:  # Flag deeply nested sections
                sections.append({
                    "line": i,
                    "nesting_depth": nesting_depth,
                    "severity": "high" if nesting_depth > 5 else "medium"
                })

        return sections[:5]  # Return top 5

    def get_refactoring_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """Get actionable refactoring suggestions."""
        suggestions = []

        if analysis["overall_health"] == "risky":
            suggestions.append("🛑 CRITICAL: Multiple complexity issues detected")
            suggestions.append("🔧 REFACTOR: Consider breaking large functions into smaller units")

        elif analysis["overall_health"] == "acceptable":
            suggestions.append("⚠️ WARNING: Some files exceed complexity thresholds")
            suggestions.append("💡 TODO: Plan refactoring in next sprint")

        if analysis["high_complexity_files"]:
            suggestions.append(f"📍 FOCUS: {analysis['high_complexity_files'][0]['file']} needs refactoring first")

        # Specific techniques
        if analysis["cognitive_complexity_files"]:
            suggestions.append("🧠 TECHNIQUE: Extract helper methods to reduce nesting")
            suggestions.append("💡 TIP: Move complex logic to separate functions")

        suggestions.append(f"📊 METRIC: Average complexity is {analysis['average_complexity']} (target: <5)")

        return suggestions


# Global instance
complexity_analyzer = ComplexityAnalyzer()
