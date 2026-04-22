# AI Code Review Engine

A professional, enterprise-grade AI-powered code review engine designed for seamless integration with Bitbucket. Similar to CodeRabbit and Bito AI, this engine provides comprehensive, structured code analysis for pull requests and code changes with Kafka-driven event architecture for optimized workflows.

## Features

- **Kafka-Driven Architecture**: Event-based workflow with optimized suggestion generation
- **Deep Dependency Analysis**: Identifies dependency conflicts, transitive dependencies, and vulnerabilities across Python, Node.js, Java, C#, Go, and Rust
- **Approval Workflow Control**: Strict approval/merge gating based on analysis completion and destination branch
- **Structured Analysis**: Detailed file-by-file code review with severity levels
- **Multiple Categories**: Bugs, security issues, performance, maintainability, style, best practices
- **AI-Powered Insights**: Uses advanced language models for intelligent code analysis
- **Inline Code Suggestions**: Provides actionable code suggestions that can be applied directly in PRs
- **Consolidated Security Analysis**: Unified security assessment across all changed files
- **Interactive Chatbot**: Ask questions about review findings and get detailed explanations
- **Multi-Language Support**: Supports 40+ programming languages and file types including Python, JavaScript, TypeScript, Java, C++, Go, Rust, PHP, Ruby, and more
- **Configurable Rules**: Customizable review criteria and severity thresholds
- **RESTful API**: Clean, documented API for easy integration
- **Caching**: Intelligent caching to optimize performance and costs
- **Enterprise Ready**: Logging, error handling, and scalability features

## Project Structure

```
ai-code-review-engine/
├── models/                 # Pydantic data models
│   ├── __init__.py
│   └── review.py          # Review request/response models
├── services/              # Business logic
│   ├── __init__.py
│   ├── ai_review.py       # Core AI review engine
│   ├── chatbot_service.py # Interactive chatbot for review discussions
│   ├── kafka_config.py    # Kafka event handler & approval workflow
│   └── dependency_analyzer.py  # Deep dependency analysis
├── integrations/          # Platform integrations
│   ├── __init__.py
│   └── bitbucket_integration.py  # Bitbucket webhook handler
├── tests/                 # Unit and integration tests
│   ├── test_api.py
│   ├── test_chatbot.py    # Chatbot functionality tests
│   └── test_security.py
├── app.py                 # FastAPI application
├── demo_chatbot.py        # Interactive chatbot demo script
├── requirements.txt       # Dependencies
├── .env.example          # Environment template
├── .gitignore            # Git ignore rules
└── README.md             # This documentation
```

## Quick Start

### 1. Setup Environment
```bash
git clone <your-repo-url>
cd ai-code-review-engine
cp .env.example .env
# Edit .env with your Azure OpenAI and Bitbucket credentials
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file with:

```bash
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com
AZURE_OPENAI_API_VERSION=2025-01-01-preview
AZURE_OPENAI_MODEL=gpt-4o-india-atul-b2b

# Bitbucket Configuration
BITBUCKET_OAUTH_TOKEN=your_oauth_token_or_app_password
BITBUCKET_USERNAME=your_username  # Required if using app password
BITBUCKET_WEBHOOK_SECRET=your_webhook_secret

# Optional: Kafka Configuration
KAFKA_BROKER=localhost:9092
KAFKA_TOPIC_PREFIX=code-review
```

### 4. Run the Application
```bash
# Start the main API server
uvicorn app:app --reload --host 0.0.0.0 --port 10000
```

### 5. Access Services
- **Main API**: http://localhost:10000
- **API Documentation**: http://localhost:10000/docs
- **Health Check**: http://localhost:10000/health

### 6. Using the Interactive Chatbot
After performing a code review, you can chat with the AI about the findings:

```python
import requests

# 1. Perform a code review
review_response = requests.post("http://localhost:10000/review", json={
    "diff": "your-git-diff-here"
})
review_data = review_response.json()
chat_id = review_data["metadata"]["chat_review_id"]

