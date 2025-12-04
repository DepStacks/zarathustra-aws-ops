"""
Workflow Manager - Orchestrates AWS operations requests
"""

import os
import logging
from typing import Dict, Any, Optional

from .agent import AWSOpsAgent

logger = logging.getLogger(__name__)


class WorkflowManager:
    """
    Manages the workflow for processing AWS operations requests.
    
    Receives requests from the SQS listener, processes them through
    the AI agent, and returns results.
    """
    
    def __init__(
        self,
        openai_api_key: str,
        mcp_servers: list = None
    ):
        self.openai_api_key = openai_api_key
        
        self.agent = AWSOpsAgent(
            openai_api_key=openai_api_key,
            mcp_servers=mcp_servers
        )
        
        logger.info("Workflow Manager initialized successfully")
    
    def process_aws_operation(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an AWS operation request.
        
        Args:
            request_data: Dictionary containing:
                - request: The user's AWS operation request (required)
                - profile: AWS profile to use (optional)
                - role_arn: IAM role ARN for cross-account (optional)
                - region: AWS region (optional)
                - callback_url: URL to send response (optional)
                - metadata: Additional context (optional)
                
        Returns:
            Dictionary with operation results
        """
        try:
            request_text = request_data.get('request') or request_data.get('prompt')
            
            if not request_text:
                return {
                    'success': False,
                    'error': 'Missing required field: request or prompt'
                }
            
            # Build context from request data
            context = {}
            
            if request_data.get('profile'):
                context['default_profile'] = request_data['profile']
            
            if request_data.get('role_arn'):
                context['default_role_arn'] = request_data['role_arn']
            
            if request_data.get('region'):
                context['default_region'] = request_data['region']
            
            if request_data.get('metadata'):
                context['metadata'] = request_data['metadata']
            
            # Process through agent
            result = self.agent.process_request(request_text, context)
            
            if result['success']:
                logger.info(f"Successfully processed request: {request_text[:100]}...")
                return {
                    'success': True,
                    'result': result,
                    'request': request_text
                }
            else:
                logger.error(f"Failed to process request: {result.get('error', 'Unknown error')}")
                return {
                    'success': False,
                    'error': result.get('error', 'Processing failed'),
                    'request': request_text
                }
                
        except Exception as e:
            logger.error(f"Error in workflow processing: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def close(self):
        """Clean up resources"""
        self.agent.close()
