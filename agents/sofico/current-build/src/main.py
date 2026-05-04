#!/usr/bin/env python3
"""
Sofi - Educational Tutor Familiar
Entry point for the Slack bot
"""

import os
import logging
from dotenv import load_dotenv

from slack_bot import SofiSlackBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Start Sofi"""
    # Load environment variables
    load_dotenv()

    # Verify required environment variables
    required_vars = ['SLACK_BOT_TOKEN', 'SLACK_APP_TOKEN', 'ANTHROPIC_API_KEY']

    use_local = os.getenv('SOFI_USE_LOCAL_FILES', 'true').lower() == 'true'
    if not use_local:
        required_vars.append('GITLAB_ACCESS_TOKEN')

    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Copy .env.example to .env and fill in your values")
        return

    commit = os.getenv("GIT_COMMIT", "unknown")
    logger.info("Starting Sofi — commit=%s", commit)

    # Create and run the bot
    bot = SofiSlackBot()
    bot.run()


if __name__ == "__main__":
    main()