# 2. Ask questions about the review
chat_response = requests.post(f"http://localhost:10000/chat/{chat_id}", json={
    "message": "Can you explain the security issues in more detail?"
})
print(chat_response.json()["response"])

# 3. Get conversation history
history = requests.get(f"http://localhost:10000/chat/{chat_id}/history")
print(history.json())
```

**Chatbot Features:**
- Ask for detailed explanations of review findings
- Get clarification on technical recommendations
- Request examples of how to fix issues
- Discuss specific code quality concerns
- Understand complex security or performance issues
- **Access complete file content** for files being reviewed in the PR

### 7. Configure Bitbucket Webhook
1. Go to your Bitbucket repository
2. Settings → Webhooks → Add webhook
3. URL: `http://your-server.com:10000/webhook/bitbucket`
4. Events: Pull request (created, updated, reopened)
5. Active: ✓
6. Secret: Same as `BITBUCKET_WEBHOOK_SECRET`


## API Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation.

### Endpoints

#### POST `/review`
Perform comprehensive AI-powered code review.

**Request Body:**
```json
{
  "diff": "git diff content...",
  "repository_url": "https://github.com/user/repo",
  "branch": "feature/branch",
  "commit_sha": "abc123...",
  "author": "developer@example.com",
  "files_changed": ["src/main.py", "tests/test.py"],
  "config": {
    "enabled_categories": ["bugs", "security", "performance"],
    "severity_threshold": "medium",
    "max_comments_per_file": 5
  }
}
```

**Response:**
```json
{
  "review_id": "review_2024-01-01T12:00:00",
  "summary": {
    "overall_score": 85,
    "total_comments": 12,
    "critical_issues": 0,
    "high_issues": 2,
    "medium_issues": 5,
    "low_issues": 3,
    "info_suggestions": 2,
    "categories_breakdown": {
      "bugs": 3,
      "security": 1,
      "performance": 2,
      "maintainability": 4,
      "style": 1,
      "best_practices": 1
    }
  },
  "files": [
    {
      "file_path": "src/main.py",
      "language": "python",
      "summary": "Good implementation with minor style issues",
      "comments": [
        {
          "id": "src/main.py_12345",
          "category": "style",
          "severity": "low",
          "title": "Missing docstring",
          "description": "Function lacks documentation",
          "location": {"line_start": 10, "line_end": 15},
          "suggestion": "Add a docstring explaining the function's purpose",
          "code_example": "```python\ndef my_function():\n    \"\"\"Brief description of what this function does.\"\"\"\n    pass\n```"
        }
      ],
      "metrics": {
        "complexity_score": 3,
        "maintainability_index": 85
      }
    }
  ],
  "overall_feedback": "Good job! The code changes are solid with some minor improvements needed.",
  "recommendations": [
    "Fix all critical issues before merging",
    "Ensure Python code follows PEP 8 style guidelines"
  ]
}
```

## Inline Code Suggestions

The AI Code Review Engine now supports **inline code suggestions** that can be applied directly within pull request interfaces on Bitbucket.

### How It Works

When reviewing code changes, the AI analyzes the diff and generates specific, actionable code replacements for identified issues. These suggestions appear as inline comments in the PR that developers can reference for fixes.

### Features

- **Bitbucket Integration**: Provides formatted code suggestions in PR comments
- **Precise Location**: Suggestions are tied to specific line numbers in the diff
- **Actionable Fixes**: Each suggestion includes the exact replacement code
- **Severity-Based**: Suggestions are provided for issues of all severity levels that have clear fixes

### Example

For a security issue like plain-text password storage, the AI might suggest:

**Bitbucket Format:**
```markdown
🔴 Plain text password storage

**Category:** Security  
**Severity:** High

Storing passwords in plain text is a security vulnerability.

**Suggestion:** Use proper password hashing with bcrypt

