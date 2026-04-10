# Project Impact Analysis - Usage Guide

## How to See Affected Files in Code Review

The **Project Impact Analysis** shows you which files will be affected by your code changes across the entire repository.

---

## ✅ Quick Start: Enable Project Impact Analysis

Add these **three fields** to your code review request:

```json
{
  "diff": "your code diff here",
  "repository_url": "https://bitbucket.org/workspace/repo",
  "author": "your-email@company.com",
  
  "analyze_full_project": true,
  "workspace": "your-bitbucket-workspace",
  "repo_slug": "your-repository-name"
}
```

---

## 📋 Example API Request

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "diff": "diff --git a/models/user.py b/models/user.py
index 1234567..abcdef0 100644
--- a/models/user.py
+++ b/models/user.py
@@ -1,5 +1,10 @@
+def validate_email(email):
+    return @ in email
+
 class User:
     def __init__(self, name):
         self.name = name",
    
    "repository_url": "https://bitbucket.org/myworkspace/myrepo",
    "author": "developer@company.com",
    
    "analyze_full_project": true,
    "workspace": "myworkspace",
    "repo_slug": "myrepo"
  }'
```

---

## 📊 Example Response: Affected Files Shown

```json
{
  "review_id": "review_2026-04-11T...",
  "overall_feedback": "
### 🌍 Project Impact Analysis

**Repository Scope:** 42 total files analyzed
**Your Changes:** 1 file(s) modified

### ⚠️ **3 FILE(S) AFFECTED**

**Status:** Your changes will affect 3 other file(s)

**Files Changed:**
- 📝 models/user.py

**Affected Files (may need review/update):**
1. ⚠️ services/auth_service.py
2. ⚠️ api/routes/users.py
3. ⚠️ tests/test_auth.py

### ⚠️ Recommendation: REVIEW AFFECTED FILES
Before merging, please:
1. Review the 1 changed file(s)
2. Check the 3 affected file(s) for compatibility
3. Run tests to ensure no breaking changes
  ",
  "project_impact_analysis": {
    "all_files_count": 42,
    "affected_files_count": 3,
    "changed_files": ["models/user.py"],
    "dependency_analysis": {
      "affected_files": [
        "services/auth_service.py",
        "api/routes/users.py",
        "tests/test_auth.py"
      ],
      "dependency_graph": {
        "models/user.py": [
          "services/auth_service.py",
          "api/routes/users.py",
          "tests/test_auth.py"
        ]
      }
    }
  }
}
```

---

## 🔑 Required Credentials

Your Bitbucket credentials must be set as environment variables:

```bash
# .env file
BITBUCKET_USERNAME=your-username
BITBUCKET_APP_PASSWORD=your-app-password
# OR
BITBUCKET_OAUTH_TOKEN=your-oauth-token
```

---

## 🎯 What You'll See

### Safe Changes (No Impact)
```
### ✅ **NO ISSUES DETECTED**

Status: This change is ISOLATED and does NOT affect other files

Your changes in:
- utils/helpers.py

Safe: All other files in the project are NOT impacted

### ✅ Recommendation: SAFE TO MERGE
This PR can be safely merged without affecting other parts of the codebase.
```

### Risky Changes (Files Affected)
```
### ⚠️ **5 FILE(S) AFFECTED**

Status: Your changes will affect 5 other file(s)

Files Changed:
- 📝 services/payment.py

Affected Files (may need review/update):
1. ⚠️ api/routes/orders.py
2. ⚠️ services/checkout.py
3. ⚠️ integrations/stripe.py
4. ⚠️ tests/test_payment.py
5. ⚠️ models/transaction.py

### ⚠️ Recommendation: REVIEW AFFECTED FILES
Before merging, please:
1. Review the 1 changed file(s)
2. Check the 5 affected file(s) for compatibility
3. Run tests to ensure no breaking changes
```

---

## 🔍 How It Works

1. **Fetches full repository** - Gets all source files from Bitbucket
2. **Analyzes changed files** - Extracts exports (functions, classes)
3. **Builds dependency graph** - Identifies which files import those exports
4. **Calculates impact** - Shows exactly which files are affected
5. **Displays results** - Shows affected files in the review output

---

## 🐛 Troubleshooting

**Q: I don't see "Project Impact Analysis" in the output**
A: Make sure you set these fields:
   - `analyze_full_project: true`
   - `workspace: "your-workspace"`
   - `repo_slug: "your-repo"`

**Q: Getting authentication error?**
A: Verify your Bitbucket credentials in `.env`:
   ```bash
   BITBUCKET_USERNAME=correct-username
   BITBUCKET_APP_PASSWORD=correct-password
   ```

**Q: Repository file count seems wrong?**
A: The analyzer skips:
   - Hidden files (.git, .env, etc.)
   - node_modules, __pycache__, .venv
   - .class, .pyc, .o build artifacts
   - Large binary files

---

## 📈 Key Benefits

✅ **Catch breaking changes** - See exactly what your code breaks
✅ **Review dependencies** - Know what files use your code
✅ **Safer merges** - Confirm impact before production  
✅ **Faster code reviews** - Understand scope automatically
✅ **Prevent bugs** - Identify forgotten test updates

---

## 🚀 Next Steps

1. **Add credentials** to `.env` if not already done
2. **Include fields** in code review request:
   ```json
   {
     "analyze_full_project": true,
     "workspace": "YOUR-WORKSPACE",
     "repo_slug": "YOUR-REPO"
   }
   ```
3. **Send review request** and see affected files in output
4. **Review recommendations** before merging

---

**Your code review now shows the full impact of every change!** 🎯
