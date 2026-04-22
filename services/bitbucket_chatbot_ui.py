"""
Bitbucket PR Chatbot UI - Posts interactive chatbot to Bitbucket PRs
"""

def create_interactive_chatbot_comment(review_id, review_summary):
    """
    Creates an interactive HTML/JavaScript chatbot UI for Bitbucket PR comments
    This appears directly in the PR, not in a separate browser
    """
    
    # HTML/CSS/JS for the interactive chatbot widget
    html_content = f"""
<div id="ai-chatbot-widget" style="background: #f5f5f5; border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
    
    <!-- Header -->
    <div style="display: flex; align-items: center; margin-bottom: 15px; border-bottom: 2px solid #0052cc; padding-bottom: 10px;">
        <span style="font-size: 18px; margin-right: 8px;">🤖</span>
        <h3 style="margin: 0; color: #0052cc; font-size: 16px;">AI Code Review Chatbot</h3>
        <button onclick="toggleChatbot()" style="margin-left: auto; background: none; border: none; font-size: 18px; cursor: pointer;">⬇️</button>
    </div>
    
    <!-- Quick Info -->
    <div style="background: white; padding: 10px; border-radius: 4px; margin-bottom: 10px; font-size: 13px;">
        <div style="margin-bottom: 8px;">
            <strong style="color: #0052cc;">Review ID:</strong> 
            <code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px;">{review_id}</code>
        </div>
        <div style="margin-bottom: 8px;">
            <strong style="color: #0052cc;">Overall Score:</strong> 
            <span style="font-weight: bold; color: #4CAF50;">{review_summary.get('overall_score', 'N/A')}/100</span>
        </div>
        <div style="margin-bottom: 8px;">
            <strong style="color: #0052cc;">Issues Found:</strong>
            <span>Critical: {review_summary.get('critical_issues', 0)} | High: {review_summary.get('high_issues', 0)} | Medium: {review_summary.get('medium_issues', 0)}</span>
        </div>
    </div>
    
    <!-- Chat Container -->
    <div id="chatbot-container" style="display: none; background: white; border: 1px solid #ddd; border-radius: 4px; padding: 10px; max-height: 400px; overflow-y: auto;">
        
        <!-- Messages Display -->
        <div id="chat-messages" style="margin-bottom: 10px; font-size: 13px; min-height: 150px;">
            <div style="color: #666; text-align: center; padding: 20px;">
                [*] Chatbot Ready. Ask about the review findings...
            </div>
        </div>
        
        <!-- Input Area -->
        <div style="display: flex; gap: 8px; margin-top: 10px;">
            <input 
                type="text" 
                id="chat-input" 
                placeholder="Ask a question about the code review..." 
                style="flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 12px;"
            />
            <button 
                onclick="sendChatMessage()" 
                style="background: #0052cc; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 12px;"
            >Send</button>
        </div>
        
        <!-- Suggested Questions -->
        <div style="margin-top: 10px; font-size: 12px; color: #666;">
            <strong>Suggested Questions:</strong>
            <div style="display: flex; flex-wrap: wrap; gap: 5px; margin-top: 5px;">
                <button onclick="askQuestion('What are the critical security issues?')" style="background: #e8f0ff; border: 1px solid #0052cc; color: #0052cc; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 11px;">Security Issues</button>
                <button onclick="askQuestion('How can I improve performance?')" style="background: #e8f0ff; border: 1px solid #0052cc; color: #0052cc; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 11px;">Performance</button>
                <button onclick="askQuestion('Show me how to fix the bugs')" style="background: #e8f0ff; border: 1px solid #0052cc; color: #0052cc; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 11px;">Bug Fixes</button>
                <button onclick="askQuestion('View conversation history')" style="background: #e8f0ff; border: 1px solid #0052cc; color: #0052cc; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 11px;">History</button>
            </div>
        </div>
    </div>
    
    <!-- Toggle Button -->
    <button 
        onclick="toggleChatbot()" 
        style="width: 100%; margin-top: 10px; background: #0052cc; color: white; border: none; padding: 8px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 13px;"
        id="toggle-btn"
    >Open Chatbot</button>
    
</div>

<script>
// Global variables
const REVIEW_ID = "{review_id}";
const API_BASE = "http://localhost:10000";
let chatOpen = false;
let isLoading = false;

// Toggle chatbot visibility
function toggleChatbot() {{
    chatOpen = !chatOpen;
    const container = document.getElementById("chatbot-container");
    const btn = document.getElementById("toggle-btn");
    
    if (chatOpen) {{
        container.style.display = "block";
        btn.textContent = "Close Chatbot";
        document.getElementById("chat-input").focus();
    }} else {{
        container.style.display = "none";
        btn.textContent = "Open Chatbot";
    }}
}}

// Send chat message
async function sendChatMessage() {{
    const input = document.getElementById("chat-input");
    const message = input.value.trim();
    
    if (!message || isLoading) return;
    
    isLoading = true;
    input.disabled = true;
    
    try {{
        // Add user message to chat
        addMessageToChat("YOU", message);
        input.value = "";
        
        // Send to API
        const response = await fetch(`${{API_BASE}}/chat/${{REVIEW_ID}}`, {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify({{message: message}})
        }});
        
        if (!response.ok) {{
            addMessageToChat("ERROR", "Failed to get response from chatbot");
            return;
        }}
        
        const data = await response.json();
        addMessageToChat("CHATBOT", data.message || "No response");
        
    }} catch (error) {{
        addMessageToChat("ERROR", `Error: ${{error.message}}`);
    }} finally {{
        isLoading = false;
        input.disabled = false;
        input.focus();
    }}
}}

// Ask a suggested question
function askQuestion(question) {{
    document.getElementById("chat-input").value = question;
    sendChatMessage();
}}

// Add message to chat display
function addMessageToChat(role, message) {{
    const messagesDiv = document.getElementById("chat-messages");
    const msgEl = document.createElement("div");
    msgEl.style.marginBottom = "8px";
    msgEl.style.padding = "8px";
    msgEl.style.backgroundColor = role === "YOU" ? "#e3f2fd" : role === "ERROR" ? "#ffebee" : "#f1f1f1";
    msgEl.style.borderRadius = "4px";
    msgEl.style.fontSize = "12px";
    msgEl.innerHTML = `<strong style="color: #0052cc;">[${role}]</strong><br>${message}`;
    messagesDiv.appendChild(msgEl);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}}

// Handle Enter key
document.addEventListener("DOMContentLoaded", function() {{
    const input = document.getElementById("chat-input");
    if (input) {{
        input.addEventListener("keypress", function(e) {{
            if (e.key === "Enter") {{
                sendChatMessage();
            }}
        }});
    }}
}});
</script>
"""
    
    return html_content