**Suggested change:**
```python
hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
```
```

### Supported Languages & File Types

The AI Code Review Engine supports 40+ programming languages and file types:

**Programming Languages:**
- Python (.py, .pyx, .pyw)
- JavaScript (.js, .mjs, .cjs, .jsx)
- TypeScript (.ts, .tsx, .d.ts)
- Java (.java, .jsp, .jar)
- C/C++ (.c, .cpp, .cc, .cxx, .h, .hpp)
- C# (.cs, .csx)
- Go (.go)
- Rust (.rs)
- PHP (.php, .phtml)
- Ruby (.rb, .rbw)
- Swift (.swift)
- Kotlin (.kt, .kts)
- Scala (.scala, .sc)
- R (.r, .rmd)
- Perl (.pl, .pm, .t)
- Lua (.lua)
- Dart (.dart)
- Haskell (.hs)
- OCaml (.ml)
- F# (.fs)
- VB.NET (.vb)
- Clojure (.clj)
- Elm (.elm)
- Elixir (.ex, .exs)

**Scripts & Shell:**
- Shell scripts (.sh, .bash, .zsh, .fish)
- PowerShell (.ps1)

**Web Technologies:**
- HTML (.html, .htm)
- CSS (.css, .scss, .sass, .less)

**Configuration & Data:**
- JSON (.json)
- XML (.xml)
- YAML (.yaml, .yml)
- TOML (.toml)
- INI (.ini, .cfg)

**Database:**
- SQL (.sql)

The AI automatically detects the language from file extensions and applies language-specific best practices and conventions.

### Benefits

- **Faster Reviews**: Developers can apply fixes instantly without manual implementation
- **Consistent Code**: AI ensures suggestions follow best practices and coding standards
- **Reduced Back-and-Forth**: Clear, actionable suggestions minimize review iterations
- **Learning Opportunity**: Developers learn from AI-suggested improvements

#### POST `/review/legacy`
Legacy endpoint for backward compatibility (returns simple text response).

#### GET `/health`
Health check endpoint.

#### GET `/config/default`
Get default review configuration.

## Configuration

### Azure OpenAI Setup

The AI Code Review Engine uses **Azure OpenAI GPT-4o** for intelligent code analysis. 

**Current Configuration:**
- **Model**: `gpt-4o-india-atul-b2b` (GPT-4 with extended capabilities)
- **API Version**: `2025-01-01-preview` (Latest stable preview)
- **Endpoint**: `https://agentictechops.openai.azure.com`
- **Embedding Model**: `text-embedding-3-large` (For advanced semantic analysis)

### Environment Variables

- `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key
- `AZURE_OPENAI_API_VERSION`: API version (default: 2023-12-01-preview)
- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint URL
- `AZURE_OPENAI_MODEL`: Your Azure OpenAI deployment/model name (preferred)
- `AZURE_OPENAI_DEPLOYMENT`: Your deployment name (fallback)

### Review Configuration

Customize review behavior through the `config` parameter:

```json
{
  "enabled_categories": ["bugs", "security", "performance", "maintainability"],
  "severity_threshold": "low",
  "max_comments_per_file": 10,
  "include_code_examples": true,
  "language_specific_rules": {
    "python": {
      "max_line_length": 88,
      "require_docstrings": true
    }
  }
}
```

## Integration Examples

### Bitbucket Cloud Integration

The engine includes comprehensive Bitbucket integration with automatic webhook handling:

#### Features:
- **PR Review**: Automatic review of pull request diffs
- **File Analysis**: Gets all changed files for comprehensive analysis
- **Deep Dependency Analysis**: Identifies and reports dependency issues
- **Security Analysis**: Consolidated security assessment across all files
- **Approval Workflow**: Gated approvals based on analysis completion and branch destination (master/sit only)
- **Kafka Events**: Emits events for analysis workflow coordination
- **Comment Posting**: Posts review comments and summaries to PRs
- **Multi-Platform**: Supports both Bitbucket Cloud and Bitbucket Server/Data Center
- **Authentication**: Supports OAuth tokens and personal access tokens

#### Setup for Bitbucket Cloud:
```bash

