"""
Slack Responder - Sends responses back to Slack via response_url
"""

import logging
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)


class SlackResponder:
    """
    Handles sending responses back to Slack.
    
    Uses Slack's response_url (from slash commands) or Web API
    to send formatted messages back to the user.
    """
    
    def __init__(self, timeout: float = 30.0):
        self._http_client = httpx.Client(timeout=timeout)
    
    def send_response(
        self,
        response_url: str,
        text: str,
        success: bool = True,
        response_type: str = "in_channel",
        replace_original: bool = True
    ) -> Dict[str, Any]:
        """
        Send a response to Slack via response_url.
        
        Args:
            response_url: Slack's response_url from the slash command
            text: The message text to send
            success: Whether the operation was successful
            response_type: "in_channel" (visible to all) or "ephemeral" (only to user)
            replace_original: Whether to replace the original "Processing..." message
            
        Returns:
            Dictionary with success status
        """
        try:
            # Format the message for Slack
            formatted_text = self._format_message(text, success)
            
            payload = {
                "response_type": response_type,
                "replace_original": replace_original,
                "text": formatted_text
            }
            
            # Add blocks for richer formatting
            blocks = self._create_blocks(text, success)
            if blocks:
                payload["blocks"] = blocks
            
            response = self._http_client.post(
                response_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            # Slack returns 200 with "ok" for success
            if response.status_code == 200:
                logger.info(f"Successfully sent response to Slack")
                return {"success": True}
            else:
                logger.error(f"Slack response error: {response.status_code} - {response.text}")
                return {"success": False, "error": f"Slack returned {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Failed to send Slack response: {e}")
            return {"success": False, "error": str(e)}
    
    def send_error(
        self,
        response_url: str,
        error_message: str,
        response_type: str = "ephemeral"
    ) -> Dict[str, Any]:
        """Send an error response to Slack"""
        return self.send_response(
            response_url=response_url,
            text=error_message,
            success=False,
            response_type=response_type
        )
    
    def _format_message(self, text: str, success: bool) -> str:
        """Format message with appropriate emoji prefix"""
        if success:
            return f"✅ {text}"
        else:
            return f"❌ {text}"
    
    def _create_blocks(self, text: str, success: bool) -> list:
        """
        Create Slack blocks for richer formatting.
        
        Returns None for simple messages, blocks for complex ones.
        """
        # For longer responses, use blocks for better formatting
        if len(text) > 200 or '\n' in text:
            icon = ":white_check_mark:" if success else ":x:"
            
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{icon} *Result*"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": self._truncate_for_slack(text)
                    }
                }
            ]
            
            return blocks
        
        return None
    
    def _truncate_for_slack(self, text: str, max_length: int = 2900) -> str:
        """Truncate text to fit Slack's limits (3000 chars per block)"""
        if len(text) <= max_length:
            return text
        
        return text[:max_length] + "\n\n_...truncated_"
    
    def format_agent_response(self, agent_result: Dict[str, Any]) -> str:
        """
        Format the agent's result for Slack display.
        
        Args:
            agent_result: The result from the AI agent
            
        Returns:
            Formatted string for Slack
        """
        if not agent_result.get("success"):
            error = agent_result.get("error", "Unknown error occurred")
            return f"*Error:* {error}"
        
        response = agent_result.get("response", "")
        
        # If there are intermediate steps, summarize them
        steps = agent_result.get("intermediate_steps", [])
        if steps:
            tools_used = []
            for step in steps:
                if isinstance(step, tuple) and len(step) >= 1:
                    action = step[0]
                    if hasattr(action, 'tool'):
                        tools_used.append(action.tool)
            
            if tools_used:
                tools_str = ", ".join(set(tools_used))
                response = f"*Tools used:* `{tools_str}`\n\n{response}"
        
        return response
    
    def close(self):
        """Close HTTP client"""
        self._http_client.close()
