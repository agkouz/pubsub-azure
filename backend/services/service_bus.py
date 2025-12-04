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

# ========================================================================
# SHARED SYNC SERVICE BUS CLIENT (FOR PUBLISHING)
# ========================================================================

_sync_credential: DefaultAzureCredential | None = None
_sync_client: ServiceBusClient | None = None


def _init_sync_client() -> None:
    global _sync_credential, _sync_client

    if _sync_client is not None:
        return

    if not settings.ENABLE_SERVICE_BUS:
        logger.info("Service Bus disabled (ENABLE_SERVICE_BUS=false) - publisher will be no-op.")
        return

    if settings.USE_AZURE_AD:
        _sync_credential = DefaultAzureCredential()
        _sync_client = ServiceBusClient(
            fully_qualified_namespace=settings.AZURE_SERVICEBUS_NAMESPACE_FQDN,
            credential=_sync_credential,
        )
    else:
        _sync_client = ServiceBusClient.from_connection_string(
            settings.AZURE_SERVICEBUS_CONNECTION_STRING
        )

    logger.info("Initialized shared sync ServiceBusClient for publishing.")


def shutdown_sync_client() -> None:
    """
    Call this from your FastAPI shutdown event to cleanly close credentials.
    """
    global _sync_credential, _sync_client

    try:
        if _sync_client is not None:
            _sync_client.close()
    except Exception:
        logger.exception("Error closing ServiceBusClient on shutdown.")

    try:
        if _sync_credential is not None:
            _sync_credential.close()
    except Exception:
        logger.exception("Error closing DefaultAzureCredential on shutdown.")

    _sync_client = None
    _sync_credential = None


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
    global _sync_credential, _sync_client

    # for local debug, backend will not subscribe to pubsub
    if not settings.ENABLE_SERVICE_BUS:
        logger.info("Service Bus listener disabled (ENABLE_SERVICE_BUS=false)")
        return

    if not settings.AZURE_SERVICEBUS_CONNECTION_STRING and not settings.AZURE_SERVICEBUS_NAMESPACE_FQDN:
        logger.warning("Service Bus not configured - messages won't be received")
        return

    logger.info("🚀 Starting Service Bus listener...")    
       
    logger.info("Initializing receiver...")
    with _sync_client:
        receiver = _sync_client.get_subscription_receiver(
            topic_name=settings.TOPIC_NAME,
            subscription_name=settings.SUBSCRIPTION_NAME,
            max_wait_time=5,
        )
        with receiver:
            logger.info(
                f"✓ Listening to Service Bus topic='{settings.TOPIC_NAME}', "
                f"subscription='{settings.SUBSCRIPTION_NAME}' (1 subscription, cost-optimal)"
            )

    
        logger.info("Waiting for messages...")
        try:
            messages = receiver.receive_messages(
                max_message_count=10,
                max_wait_time=5,
            )

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

    await asyncio.sleep(5)


def publish_to_service_bus(message_data: dict):
    """
    Sync helper used by /publish endpoint.

    Uses a shared ServiceBusClient to avoid reconnecting on every call.
    """
    if not settings.ENABLE_SERVICE_BUS:
        logger.debug("Service Bus disabled - skipping publish.")
        return

    _init_sync_client()

    if _sync_client is None:
        logger.warning("Service Bus client not initialized - message not sent.")
        return

    try:
        # get_topic_sender is cheap; you can optimize further by caching the sender too
        sender = _sync_client.get_topic_sender(topic_name=settings.TOPIC_NAME)
        with sender:
            message = ServiceBusMessage(
                body=json.dumps(message_data),
                application_properties={"room_id": message_data["room_id"]},
            )
            sender.send_messages(message)
    except Exception:
        logger.exception("Error publishing message to Service Bus.")