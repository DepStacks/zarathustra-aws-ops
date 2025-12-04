# Zarathustra AWS Ops

AI Agent for AWS Operations - Uses MCP (Model Context Protocol) tools for Secrets Manager, Route53, S3, and more.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Zarathustra AWS Ops                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    │
│  │ SQS Queue   │───▶│  SQS         │───▶│ Workflow        │    │
│  │ (Requests)  │    │  Listener    │    │ Manager         │    │
│  └─────────────┘    └──────────────┘    └────────┬────────┘    │
│                                                   │             │
│                                         ┌─────────▼─────────┐   │
│                                         │   LangChain       │   │
│                                         │   AWS Ops Agent   │   │
│                                         └─────────┬─────────┘   │
│                                                   │             │
│                                         ┌─────────▼─────────┐   │
│                                         │   MCP Client      │   │
│                                         └─────────┬─────────┘   │
│                                                   │             │
└───────────────────────────────────────────────────┼─────────────┘
                                                    │
                    ┌───────────────────────────────┼───────────────────────────────┐
                    │                               │                               │
           ┌────────▼────────┐            ┌────────▼────────┐            ┌────────▼────────┐
           │  AWS Ops MCP    │            │  Route53 MCP    │            │  S3 MCP         │
           │  (Secrets Mgr)  │            │  (Coming Soon)  │            │  (Coming Soon)  │
           └────────┬────────┘            └────────┬────────┘            └────────┬────────┘
                    │                               │                               │
           ┌────────▼────────┐            ┌────────▼────────┐            ┌────────▼────────┐
           │ AWS Secrets     │            │ AWS Route53     │            │ AWS S3          │
           │ Manager         │            │                 │            │                 │
           └─────────────────┘            └─────────────────┘            └─────────────────┘
```

## Features

- **AI-Powered Operations**: LangChain agent understands natural language requests
- **MCP Integration**: Connects to MCP servers for AWS operations
- **Multi-Account Support**: Profile and AssumeRole authentication
- **SQS-Based**: Async request processing via SQS queue
- **Callback Support**: Send results back to calling applications
- **Docker Ready**: Production-ready containerization

## Project Structure

```
zarathustra-aws-ops/
├── main.py                    # Entry point
├── src/
│   ├── core/
│   │   ├── agent.py           # LangChain agent with MCP tools
│   │   └── workflow_manager.py
│   ├── integrations/
│   │   └── mcp_client.py      # MCP client for tool execution
│   ├── listeners/
│   │   └── sqs_listener.py    # SQS message processor
│   └── resources/
│       └── prompt.md          # Agent system prompt
├── config/
│   └── mcp_servers.yaml       # MCP server configuration
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.12+
- AWS credentials configured
- OpenAI API key
- MCP server running (e.g., tool.aws-ops)

### Local Development

1. **Clone and setup**:
```bash
git clone https://github.com/DepStacks/zarathustra-aws-ops.git
cd zarathustra-aws-ops
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. **Run the agent**:
```bash
python main.py
```

### Docker Deployment

```bash
# With MCP server
docker-compose up -d

# Agent only (external MCP server)
docker build -t zarathustra-aws-ops .
docker run -d --env-file .env zarathustra-aws-ops
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | - |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4-turbo-preview` |
| `SQS_QUEUE_URL` | SQS queue URL (required) | - |
| `AWS_REGION` | AWS region | `us-east-1` |
| `MCP_AWS_OPS_URL` | AWS Ops MCP server URL | `http://localhost:8100` |
| `MCP_AWS_OPS_TOKEN` | MCP authentication token | - |
| `MAX_WORKERS` | Parallel message processors | `5` |

## SQS Message Format

Send messages to the SQS queue in this format:

```json
{
  "prompt": "Create a secret called prod/myapp/database with value {\"host\": \"db.example.com\"}",
  "profile": "production",
  "region": "us-east-1",
  "callback_url": "https://your-app.com/webhook/response",
  "metadata": {
    "request_id": "abc123",
    "user": "john@example.com"
  }
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `prompt` or `request` | Yes | Natural language AWS operation request |
| `profile` | No | AWS profile for credentials |
| `role_arn` | No | IAM role ARN for cross-account |
| `region` | No | AWS region override |
| `callback_url` | No | URL to send results |
| `metadata` | No | Additional context |

## Supported Operations

### Secrets Manager
- ✅ Create secret
- ✅ Get secret value
- ✅ Update secret
- ✅ Delete secret
- ✅ List secrets

### Route53 (Coming Soon)
- 🔜 Create/update DNS records
- 🔜 Delete DNS records
- 🔜 List hosted zones

### S3 (Coming Soon)
- 🔜 Create bucket
- 🔜 List buckets
- 🔜 Manage bucket policies

### EC2 (Coming Soon)
- 🔜 Instance management
- 🔜 Security groups

## Example Requests

### Create a Secret
```json
{
  "prompt": "Create a secret called prod/api/keys with value {\"stripe_key\": \"sk_live_xxx\", \"sendgrid_key\": \"SG.xxx\"}",
  "profile": "production"
}
```

### List Secrets
```json
{
  "prompt": "List all secrets starting with 'prod/' in the staging account",
  "profile": "staging"
}
```

### Delete a Secret
```json
{
  "prompt": "Delete the secret staging/old-app/config with 7 day recovery window",
  "profile": "staging"
}
```

## Integration with zarathustra-api

This agent is designed to work with [zarathustra-api](https://github.com/DepStacks/zarathustra-api), which provides an API Gateway that publishes requests to the SQS queue.

```
Slack/Telegram/Jira → zarathustra-api → SQS → zarathustra-aws-ops → MCP → AWS
```

## Development

### Adding New MCP Tools

1. Add tool definitions in `src/core/agent.py`:
```python
def _create_new_service_tools(self) -> List[BaseTool]:
    class NewToolArgs(BaseModel):
        param: str = Field(description="Parameter description")
    
    return [self._create_mcp_tool(
        "aws-ops", "new_tool",
        "Tool description",
        NewToolArgs
    )]
```

2. Register tools in `_build_tools()`:
```python
tools.extend(self._create_new_service_tools())
```

### Running Tests
```bash
pytest tests/
```

## Security

- Never hardcode AWS credentials
- Use IAM roles (IRSA) in production
- MCP tokens should be stored securely
- Enable CloudTrail for audit logging

## License

MIT

## Related Projects

- [zarathustra-api](https://github.com/DepStacks/zarathustra-api) - API Gateway for AI agents
- [tool.aws-ops](https://github.com/DepStacks/tool.aws-ops) - AWS Operations MCP Server
- [zarathustra](https://github.com/DepStacks/zarathustra) - Original IaC automation agent
