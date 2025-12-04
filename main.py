"""
Zarathustra AWS Ops - AI Agent for AWS Operations
Entry point for the SQS listener service
"""

import os
import sys
import logging
from dotenv import load_dotenv

from src.listeners import ZarathustraAWSOpsListener


def setup_logging():
    """Configure logging for the application"""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('/app/logs/zarathustra-aws-ops.log') if os.path.exists('/app/logs') else logging.NullHandler()
        ]
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)


def main():
    """Main entry point"""
    load_dotenv()
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("🤖 Starting Zarathustra AWS Ops Agent")
    logger.info("Mode: SQS Listener - AWS Operations via MCP Tools")
    
    try:
        listener = ZarathustraAWSOpsListener()
        listener.run()
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal, stopping service...")
    except Exception as e:
        logger.error(f"Fatal error in backend service: {e}")
        sys.exit(1)
    
    logger.info("🤖 Zarathustra AWS Ops Agent stopped")


if __name__ == "__main__":
    main()
