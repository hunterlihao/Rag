"""
RabbitMQ消息队列服务
使用aio-pika支持Python 3.13+
集成到主进程,无需单独启动Worker
"""
import asyncio
import json
import logging
from typing import Callable

from aio_pika import connect_robust, Message
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue

from rag_app import config

logger = logging.getLogger(__name__)

_ALL_QUEUE_NAMES = [
    config.RABBITMQ_QUEUE_NAME,
    config.RABBITMQ_QUEUE_FILE_DELETE,
    config.RABBITMQ_QUEUE_BATCH_DELETE,
    config.RABBITMQ_QUEUE_USER_DELETE,
    config.RABBITMQ_QUEUE_SESSION_EXPORT,
]


class QueueService:
    """RabbitMQ队列服务(异步版本,支持多队列)"""

    def __init__(self):
        self.connection = None
        self.channel = None
        self._queues: dict[str, AbstractQueue] = {}

    async def connect(self):
        """连接到RabbitMQ并声明所有队列"""
        try:
            self.connection = await connect_robust(
                config.RABBITMQ_URL,
                timeout=10,
                reconnect_interval=5,
            )
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=config.RABBITMQ_PREFETCH_COUNT)

            for queue_name in _ALL_QUEUE_NAMES:
                queue = await self.channel.declare_queue(queue_name, durable=True)
                self._queues[queue_name] = queue

            logger.info("RabbitMQ连接成功,已声明 %d 个队列", len(self._queues))
            return True
        except Exception as e:
            logger.error("RabbitMQ连接失败: %s", e)
            return False

    async def publish(self, message: dict, queue_name: str | None = None) -> bool:
        """发布消息到指定队列"""
        target_queue = queue_name or config.RABBITMQ_QUEUE_NAME

        if not self.channel:
            if not await self.connect():
                return False

        if target_queue not in self._queues:
            logger.error("队列未声明: %s", target_queue)
            return False

        try:
            await self.channel.default_exchange.publish(
                Message(
                    body=json.dumps(message, ensure_ascii=False).encode(),
                    delivery_mode=2,
                ),
                routing_key=target_queue,
            )
            return True
        except Exception as e:
            logger.error("发布消息失败: %s", e)
            return False

    async def start_consumer(self, callback: Callable, queue_name: str | None = None):
        """启动消费者监听指定队列"""
        target_queue = queue_name or config.RABBITMQ_QUEUE_NAME

        if target_queue not in self._queues:
            if not await self.connect():
                return

        queue = self._queues[target_queue]

        async def on_message(message: AbstractIncomingMessage):
            async with message.process():
                try:
                    data = json.loads(message.body.decode())
                    await callback(data)
                except Exception as e:
                    logger.error("处理消息失败: %s", e)

        await queue.consume(on_message)
        logger.info("RabbitMQ消费者已启动: %s", target_queue)

    async def close(self):
        """关闭连接"""
        if self.connection:
            await self.connection.close()
            logger.info("RabbitMQ连接已关闭")


# 全局实例
_queue_service = None


def get_queue_service() -> QueueService:
    """获取队列服务单例"""
    global _queue_service
    if _queue_service is None:
        _queue_service = QueueService()
    return _queue_service
