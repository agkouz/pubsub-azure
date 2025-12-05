# backend/core/config.py
import os
from typing import Literal
from dotenv import load_dotenv

class Settings:
    """
    Setup environment variables.
        - AZURE_SERVICEBUS_CONNECTION_STRING the connection string or empty
        - AZURE_SERVICEBUS_NAMESPACE_FQDN holds the pubservice url if AAD authentication
        - TOPIC_NAME the topic name of pubsub
        - SUBSCRIPTION_NAME the subscription name of pubsub
        - PUB_SUB_SERVICE the pubsub service to use: "service_bus" or "redis"
    """

    # Load environment variables from the .env file
    load_dotenv()

    AZURE_SERVICEBUS_CONNECTION_STRING: str = os.getenv("AZURE_SERVICEBUS_CONNECTION_STRING", "")
    AZURE_SERVICEBUS_NAMESPACE_FQDN: str = os.getenv("AZURE_SERVICEBUS_NAMESPACE_FQDN", "")
    TOPIC_NAME: str = os.getenv("AZURE_SERVICEBUS_TOPIC_NAME", "backend-messages")
    SUBSCRIPTION_NAME: str = os.getenv("AZURE_SERVICEBUS_SUBSCRIPTION_NAME", "backend-subscription")
    PUB_SUB_SERVICE: Literal["redis", "service_bus", "google_pub_sub"] =(os.getenv("PUB_SUB_SERVICE", "service_bus"))
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_ACCESS_KEY: str = os.getenv("REDIS_ACCESS_KEY", "")
    PROJECT_ID = os.getenv("PROJECT_ID", "")
    TOPIC_ID = os.getenv("TOPIC_ID", "")
    SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID", "")

    # For running locally, set this to false
    ENABLE_SERVICE_BUS: bool = os.getenv("ENABLE_SERVICE_BUS", "true").lower() == "true"

    @property
    def USE_AZURE_AD(self) -> bool:
        """
        Resolve which authentication message to use. Will use AAD if FQDN is set and connection string is empty
        """
        return bool(self.AZURE_SERVICEBUS_NAMESPACE_FQDN and not self.AZURE_SERVICEBUS_CONNECTION_STRING)

settings = Settings()