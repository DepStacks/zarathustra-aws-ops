"""
SQS Listener for Zarathustra AWS Ops
Listens to SQS queue for AWS operation requests
"""

import os
import json
import time
import logging
import httpx
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

from ..core.workflow_manager import WorkflowManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ZarathustraAWSOpsListener:
    """
    SQS Listener for AWS Operations requests.
    
    Listens to an SQS queue for requests, processes them through
    the AI agent, and optionally sends responses to callback URLs.
    """
    
    def __init__(self):
        load_dotenv()
        
        # SQS Configuration
        self.queue_url = os.getenv("SQS_QUEUE_URL")
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.max_messages = int(os.getenv("SQS_MAX_MESSAGES", "10"))
        self.wait_time = int(os.getenv("SQS_WAIT_TIME", "20"))
        self.visibility_timeout = int(os.getenv("SQS_VISIBILITY_TIMEOUT", "300"))
        
        # API Keys
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Worker Configuration
        self.max_workers = int(os.getenv("MAX_WORKERS", "5"))
        self.poll_interval = int(os.getenv("POLL_INTERVAL", "5"))
        
        # Validate required configuration
        if not self.queue_url:
            raise ValueError("Missing required environment variable: SQS_QUEUE_URL")
        if not self.openai_api_key:
            raise ValueError("Missing required environment variable: OPENAI_API_KEY")
        
        # Initialize SQS client
        try:
            self.sqs = boto3.client('sqs', region_name=self.aws_region)
            logger.info(f"Initialized SQS client for region: {self.aws_region}")
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please configure AWS credentials.")
            raise
        
        # Initialize HTTP client for callbacks
        self.http_client = httpx.Client(timeout=30.0)
        
        # Initialize Workflow Manager
        self.workflow_manager = WorkflowManager(
            openai_api_key=self.openai_api_key
        )
        
        # Thread pool for parallel message processing
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Graceful shutdown handling
        self.shutdown_requested = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Zarathustra AWS Ops Listener initialized successfully")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
    
    def validate_message(self, message_body: Dict[str, Any]) -> bool:
        """Validate that message contains required fields"""
        # Accept either 'request' or 'prompt' field
        if 'request' not in message_body and 'prompt' not in message_body:
            logger.error("Missing required field: request or prompt")
            return False
        return True
    
    def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single SQS message"""
        message_id = message.get('MessageId', 'unknown')
        receipt_handle = message.get('ReceiptHandle')
        
        try:
            message_body = json.loads(message['Body'])
            
            # Validate message format
            if not self.validate_message(message_body):
                self._delete_message(receipt_handle)
                return {
                    'success': False,
                    'message_id': message_id,
                    'error': 'Invalid message format'
                }
            
            # Get request text (support both 'request' and 'prompt' fields)
            request_text = message_body.get('request') or message_body.get('prompt')
            logger.info(f"Processing message {message_id}: {request_text[:100]}...")
            
            # Process through workflow manager
            result = self.workflow_manager.process_aws_operation(message_body)
            
            if result['success']:
                logger.info(f"Successfully processed message {message_id}")
                self._delete_message(receipt_handle)
                
                # Send callback if configured
                callback_url = message_body.get('callback_url')
                if callback_url:
                    self._send_callback(callback_url, message_id, result)
                
                return {
                    'success': True,
                    'message_id': message_id,
                    'result': result
                }
            else:
                logger.error(f"Failed to process message {message_id}: {result.get('error', 'Unknown error')}")
                return {
                    'success': False,
                    'message_id': message_id,
                    'error': result.get('error', 'Processing failed')
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message {message_id}: {e}")
            self._delete_message(receipt_handle)
            return {
                'success': False,
                'message_id': message_id,
                'error': f'Invalid JSON: {e}'
            }
        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}")
            return {
                'success': False,
                'message_id': message_id,
                'error': str(e)
            }
    
    def _delete_message(self, receipt_handle: str):
        """Delete message from SQS queue"""
        try:
            self.sqs.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            logger.debug("Message deleted from queue")
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
    
    def _send_callback(self, callback_url: str, message_id: str, result: Dict[str, Any]):
        """Send result to callback URL"""
        try:
            response = self.http_client.post(
                callback_url,
                json={
                    'message_id': message_id,
                    'success': result.get('success', False),
                    'response': result.get('result', {}).get('response', ''),
                    'error': result.get('error')
                },
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            logger.info(f"Callback sent successfully to {callback_url}")
        except Exception as e:
            logger.error(f"Failed to send callback to {callback_url}: {e}")
    
    def receive_messages(self) -> List[Dict[str, Any]]:
        """Receive messages from SQS queue"""
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=self.max_messages,
                WaitTimeSeconds=self.wait_time,
                VisibilityTimeout=self.visibility_timeout,
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            if messages:
                logger.info(f"Received {len(messages)} messages from queue")
            return messages
            
        except ClientError as e:
            logger.error(f"Error receiving messages: {e}")
            return []
    
    def run(self):
        """Main processing loop"""
        logger.info("Starting Zarathustra AWS Ops Listener")
        logger.info(f"Queue URL: {self.queue_url}")
        logger.info(f"Max workers: {self.max_workers}")
        logger.info(f"Poll interval: {self.poll_interval}s")
        
        while not self.shutdown_requested:
            try:
                messages = self.receive_messages()
                
                if not messages:
                    logger.debug("No messages received, continuing...")
                    time.sleep(self.poll_interval)
                    continue
                
                # Process messages in parallel
                futures = []
                for message in messages:
                    future = self.executor.submit(self.process_message, message)
                    futures.append(future)
                
                # Wait for all messages to be processed
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result['success']:
                            logger.info(f"Message {result['message_id']} processed successfully")
                        else:
                            logger.error(f"Message {result['message_id']} failed: {result['error']}")
                    except Exception as e:
                        logger.error(f"Error in message processing: {e}")
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(self.poll_interval)
        
        # Cleanup
        logger.info("Shutting down executor...")
        self.executor.shutdown(wait=True)
        self.http_client.close()
        self.workflow_manager.close()
        logger.info("Zarathustra AWS Ops Listener stopped")


def main():
    """Main entry point"""
    try:
        listener = ZarathustraAWSOpsListener()
        listener.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Failed to start SQS listener: {e}")
        import sys
        sys.exit(1)


if __name__ == "__main__":
    main()
