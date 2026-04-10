"""
Test Coverage Impact Analyzer

Detects if code changes have corresponding test updates,
warning when risky changes lack test coverage.
"""

import re
import logging
from typing import Dict, List, Set, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class TestCoverageAnalyzer:
    """Analyzes test coverage for code changes."""

    def __init__(self):
        """Initialize test coverage analyzer."""
        self.test_patterns = {
            'python': {
                'test_dirs': ['tests', 'test', 'testing'],
                'test_files': r'^test_.*\.py$|^.*_test\.py$',
                'test_methods': r'def\s+test_\w+|def\s+setUp|def\s+tearDown',
                'assertions': r'assert\s+|assertEqual|assertTrue|assertFalse|assertIn|assertRaises|self\.assert',
                'mocks': r'@mock\.|@patch|Mock\(|MagicMock\(|patch\('
            },
            'javascript': {
                'test_dirs': ['tests', 'test', '__tests__', 'spec'],
                'test_files': r'\.test\.js$|\.spec\.js$',
                'test_methods': r'describe\(|it\(|test\(',
                'assertions': r'expect\(|assert\.|should\.',
                'mocks': r'jest\.mock|sinon\.stub|proxyquire'
            },
            'java': {
                'test_dirs': ['src/test', 'test'],
                'test_files': r'^.*Test\.java$',
                'test_methods': r'@Test|@Override.*void\s+test',
                'assertions': r'assertTrue|assertFalse|assertEquals|assertThrows',
                'mocks': r'@Mock|Mockito\.mock|new MockedStatic'
            }
        }

    def analyze_test_coverage(
        self,
        changed_files: List[Dict[str, Any]],
        all_files: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Analyze if code changes have corresponding test updates.

        Args:
            changed_files: List of changed file objects with path and content
            all_files: Dictionary of all project files for context

        Returns:
            Dictionary with coverage analysis results
        """
        analysis = {
            "has_tests": False,
            "test_coverage_level": "not_tested",  # not_tested, partial, good, excellent
            "coverage_percentage": 0,
            "test_files": [],
            "risky_untested_changes": [],
            "recommendations": [],
            "warnings": []
        }

        all_files = all_files or {}

        # Detect language from changed files
        languages = self._detect_languages([f.get('path', '') for f in changed_files])

        # Identify test files in the project
        test_files = self._find_test_files(all_files, languages)
        analysis["test_files"] = list(test_files)

        if not test_files:
            analysis["warnings"].append("⚠️ No test files detected in the project!")
            analysis["recommendations"].append("🎯 ADD TESTS: Project has no automated tests. This is a critical gap.")
            return analysis

        # Analyze coverage for each changed file
        high_risk_files = []
        moderate_risk_files = []

        for changed_file in changed_files:
            file_path = changed_file.get('path', '')
            content = changed_file.get('content', '')
            language = self._detect_file_language(file_path)

            # Skip test files themselves
            if self._is_test_file(file_path, languages.get(language, {})):
                continue

            # Check if there's a corresponding test file
            corresponding_tests = self._find_corresponding_tests(file_path, test_files, language)

            if not corresponding_tests:
                # No test file for this code file
                risk_level = self._assess_risk_level(file_path, content)
                if risk_level == "high":
                    high_risk_files.append({
                        "file": file_path,
                        "reason": "Critical logic change with no tests",
                        "suggestions": [
                            f"Create test file: {self._suggest_test_file(file_path)}",
                            "Add unit tests for all public functions",
                            "Include edge case testing"
                        ]
                    })
                else:
                    moderate_risk_files.append({
                        "file": file_path,
                        "reason": "No test coverage for this file",
                        "suggestions": [f"Create/update: {self._suggest_test_file(file_path)}"]
                    })
            else:
                # Check if test file is being updated
                test_updated = any(
                    t in [f.get('path', '') for f in changed_files]
                    for t in corresponding_tests
                )

                if not test_updated and self._has_logic_changes(content):
                    moderate_risk_files.append({
                        "file": file_path,
                        "reason": "Logic changed but tests not updated",
                        "test_file": corresponding_tests[0],
                        "suggestions": [
                            "Update corresponding test file",
                            "Add tests for new functionality",
                            "Update existing test cases"
                        ]
                    })

        analysis["risky_untested_changes"] = high_risk_files + moderate_risk_files

        # Calculate coverage percentage
        total_code_files = sum(
            1 for f in changed_files
            if not self._is_test_file(f.get('path', ''), self.test_patterns)
        )

        if total_code_files > 0:
            tested_files = total_code_files - len(analysis["risky_untested_changes"])
            coverage_percentage = int((tested_files / total_code_files) * 100)
            analysis["coverage_percentage"] = max(0, min(100, coverage_percentage))

            if coverage_percentage == 100:
                analysis["test_coverage_level"] = "excellent"
            elif coverage_percentage >= 80:
                analysis["test_coverage_level"] = "good"
            elif coverage_percentage >= 50:
                analysis["test_coverage_level"] = "partial"
            else:
                analysis["test_coverage_level"] = "not_tested"
        else:
            analysis["test_coverage_level"] = "not_applicable"

        analysis["has_tests"] = len(high_risk_files) == 0

        # Generate recommendations
        if high_risk_files:
            analysis["recommendations"].append(f"🛑 CRITICAL: {len(high_risk_files)} file(s) with high-risk logic have NO test coverage")
            analysis["recommendations"].append("⚠️ ACTION: Create tests before merging these files")

        if moderate_risk_files:
            analysis["recommendations"].append(f"⚠️ WARNING: {len(moderate_risk_files)} file(s) lack proper test coverage")

        if analysis["coverage_percentage"] >= 80:
            analysis["recommendations"].append(f"✅ GOOD: Test coverage at {analysis['coverage_percentage']}% - keep it up!")

        return analysis

    def _detect_languages(self, file_paths: List[str]) -> Dict[str, Dict]:
        """Detect programming languages from file extensions."""
        languages_found = {}
        for path in file_paths:
            lang = self._detect_file_language(path)
            if lang in self.test_patterns:
                languages_found[lang] = self.test_patterns[lang]
        return languages_found or {"python": self.test_patterns["python"]}

    def _detect_file_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        if file_path.endswith('.py'):
            return 'python'
        elif file_path.endswith(('.js', '.ts', '.jsx', '.tsx')):
            return 'javascript'
        elif file_path.endswith('.java'):
            return 'java'
        return 'python'  # Default

    def _is_test_file(self, file_path: str, patterns: Dict = None) -> bool:
        """Check if file is a test file."""
        if not patterns:
            lang = self._detect_file_language(file_path)
            patterns = self.test_patterns.get(lang, {})

        test_file_pattern = patterns.get('test_files', '')
        test_dirs = patterns.get('test_dirs', [])

        # Check filename pattern
        if re.search(test_file_pattern, Path(file_path).name):
            return True

        # Check directory
        for test_dir in test_dirs:
            if f"/{test_dir}/" in f"/{file_path}" or file_path.startswith(f"{test_dir}/"):
                return True

        return False

    def _find_test_files(self, all_files: Dict[str, str], languages: Dict) -> Set[str]:
        """Find all test files in the project."""
        test_files = set()

        for file_path in all_files.keys():
            for lang_patterns in languages.values():
                if self._is_test_file(file_path, lang_patterns):
                    test_files.add(file_path)

        return test_files

    def _find_corresponding_tests(
        self,
        file_path: str,
        test_files: Set[str],
        language: str
    ) -> List[str]:
        """Find corresponding test files for a code file."""
        corresponding = []

        # Try various naming conventions
        base_name = Path(file_path).stem
        base_dir = str(Path(file_path).parent)

        for test_file in test_files:
            test_stem = Path(test_file).stem
            test_dir = str(Path(test_file).parent)

            # Match: original.py <-> test_original.py, original_test.py
            if base_name in test_stem or test_stem in base_name:
                corresponding.append(test_file)

            # Match: src/utils/helper.py <-> tests/utils/test_helper.py
            if base_name.replace('_', '') in test_stem.replace('_', ''):
                corresponding.append(test_file)

        return list(set(corresponding))

    def _assess_risk_level(self, file_path: str, content: str) -> str:
        """Assess risk level of changes in a file."""
        # High risk indicators
        high_risk_patterns = [
            r'user_id|password|secret|api_key|token',  # Security
            r'database|query|insert|update|delete',  # Database
            r'authenticate|authorize|permission',  # Auth
            r'payment|stripe|charge|transaction',  # Payment
            r'async def|await',  # Async logic
        ]

        risk_score = 0
        for pattern in high_risk_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                risk_score += 1

        # File path risk indicators
        risky_paths = ['auth', 'security', 'payment', 'core', 'api', 'db']
        for risky_path in risky_paths:
            if risky_path in file_path.lower():
                risk_score += 1

        if risk_score >= 3:
            return "high"
        elif risk_score >= 1:
            return "moderate"
        else:
            return "low"

    def _has_logic_changes(self, content: str) -> bool:
        """Check if content has logic changes (not just comments/formatting)."""
        # Look for function/method definitions
        if re.search(r'def\s+\w+|function\s+\w+|public\s+\w+', content):
            return True

        # Look for control flow changes
        if re.search(r'if\s+|for\s+|while\s+|try:|except|switch|case', content):
            return True

        return len(content.strip()) > 50

    def _suggest_test_file(self, file_path: str) -> str:
        """Suggest a test file name for a code file."""
        path = Path(file_path)
        stem = path.stem

        lang = self._detect_file_language(file_path)

        if lang == 'python':
            return f"tests/test_{stem}.py"
        elif lang == 'javascript':
            return f"tests/{stem}.test.js"
        elif lang == 'java':
            return f"src/test/java/{stem}Test.java"

        return f"tests/test_{stem}"

    def get_test_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Get actionable test recommendations."""
        recommendations = []

        if analysis["coverage_percentage"] < 50:
            recommendations.append("🚨 CRITICAL: Test coverage below 50% - prioritize test creation")
        elif analysis["coverage_percentage"] < 80:
            recommendations.append("⚠️ WARNING: Test coverage below 80% - add more tests")

        risky_count = len(analysis.get("risky_untested_changes", []))
        if risky_count > 0:
            recommendations.append(f"❌ {risky_count} file(s) lack test coverage - block merge until tests are added")

        if not analysis["test_files"]:
            recommendations.append("🎯 TODO: Establish testing infrastructure (create test directory, add test runner)")

        return recommendations


# Global instance
test_coverage_analyzer = TestCoverageAnalyzer()
