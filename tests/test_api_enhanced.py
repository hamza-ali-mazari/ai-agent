"""
Enhanced Test Suite for AI Code Review Engine
Tests with better assertions, formatting, and developer-friendly output
"""
import pytest
from fastapi.testclient import TestClient
from app import app
from models.review import CodeReviewRequest, ReviewSeverity
from services.token_tracker import token_tracker

client = TestClient(app)

# Check if Azure OpenAI is available by making a test call
azure_available = getattr(app.state, "azure_openai_available", False)


class TestHealthAndBasic:
    """Basic health and configuration tests."""
    
    def test_health_check(self):
        """✅ Test health check endpoint."""
        response = client.get("/health")
        # Accept both 200 (healthy) and 503 (degraded but responsive)
        assert response.status_code in [200, 503], "Health check should return 200 or 503"
        data = response.json()
        assert data["status"] in ["healthy", "degraded"], "Status should be healthy or degraded"
        assert "version" in data, "Version should be present"
        assert "azure_openai_available" in data, "Azure availability should be present"
        assert "azure_openai_health_message" in data, "Health message should be present"
        logging.info(f"✅ Health check passed: {data['status']} ({response.status_code})")

    def test_review_empty_diff(self):
        """✅ Test review with empty diff - should fail gracefully."""
        response = client.post("/review", json={"diff": ""})
        assert response.status_code == 400, "Empty diff should return 400"
        detail = response.json()["detail"].lower()
        assert "empty" in detail, "Should mention empty diff"
        logging.info("✅ Empty diff validation passed")


class TestCodeReview:
    """Core code review functionality tests."""
    
    @pytest.mark.skipif(not azure_available, reason="Azure OpenAI not available")
    def test_python_code_review(self):
        """✅ Test Python code review."""
        test_diff = """diff --git a/test.py b/test.py
index 1234567..abcdef0 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,3 @@
 def hello():
-    name = input("Enter name: ")
+    name = input("Enter name: ").strip()
     print(f"Hello {name}")"""

        response = client.post("/review", json={
            "diff": test_diff,
            "repository_url": "https://bitbucket.org/test/repo",
            "files_changed": ["test.py"]
        })
        
        assert response.status_code == 200, "Review should succeed"
        data = response.json()
        
        # Validate response structure
        assert "review_id" in data, "Should have review_id"
        assert "summary" in data, "Should have summary"
        assert "files" in data, "Should have files"
        assert "overall_feedback" in data, "Should have overall_feedback"
        
        # Validate summary structure
        summary = data["summary"]
        assert isinstance(summary["overall_score"], int), "Score should be int"
        assert 0 <= summary["overall_score"] <= 100, "Score should be 0-100"
        assert isinstance(summary["total_comments"], int), "Comments should be int"
        assert isinstance(summary["critical_issues"], int), "Critical should be int"
        assert "tokens_used" in summary, "Should track token usage"
        assert "estimated_cost" in summary, "Should show estimated cost"
        
        logging.info(f"✅ Python review passed - Score: {summary['overall_score']}/100")
        logging.debug(f"   Tokens: {summary.get('tokens_used', 0)} | Cost: {summary.get('estimated_cost', 'N/A')}")

    @pytest.mark.skipif(not azure_available, reason="Azure OpenAI not available")
    def test_javascript_code_review(self):
        """✅ Test JavaScript code review."""
        test_diff = """diff --git a/app.js b/app.js
index 1234567..abcdef0 100644
--- a/app.js
+++ b/app.js
@@ -1,5 +1,5 @@
 async function fetchUser(id) {
-    const response = await fetch('/api/users/' + id);
+    const response = await fetch(`/api/users/${id}`);
     const data = await response.json();
     return data;
 }"""

        response = client.post("/review", json={
            "diff": test_diff,
            "repository_url": "https://bitbucket.org/test/repo",
            "files_changed": ["app.js"]
        })
        
        assert response.status_code == 200, "JavaScript review should succeed"
        data = response.json()
        assert len(data["files"]) > 0, "Should analyze JavaScript file"
        summary = data["summary"]
        assert isinstance(summary["overall_score"], int), "Should provide score for JS"
        print("✅ JavaScript review passed")

    @pytest.mark.skipif(not azure_available, reason="Azure OpenAI not available")
    def test_security_issues_detection(self):
        """✅ Test detection of security issues."""
        test_diff = """diff --git a/db.py b/db.py
index 1234567..abcdef0 100644
--- a/db.py
+++ b/db.py
@@ -1,3 +1,3 @@
 def get_user(user_id):
-    query = f"SELECT * FROM users WHERE id = {user_id}"
+    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
     return cursor.fetchone()"""

        response = client.post("/review", json={"diff": test_diff})
        assert response.status_code == 200, "Should analyze security issues"
        data = response.json()
        summary = data["summary"]
        
        # Security issues should be detected in critical/high
        has_security_feedback = (
            summary["critical_issues"] > 0 or 
            summary["high_issues"] > 0 or
            "security" in data["overall_feedback"].lower()
        )
        assert has_security_feedback, "Should detect security issues"
        print("✅ Security issue detection passed")


