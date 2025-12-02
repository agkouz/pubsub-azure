# backend/services/service_bus.py

from __future__ import annotations

import asyncio
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

# ============================================================================
# SERVICE BUS BACKGROUND LISTENER
# ============================================================================

async def listen_to_service_bus():
    """
    Background task that listens to Azure Service Bus and broadcasts messages.
    
    This is the heart of the cost-optimal architecture:
    
    Flow:
        1. Listens to SINGLE subscription (not one per room!)
        2. Receives message with room_id property
        3. Calls manager.broadcast_to_room(room_id, message)
        4. Only WebSockets subscribed to that room receive the message
    
    Cost Analysis:
        - Each message = 1 publish + 1 delivery = 2 operations
        - If we had N subscriptions (one per room):
          Each message = 1 publish + N deliveries = (1 + N) operations
        - For 1000 rooms: 2 ops vs 1001 ops = 500x cost savings!
    
    Error Handling:
        - Retries on connection failure
        - Completes messages even on processing errors
        - Auto-reconnects if connection drops
    
    Lifecycle:
        Started by @app.on_event("startup")
        Runs continuously in background
        Uses async context managers for proper cleanup
    """
    if not settings.AZURE_SERVICEBUS_CONNECTION_STRING and not settings.AZURE_SERVICEBUS_NAMESPACE_FQDN:
        logger.warning("Service Bus not configured - messages won't be received")
        return

    logger.info("🚀 Starting Service Bus listener...")

    while True:
        try:
            if settings.USE_AZURE_AD:
                credential = AsyncDefaultAzureCredential()
                client = AsyncServiceBusClient(
                    fully_qualified_namespace=settings.AZURE_SERVICEBUS_NAMESPACE_FQDN,
                    credential=credential,
                )
            else:
                credential = None
                client = AsyncServiceBusClient.from_connection_string(
                    settings.AZURE_SERVICEBUS_CONNECTION_STRING
                )

            try:
                async with client:
                    receiver = client.get_subscription_receiver(
                        topic_name=settings.TOPIC_NAME,
                        subscription_name=settings.SUBSCRIPTION_NAME,
                        max_wait_time=5,
                    )
                    async with receiver:
                        logger.info(
                            f"✓ Listening to Service Bus topic='{settings.TOPIC_NAME}', "
                            f"subscription='{settings.SUBSCRIPTION_NAME}' (1 subscription, cost-optimal)"
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
                                        message_body = body_bytes.decode("utf-8")
                                        logger.info(f"📥 Received raw message body: {message_body}")

                                        message_data = json.loads(message_body)
                                        room_id = message_data.get("room_id")

                                        if room_id:
                                            logger.info(
                                                f"➡ Routing message to room_id={room_id}, "
                                                f"content={message_data.get('content')!r}, "
                                                f"sender={message_data.get('sender')!r}"
                                            )
                                            await state.connection_manager.broadcast_to_room(room_id, message_data)
                                        else:
                                            logger.warning("Message without room_id - ignoring")

                                        await receiver.complete_message(msg)

                                    except Exception as e:
                                        logger.error(f"Error processing individual message: {e}")
                                        logger.error(traceback.format_exc())
                                        await receiver.complete_message(msg)

                            except Exception as e:
                                logger.error(f"Service Bus receive loop error: {e}")
                                logger.error(traceback.format_exc())
                                break
            finally:
                if credential is not None:
                    try:
                        await credential.close()
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Service Bus listener error (outer): {e}")
            logger.error(traceback.format_exc())

        await asyncio.sleep(5)


    def publish_to_service_bus(message_data: dict):
        """
        Sync helper used by /publish endpoint.
        """
        if settings.USE_AZURE_AD:
            credential = DefaultAzureCredential()
            client = ServiceBusClient(
                fully_qualified_namespace=settings.AZURE_SERVICEBUS_NAMESPACE_FQDN,
                credential=credential,
            )
        else:
            credential = None
            client = ServiceBusClient.from_connection_string(
                settings.AZURE_SERVICEBUS_CONNECTION_STRING
            )

        try:
            with client:
                sender = client.get_topic_sender(topic_name=settings.TOPIC_NAME)
                with sender:
                    message = ServiceBusMessage(
                        body=json.dumps(message_data),
                        application_properties={"room_id": message_data["room_id"]},
                    )
                    sender.send_messages(message)
        finally:
            if credential is not None:
                try:
                    credential.close()
                except Exception:
                    pass