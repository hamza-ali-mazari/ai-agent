#!/usr/bin/env python3
"""
Simple Chatbot Client for AI Code Review Engine
Easy way to interact with the chatbot after performing a code review
"""

import requests
import json
import sys

BASE_URL = "http://localhost:10000"

def perform_code_review():
    """Perform a code review and get review_id"""
    print("\n" + "="*60)
    print("[*] STEP 1: Performing Code Review")
    print("="*60)
    
    # Sample code with issues
    sample_diff = """diff --git a/example.py b/example.py
index 1234567..abcdef0 100644
--- a/example.py
+++ b/example.py
@@ -1,3 +1,10 @@
+import sqlite3
+
 def authenticate_user(username, password):
-    # Simple authentication (vulnerable to SQL injection)
-    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
-    # Execute query...
+    # Fixed: Use parameterized queries to prevent SQL injection
+    query = "SELECT * FROM users WHERE username = ? AND password = ?"
+    # Execute parameterized query...
+
+def process_data(data):
+    # Inefficient processing
+    result = []
+    for item in data:
+        result.append(item * 2)
+    return result
"""

    print("[*] Sending code review request...")
    
    response = requests.post(
        f"{BASE_URL}/review",
        json={"diff": sample_diff},
        timeout=60
    )
    
    if response.status_code != 200:
        print(f"[!] Error: {response.status_code}")
        print(response.text)
        return None
    
    result = response.json()
    review_id = result.get("review_id")
    chat_review_id = result.get("metadata", {}).get("chat_review_id")
    
    print(f"[✓] Review completed!")
    print(f"[✓] Review ID: {review_id}")
    print(f"[✓] Chat Review ID: {chat_review_id}")
    print(f"[✓] Overall Score: {result.get('summary', {}).get('overall_score')}/100")
    print(f"[✓] Total Comments: {result.get('summary', {}).get('total_comments')}")
    
    return chat_review_id or review_id


def chat_with_bot(review_id):
    """Interactive chatbot conversation"""
    print("\n" + "="*60)
    print("[*] STEP 2: Chat with Chatbot")
    print("="*60)
    print(f"[*] Review ID: {review_id}")
    print("[*] Type 'quit' or 'exit' to end conversation")
    print("[*] Type 'history' to see conversation history")
    print("="*60 + "\n")
    
    conversation_count = 0
    
    while True:
        try:
            user_message = input("\n[YOU] > ").strip()
            
            if not user_message:
                print("[!] Please enter a message")
                continue
            
            if user_message.lower() in ['quit', 'exit']:
                print("\n[*] Goodbye!")
                break
            
            if user_message.lower() == 'history':
                print("\n[*] Getting conversation history...")
                get_conversation_history(review_id)
                continue
            
            print("\n[*] Sending message...")
            
            response = requests.post(
                f"{BASE_URL}/chat/{review_id}",
                json={"message": user_message},
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"[!] Error: {response.status_code}")
                print(response.text)
                continue
            
            result = response.json()
            assistant_message = result.get("message", "No response")
            
            # Print assistant response with better formatting
            print(f"\n[CHATBOT] > {assistant_message}")
            conversation_count += 1
            
        except KeyboardInterrupt:
            print("\n\n[*] Chat interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"[!] Error: {str(e)}")
            continue


def get_conversation_history(review_id):
    """Get and display conversation history"""
    try:
        response = requests.get(
            f"{BASE_URL}/chat/{review_id}/history",
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"[!] Error: {response.status_code}")
            return
        
        result = response.json()
        conversation = result.get("conversation", [])
        
        if not conversation:
            print("[*] No conversation history yet")
            return
        
        print("\n" + "="*60)
        print("[*] Conversation History")
        print("="*60)
        
        for i, msg in enumerate(conversation, 1):
            role = msg.get("role", "").upper()
            text = msg.get("message", "")
            print(f"\n[{i}] [{role}]")
            print(f"    {text[:200]}..." if len(text) > 200 else f"    {text}")
        
        print("\n" + "="*60 + "\n")
        
    except Exception as e:
        print(f"[!] Error fetching history: {str(e)}")


def main():
    """Main function"""
    print("\n" + "="*60)
    print("[*] AI Code Review Chatbot Client")
    print("="*60)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("[!] Server is not responding properly")
            print("[*] Make sure to run: uvicorn app:app --reload")
            return
    except Exception as e:
        print("[!] Cannot connect to server!")
        print(f"[!] Error: {str(e)}")
        print("\n[*] Please start the server first:")
        print("    uvicorn app:app --reload --host 0.0.0.0 --port 10000")
        return
    
    print("[✓] Server is running!")
    
    # Option 1: Use existing review_id or perform new review
    print("\n[*] Options:")
    print("    1. Perform new code review (and then chat)")
    print("    2. Use existing review_id")
    
    choice = input("\n[*] Choose option (1 or 2): ").strip()
    
    if choice == "1":
        review_id = perform_code_review()
        if not review_id:
            print("[!] Failed to perform review")
            return
    else:
        review_id = input("\n[*] Enter review_id: ").strip()
        if not review_id:
            print("[!] No review_id provided")
            return
    
    # Start chatting
    chat_with_bot(review_id)


if __name__ == "__main__":
    main()
