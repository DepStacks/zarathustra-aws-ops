# Zarathustra AWS Ops - Agent Guidelines

## Project Overview

AI Agent for AWS Operations using MCP (Model Context Protocol) tools. Processes natural language requests from SQS queue and executes AWS operations via MCP servers.

## Architecture

### Components

1. **main.py** - Application entry point
2. **src/listeners/sqs_listener.py** - SQS message consumer
3. **src/core/workflow_manager.py** - Request orchestration
4. **src/core/agent.py** - LangChain agent with MCP tools
5. **src/integrations/mcp_client.py** - MCP server communication
6. **src/resources/prompt.md** - Agent system prompt

### Data Flow

```
SQS Message → SQS Listener → Workflow Manager → Agent → MCP Client → MCP Server → AWS
```

## Code Conventions

### Python Version
- Use Python 3.12

### Type Hints
- Always use type hints for function parameters and return values

### Logging
- Use `logging` module with appropriate levels
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

### Error Handling
- Return dictionaries with `success` boolean and `error` message
- Log errors before returning

### Example Pattern
```python
def operation(self, param: str) -> Dict[str, Any]:
    try:
        # operation logic
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        return {"success": False, "error": str(e)}
```

## Adding New MCP Tools

### Step 1: Define Args Schema
```python
class NewToolArgs(BaseModel):
    required_param: str = Field(description="Description")
    optional_param: Optional[str] = Field(None, description="Optional")
    profile: Optional[str] = Field(None, description="AWS profile")
    role_arn: Optional[str] = Field(None, description="IAM role ARN")
    region: Optional[str] = Field(None, description="AWS region")
```

### Step 2: Create Tool
```python
def _create_new_tools(self) -> List[BaseTool]:
    return [self._create_mcp_tool(
        "aws-ops",           # MCP server name
        "tool_name",         # Tool name on MCP server
        "Tool description",  # Description for LLM
        NewToolArgs          # Args schema
    )]
```

### Step 3: Register Tool
Add to `_build_tools()` in `agent.py`:
```python
tools.extend(self._create_new_tools())
```

## MCP Client Usage

### Calling MCP Tools
```python
result = self.mcp_client.call_tool(
    server_name="aws-ops",
    tool_name="create_secret",
    arguments={
        "name": "my-secret",
        "secret_value": "secret123",
        "profile": "production"
    }
)
```

### Adding MCP Servers
```python
self.mcp_client.add_server(MCPServer(
    name="new-server",
    url="http://server:8000",
    auth_token="token"
))
```

## Environment Variables

### Required
- `OPENAI_API_KEY` - OpenAI API key
- `SQS_QUEUE_URL` - SQS queue URL

### Optional
- `OPENAI_MODEL` - Model name (default: gpt-4-turbo-preview)
- `AWS_REGION` - AWS region (default: us-east-1)
- `MCP_AWS_OPS_URL` - MCP server URL
- `MCP_AWS_OPS_TOKEN` - MCP auth token
- `MAX_WORKERS` - Parallel workers (default: 5)
- `LOG_LEVEL` - Logging level (default: INFO)

## SQS Message Format

### Input
```json
{
  "prompt": "Natural language request",
  "profile": "aws-profile",
  "role_arn": "arn:aws:iam::xxx:role/xxx",
  "region": "us-east-1",
  "callback_url": "https://callback.url",
  "metadata": {}
}
```

### Output (Callback)
```json
{
  "message_id": "sqs-message-id",
  "success": true,
  "response": "Agent response text",
  "error": null
}
```

## Security Mandates

1. **No AWS Keys** - Use IAM roles or profiles, never access keys
2. **MCP Auth** - Always use authentication tokens for MCP servers
3. **Least Privilege** - Request only needed permissions
4. **Audit Logging** - Log all operations for compliance

## Testing

### Unit Tests
```bash
pytest tests/unit/
```

### Integration Tests
```bash
pytest tests/integration/ --mcp-url http://localhost:8100
```

## Docker Deployment

### Build
```bash
docker build -t zarathustra-aws-ops .
```

### Run
```bash
docker run -d \
  --env-file .env \
  -v ~/.aws:/root/.aws:ro \
  zarathustra-aws-ops
```

## Troubleshooting

### MCP Connection Failed
- Verify MCP server is running
- Check `MCP_AWS_OPS_URL` is correct
- Verify `MCP_AWS_OPS_TOKEN` matches server config

### AWS Permission Denied
- Check profile/role has required permissions
- Verify region is correct
- Check resource-level policies

### Agent Timeout
- Increase `SQS_VISIBILITY_TIMEOUT`
- Reduce `max_iterations` in agent config
- Check for infinite loops in tool calls

## Git Conventions

### Branches
- `main` - Production ready code
- `develop` - Development branch
- `feature/*` - New features
- `fix/*` - Bug fixes

### Commits
Use conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `refactor:` - Code refactoring
- `test:` - Tests

## Maintainers

- DepStacks Team
