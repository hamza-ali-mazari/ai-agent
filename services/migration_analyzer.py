"""
Database Migration & Schema Changes Analyzer

Detects and analyzes database migrations, schema changes,
and provides migration safety assessment.
"""

import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class MigrationAnalyzer:
    """Analyzes database migrations and schema changes."""

    def __init__(self):
        """Initialize migration analyzer."""
        self.migration_patterns = {
            'alembic': r'def\s+upgrade\(|def\s+downgrade\(',
            'django': r'class\s+\w+\(migrations\.Migration\)|operations\s*=',
            'sql': r'ALTER TABLE|CREATE TABLE|DROP TABLE|ADD COLUMN|DROP COLUMN',
            'prisma': r'model\s+\w+\s*{|@(unique|id|default)',
        }

    def analyze_migrations(self, changed_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze database migrations in changed files."""
        analysis = {
            "has_migrations": False,
            "migration_files": [],
            "risky_migrations": [],
            "schema_changes": [],
            "recommendations": [],
            "warnings": [],
            "total_migrations": 0
        }

        for changed_file in changed_files:
            file_path = changed_file.get('path', '')
            content = changed_file.get('content', '')

            # Check if it's a migration file
            if self._is_migration_file(file_path):
                analysis["has_migrations"] = True
                analysis["total_migrations"] += 1

                analysis["migration_files"].append({
                    "file": file_path,
                    "type": self._detect_migration_type(file_path),
                })

                # Detect risky operations
                risky = self._detect_risky_operations(file_path, content)
                if risky:
                    analysis["risky_migrations"].append({
                        "file": file_path,
                        "operations": risky
                    })

                # Track schema changes
                schema = self._extract_schema_changes(content)
                if schema:
                    analysis["schema_changes"].extend(schema)

        # Generate recommendations
        if not analysis["has_migrations"]:
            if any('model' in f.get('path', '').lower() or 'schema' in f.get('path', '').lower() 
                   for f in changed_files):
                analysis["warnings"].append(
                    "⚠️ Database schema changes detected but no migration file found"
                )
                analysis["recommendations"].append(
                    "📝 ACTION: Create migration file to track schema changes"
                )

        if analysis["risky_migrations"]:
            analysis["warnings"].append(
                f"⚠️ {len(analysis['risky_migrations'])} migration(s) with risky operations"
            )
            analysis["recommendations"].append(
                "❌ CAUTION: These migrations may cause data loss. Add backups first"
            )

        if analysis["schema_changes"]:
            analysis["recommendations"].append(
                f"📊 {len(analysis['schema_changes'])} schema change(s) detected"
            )

        return analysis

    def _is_migration_file(self, file_path: str) -> bool:
        """Check if file is a migration file."""
        migration_indicators = [
            'migration', 'migrate', 'schema', 'alter', 'alembic',
            'flyway', 'liquibase'
        ]
        return any(indicator in file_path.lower() for indicator in migration_indicators)

    def _detect_migration_type(self, file_path: str) -> str:
        """Detect migration framework type."""
        if 'alembic' in file_path.lower():
            return 'alembic'
        elif 'django' in file_path.lower():
            return 'django'
        elif file_path.endswith('.sql'):
            return 'sql'
        elif 'prisma' in file_path.lower():
            return 'prisma'
        return 'unknown'

    def _detect_risky_operations(self, file_path: str, content: str) -> List[str]:
        """Detect risky migration operations."""
        risky = []

        # Data-destructive operations
        if re.search(r'DROP\s+TABLE|DELETE\s+FROM|TRUNCATE', content, re.IGNORECASE):
            risky.append("DROP TABLE or DELETE - data loss risk")

        if re.search(r'DROP\s+COLUMN', content, re.IGNORECASE):
            risky.append("DROP COLUMN - existing data will be lost")

        # Operations without backups
        if re.search(r'ALTER\s+TABLE.*?MODIFY|ALTER\s+TABLE.*?CHANGE', content, re.IGNORECASE):
            risky.append("Column type change - verify data compatibility")

        # Missing rollback/downgrade
        if 'upgrade' in content and 'downgrade' not in content:
            risky.append("Missing downgrade function - can't rollback")

        return risky

    def _extract_schema_changes(self, content: str) -> List[Dict]:
        """Extract schema changes from migration content."""
        changes = []

        # Create table
        for match in re.finditer(r'CREATE\s+TABLE\s+(\w+)', content, re.IGNORECASE):
            changes.append({
                "type": "create_table",
                "table": match.group(1),
                "severity": "info"
            })

        # Drop table
        for match in re.finditer(r'DROP\s+TABLE\s+(\w+)', content, re.IGNORECASE):
            changes.append({
                "type": "drop_table",
                "table": match.group(1),
                "severity": "critical"
            })

        # Add column
        for match in re.finditer(r'ADD\s+COLUMN\s+(\w+)', content, re.IGNORECASE):
            changes.append({
                "type": "add_column",
                "column": match.group(1),
                "severity": "info"
            })

        # Drop column
        for match in re.finditer(r'DROP\s+COLUMN\s+(\w+)', content, re.IGNORECASE):
            changes.append({
                "type": "drop_column",
                "column": match.group(1),
                "severity": "critical"
            })

        return changes


# Global instance
migration_analyzer = MigrationAnalyzer()


class AutomatedFixGenerator:
    """Generates automated fix suggestions for detected issues."""

    def generate_fixes(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate code fix suggestions for detected issues."""
        fixes = []

        for issue in issues[:5]:  # Top 5 issues
            fix = self._generate_fix_for_issue(issue)
            if fix:
                fixes.append(fix)

        return fixes

    def _generate_fix_for_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Generate specific fix for an issue."""
        issue_type = issue.get('type', '')

        if issue_type == 'n_plus_one_query':
            return {
                "issue_type": "n_plus_one_query",
                "title": "Fix N+1 Query",
                "code_before": """# ❌ N+1 Query
for user_id in user_ids:
    user = User.objects.get(id=user_id)  # Query per iteration
    process(user)
""",
                "code_after": """# ✅ Optimized
users = User.objects.filter(id__in=user_ids)  # Single query
for user in users:
    process(user)
""",
                "explanation": "Use filter() with __in lookup to fetch all users in one query"
            }

        elif issue_type == 'string_concatenation_loop':
            return {
                "issue_type": "string_concatenation_loop",
                "title": "Optimize String Concatenation",
                "code_before": """# ❌ Inefficient (O(n²))
result = ''
for item in items:
    result += str(item) + ','
""",
                "code_after": """# ✅ Efficient (O(n))
result = ','.join(str(item) for item in items)
""",
                "explanation": "join() is optimized for string concatenation and avoids repeated allocations"
            }

        elif issue_type == 'blocking_io':
            return {
                "issue_type": "blocking_io",
                "title": "Make I/O Operations Concurrent",
                "code_before": """# ❌ Sequential (slow)
for url in urls:
    response = requests.get(url)  # Blocks each iteration
    process(response)
""",
                "code_after": """# ✅ Concurrent (fast)
import asyncio
import aiohttp

async def fetch_all():
    async with aiohttp.ClientSession() as session:
        tasks = [session.get(url) for url in urls]
        responses = await asyncio.gather(*tasks)
        for response in responses:
            process(response)
""",
                "explanation": "Use async/await for concurrent requests instead of sequential"
            }

        elif issue_type == 'high_cyclomatic_complexity':
            return {
                "issue_type": "high_cyclomatic_complexity",
                "title": "Reduce Cyclomatic Complexity",
                "code_before": """# ❌ Complex (CC=8)
def process_user(user):
    if user.active:
        if user.premium:
            if user.verified:
                return 'premium_verified'
            else:
                return 'premium_unverified'
        else:
            return 'active'
    else:
        return 'inactive'
""",
                "code_after": """# ✅ Simple (CC=1)
def get_user_status(user):
    status_map = {
        (True, True, True): 'premium_verified',
        (True, True, False): 'premium_unverified',
        (True, False, None): 'active',
        (False, None, None): 'inactive'
    }
    key = (user.active, user.premium if user.active else None, 
           user.verified if user.premium else None)
    return status_map.get(key, 'unknown')
""",
                "explanation": "Use lookup tables or early returns to reduce nesting"
            }

        elif issue_type == 'unclosed_resources':
            return {
                "issue_type": "unclosed_resources",
                "title": "Use Context Manager for Resources",
                "code_before": """# ❌ May leak if exception occurs
file = open('data.txt')
data = file.read()
file.close()
""",
                "code_after": """# ✅ Guaranteed cleanup
with open('data.txt') as file:
    data = file.read()
# File automatically closed
""",
                "explanation": "Context managers ensure resources are always cleaned up"
            }

        elif issue_type == 'missing_caching':
            return {
                "issue_type": "missing_caching",
                "title": "Add Caching to Expensive Function",
                "code_before": """# ❌ Recalculates every time
def get_user_summary(user_id):
    # Expensive database query
    return db.query(...).compute()
""",
                "code_after": """# ✅ Cached result
from functools import lru_cache

@lru_cache(maxsize=128)
def get_user_summary(user_id):
    # Only executed on cache miss
    return db.query(...).compute()
""",
                "explanation": "Use @lru_cache decorator for expensive calculations"
            }

        elif issue_type == 'missing_tests':
            return {
                "issue_type": "missing_tests",
                "title": "Create Test Coverage",
                "code_before": """# No test file exists""",
                "code_after": """# tests/test_module.py
import pytest
from module import function_to_test

def test_function_success():
    result = function_to_test(valid_input)
    assert result == expected_output

def test_function_error():
    with pytest.raises(ValueError):
        function_to_test(invalid_input)
""",
                "explanation": "Add unit tests for critical functions and edge cases"
            }

        return None


# Global instance
fix_generator = AutomatedFixGenerator()
