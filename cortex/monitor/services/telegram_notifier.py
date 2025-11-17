"""
Telegram 通知服务
"""

import asyncio
from typing import List, Optional

import httpx
from loguru import logger

from cortex.config.settings import Settings
from cortex.common.retry import retry_async, FAST_RETRY_CONFIG
from cortex.monitor.database import Alert


class TelegramNotifier:
    """
    Telegram Bot 通知服务

    负责将 L3 告警和摘要报告发送到 Telegram
    """

    def __init__(self, settings: Settings) -> None:
        """
        初始化 Telegram 通知器

        Args:
            settings: 全局配置
        """
        self.settings = settings
        self.bot_token = settings.telegram.bot_token
        self.chat_id = settings.telegram.chat_id
        self.enabled = settings.telegram.enabled

        if not self.enabled:
            logger.warning("Telegram notifications are DISABLED in settings")
            return

        if not self.bot_token or not self.chat_id:
            logger.error("Telegram bot_token or chat_id not configured")
            self.enabled = False

        self.api_base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        发送消息到 Telegram（带重试机制）

        Args:
            message: 消息文本
            parse_mode: 解析模式 (Markdown 或 HTML)

        Returns:
            True 如果发送成功
        """
        if not self.enabled:
            logger.debug("Telegram disabled, skipping message send")
            return False

        # 定义实际的请求函数（用于重试）
        async def _make_request():
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": True,
                    },
                )

                response.raise_for_status()
                return response.json()

        try:
            # 使用快速重试策略（Telegram 通知一般延迟敏感）
            result = await retry_async(_make_request, config=FAST_RETRY_CONFIG)

            if result.get("ok"):
                logger.info("Telegram message sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {result}")
                return False

        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending Telegram message after retries: {e}")
            return False
        except Exception as e:
            logger.error(
                f"Error sending Telegram message after retries: {e}", exc_info=True
            )
            return False

    async def send_alert(self, alert: Alert) -> bool:
        """
        发送单个告警通知

        Args:
            alert: 告警对象

        Returns:
            True 如果发送成功
        """
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }

        emoji = severity_emoji.get(alert.severity, "⚠️")

        # 格式化消息
        message = f"""{emoji} *L3 告警*

*严重性*: {alert.severity.upper()}
*Agent*: `{alert.agent_id}`
*类型*: {alert.type}
*时间*: {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}

*描述*:
{alert.description}

_Alert ID: {alert.id}_
"""

        return await self.send_message(message)

    async def send_batch_alerts(self, alerts: List[Alert]) -> int:
        """
        批量发送告警通知

        Args:
            alerts: 告警列表

        Returns:
            成功发送的数量
        """
        if not alerts:
            return 0

        success_count = 0

        for alert in alerts:
            success = await self.send_alert(alert)
            if success:
                success_count += 1

            # 防止发送过快（Telegram API 限流）
            await asyncio.sleep(0.5)

        logger.info(f"Sent {success_count}/{len(alerts)} Telegram notifications")
        return success_count

    async def send_summary(self, summary_text: str) -> bool:
        """
        发送摘要报告

        Args:
            summary_text: 摘要文本

        Returns:
            True 如果发送成功
        """
        return await self.send_message(summary_text)

    async def test_connection(self) -> bool:
        """
        测试 Telegram 连接

        Returns:
            True 如果连接成功
        """
        if not self.enabled:
            logger.warning("Telegram is disabled")
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.api_base_url}/getMe")
                response.raise_for_status()
                result = response.json()

                if result.get("ok"):
                    bot_info = result.get("result", {})
                    logger.info(
                        f"Telegram bot connected: @{bot_info.get('username')} ({bot_info.get('first_name')})"
                    )
                    return True
                else:
                    logger.error(f"Telegram connection test failed: {result}")
                    return False

        except Exception as e:
            logger.error(f"Telegram connection test error: {e}")
            return False
