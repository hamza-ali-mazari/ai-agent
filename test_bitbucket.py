#!/usr/bin/env python3
"""
Bitbucket Integration Test Script

This script helps test the Bitbucket integration locally by simulating
webhook payloads and testing the API endpoints.
"""

import os
import json
import requests
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_bitbucket_integration():
    """Test the Bitbucket integration with sample data."""

    print("🧪 Testing Bitbucket Integration")
    print("=" * 50)

    # Check environment variables
    required_vars = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "BITBUCKET_USERNAME",
        "BITBUCKET_TOKEN"
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        return False

    print("✅ Environment variables configured")

    # Test main API health
    try:
        response = requests.get("http://localhost:8000/health")
        if response.status_code == 200:
            print("✅ Main API server is running")
        else:
            print(f"❌ Main API server error: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Main API server not running. Start with: uvicorn app:app --reload --port 8000")
        return False

    # Test Bitbucket integration server
    try:
        # Try to start the Bitbucket integration if not running
        import subprocess
        import signal
        import sys

        print("🚀 Starting Bitbucket integration server...")
        process = subprocess.Popen([
            sys.executable, "integrations/bitbucket_integration.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Wait a bit for server to start
        time.sleep(3)

        # Test if server started
        try:
            response = requests.get("http://localhost:8002/docs")
            if response.status_code == 200:
                print("✅ Bitbucket integration server started on port 8002")
            else:
                print("⚠️ Bitbucket integration server may not be fully started")
        except:
            print("⚠️ Could not verify Bitbucket integration server")

    except Exception as e:
        print(f"❌ Error starting Bitbucket integration: {e}")
        return False

    # Test with sample PR data
    print("\n🧪 Testing with sample PR data...")

    sample_payload = {
        "eventKey": "pullrequest:created",
        "pullRequest": {
            "id": 1,
            "title": "Test PR for AI Code Review",
            "source": {
                "branch": {"name": "feature/test-ai-review"},
                "commit": {"hash": "abc123def456"}
            },
            "author": {"display_name": "Test User"}
        },
        "repository": {
            "slug": "ai-code-review-test",
            "workspace": {"slug": "test-workspace"}
        },
        "actor": {
            "display_name": "Test User",
            "uuid": "{12345678-1234-1234-1234-123456789012}"
        }
    }

    try:
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            "http://localhost:8002/webhook/bitbucket",
            json=sample_payload,
            headers=headers
        )

        if response.status_code == 200:
            print("✅ Webhook simulation successful")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Webhook simulation failed: {response.status_code}")
            print(f"Response: {response.text}")

    except requests.exceptions.ConnectionError:
        print("❌ Bitbucket integration server not accessible")
        return False
    except Exception as e:
        print(f"❌ Error testing webhook: {e}")
        return False

    # Test direct API call
    print("\n🧪 Testing direct API review...")

    test_diff = """diff --git a/test.py b/test.py
index 1234567..abcdef0 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,7 @@
+def hello_world():
+    print("Hello World")
+    return "test"
+
 def calculate_sum(a, b):
-    return a + b
+    result = a + b
+    return result"""

    try:
        review_payload = {
            "diff": test_diff,
            "repository_url": "https://bitbucket.org/test-workspace/test-repo",
            "branch": "feature/test",
            "commit_sha": "abc123",
            "author": "Test User",
            "files_changed": ["test.py"]
        }

        response = requests.post(
            "http://localhost:8000/review",
            json=review_payload
        )

        if response.status_code == 200:
            result = response.json()
            print("✅ Direct API review successful")
            print(f"Overall Score: {result['summary']['overall_score']}/100")
            print(f"Total Comments: {result['summary']['total_comments']}")
            print(f"Critical Issues: {result['summary']['critical_issues']}")
        else:
            print(f"❌ Direct API review failed: {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"❌ Error testing direct API: {e}")
        return False

    print("\n🎉 All tests completed!")
    print("\n📋 Next steps:")
    print("1. Set up a real Bitbucket repository")
    print("2. Configure webhooks in Bitbucket")
    print("3. Create a test PR to trigger real review")
    print("4. Check BITBUCKET_TESTING.md for detailed instructions")

    return True

if __name__ == "__main__":
    success = test_bitbucket_integration()
    exit(0 if success else 1)