## Development

### Running Tests
```bash
pytest tests/
```

### Code Quality
```bash
# Linting
flake8 .

# Type checking
mypy .

# Formatting
black .
```

## Performance Optimization

- **Caching**: Reviews are cached based on diff content and configuration
- **Rate Limiting**: Built-in protection against abuse
- **Async Processing**: Non-blocking AI model calls
- **Batch Processing**: Support for multiple file analysis

## Security Considerations

- Input validation and sanitization
- Rate limiting to prevent abuse
- Secure environment variable handling
- No sensitive data logging
- HTTPS recommended for production

## Integrations

### Bitbucket Cloud Integration

Complete Bitbucket integration with Kafka-driven events and approval workflows in `integrations/bitbucket_integration.py`:

#### Features:
- **PR Review**: Automatic review of pull request diffs
- **Deep Dependency Analysis**: Identifies dependency conflicts and vulnerabilities
- **Consolidated Security Analysis**: Single unified security assessment across all files
- **Approval Workflow**: Automatic approval readiness check based on:
  - Analysis completion
  - No critical security issues
  - Destination branch (master/sit only)
- **Kafka Events**: Emits review workflow events for external system coordination
- **File Analysis**: Gets all changed files for comprehensive analysis
- **Comment Posting**: Posts review comments and summaries to PRs
- **Multi-Platform**: Supports both Bitbucket Cloud and Bitbucket Server/Data Center
- **Authentication**: Supports OAuth tokens and personal access tokens

#### Setup for Bitbucket Cloud:
```bash
# Set environment variables
export BITBUCKET_USERNAME=your_username
export BITBUCKET_TOKEN=your_app_password_or_access_token
export BITBUCKET_WEBHOOK_SECRET=your_webhook_secret

# Alternatively, if using OAuth tokens (recommended):
export BITBUCKET_OAUTH_TOKEN=your_oauth_token

# Install dependencies and run
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 10000
```

#### Setup for Bitbucket Server/Data Center:
```bash
# Set environment variables
export BITBUCKET_TOKEN=your_personal_access_token
export BITBUCKET_SERVER_URL=https://your-bitbucket-server.com
export BITBUCKET_WEBHOOK_SECRET=your_webhook_secret

# Run the application
uvicorn app:app --host 0.0.0.0 --port 10000
```

#### Bitbucket Webhook Setup:
1. Go to Repository Settings → Webhooks
2. Add webhook URL: `{your_server}/webhook/bitbucket`
3. Select the following events:
   - Pull request created
   - Pull request updated
   - Pull request reopened
4. Set webhook secret for security
5. Check "Skip certificate verification" (if using self-signed certs)

#### Kafka Event Types Emitted:
- `review:started` - Analysis started
- `review:analysis_complete` - Analysis finished
- `review:security_issue` - Security issue found (critical/high)
- `review:approval_ready` - Ready for approval (no critical issues, valid branch)
- `review:merge_requested` - Merge requested
- `review:failed` - Analysis failed

#### Approval Endpoint:
```
POST /bitbucket/approval/{workspace}/{repo_slug}/{pr_id}
```

**Request:**
```json
{
  "analysis_complete": true,
  "has_critical_issues": false,
  "destination_branch": "master"
}
```

**Response:**
```json
{
  "can_approve": true,
  "can_merge": true,
  "allowed_destinations": ["master", "sit"],
  "reason": "Code ready for approval"
}
```

## Kafka Configuration

The engine emits events to Kafka for workflow coordination:

```bash
# Set environment variables
export KAFKA_BROKER=localhost:9092
export KAFKA_TOPIC_PREFIX=code-review

# Events are automatically emitted on:
# - PR analysis start
# - Analysis completion with summary
# - Security issues (high/critical)
# - Approval readiness status
```

