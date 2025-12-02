# backend/core/config.py
import os

class Settings:
    """
    Setup environment variables.
        - AZURE_SERVICEBUS_CONNECTION_STRING the connection string or empty
        - AZURE_SERVICEBUS_NAMESPACE_FQDN holds the pubservice url if AAD authentication
        - TOPIC_NAME the topic name of pubsub
        - SUBSCRIPTION_NAME the subscription name of pubsub
    """
    AZURE_SERVICEBUS_CONNECTION_STRING: str = os.getenv("AZURE_SERVICEBUS_CONNECTION_STRING", "")
    AZURE_SERVICEBUS_NAMESPACE_FQDN: str = os.getenv("AZURE_SERVICEBUS_NAMESPACE_FQDN", "")
    TOPIC_NAME: str = os.getenv("AZURE_SERVICEBUS_TOPIC_NAME", "backend-messages")
    SUBSCRIPTION_NAME: str = os.getenv("AZURE_SERVICEBUS_SUBSCRIPTION_NAME", "backend-subscription")

    # For running locally, set this to false
    ENABLE_SERVICE_BUS: bool = os.getenv("ENABLE_SERVICE_BUS", "true").lower() == "true"

    @property
    def USE_AZURE_AD(self) -> bool:
        """
        Resolve which authentication message to use. Will use AAD if FQDN is set and connection string is empty
        """
        return bool(self.AZURE_SERVICEBUS_NAMESPACE_FQDN and not self.AZURE_SERVICEBUS_CONNECTION_STRING)

settings = Settings()