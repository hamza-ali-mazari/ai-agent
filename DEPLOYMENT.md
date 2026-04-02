# AI Code Review Engine - Deployment Guide

## 🚀 Deploy to Render

### Option 1: Using render.yaml (Recommended)

1. **Connect your GitHub repository to Render**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New" → "Blueprint"
   - Connect your GitHub repository

2. **Render will automatically detect `render.yaml`** and set up the service

3. **Configure Environment Variables** in Render dashboard:
   ```
   AZURE_OPENAI_API_KEY=your_azure_openai_key
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_DEPLOYMENT=your_gpt4_deployment
   AZURE_OPENAI_API_VERSION=2023-12-01-preview
   BITBUCKET_USERNAME=your_bitbucket_username
   BITBUCKET_TOKEN=your_bitbucket_api_token
   BITBUCKET_WEBHOOK_SECRET=your_webhook_secret
   ```

4. **Deploy** - Render will build and deploy automatically

### Option 2: Manual Web Service Setup

1. **Create a new Web Service** in Render
2. **Connect your repository**
3. **Configure build & start commands**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. **Add environment variables** as above
5. **Deploy**

### Option 3: Using Docker

1. **Create a new Web Service** in Render
2. **Select "Docker"** as runtime
3. **Connect your repository**
4. **Render will automatically use the `Dockerfile`**
5. **Add environment variables** as above
6. **Deploy**

## 🔗 Configure Webhooks

### Bitbucket Setup

1. **Go to your Bitbucket repository** → **Repository settings** → **Webhooks**

2. **Create webhook**:
   - **Title**: `AI Code Review`
   - **URL**: `https://your-render-app-url.onrender.com/webhook/bitbucket`
   - **Secret**: Your `BITBUCKET_WEBHOOK_SECRET`
   - **Triggers**: Select PR events (created, updated, comments)

### GitHub Setup (Optional)

1. **Go to your GitHub repository** → **Settings** → **Webhooks**

2. **Add webhook**:
   - **Payload URL**: `https://your-render-app-url.onrender.com/webhook/github`
   - **Secret**: Your `GITHUB_WEBHOOK_SECRET`
   - **Events**: Pull requests

## 🧪 Testing Your Deployment

1. **Check health endpoint**: `https://your-app.onrender.com/health`

2. **Test API directly**:
   ```bash
   curl -X POST https://your-app.onrender.com/review \
     -H "Content-Type: application/json" \
     -d '{"diff": "+ def hello():\n+     print(\"Hello World\")"}'
   ```

3. **Create a test PR** in your repository to trigger webhook

## 📊 Monitoring

- **Render Dashboard**: View logs and metrics
- **Webhook Delivery**: Check Bitbucket webhook delivery logs
- **API Logs**: Monitor FastAPI logs in Render

## 🔧 Troubleshooting

### Common Issues:

1. **Webhook not triggering**:
   - Verify webhook URL is accessible
   - Check webhook secret matches
   - Ensure repository permissions are correct

2. **AI review not working**:
   - Verify Azure OpenAI credentials
   - Check API quota/limits
   - Review Render logs for errors

3. **Port issues**:
   - Render provides `$PORT` environment variable
   - App automatically uses this port

## 🎯 Production Checklist

- ✅ Environment variables configured
- ✅ Webhook URL updated in repository settings
- ✅ Azure OpenAI API access verified
- ✅ Repository permissions checked
- ✅ SSL certificate (Render provides automatically)
- ✅ Health checks passing

## 📞 Support

If you encounter issues:
1. Check Render deployment logs
2. Verify environment variables
3. Test webhook URL accessibility
4. Review Bitbucket webhook delivery logs

---

**Your AI Code Review Engine is now deployed and ready to automatically review pull requests! 🎉**