import json
import logging
from typing import Any, Dict, Optional
import aio_pika
from app.config import settings

logger = logging.getLogger("api.event_bus")


class EventBusService:
    """Distributed Event Bus for event-driven microservices using RabbitMQ / Message Streaming."""

    def __init__(self):
        self._connection: Optional[aio_pika.RobustConnection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._exchange: Optional[aio_pika.Exchange] = None

    async def init_broker(self) -> None:
        if settings.USE_RABBITMQ:
            try:
                self._connection = await aio_pika.connect_robust(
                    settings.RABBITMQ_URL,
                    timeout=3.0,
                )
                self._channel = await self._connection.channel()
                # Declare durable topic exchange for e-commerce event streams
                self._exchange = await self._channel.declare_exchange(
                    "ecommerce.events",
                    aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )
                logger.info("Connected to RabbitMQ broker at %s", settings.RABBITMQ_URL)
            except Exception as e:
                logger.warning("RabbitMQ connection failed (%s); operating on fallback event logger.", e)
                self._connection = None

    async def close_broker(self) -> None:
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            self._connection = None

    async def publish(self, routing_key: str, payload: Dict[str, Any]) -> bool:
        """Publishes an event to the message exchange."""
        serialized = json.dumps(payload, default=str)

        # 1. RabbitMQ Delivery
        if self._exchange:
            try:
                message = aio_pika.Message(
                    body=serialized.encode("utf-8"),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json",
                )
                await self._exchange.publish(message, routing_key=routing_key)
                logger.info("Published event [%s] to RabbitMQ exchange.", routing_key)
                return True
            except Exception as e:
                logger.warning("Failed to publish event to RabbitMQ (%s); falling back to audit log.", e)

        # 2. Local Fallback Stream
        logger.info('{"event_stream": "fallback", "routing_key": "%s", "data": %s}', routing_key, serialized)
        return True


event_bus = EventBusService()
