# Bitbucket Integration Testing Guide

## Prerequisites

1. **Azure OpenAI Setup**: You need an Azure OpenAI resource with a GPT-4 deployment
2. **Bitbucket Account**: A Bitbucket Cloud account (or Server/Data Center instance)
3. **Test Repository**: A Bitbucket repository with some code to test

## Step 1: Configure Environment Variables

Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
```

### Required for AI Engine:
```bash
AZURE_OPENAI_API_KEY=your_actual_azure_openai_key
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=your-gpt4-deployment-name
AZURE_OPENAI_API_VERSION=2023-12-01-preview
```

### Required for Bitbucket:
```bash
# For Bitbucket Cloud (use API tokens - app passwords are deprecated):
BITBUCKET_USERNAME=your_bitbucket_username
BITBUCKET_TOKEN=your_api_token_from_bitbucket
BITBUCKET_WEBHOOK_SECRET=your_webhook_secret  # Optional but recommended
```

# OR for Bitbucket Server:
BITBUCKET_TOKEN=your_personal_access_token
BITBUCKET_SERVER_URL=https://your-bitbucket-server.com

# Webhook security (optional but recommended):
BITBUCKET_WEBHOOK_SECRET=your_webhook_secret
```

## Step 2: Create Bitbucket API Token

**⚠️ IMPORTANT: App passwords are deprecated! Use API tokens instead.**

1. Go to Bitbucket → Your Profile → Personal Bitbucket Settings
2. Click **"API tokens"** (not "App passwords" - that's deprecated)
3. Click **"Create API token"**
4. Give it a name like "AI Code Review"
5. Select these scopes/permissions:
   - ✅ **Pull requests**: Read, Write
   - ✅ **Repositories**: Read
   - ✅ **Webhooks**: Read, Write
   - ✅ **Projects**: Read (if needed)
6. Copy the generated token (you won't see it again!)

## Step 3: Setup Test Repository

1. Create a new repository on Bitbucket (or use existing)
2. Add some code files (Python, JavaScript, etc.)
3. Create a branch and make some changes
4. Create a Pull Request

## Step 4: Setup Webhook

### For Bitbucket Cloud:
1. Go to Repository → Repository settings → Webhooks
2. Click "Add webhook"
3. Configure:
   - **Title**: "AI Code Review"
   - **URL**: `http://your-server:8002/webhook/bitbucket`
   - **Secret**: Your webhook secret (same as `BITBUCKET_WEBHOOK_SECRET`)
   - **Triggers**: Select "Pull request" events:
     - Pull request created
     - Pull request updated
     - Pull request reopened

### For Local Testing:
- Use a service like ngrok to expose your local server
- Command: `ngrok http 8002`
- Use the ngrok URL in webhook configuration

## Step 5: Install Dependencies & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run Bitbucket integration
python integrations/bitbucket_integration.py
```

The server will start on port 8002.

## Step 6: Test the Integration

### Method 1: Create/Update a PR
1. Create a new Pull Request in your test repository
2. Or update an existing PR (push new commits)
3. The webhook should trigger automatically
4. Check the PR for AI review comments

### Method 2: Manual Testing
Use curl to simulate a webhook:

```bash
curl -X POST http://localhost:8002/webhook/bitbucket \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature: sha256=your_signature" \
  -d '{
    "eventKey": "pullrequest:created",
    "pullRequest": {
      "id": 1,
      "title": "Test PR",
      "source": {
        "branch": {"name": "feature/test"},
        "commit": {"hash": "abc123"}
      },
      "author": {"display_name": "Test User"}
    },
    "repository": {
      "slug": "test-repo",
      "workspace": {"slug": "your-workspace"}
    }
  }'
```

## Step 7: Verify Results

1. **Check Server Logs**: Look for processing messages
2. **Check Bitbucket PR**: Should have AI review comments
3. **Review Comment Format**:
   ```
   🤖 AI Code Review Summary

   Overall Score: 85/100

   Issues Found:
   🔴 Critical: 0
   🟠 High: 2
   🟡 Medium: 5
   🟢 Low: 3
   ℹ️ Info: 2

   Feedback:
   Good job! The code changes are solid...

   Recommendations:
   - Fix all critical issues before merging
   - Ensure Python code follows PEP 8
   ```

## Troubleshooting

### Common Issues:

1. **"Authentication failed"**
   - Check `BITBUCKET_USERNAME` and `BITBUCKET_TOKEN`
   - Verify API token permissions (Pull requests: Read/Write, Repositories: Read)

2. **"Webhook not triggering"**
   - Check webhook URL is accessible (use ngrok for local testing)
   - Verify webhook secret matches
   - Check Bitbucket webhook delivery logs

3. **"No diff content"**
   - Ensure PR has actual code changes
   - Check repository permissions

4. **"AI API errors"**
   - Verify Azure OpenAI credentials
   - Check deployment name and endpoint
   - Ensure sufficient API quota

### Debug Mode:
Add logging to see more details:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Expected Behavior

✅ **Successful Test**:
- Server logs show PR processing
- AI review comments appear on PR
- Overall summary posted
- No errors in server logs

## Next Steps

Once testing works:
1. Deploy to production server
2. Configure production webhook URLs
3. Set up monitoring and alerts
4. Add more repositories
5. Customize review rules if needed