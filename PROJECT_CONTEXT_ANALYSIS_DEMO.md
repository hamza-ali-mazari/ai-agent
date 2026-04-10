"""
FULL PROJECT CONTEXT ANALYSIS DEMO
Demonstrates how to use the new project-wide dependency analysis

This feature analyzes how changes in one file might affect other files
throughout the entire project by:
1. Fetching the complete project from Bitbucket
2. Extracting all exports and imports (language-aware)
3. Building a dependency graph
4. Identifying affected files
5. Providing detailed impact analysis
"""

from services.ai_review import analyze_code_diff
from models.review import CodeReviewRequest

# Example 1: Simple review WITHOUT full project context
print("=" * 80)
print("EXAMPLE 1: Review WITHOUT Full Project Context (Fast)")
print("=" * 80)

simple_request = CodeReviewRequest(
    diff="""diff --git a/utils.py b/utils.py
index 1234567..abcdef0 100644
--- a/utils.py
+++ b/utils.py
@@ -1,5 +1,6 @@
 def format_user_data(user):
-    return f"{user['name']} - {user['email']}"
+    return f"{user.get('name')} - {user.get('email', 'N/A')}"
""",
    repository_url="https://bitbucket.org/workspace/repo",
    files_changed=["utils.py"],
    analyze_full_project=False  # ← DISABLED (default)
)

print("Request: Analyze utils.py changes (quick mode)")
print("analyze_full_project: False")
print()

# ============================================================================

# Example 2: Full project context analysis
print("=" * 80)
print("EXAMPLE 2: Review WITH Full Project Context Analysis (Comprehensive)")
print("=" * 80)

context_request = CodeReviewRequest(
    diff="""diff --git a/utils.py b/utils.py
index 1234567..abcdef0 100644
--- a/utils.py
+++ b/utils.py
@@ -1,5 +1,6 @@
 def format_user_data(user):
-    return f"{user['name']} - {user['email']}"
+    return f"{user.get('name')} - {user.get('email', 'N/A')}"
""",
    repository_url="https://bitbucket.org/yourworkspace/yourrepo",
    branch="master",
    files_changed=["utils.py"],
    workspace="yourworkspace",           # ← REQUIRED for full context
    repo_slug="yourrepo",                # ← REQUIRED for full context
    analyze_full_project=True            # ← ENABLED
)

print("Request: Analyze utils.py with full project context")
print("Properties:")
print("  - workspace: 'yourworkspace'")
print("  - repo_slug: 'yourrepo'")
print("  - analyze_full_project: True")
print()

# This would fetch the entire repository and analyze:
print("What this will analyze:")
print("  1. Fetch ALL files from the repository")
print("  2. Extract all function/class definitions and exports")
print("  3. Extract all imports in each file")
print("  4. Build dependency graph")
print("  5. Find which files import from 'utils.py'")
print("  6. Identify affected files")
print("  7. Calculate impact level (critical/high/medium/low/isolated)")
print()

# Response structure with project impact analysis
print("Response will include:")
print("""
{
    "review_id": "review_2024-04-11T10:30:00.000000",
    "summary": {...},
    "files": [...],
    "overall_feedback": "...",
    "recommendations": [...],
    "project_impact_analysis": {
        "all_files_count": 42,
        "changed_files": ["utils.py"],
        "dependency_analysis": {
            "affected_files": [
                "auth/user.py",
                "api/endpoints.py",
                "services/formatter.py"
            ],
            "dependency_graph": {
                "utils.py": [
                    "auth/user.py",
                    "api/endpoints.py",
                    "services/formatter.py"
                ]
            },
            "impact_level": "high",  # 7 files affected (16% of project)
            "changed_exports": {
                "utils.py": ["format_user_data", "process_data"]
            }
        },
        "impact_report": "## 📊 Project Impact Analysis
        
🚨 Impact Level: HIGH
📊 Affected Files: 3

Files that may be affected by your changes:
- auth/user.py
- api/endpoints.py
- services/formatter.py

Dependency Graph:
- **utils.py** is used by:
  - auth/user.py
  - api/endpoints.py
  - services/formatter.py

Recommendation: Review affected files to ensure compatibility..."
    }
}
"""
)