## Dependency Analysis

The engine performs deep dependency analysis across multiple languages:

**Supported Languages:**
- Python (requirements.txt, setup.py, pyproject.toml)
- Node.js (package.json, package-lock.json, yarn.lock)
- Java (pom.xml, build.gradle)
- C# (.csproj, packages.config)
- Go (go.mod, go.sum)
- Rust (Cargo.toml, Cargo.lock)

**Analysis Includes:**
- Direct and transitive dependency detection
- Version conflict identification
- Known vulnerability checking
- Deprecated package detection
- Unused dependency identification

**Example Output:**
```json
{
  "total_packages": 45,
  "conflicts": ["package-a: 1.0 vs 2.0"],
  "critical_issues": ["log4j: CVE-2021-44228"],
  "recommendations": [
    "Update log4j to 2.17.0 or later",
    "Remove unused dependency: old-lib"
  ]
}
```

## Usage Examples

### Bitbucket PR Review (Automatic)
```python
# No code needed - webhook automatically triggers on:
# - PR creation
# - PR update
# - PR reopening

# Review results are automatically posted as PR comments
```

### Check Approval Status
```python
import requests

response = requests.post(
    'http://localhost:10000/bitbucket/approval/workspace/repo/123',
    json={
        'analysis_complete': True,
        'has_critical_issues': False,
        'destination_branch': 'master'
    }
)

approval = response.json()
if approval['can_merge']:
    print("✓ Ready to merge")
else:
    print(f"✗ Cannot merge: {approval['reason']}")
```

## Configuration Options

### Review Categories

- `bugs`: Logic errors, crashes, incorrect behavior
- `security`: Vulnerabilities, insecure practices
- `performance`: Speed, memory, resource issues
- `maintainability`: Code structure, readability, technical debt
- `style`: Formatting, naming conventions
- `best_practices`: Industry standards, patterns
- `testing`: Test coverage, test quality
- `documentation`: Comments, docstrings, READMEs

### Severity Levels

- `critical`: Must fix before merge
- `high`: Should fix, major issues
- `medium`: Consider fixing, moderate impact
- `low`: Minor issues, nice to have
- `info`: Suggestions, informational only

### Environment Variables

#### GitHub:
- `GITHUB_TOKEN`: GitHub personal access token
- `GITHUB_WEBHOOK_SECRET`: Webhook secret for signature verification
- `GITHUB_DEEP_ANALYSIS`: Enable deep file content analysis (default: false)

#### Bitbucket:
- `BITBUCKET_USERNAME`: Bitbucket username for Cloud Basic Auth
- `BITBUCKET_TOKEN`: App password or access token for Cloud; also accepted as bearer auth when username is not set
- `BITBUCKET_APP_PASSWORD`: Optional Bitbucket Cloud app password when using `BITBUCKET_USERNAME`
- `BITBUCKET_OAUTH_TOKEN`: Optional OAuth token for Bitbucket Cloud
- `BITBUCKET_SERVER_URL`: Server URL for Data Center
- `BITBUCKET_WEBHOOK_SECRET`: Webhook secret

## Configuration Options

### Review Categories

- `bugs`: Logic errors, crashes, incorrect behavior
- `security`: Vulnerabilities, insecure practices
- `performance`: Speed, memory, resource issues
- `maintainability`: Code structure, readability, technical debt
- `style`: Formatting, naming conventions
- `best_practices`: Industry standards, patterns
- `testing`: Test coverage, test quality
- `documentation`: Comments, docstrings, READMEs

### Severity Levels

- `critical`: Must fix before merge
- `high`: Should fix, major issues
- `medium`: Consider fixing, moderate impact
- `low`: Minor issues, nice to have
- `info`: Suggestions, informational only

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Your License Here]#   a i - a g e n t 
 
 #   a i - a g e n t 
 
 