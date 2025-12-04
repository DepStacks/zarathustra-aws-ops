"""
MCP Client for connecting to MCP servers and executing tools
Supports both HTTP/SSE and STDIO transports
"""

import os
import json
import logging
import httpx
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MCPServer:
    """Configuration for an MCP server"""
    name: str
    url: str
    auth_token: Optional[str] = None
    transport: str = "sse"  # sse or stdio


class MCPClient:
    """
    Client for connecting to MCP servers and executing tools.
    
    Supports multiple MCP servers and provides a unified interface
    for the LangChain agent to call MCP tools.
    """
    
    def __init__(self, servers: List[MCPServer] = None):
        self.servers: Dict[str, MCPServer] = {}
        self._tools_cache: Dict[str, Dict[str, Any]] = {}
        self._http_client = httpx.Client(timeout=60.0)
        
        if servers:
            for server in servers:
                self.add_server(server)
    
    def add_server(self, server: MCPServer):
        """Add an MCP server configuration"""
        self.servers[server.name] = server
        logger.info(f"Added MCP server: {server.name} at {server.url}")
    
    def add_server_from_env(self, name: str, url_env: str, token_env: str = None):
        """Add an MCP server from environment variables"""
        url = os.getenv(url_env)
        if not url:
            logger.warning(f"MCP server {name} not configured (missing {url_env})")
            return
        
        token = os.getenv(token_env) if token_env else None
        self.add_server(MCPServer(name=name, url=url, auth_token=token))
    
    def _get_headers(self, server: MCPServer) -> Dict[str, str]:
        """Get HTTP headers for MCP server requests"""
        headers = {"Content-Type": "application/json"}
        if server.auth_token:
            headers["Authorization"] = f"Bearer {server.auth_token}"
        return headers
    
    async def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """List available tools from an MCP server"""
        if server_name not in self.servers:
            raise ValueError(f"Unknown MCP server: {server_name}")
        
        server = self.servers[server_name]
        
        # Check cache
        if server_name in self._tools_cache:
            return self._tools_cache[server_name]
        
        try:
            # MCP protocol: POST to /mcp with tools/list method
            response = self._http_client.post(
                f"{server.url}/mcp",
                headers=self._get_headers(server),
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {}
                }
            )
            response.raise_for_status()
            result = response.json()
            
            tools = result.get("result", {}).get("tools", [])
            self._tools_cache[server_name] = tools
            logger.info(f"Retrieved {len(tools)} tools from {server_name}")
            return tools
            
        except Exception as e:
            logger.error(f"Failed to list tools from {server_name}: {e}")
            return []
    
    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call a tool on an MCP server synchronously.
        
        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result
        """
        if server_name not in self.servers:
            return {"success": False, "error": f"Unknown MCP server: {server_name}"}
        
        server = self.servers[server_name]
        
        try:
            logger.info(f"Calling {server_name}.{tool_name} with args: {json.dumps(arguments, default=str)[:200]}...")
            
            # MCP protocol: POST to /mcp with tools/call method
            response = self._http_client.post(
                f"{server.url}/mcp",
                headers=self._get_headers(server),
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                logger.error(f"MCP tool error: {result['error']}")
                return {"success": False, "error": result["error"]}
            
            tool_result = result.get("result", {})
            logger.info(f"Tool {tool_name} completed successfully")
            return tool_result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling {tool_name}: {e.response.status_code} - {e.response.text}")
            return {"success": False, "error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            logger.error(f"Error calling {tool_name}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all tools from all configured servers"""
        all_tools = {}
        for server_name in self.servers:
            try:
                # Synchronous version using httpx
                server = self.servers[server_name]
                response = self._http_client.post(
                    f"{server.url}/mcp",
                    headers=self._get_headers(server),
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/list",
                        "params": {}
                    }
                )
                response.raise_for_status()
                result = response.json()
                tools = result.get("result", {}).get("tools", [])
                all_tools[server_name] = tools
            except Exception as e:
                logger.error(f"Failed to get tools from {server_name}: {e}")
                all_tools[server_name] = []
        return all_tools
    
    def close(self):
        """Close HTTP client connections"""
        self._http_client.close()


class MCPToolWrapper:
    """
    Wrapper to convert MCP tools into LangChain-compatible tools.
    
    This allows the LangChain agent to call MCP tools seamlessly.
    """
    
    def __init__(self, mcp_client: MCPClient, server_name: str, tool_spec: Dict[str, Any]):
        self.mcp_client = mcp_client
        self.server_name = server_name
        self.tool_name = tool_spec.get("name", "unknown")
        self.description = tool_spec.get("description", "")
        self.input_schema = tool_spec.get("inputSchema", {})
    
    def run(self, **kwargs) -> str:
        """Execute the MCP tool and return result as string"""
        result = self.mcp_client.call_tool(
            server_name=self.server_name,
            tool_name=self.tool_name,
            arguments=kwargs
        )
        return json.dumps(result, default=str, indent=2)
    
    def to_langchain_tool(self):
        """Convert to a LangChain BaseTool"""
        from langchain.tools import BaseTool
        from langchain_core.callbacks import CallbackManagerForToolRun
        from typing import Optional
        
        wrapper = self
        
        class MCPLangChainTool(BaseTool):
            name: str = f"{wrapper.server_name}_{wrapper.tool_name}"
            description: str = wrapper.description
            
            def _run(
                self,
                run_manager: Optional[CallbackManagerForToolRun] = None,
                **kwargs
            ) -> str:
                return wrapper.run(**kwargs)
        
        return MCPLangChainTool()
