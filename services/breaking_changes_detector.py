"""
Breaking Changes Detector

Identifies API signature changes, removed functions, schema changes,
and other modifications that could break dependent code.
"""

import re
import logging
from typing import Dict, List, Any, Tuple, Set
from pathlib import Path

logger = logging.getLogger(__name__)


class BreakingChangesDetector:
    """Detects breaking changes in code modifications."""

    def __init__(self):
        """Initialize breaking changes detector."""
        self.breaking_patterns = {
            'python': {
                'removed_function': r'^\s*def\s+(\w+)\s*\(',
                'changed_signature': r'def\s+(\w+)\s*\(([^)]*)\)',
                'removed_class': r'^\s*class\s+(\w+)',
                'removed_import': r'^\s*(?:from|import)\s+',
                'removed_constant': r'^\s*([A-Z_]+)\s*=',
            },
            'javascript': {
                'removed_function': r'(?:export\s+)?(?:async\s+)?(?:function|const|let|var)\s+(\w+)',
                'changed_signature': r'(?:function|const|let|var)\s+(\w+)\s*(?:=|:|\().*?\(',
                'removed_class': r'(?:export\s+)?class\s+(\w+)',
                'removed_export': r'export\s+(?:default\s+)?',
                'removed_import': r'import\s+.*?\s+from|import\s+',
            },
            'java': {
                'removed_class': r'public\s+(?:final\s+)?class\s+(\w+)',
                'removed_method': r'public\s+(?:static\s+)?(?:\w+)?\s+(\w+)\s*\(',
                'removed_interface': r'public\s+interface\s+(\w+)',
                'removed_annotation': r'@\w+',
            }
        }

    def detect_breaking_changes(
        self,
        changed_files: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Detect breaking changes in code modifications.

        Args:
            changed_files: List of changed files with old/new content

        Returns:
            Dictionary with breaking changes analysis
        """
        analysis = {
            "has_breaking_changes": False,
            "breaking_changes_count": 0,
            "severity": "none",  # none, low, medium, high, critical
            "breaking_changes": [],
            "warnings": [],
            "recommendations": []
        }

        for changed_file in changed_files:
            file_path = changed_file.get('path', '')
            old_content = changed_file.get('old_content', '')
            new_content = changed_file.get('content', '') or changed_file.get('new_content', '')

            if not old_content:
                # No old content means new file - no breaking changes
                continue

            language = self._detect_language(file_path)

            # Detect specific breaking changes
            breaking = self._analyze_changes(
                file_path,
                old_content,
                new_content,
                language
            )

            if breaking:
                analysis["breaking_changes"].extend(breaking)

        # Calculate results
        analysis["breaking_changes_count"] = len(analysis["breaking_changes"])
        analysis["has_breaking_changes"] = analysis["breaking_changes_count"] > 0

        if analysis["breaking_changes_count"] > 0:
            # Determine severity
            critical_count = sum(
                1 for c in analysis["breaking_changes"]
                if c.get('severity') == 'critical'
            )
            high_count = sum(
                1 for c in analysis["breaking_changes"]
                if c.get('severity') == 'high'
            )

            if critical_count > 0:
                analysis["severity"] = "critical"
                analysis["warnings"].append(f"🚨 {critical_count} CRITICAL breaking change(s) detected")
            elif high_count > 0:
                analysis["severity"] = "high"
                analysis["warnings"].append(f"⚠️ {high_count} HIGH-RISK breaking change(s) detected")
            else:
                analysis["severity"] = "medium"

            analysis["recommendations"].append("❌ BREAKING: Must bump major version and notify users")
            analysis["recommendations"].append("📝 ACTION: Document migration path for consumers")
            analysis["recommendations"].append("⚠️ RISK: This change will break dependent code")

        return analysis

    def _analyze_changes(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        language: str
    ) -> List[Dict[str, Any]]:
        """Analyze specific breaking changes between old and new content."""
        breaking = []

        # Parse old and new content to find removed/changed elements
        old_items = self._extract_public_items(old_content, language)
        new_items = self._extract_public_items(new_content, language)

        # Detect removed items (breaking)
        removed_items = old_items - new_items
        for item in removed_items:
            breaking.append({
                "type": "removed_" + self._classify_item(item, old_content),
                "name": item,
                "file": file_path,
                "severity": self._assess_removal_severity(item, old_content),
                "impact": f"Consumers relying on `{item}()` will experience failures",
                "fix": f"Add deprecation notice before removing: @deprecated or @Deprecated"
            })

        # Detect changed signatures (breaking)
        signature_changes = self._detect_signature_changes(old_content, new_content, language)
        for change in signature_changes:
            breaking.append({
                "type": "signature_changed",
                "name": change['name'],
                "file": file_path,
                "old_signature": change['old_signature'],
                "new_signature": change['new_signature'],
                "severity": "high",
                "impact": "Function signature changed - all callers must be updated",
                "fix": f"Provide backward compatibility or deprecation path"
            })

        # Detect schema changes (if applicable)
        schema_changes = self._detect_schema_changes(old_content, new_content, file_path)
        breaking.extend(schema_changes)

        # Detect removed constants/configs (potentially breaking)
        removed_constants = self._detect_removed_constants(old_content, new_content, language)
        for constant in removed_constants:
            breaking.append({
                "type": "removed_constant",
                "name": constant,
                "file": file_path,
                "severity": "medium",
                "impact": f"Code using constant `{constant}` will fail",
                "fix": "Export constant for backward compatibility period"
            })

        return breaking

    def _extract_public_items(self, content: str, language: str) -> Set[str]:
        """Extract public functions/classes/methods."""
        items = set()

        patterns = self.breaking_patterns.get(language, {})

        # Find function definitions
        for match in re.finditer(patterns.get('removed_function', r''), content, re.MULTILINE):
            items.add(match.group(1))

        # Find class definitions
        for match in re.finditer(patterns.get('removed_class', r''), content, re.MULTILINE):
            items.add(match.group(1))

        return items

    def _classify_item(self, item: str, content: str) -> str:
        """Classify if item is function, class, or method."""
        # Look for class definition
        if re.search(rf'class\s+{item}\s*[\(:]', content):
            return "class"
        # Look for async function
        elif re.search(rf'async\s+def\s+{item}\s*\(', content):
            return "async_function"
        # Look for method (in a class context)
        elif "    def " in content and f"def {item}" in content:
            return "method"
        else:
            return "function"

    def _assess_removal_severity(self, item: str, content: str) -> str:
        """Assess severity of removing an item."""
        # Higher severity for commonly used patterns
        if item.startswith('_'):
            return "low"  # Private items are less likely to be used
        elif item in ['__init__', '__main__', 'setup', 'teardown']:
            return "low"
        elif re.search(rf'@deprecated|warnings\.warn.*{item}', content):
            return "medium"  # Already marked for deprecation
        else:
            return "critical"  # Public API removal

    def _detect_signature_changes(
        self,
        old_content: str,
        new_content: str,
        language: str
    ) -> List[Dict[str, Any]]:
        """Detect function/method signature changes."""
        changes = []

        # Find function signatures in old content
        old_sigs = self._extract_function_signatures(old_content, language)
        new_sigs = self._extract_function_signatures(new_content, language)

        # Compare signatures
        for func_name in old_sigs:
            if func_name in new_sigs:
                if old_sigs[func_name] != new_sigs[func_name]:
                    changes.append({
                        "name": func_name,
                        "old_signature": old_sigs[func_name],
                        "new_signature": new_sigs[func_name]
                    })

        return changes

    def _extract_function_signatures(self, content: str, language: str) -> Dict[str, str]:
        """Extract function signatures from content."""
        signatures = {}

        if language == 'python':
            pattern = r'def\s+(\w+)\s*\(([^)]*)\)'
        elif language == 'javascript':
            pattern = r'(?:async\s+)?(?:function|const|let|var)\s+(\w+)\s*\(([^)]*)\)'
        elif language == 'java':
            pattern = r'public\s+(?:static\s+)?(\w+)\s+(\w+)\s*\(([^)]*)\)'
        else:
            return signatures

        for match in re.finditer(pattern, content, re.MULTILINE):
            if language == 'java':
                func_name = match.group(2)
                params = match.group(3)
            else:
                func_name = match.group(1)
                params = match.group(2)

            signatures[func_name] = params.strip()

        return signatures

    def _detect_schema_changes(
        self,
        old_content: str,
        new_content: str,
        file_path: str
    ) -> List[Dict[str, Any]]:
        """Detect schema/data model changes (primarily for Python dataclasses/Pydantic)."""
        changes = []

        # Look for removed fields in dataclasses or Pydantic models
        old_fields = self._extract_model_fields(old_content)
        new_fields = self._extract_model_fields(new_content)

        removed_fields = set(old_fields.keys()) - set(new_fields.keys())
        for field in removed_fields:
            changes.append({
                "type": "removed_field",
                "name": field,
                "file": file_path,
                "severity": "high",
                "impact": f"Existing data with field `{field}` will cause deserialization errors",
                "fix": "Keep field as optional/deprecated for backward compatibility"
            })

        # Look for required field changes
        for field in new_fields:
            if field in old_fields:
                if old_fields[field].get('required', True) != new_fields[field].get('required', True):
                    if new_fields[field].get('required'):
                        changes.append({
                            "type": "field_became_required",
                            "name": field,
                            "file": file_path,
                            "severity": "high",
                            "impact": f"Field `{field}` is now required - old records will fail validation",
                            "fix": "Provide a default value or migration path"
                        })

        return changes

    def _extract_model_fields(self, content: str) -> Dict[str, Dict]:
        """Extract fields from dataclasses or Pydantic models."""
        fields = {}

        # Pydantic/dataclass field patterns
        patterns = [
            r'(\w+):\s*(\w+)(?:\s*=\s*Field\()?',  # Annotated fields
            r'(\w+):\s*Optional\[(\w+)\]',  # Optional fields
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, content):
                field_name = match.group(1)
                field_type = match.group(2)
                # Check if field has a default value
                has_default = '=' in content[max(0, match.end() - 20):match.end() + 20]
                fields[field_name] = {
                    'type': field_type,
                    'required': not has_default and 'Optional' not in field_type
                }

        return fields

    def _detect_removed_constants(
        self,
        old_content: str,
        new_content: str,
        language: str
    ) -> List[str]:
        """Detect removed constants/configuration values."""
        removed = []

        # Find constants in old content
        if language == 'python':
            pattern = r'^([A-Z_][A-Z0-9_]*)\s*='
        elif language == 'javascript':
            pattern = r'(?:const|var)\s+([A-Z_][A-Z0-9_]*)\s*='
        else:
            return removed

        old_constants = set(
            m.group(1) for m in re.finditer(pattern, old_content, re.MULTILINE)
        )
        new_constants = set(
            m.group(1) for m in re.finditer(pattern, new_content, re.MULTILINE)
        )

        return list(old_constants - new_constants)

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        if file_path.endswith('.py'):
            return 'python'
        elif file_path.endswith(('.js', '.ts')):
            return 'javascript'
        elif file_path.endswith('.java'):
            return 'java'
        return 'python'

    def get_breaking_change_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Get actionable recommendations for breaking changes."""
        recommendations = []

        if analysis["severity"] == "critical":
            recommendations.append("🛑 ACTION REQUIRED: Critical breaking changes must be resolved before merge")
            recommendations.append("📌 Plan: Version bump, deprecation period, clear migration guide")

        elif analysis["severity"] == "high":
            recommendations.append("⚠️ WARNING: High-risk breaking changes detected")
            recommendations.append("📋 TODO: Document migration path and notify users")

        if analysis["breaking_changes_count"] > 0:
            recommendations.append(f"❌ BLOCKED: {analysis['breaking_changes_count']} breaking change(s) found")

        return recommendations


# Global instance
breaking_changes_detector = BreakingChangesDetector()