class TestTokenTracking:
    """Token usage tracking tests."""
    
    def test_token_stats_endpoint(self):
        """✅ Test token statistics endpoint."""
        response = client.get("/stats/tokens")
        assert response.status_code == 200, "Token stats should be available"
        data = response.json()
        
        assert "data" in data, "Should have data key"
        stats = data["data"]
        assert "prompt_tokens" in stats, "Should track prompt tokens"
        assert "completion_tokens" in stats, "Should track completion tokens"
        assert "total_tokens" in stats, "Should track total tokens"
        assert "analyses_count" in stats, "Should count analyses"
        
        print(f"✅ Token stats endpoint passed")
        print(f"   Total tokens: {stats['total_tokens']}")
        print(f"   Analyses: {stats['analyses_count']}")

    def test_token_report_endpoint(self):
        """✅ Test token report endpoint."""
        response = client.get("/stats/tokens/report")
        assert response.status_code == 200, "Token report should be available"
        data = response.json()
        
        assert "report" in data, "Should have report"
        report = data["report"]
        assert "Token Usage" in report, "Report should mention token usage"
        
        print("✅ Token report endpoint passed")
        print(f"   Report:\n   {report.replace(chr(10), chr(10) + '   ')}")


class TestLegacyEndpoints:
    """Test backward compatibility."""
    
    @pytest.mark.skipif(not azure_available, reason="Azure OpenAI not available")
    def test_legacy_review_endpoint(self):
        """✅ Test legacy review endpoint."""
        test_diff = "+ def hello():\n+     print('Hello World')"
        
        response = client.post("/review/legacy", json={"diff": test_diff})
        assert response.status_code == 200, "Legacy endpoint should work"
        
        data = response.json()
        assert "review" in data, "Should have review key"
        assert "details" in data, "Should have details"
        print("✅ Legacy endpoint passed")

    @pytest.mark.skipif(not azure_available, reason="Azure OpenAI not available")
    def test_default_config(self):
        """✅ Test default configuration."""
        response = client.get("/config/default")
        assert response.status_code == 200, "Config endpoint should work"
        
        data = response.json()
        assert "enabled_categories" in data, "Should have enabled_categories"
        print("✅ Default config passed")


class TestResponseQuality:
    """Test response quality and completeness."""
    
    @pytest.mark.skipif(not azure_available, reason="Azure OpenAI not available")
    def test_response_includes_recommendations(self):
        """✅ Test that recommendations are included."""
        test_diff = "+ print('test')"
        
        response = client.post("/review", json={"diff": test_diff})
        assert response.status_code == 200
        
        data = response.json()
        assert "recommendations" in data, "Should include recommendations"
        assert isinstance(data["recommendations"], list), "Recommendations should be a list"
        
        print("✅ Recommendations included in response")

    @pytest.mark.skipif(not azure_available, reason="Azure OpenAI not available")
    def test_response_includes_feedback(self):
        """✅ Test that overall feedback is included."""
        test_diff = "+ def test():\n+    pass"
        
        response = client.post("/review", json={"diff": test_diff})
        assert response.status_code == 200
        
        data = response.json()
        assert "overall_feedback" in data, "Should include overall_feedback"
        assert len(data["overall_feedback"]) > 0, "Feedback should not be empty"
        assert "metrics" in data["overall_feedback"].lower() or "token" in data["overall_feedback"].lower(),  "Should include metrics"
        
        print("✅ Overall feedback and metrics included")


def run_all_tests():
    """Run all tests with nice formatting."""
    print("\n" + "="*60)
    print("🧪 Running Enhanced Test Suite")
    print("="*60 + "\n")
    
    pytest.main([__file__, "-v", "--tb=short"])
    
    print("\n" + "="*60)
    print("✅ Test Suite Complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_tests()
