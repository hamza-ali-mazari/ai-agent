import pytest
import os
from fastapi.testclient import TestClient
from app import app
from models.review import CodeReviewRequest

# Set testing environment variable
os.environ["TESTING"] = "true"

client = TestClient(app)

def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "2.0.0"
    assert "azure_openai_available" in data

def test_review_code_empty_diff():
    """Test review endpoint with empty diff."""
    response = client.post("/review", json={"diff": ""})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_review_code_basic():
    """Test basic code review functionality."""
    test_diff = """diff --git a/test.py b/test.py
index 1234567..abcdef0 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,5 @@
+def hello():
+    print('Hello World')
+
 def goodbye():
-    print('Goodbye')
+    print('Goodbye World')"""

    response = client.post("/review", json={"diff": test_diff})
    assert response.status_code == 200

    data = response.json()
    assert "review_id" in data
    assert "summary" in data
    assert "files" in data
    assert "overall_feedback" in data
    assert isinstance(data["summary"]["overall_score"], int)
    assert data["summary"]["overall_score"] >= 0
    assert data["summary"]["overall_score"] <= 100

def test_legacy_review():
    """Test legacy review endpoint."""
    test_diff = "+ def hello():\n+     print('Hello World')"

    response = client.post("/review/legacy", json={"diff": test_diff})
    assert response.status_code == 200

    data = response.json()
    assert "review" in data
    assert "details" in data
    assert "score" in data["details"]

def test_default_config():
    """Test default configuration endpoint."""
    response = client.get("/config/default")
    assert response.status_code == 200

    config = response.json()
    assert "enabled_categories" in config
    assert "severity_threshold" in config
    assert "max_comments_per_file" in config


def test_bitbucket_get_auth_headers():
    """Test Bitbucket auth headers priority and presence."""
    import os
    from integrations.bitbucket_integration import BitbucketIntegration

    # Test 1: OAuth token takes priority
    os.environ["BITBUCKET_OAUTH_TOKEN"] = "oauth-123"
    os.environ.pop("BITBUCKET_APP_PASSWORD", None)
    os.environ.pop("BITBUCKET_USERNAME", None)
    os.environ.pop("BITBUCKET_TOKEN", None)

    integration = BitbucketIntegration()
    headers = integration.get_auth_headers()
    assert headers["Authorization"] == "Bearer oauth-123"

    # Test 2: Username + token fallback
    os.environ.pop("BITBUCKET_OAUTH_TOKEN", None)
    os.environ.pop("BITBUCKET_APP_PASSWORD", None)
    os.environ["BITBUCKET_USERNAME"] = "user"
    os.environ["BITBUCKET_TOKEN"] = "api-token"

    integration = BitbucketIntegration()
    headers = integration.get_auth_headers()
    assert headers["Authorization"].startswith("Basic ")

    # Test 3: No credentials should raise ValueError
    os.environ.pop("BITBUCKET_OAUTH_TOKEN", None)
    os.environ.pop("BITBUCKET_APP_PASSWORD", None)
    os.environ.pop("BITBUCKET_USERNAME", None)
    os.environ.pop("BITBUCKET_TOKEN", None)

    integration = BitbucketIntegration()
    with pytest.raises(ValueError):
        integration.get_auth_headers()


if __name__ == "__main__":
    pytest.main([__file__])