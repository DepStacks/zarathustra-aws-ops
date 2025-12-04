"""
AWS Ops Agent - LangChain agent that orchestrates AWS operations via MCP tools
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.tools import BaseTool, StructuredTool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Field

from ..integrations.mcp_client import MCPClient, MCPServer

logger = logging.getLogger(__name__)


class AWSOpsAgent:
    """
    AI Agent for AWS Operations using MCP tools.
    
    This agent uses LangChain to orchestrate AWS operations by calling
    MCP servers that provide tools for Secrets Manager, Route53, S3, etc.
    """
    
    def __init__(
        self,
        openai_api_key: str,
        mcp_servers: List[Dict[str, str]] = None
    ):
        self.openai_api_key = openai_api_key
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
            temperature=0.1,
            openai_api_key=openai_api_key
        )
        
        # Initialize MCP client
        self.mcp_client = MCPClient()
        self._setup_mcp_servers(mcp_servers)
        
        # Load system prompt
        self.system_prompt = self._load_system_prompt()
        
        # Create agent
        self.agent_executor = self._create_agent()
        
        logger.info("AWS Ops Agent initialized successfully")
    
    def _setup_mcp_servers(self, mcp_servers: List[Dict[str, str]] = None):
        """Setup MCP server connections from config or environment"""
        
        # Default: Add aws-ops server from environment
        aws_ops_url = os.getenv("MCP_AWS_OPS_URL")
        aws_ops_token = os.getenv("MCP_AWS_OPS_TOKEN")
        
        if aws_ops_url:
            self.mcp_client.add_server(MCPServer(
                name="aws-ops",
                url=aws_ops_url,
                auth_token=aws_ops_token
            ))
        
        # Add additional servers from config
        if mcp_servers:
            for server_config in mcp_servers:
                self.mcp_client.add_server(MCPServer(
                    name=server_config.get("name"),
                    url=server_config.get("url"),
                    auth_token=server_config.get("auth_token")
                ))
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from file"""
        prompt_path = Path(__file__).parent.parent / "resources" / "prompt.md"
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return self._get_default_prompt()
    
    def _get_default_prompt(self) -> str:
        """Default system prompt if file not found"""
        return """You are an AI agent specialized in AWS operations.

You have access to MCP tools that can:
- Manage AWS Secrets Manager (create, read, update, delete secrets)
- Manage Route53 DNS records
- Manage S3 buckets and objects
- And more AWS services

When executing operations:
1. Always confirm the target AWS account (via profile or role_arn)
2. Use the appropriate tool for each operation
3. Report results clearly
4. Handle errors gracefully

Be precise, security-conscious, and efficient."""
    
    def _create_agent(self) -> AgentExecutor:
        """Create LangChain agent with MCP tools"""
        tools = self._build_tools()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_openai_functions_agent(self.llm, tools, prompt)
        
        return AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            return_intermediate_steps=True,
            max_iterations=15,
            handle_parsing_errors=True
        )
    
    def _build_tools(self) -> List[BaseTool]:
        """Build LangChain tools from MCP servers and local tools"""
        tools = []
        
        # Add MCP-based tools
        tools.extend(self._create_secrets_manager_tools())
        tools.extend(self._create_route53_tools())
        tools.extend(self._create_s3_tools())
        
        # Add utility tools
        tools.append(self._create_list_accounts_tool())
        
        logger.info(f"Built {len(tools)} tools for agent")
        return tools
    
    def _create_mcp_tool(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        args_schema: type
    ) -> BaseTool:
        """Create a LangChain tool that calls an MCP server tool"""
        
        mcp_client = self.mcp_client
        
        def tool_func(**kwargs) -> str:
            result = mcp_client.call_tool(server_name, tool_name, kwargs)
            return json.dumps(result, default=str, indent=2)
        
        return StructuredTool.from_function(
            func=tool_func,
            name=f"{server_name}_{tool_name}",
            description=description,
            args_schema=args_schema
        )
    
    # ==========================================================================
    # Secrets Manager Tools
    # ==========================================================================
    
    def _create_secrets_manager_tools(self) -> List[BaseTool]:
        """Create Secrets Manager tools"""
        tools = []
        
        class CreateSecretArgs(BaseModel):
            name: str = Field(description="Secret name (e.g., 'prod/myapp/database')")
            secret_value: str = Field(description="The secret value")
            description: Optional[str] = Field(None, description="Secret description")
            profile: Optional[str] = Field(None, description="AWS profile for local dev")
            role_arn: Optional[str] = Field(None, description="IAM role ARN for cross-account")
            region: Optional[str] = Field(None, description="AWS region")
        
        tools.append(self._create_mcp_tool(
            "aws-ops", "create_secret",
            "Create a new secret in AWS Secrets Manager",
            CreateSecretArgs
        ))
        
        class GetSecretArgs(BaseModel):
            secret_id: str = Field(description="Secret name or ARN")
            profile: Optional[str] = Field(None, description="AWS profile for local dev")
            role_arn: Optional[str] = Field(None, description="IAM role ARN for cross-account")
            region: Optional[str] = Field(None, description="AWS region")
        
        tools.append(self._create_mcp_tool(
            "aws-ops", "get_secret_value",
            "Retrieve the value of a secret from AWS Secrets Manager",
            GetSecretArgs
        ))
        
        class UpdateSecretArgs(BaseModel):
            secret_id: str = Field(description="Secret name or ARN")
            secret_value: str = Field(description="New secret value")
            description: Optional[str] = Field(None, description="New description")
            profile: Optional[str] = Field(None, description="AWS profile for local dev")
            role_arn: Optional[str] = Field(None, description="IAM role ARN for cross-account")
            region: Optional[str] = Field(None, description="AWS region")
        
        tools.append(self._create_mcp_tool(
            "aws-ops", "update_secret",
            "Update an existing secret's value in AWS Secrets Manager",
            UpdateSecretArgs
        ))
        
        class DeleteSecretArgs(BaseModel):
            secret_id: str = Field(description="Secret name or ARN")
            recovery_window_in_days: int = Field(30, description="Days before permanent deletion (7-30)")
            force_delete_without_recovery: bool = Field(False, description="Delete immediately without recovery")
            profile: Optional[str] = Field(None, description="AWS profile for local dev")
            role_arn: Optional[str] = Field(None, description="IAM role ARN for cross-account")
            region: Optional[str] = Field(None, description="AWS region")
        
        tools.append(self._create_mcp_tool(
            "aws-ops", "delete_secret",
            "Delete a secret from AWS Secrets Manager",
            DeleteSecretArgs
        ))
        
        class ListSecretsArgs(BaseModel):
            name_prefix: Optional[str] = Field(None, description="Filter secrets by name prefix")
            max_results: int = Field(100, description="Maximum number of results")
            profile: Optional[str] = Field(None, description="AWS profile for local dev")
            role_arn: Optional[str] = Field(None, description="IAM role ARN for cross-account")
            region: Optional[str] = Field(None, description="AWS region")
        
        tools.append(self._create_mcp_tool(
            "aws-ops", "list_secrets",
            "List secrets in AWS Secrets Manager",
            ListSecretsArgs
        ))
        
        return tools
    
    # ==========================================================================
    # Route53 Tools (placeholder - to be implemented in MCP server)
    # ==========================================================================
    
    def _create_route53_tools(self) -> List[BaseTool]:
        """Create Route53 tools (placeholder)"""
        # TODO: Add Route53 tools when MCP server supports them
        return []
    
    # ==========================================================================
    # S3 Tools (placeholder - to be implemented in MCP server)
    # ==========================================================================
    
    def _create_s3_tools(self) -> List[BaseTool]:
        """Create S3 tools (placeholder)"""
        # TODO: Add S3 tools when MCP server supports them
        return []
    
    # ==========================================================================
    # Utility Tools
    # ==========================================================================
    
    def _create_list_accounts_tool(self) -> BaseTool:
        """Create tool to list configured AWS accounts"""
        
        mcp_client = self.mcp_client
        
        class ListAccountsArgs(BaseModel):
            region: Optional[str] = Field(None, description="AWS region")
        
        def list_accounts(**kwargs) -> str:
            result = mcp_client.call_tool("aws-ops", "list_accounts", kwargs)
            return json.dumps(result, default=str, indent=2)
        
        return StructuredTool.from_function(
            func=list_accounts,
            name="list_aws_accounts",
            description="List all configured AWS accounts with their profiles and role ARNs",
            args_schema=ListAccountsArgs
        )
    
    # ==========================================================================
    # Public Methods
    # ==========================================================================
    
    def process_request(self, user_request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a user request to execute AWS operations.
        
        Args:
            user_request: The user's AWS operation request
            context: Optional context (e.g., default profile, region)
            
        Returns:
            Dictionary containing the response and metadata
        """
        context = context or {}
        
        # Build full input with context
        full_input = user_request
        if context:
            context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])
            full_input = f"""Context:
{context_str}

Request: {user_request}"""
        
        try:
            result = self.agent_executor.invoke({"input": full_input})
            
            return {
                "success": True,
                "response": result["output"],
                "intermediate_steps": result.get("intermediate_steps", [])
            }
            
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def close(self):
        """Clean up resources"""
        self.mcp_client.close()
