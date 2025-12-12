import os
import json
import asyncio

from dotenv import load_dotenv
from google.cloud import pubsub_v1
from typing import Callable, Awaitable, Optional

from core import state
from core.config import settings
# ---------- CONFIG ----------
try:
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()


    PROJECT_ID = settings.PROJECT_ID
    TOPIC_ID = settings.TOPIC_ID
    SUBSCRIPTION_ID = settings.SUBSCRIPTION_ID

    TOPIC_PATH = publisher.topic_path(PROJECT_ID, TOPIC_ID)
    SUBSCRIPTION_PATH = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

    _streaming_future: Optional[pubsub_v1.subscriber.futures.StreamingPullFuture] = None
    _loop: Optional[asyncio.AbstractEventLoop] = None
    _on_event: Optional[Callable[[dict], Awaitable[None]]] = None
except Exception as e:
    print("Error initializing Pub/Sub clients. Make sure ADC or a Service Account is set.")
    pass

async def on_pubsub_event(event: dict):
    # await print(event)
    await state.connection_manager.broadcast_to_room(event['room_id'], event)
    state.message_counter += 1



def init_pubsub(
    loop: asyncio.AbstractEventLoop,
    # on_event: Callable[[dict], Awaitable[None]],
) -> None:
    """
    Call this once on app startup.
    - loop: FastAPI's event loop
    - on_event: async function that will handle each decoded message (dict)
    """
    global _loop, _on_event, _streaming_future

    _loop = loop
    _on_event = on_pubsub_event
    # _on_event = on_event

    def _callback(message: pubsub_v1.subscriber.message.Message):
        try:
            payload_str = message.data.decode("utf-8")
            event = json.loads(payload_str)

            if _loop is not None and _on_event is not None:
                # Schedule the async handler on the FastAPI event loop
                asyncio.run_coroutine_threadsafe(_on_event(event), _loop)

            message.ack()
        except Exception as exc:
            print("Error processing message:", exc)
            message.nack()

    _streaming_future = subscriber.subscribe(SUBSCRIPTION_PATH, callback=_callback)
    print(f"Listening for messages on {SUBSCRIPTION_PATH}...")


def shutdown_pubsub() -> None:
    """Call this once on app shutdown."""
    global _streaming_future
    if _streaming_future is not None:
        _streaming_future.cancel()
    subscriber.close()


def publish_event(event: dict) -> str:
    """
    Publish a dict to the topic. Returns Pub/Sub message ID.
    NOTE: This is synchronous (blocks until publish is done).
    """
    data = json.dumps(event).encode("utf-8")
    future = publisher.publish(TOPIC_PATH, data=data)
    return future.result()
