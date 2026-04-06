# AI Code Review Engine

A professional, enterprise-grade AI-powered code review engine designed for seamless integration with GitHub and Bitbucket. Similar to CodeRabbit and Bito AI, this engine provides comprehensive, structured code analysis for pull requests and code changes.

## Features

- **Structured Analysis**: Detailed file-by-file code review with severity levels
- **Multiple Categories**: Bugs, security issues, performance, maintainability, style, best practices
- **AI-Powered Insights**: Uses advanced language models for intelligent code analysis
- **Inline Code Suggestions**: Provides actionable code suggestions that can be applied directly in PRs
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
│   └── ai_review.py       # Core AI review engine
├── integrations/          # Platform integrations
│   ├── __init__.py
│   └── github_integration.py  # GitHub webhook handler
├── tests/                 # Unit and integration tests
│   └── test_api.py
├── app.py                 # FastAPI application
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
# Edit .env with your API keys and tokens
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run All Services
```bash
# Linux/Mac
./start.sh

# Windows
start.bat
```

Or run services individually:
```bash
# Main API server
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# GitHub integration (separate terminal)
python integrations/github_integration.py

# Bitbucket integration (separate terminal)
python integrations/bitbucket_integration.py
```

### 4. Access Services
- **Main API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **GitHub Integration**: http://localhost:8001 (if configured)
- **Bitbucket Integration**: http://localhost:8002 (if configured)

## Setup

1. **Clone and Install Dependencies**
   ```bash
   git clone <repository-url>
   cd ai-code-review-engine
   pip install -r requirements.txt
   ```

2. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your Azure OpenAI credentials
   ```

3. **Run the Application**
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

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

The AI Code Review Engine now supports **inline code suggestions** that can be applied directly within pull request interfaces on GitHub and Bitbucket.

### How It Works

When reviewing code changes, the AI analyzes the diff and generates specific, actionable code replacements for identified issues. These suggestions appear as inline comments that developers can apply with a single click.

### Features

- **GitHub Integration**: Uses ```suggestion blocks for one-click application
- **Bitbucket Integration**: Provides formatted code suggestions in PR comments
- **Precise Location**: Suggestions are tied to specific line numbers in the diff
- **Actionable Fixes**: Each suggestion includes the exact replacement code
- **Severity-Based**: Suggestions are provided for issues of all severity levels that have clear fixes

### Example

For a security issue like plain-text password storage, the AI might suggest:

**GitHub Format:**
```markdown
🔴 Plain text password storage

**Category:** Security  
**Severity:** High

Storing passwords in plain text is a security vulnerability

**Suggestion:** Use proper password hashing with bcrypt

```suggestion
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
```
```

**Bitbucket Format:**
```markdown
🔴 Plain text password storage

**Category:** Security  
**Severity:** High

Storing passwords in plain text is a security vulnerability

**Suggestion:** Use proper password hashing with bcrypt

**Suggested change:**
```diff
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

### GitHub Integration

```python
import requests

def review_pull_request(pr_number, diff_content):
    response = requests.post('http://localhost:8000/review', json={
        'diff': diff_content,
        'repository_url': f'https://github.com/owner/repo',
        'branch': f'pr-{pr_number}',
        'config': {
            'enabled_categories': ['bugs', 'security'],
            'severity_threshold': 'high'
        }
    })

    review = response.json()

    # Post comments to GitHub PR
    for file_review in review['files']:
        for comment in file_review['comments']:
            if comment['severity'] in ['critical', 'high']:
                # Post GitHub comment
                pass
```

### Bitbucket Integration

Similar pattern for Bitbucket webhooks and API calls.

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

### GitHub Integration

The engine includes comprehensive GitHub integration in `integrations/github_integration.py`:

#### Features:
- **PR Review**: Automatic review of pull request diffs
- **File Analysis**: Gets all changed files for comprehensive analysis
- **Deep Analysis**: Optional full file content analysis (configurable)
- **Repository Review**: Review all code files in an entire repository
- **Comment Posting**: Posts review comments and summaries to PRs
- **Authentication**: Supports GitHub tokens and webhook secrets

#### Setup:
```bash
# Set environment variables
export GITHUB_TOKEN=your_github_token
export GITHUB_WEBHOOK_SECRET=your_webhook_secret
export GITHUB_DEEP_ANALYSIS=true  # Optional: enable deep file analysis

# Run the integration server
python integrations/github_integration.py
```

#### API Endpoints:
- **`POST /review/repository/github`**: Review entire GitHub repository

#### GitHub App Setup:
1. Create a GitHub App in your organization
2. Set webhook URL to your server endpoint
3. Subscribe to "Pull request" events
4. Install the app on your repositories
5. Set repository permissions for contents, pull requests, and issues

### Bitbucket Integration

Complete Bitbucket integration in `integrations/bitbucket_integration.py`:

#### Features:
- **PR Review**: Automatic review of pull request diffs
- **File Analysis**: Gets all changed files for comprehensive analysis
- **Comment Posting**: Posts review comments and summaries to PRs
- **Multi-Platform**: Supports both Bitbucket Cloud and Bitbucket Server/Data Center
- **Authentication**: Supports API tokens and personal access tokens (app passwords deprecated)

#### Setup for Bitbucket Cloud:
```bash
# Set environment variables
export BITBUCKET_USERNAME=your_username
export BITBUCKET_TOKEN=your_api_token
export BITBUCKET_WEBHOOK_SECRET=your_webhook_secret

# Run the integration server
python integrations/bitbucket_integration.py
```

#### Setup for Bitbucket Server:
```bash
# Set environment variables
export BITBUCKET_TOKEN=your_personal_access_token
export BITBUCKET_SERVER_URL=https://your-bitbucket-server.com
export BITBUCKET_WEBHOOK_SECRET=your_webhook_secret

# Run the integration server
python integrations/bitbucket_integration.py
```

#### Bitbucket Webhook Setup:
1. Go to Repository Settings → Webhooks
2. Add webhook URL pointing to your server
3. Select "Pull request" events
4. Set webhook secret for security

## Usage Examples

### GitHub PR Review
```python
# Automatic via webhook - no code needed
# Webhook triggers on PR open/update
```

### GitHub Repository Review
```python
import requests

response = requests.post('http://localhost:8000/review/repository/github', json={
    'repo_full_name': 'owner/repository-name',
    'branch': 'main'
})

review = response.json()
print(f"Repository score: {review['summary']['overall_score']}")
```

### Bitbucket PR Review
```python
# Automatic via webhook - no code needed
# Webhook triggers on PR events
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
- `BITBUCKET_USERNAME`: Bitbucket username
- `BITBUCKET_TOKEN`: API token for Cloud (app passwords deprecated) or personal access token for Server
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