def post_chatbot_to_bitbucket(bitbucket_integration, workspace, repo_slug, pr_id, review_id, review_summary):
    """
    Posts the interactive chatbot UI as a comment to the Bitbucket PR
    """
    
    # Create the chatbot comment
    chatbot_html = create_interactive_chatbot_comment(review_id, review_summary)
    
    # Create comment body with HTML
    comment_body = f"""
# 🤖 Interactive AI Code Review Chatbot

{chatbot_html}

---

### How to Use:
1. Click "Open Chatbot" button above
2. Ask questions about the review findings
3. Get detailed explanations and suggestions
4. Use suggested questions for quick help

**Review ID:** `{review_id}`

**Quick Stats:**
- Overall Score: **{review_summary.get('overall_score', 'N/A')}/100**
- Total Comments: **{review_summary.get('total_comments', 0)}**
- Critical Issues: **{review_summary.get('critical_issues', 0)}**
- High Issues: **{review_summary.get('high_issues', 0)}**
"""
    
    # Post to Bitbucket
    try:
        bitbucket_integration.post_comment(workspace, repo_slug, pr_id, comment_body)
        print(f"[✓] Posted interactive chatbot to PR #{pr_id}")
        return True
    except Exception as e:
        print(f"[!] Failed to post chatbot: {str(e)}")
        return False


# Example usage in app.py for Bitbucket webhook:
"""
@app.post("/webhook/bitbucket")
async def bitbucket_webhook(request: Request, background_tasks: BackgroundTasks):
    # ... existing code ...
    
    # After posting review summary, also post interactive chatbot
    await bitbucket_integration.post_interactive_chatbot(
        workspace=workspace,
        repo_slug=repo_slug,
        pr_id=pr_id,
        review_id=review_response.get("review_id"),
        review_summary=review_response.get("summary", {})
    )
"""
