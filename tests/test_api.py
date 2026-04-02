import pytest
from fastapi.testclient import TestClient
from app import app
from models.review import CodeReviewRequest

client = TestClient(app)

def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": "2.0.0"}

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

if __name__ == "__main__":
    pytest.main([__file__])