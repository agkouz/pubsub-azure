# backend/core/config.py
import os
from typing import Literal
from dotenv import load_dotenv

class Settings:
    """
    Setup environment variables.
        - TOPIC_NAME the topic name of pubsub
        - SUBSCRIPTION_NAME the subscription name of pubsub
        - PUB_SUB_SERVICE the pubsub service to use: "google_pub_sub" or "redis"
    """

    # Load environment variables from the .env file
    load_dotenv()

    PUB_SUB_SERVICE: Literal["redis", "google_pub_sub"] =(os.getenv("PUB_SUB_SERVICE", "google_pub_sub"))

    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_ACCESS_KEY: str = os.getenv("REDIS_ACCESS_KEY", "")

    PROJECT_ID = os.getenv("PROJECT_ID", "")
    TOPIC_ID = os.getenv("TOPIC_ID", "")
    SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID", "")

settings = Settings()