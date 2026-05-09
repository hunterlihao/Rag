"""
RabbitMQ消息队列服务
使用aio-pika支持Python 3.13+
集成到主进程,无需单独启动Worker
"""
import asyncio
import json
import logging
from typing import Callable

from aio_pika import connect_robust, Message, ExchangeType
from aio_pika.abc import AbstractIncomingMessage

from rag_app import config

logger = logging.getLogger(__name__)


class QueueService:
    """RabbitMQ队列服务(异步版本)"""
    
    def __init__(self):
        self.connection = None
        self.channel = None
        self.queue = None
        self.consumer_task = None
        
    async def connect(self):
        """连接到RabbitMQ"""
        try:
            # 添加连接重试和超时配置
            self.connection = await connect_robust(
                config.RABBITMQ_URL,
                timeout=10,  # 连接超时10秒
                reconnect_interval=5,  # 重连间隔5秒
            )
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=config.RABBITMQ_PREFETCH_COUNT)
            
            # 声明队列
            self.queue = await self.channel.declare_queue(
                config.RABBITMQ_QUEUE_NAME,
                durable=True
            )
            
            logger.info(f"RabbitMQ连接成功: {config.RABBITMQ_QUEUE_NAME}")
            return True
        except Exception as e:
            logger.error(f"RabbitMQ连接失败: {e}")
            return False
    
    async def publish(self, message: dict) -> bool:
        """发布消息到队列"""
        if not self.channel:
            if not await self.connect():
                return False
        
        try:
            await self.channel.default_exchange.publish(
                Message(
                    body=json.dumps(message, ensure_ascii=False).encode(),
                    delivery_mode=2,  # 持久化
                ),
                routing_key=config.RABBITMQ_QUEUE_NAME,
            )
            return True
        except Exception as e:
            logger.error(f"发布消息失败: {e}")
            return False
    
    async def start_consumer(self, callback: Callable):
        """启动消费者"""
        if not self.queue:
            if not await self.connect():
                return
        
        async def on_message(message: AbstractIncomingMessage):
            async with message.process():
                try:
                    data = json.loads(message.body.decode())
                    await callback(data)
                except Exception as e:
                    logger.error(f"处理消息失败: {e}")
        
        await self.queue.consume(on_message)
        logger.info("RabbitMQ消费者已启动")
    
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