print()
print("=" * 80)
print("EXAMPLE 3: Using with Bitbucket PR Webhook")
print("=" * 80)

webhook_example = {
    "payload": {
        "pullrequest": {
            "title": "Improve user data handling",
            "source": {
                "branch": {
                    "name": "feat/user-handling"
                }
            },
            "destination": {
                "branch": {
                    "name": "master"
                }
            }
        },
        "repository": {
            "workspace": {
                "slug": "myteam"
            },
            "name": "api-service"
        }
    }
}

print("""
When a PR is created on Bitbucket:
1. Webhook is received by /webhook/bitbucket endpoint
2. If analyze_full_project=True is set:
   - Full repo is fetched from Bitbucket API
   - Dependencies are analyzed
   - Impact report is generated
3. Response includes detailed impact analysis
4. Developers see which files are affected by their changes
5. Helps prevent breaking changes and integration issues
""")

print()
print("=" * 80)
print("USE CASES")
print("=" * 80)

use_cases = """
1. DETECTING BREAKING CHANGES
   - Change function signature in utils.py
   - Agent finds 15 files using that function
   - Warns: "High impact change - 15 files may break"

2. UNDERSTANDING DEPENDENCIES
   - Change API response format
   - Agent identifies all frontend files importing that API
   - Suggests: "Update 8 frontend components to handle new format"

3. IMPACT-AWARE SUGGESTIONS
   - Remove a helper function
   - Agent finds 3 files that use it
   - Suggests either: keep for compatibility OR update all 3 files

4. CROSS-LAYER ANALYSIS
   - Database schema change
   - Agent traces through ORM layer to service layer to API layer
   - Shows full dependency chain

5. REFACTORING SAFETY
   - Rename class/module
   - Agent finds all imports
   - Warns about all affected files before refactor completes
"""

print(use_cases)

print()
print("=" * 80)
print("SUPPORTED LANGUAGES")
print("=" * 80)

languages = """
✅ Python      - Extracts: functions, classes, __all__
✅ JavaScript  - Extracts: exports, functions, module.exports
✅ Java        - Extracts: classes, public methods
✅ C#          - Extracts: using statements, class definitions
✅ TypeScript  - Same as JavaScript
"""

print(languages)

print()
print("=" * 80)
print("PERFORMANCE CONSIDERATIONS")
print("=" * 80)

performance = """
ENABLING full project context analysis:
- Takes longer (fetches entire repo)
- Uses more API calls to Bitbucket
- Better analysis and insights
- Prevents breaking changes

DISABLING full project context analysis:
- Fast analysis (only analyzes diff)
- Fewer API calls
- Basic review without impact analysis
- Use for quick PR reviews

RECOMMENDATION:
- Enable for release branches, critical services
- Disable for drafts, experimental PRs
- Enable for pull requests affecting shared code
"""

print(performance)

print()
print("=" * 80)
print("EXAMPLE API CALL")
print("=" * 80)

api_call = """
POST /review
Content-Type: application/json

{
  "diff": "...",
  "repository_url": "https://bitbucket.org/myteam/api-service",
  "branch": "master",
  "files_changed": ["src/utils/formatter.py"],
  "workspace": "myteam",
  "repo_slug": "api-service",
  "analyze_full_project": true,
  "config": {
    "enabled_categories": ["security", "bugs", "performance"],
    "severity_threshold": "low"
  }
}

RESPONSE:
{
  "review_id": "review_2024-04-11T...",
  "summary": {...},
  "files": [...],
  "overall_feedback": "...",
  "recommendations": [...],
  "project_impact_analysis": {
    "all_files_count": 42,
    "changed_files": ["src/utils/formatter.py"],
    "dependency_analysis": {
      "affected_files": ["src/auth/user.py", "src/api/routes.py"],
      "dependency_graph": {...},
      "impact_level": "medium"
    },
    "impact_report": "## 📊 Project Impact Analysis..."
  }
}
"""

print(api_call)
