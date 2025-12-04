# backend/services/service_bus.py

from __future__ import annotations

import json
import logging
import traceback
from azure.servicebus.aio import ServiceBusClient as AsyncServiceBusClient
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.identity import DefaultAzureCredential

from core.config import settings
from core import state

logger = logging.getLogger(__name__)


class AsyncServiceBusService:
    """
    Async Service Bus service for publishing and subscribing to messages.

    Architecture:
        - Uses SINGLE topic + SINGLE subscription (cost-optimal)
        - Routes messages by room_id in message body
        - 2 operations per message regardless of room count
    """

    def __init__(self):
        self.async_client = None
        self.async_credential = None
        self.sync_client = None
        self.sync_credential = None

    async def connect(self):
        """Establish async connection to Service Bus (for listening)."""
        if not settings.ENABLE_SERVICE_BUS:
            logger.info("Service Bus disabled (ENABLE_SERVICE_BUS=false)")
            return

        if settings.USE_AZURE_AD:
            self.async_credential = AsyncDefaultAzureCredential()
            self.async_client = AsyncServiceBusClient(
                fully_qualified_namespace=settings.AZURE_SERVICEBUS_NAMESPACE_FQDN,
                credential=self.async_credential,
            )
        else:
            self.async_client = AsyncServiceBusClient.from_connection_string(
                settings.AZURE_SERVICEBUS_CONNECTION_STRING
            )

        logger.info(f"✓ Connected to Service Bus at {settings.AZURE_SERVICEBUS_NAMESPACE_FQDN or 'connection string'}")

    def _init_sync_client(self):
        """Initialize sync client for publishing (lazy initialization)."""
        if self.sync_client is not None:
            return

        if not settings.ENABLE_SERVICE_BUS:
            return

        if settings.USE_AZURE_AD:
            self.sync_credential = DefaultAzureCredential()
            self.sync_client = ServiceBusClient(
                fully_qualified_namespace=settings.AZURE_SERVICEBUS_NAMESPACE_FQDN,
                credential=self.sync_credential,
            )
        else:
            self.sync_client = ServiceBusClient.from_connection_string(
                settings.AZURE_SERVICEBUS_CONNECTION_STRING
            )

        logger.info("✓ Initialized sync Service Bus client for publishing")

    def broadcast_to_room(self, room_id: str, message: dict):
        """
        Broadcast a message to a specific room via Service Bus.

        This publishes to the shared topic with room_id in the message body.
        The listener will receive it and forward to WebSocket connections.

        Args:
            room_id: Target room UUID
            message: Message dict (must include room_id)

        Note: Uses sync client because FastAPI routes are sync by default.
        """
        if not settings.ENABLE_SERVICE_BUS:
            logger.debug("Service Bus disabled - skipping publish")
            return

        self._init_sync_client()

        if self.sync_client is None:
            logger.warning("Service Bus client not initialized - message not sent")
            return

        try:
            sender = self.sync_client.get_topic_sender(topic_name=settings.TOPIC_NAME)
            with sender:
                sb_message = ServiceBusMessage(
                    body=json.dumps(message),
                    application_properties={"room_id": room_id},
                )
                sender.send_messages(sb_message)
                logger.info(f"📨 Broadcasted to room {room_id} via Service Bus")

        except Exception as e:
            logger.error(f"Error publishing to Service Bus: {e}")
            logger.error(traceback.format_exc())

    async def listen(self):
        """
        Listen to Service Bus subscription and broadcast to WebSockets.

        Cost-optimal design:
            - Single subscription for ALL rooms
            - Routes by room_id in message body
            - 2 operations per message (1 publish + 1 delivery)
        """
        if not settings.ENABLE_SERVICE_BUS:
            logger.info("Service Bus listener disabled")
            return

        if not self.async_client:
            logger.warning("Service Bus not connected - call connect() first")
            return

        logger.info("🚀 Starting Service Bus listener...")

        try:
            async with self.async_client:
                receiver = self.async_client.get_subscription_receiver(
                    topic_name=settings.TOPIC_NAME,
                    subscription_name=settings.SUBSCRIPTION_NAME,
                    max_wait_time=5,
                )

                async with receiver:
                    logger.info(
                        f"✓ Subscribed to Service Bus topic '{settings.TOPIC_NAME}', "
                        f"subscription '{settings.SUBSCRIPTION_NAME}'"
                    )

                    while True:
                        try:
                            messages = await receiver.receive_messages(
                                max_message_count=10,
                                max_wait_time=5,
                            )

                            if not messages:
                                continue

                            for msg in messages:
                                try:
                                    body_bytes = b"".join(msg.body)
                                    message_data = json.loads(body_bytes.decode("utf-8"))
                                    room_id = message_data.get("room_id")

                                    if room_id:
                                        logger.info(
                                            f"➡ Service Bus: Routing to room={room_id}, "
                                            f"sender={message_data.get('sender')}"
                                        )
                                        await state.connection_manager.broadcast_to_room(
                                            room_id, message_data
                                        )
                                    else:
                                        logger.warning("Service Bus message without room_id - ignoring")

                                    await receiver.complete_message(msg)

                                except Exception as e:
                                    logger.error(f"Error processing Service Bus message: {e}")
                                    await receiver.complete_message(msg)

                        except Exception as e:
                            logger.error(f"Service Bus receive error: {e}")
                            logger.error(traceback.format_exc())
                            break

        except Exception as e:
            logger.error(f"Service Bus listener error: {e}")
            logger.error(traceback.format_exc())

    async def close(self):
        """Close all connections."""
        try:
            if self.sync_client:
                self.sync_client.close()
            if self.sync_credential:
                self.sync_credential.close()
        except Exception as e:
            logger.error(f"Error closing sync Service Bus client: {e}")

        try:
            if self.async_client:
                await self.async_client.close()
            if self.async_credential:
                await self.async_credential.close()
        except Exception as e:
            logger.error(f"Error closing async Service Bus client: {e}")

        logger.info("Service Bus connections closed")