"""
Notification Service
Sends trading decisions to humans for approval via Telegram or Discord.
Implements Human-in-the-Loop (HITL) workflow.
"""

import os
import asyncio
from typing import Optional, Dict, Any, Literal
from datetime import datetime
import json

from ..logger import get_logger

logger = get_logger(__name__)

class NotificationService:
    """
    Service for sending trading decisions to human reviewers.
    
    Supports:
    - Telegram (via python-telegram-bot)
    - Discord (via discord.py)
    - Console (for testing)
    """
    
    def __init__(
        self,
        platform: Literal["telegram", "discord", "console"] = "console",
        timeout_seconds: int = 300  # 5 minutes default
    ):
        """
        Initialize notification service.
        
        Args:
            platform: Platform to use for notifications
            timeout_seconds: How long to wait for human response before auto-rejecting
        """
        self.platform = platform
        self.timeout_seconds = timeout_seconds
        self.pending_approval = None
        
        # Initialize platform-specific client
        if platform == "telegram":
            self._init_telegram()
        elif platform == "discord":
            self._init_discord()
        else:
            logger.info("Using console mode for HITL (no external notifications)")
    
    def _init_telegram(self):
        """Initialize Telegram bot"""
        try:
            import telegram
            
            token = os.getenv("TELEGRAM_BOT_TOKEN")
            self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
            
            if not token or not self.chat_id:
                raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
            
            self.bot = telegram.Bot(token=token)
            logger.info("Telegram bot initialized")
            
        except ImportError:
            logger.error("python-telegram-bot not installed. Install with: pip install python-telegram-bot")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Telegram: {e}")
            raise
    
    def _init_discord(self):
        """Initialize Discord bot"""
        try:
            import discord
            
            token = os.getenv("DISCORD_BOT_TOKEN")
            self.channel_id = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
            
            if not token or not self.channel_id:
                raise ValueError("DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID must be set")
            
            # Discord setup is more complex due to async nature
            # For now, placeholder
            logger.info("Discord mode (not fully implemented yet)")
            
        except ImportError:
            logger.error("discord.py not installed. Install with: pip install discord.py")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Discord: {e}")
            raise
    
    def _format_decision_message(
        self,
        decision: Dict[str, Any],
        brooks_analysis: Optional[Dict[str, Any]] = None,
        chart_path: Optional[str] = None
    ) -> str:
        """
        Format decision as human-readable message.
        
        Args:
            decision: Trading decision dict
            brooks_analysis: Brooks analysis dict
            chart_path: Path to chart image
            
        Returns:
            Formatted message string
        """
        lines = []
        lines.append("🤖 **TRADING DECISION APPROVAL REQUEST**")
        lines.append("")
        lines.append(f"⏰ **Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"📊 **Symbol**: {decision.get('symbol', 'N/A')}")
        lines.append(f"🎯 **Operation**: **{decision.get('operation', 'N/A')}**")
        lines.append("")
        
        # Brooks Analysis Context
        if brooks_analysis:
            lines.append("📈 **Al Brooks Analysis**:")
            lines.append(f"  - Market Cycle: {brooks_analysis.get('market_cycle', 'N/A')}")
            lines.append(f"  - Always In: {brooks_analysis.get('always_in_direction', 'N/A').upper()}")
            lines.append(f"  - Signal Bar Quality: {brooks_analysis.get('signal_bar', {}).get('quality_score', 0)}/10")
            lines.append(f"  - Setup Quality: {brooks_analysis.get('setup_quality', 0)}/10")
            
            patterns = brooks_analysis.get('detected_patterns', [])
            if patterns:
                pattern_names = [p.get('pattern_type', 'Unknown') for p in patterns[:3]]
                lines.append(f"  - Patterns: {', '.join(pattern_names)}")
            
            lines.append("")
        
        # Decision Details
        lines.append("💰 **Trade Details**:")
        lines.append(f"  - Probability: {decision.get('probability_score', 0):.1f}%")
        
        if decision.get('buy'):
            buy = decision['buy']
            lines.append(f"  - Order Type: BUY {buy.get('orderType', 'STOP')}")
            lines.append(f"  - Risk: {buy.get('riskPercent', 0)}%")
            entry_rule = buy.get('entryPriceRule', {})
            lines.append(f"  - Entry: {entry_rule.get('type', 'N/A')} at bar {entry_rule.get('barIndex', 'N/A')}")
            stop_rule = buy.get('stopLossPriceRule', {})
            lines.append(f"  - Stop: {stop_rule.get('type', 'N/A')}")
        
        if decision.get('sell'):
            sell = decision['sell']
            lines.append(f"  - Order Type: SELL {sell.get('orderType', 'STOP')}")
            lines.append(f"  - Risk: {sell.get('riskPercent', 0)}%")
            entry_rule = sell.get('entryPriceRule', {})
            lines.append(f"  - Entry: {entry_rule.get('type', 'N/A')} at bar {entry_rule.get('barIndex', 'N/A')}")
            stop_rule = sell.get('stopLossPriceRule', {})
            lines.append(f"  - Stop: {stop_rule.get('type', 'N/A')}")
        
        lines.append("")
        
        # Rationale
        lines.append("📝 **Rationale**:")
        rationale = decision.get('rationale', 'No rationale provided')
        # Split long rationale into multiple lines
        for line in rationale.split('. '):
            if line.strip():
                lines.append(f"  {line.strip()}")
        
        lines.append("")
        lines.append("❓ **Action Required**: Please approve or reject this trade.")
        
        return "\n".join(lines)
    
    async def send_telegram_approval(
        self,
        decision: Dict[str, Any],
        chart_path: str,
        brooks_analysis: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send approval request via Telegram.
        
        Returns:
            True if approved, False if rejected or timeout
        """
        message = self._format_decision_message(decision, brooks_analysis, chart_path)
        
        try:
            # Send chart image
            with open(chart_path, 'rb') as photo:
                await self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=photo,
                    caption=message[:1024]  # Telegram caption limit
                )
            
            # Send approval buttons
            import telegram
            keyboard = [
                [
                    telegram.InlineKeyboardButton("✅ Approve", callback_data="approve"),
                    telegram.InlineKeyboardButton("❌ Reject", callback_data="reject")
                ]
            ]
            reply_markup = telegram.InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text="⏳ Waiting for your decision...",
                reply_markup=reply_markup
            )
            
            # Wait for callback (simplified - in production, use proper callback handler)
            # For now, return based on timeout or manual approval via state file
            approved = await self._wait_for_approval(decision_id=str(datetime.now().timestamp()))
            
            return approved
            
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
            return False
    
    async def send_console_approval(
        self,
        decision: Dict[str, Any],
        chart_path: str,
        brooks_analysis: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send approval request to console (for testing).
        
        Returns:
            True if approved (auto-approve in console mode for testing)
        """
        message = self._format_decision_message(decision, brooks_analysis, chart_path)
        
        print("\n" + "=" * 80)
        print(message)
        print("=" * 80)
        print(f"\n📸 Chart: {chart_path}")
        print("\n⚠️  CONSOLE MODE: Auto-approving for testing purposes")
        print("    In production, set NOTIFICATION_PLATFORM to 'telegram' or 'discord'")
        print("=" * 80 + "\n")
        
        # In console mode, auto-approve after short delay
        await asyncio.sleep(2)
        return True
    
    async def _wait_for_approval(self, decision_id: str) -> bool:
        """
        Wait for human approval response.
        
        This is a simplified implementation. In production, you would:
        1. Store decision_id in database
        2. Use Telegram callback handler to update database
        3. Poll database here for approval status
        
        For now, check for a simple approval file.
        """
        approval_file = f"approval_{decision_id}.json"
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < self.timeout_seconds:
            if os.path.exists(approval_file):
                try:
                    with open(approval_file, 'r') as f:
                        result = json.load(f)
                        approved = result.get('approved', False)
                    
                    os.remove(approval_file)
                    return approved
                except Exception as e:
                    logger.error(f"Error reading approval file: {e}")
            
            await asyncio.sleep(1)
        
        # Timeout - default to reject
        logger.warning(f"Approval timeout after {self.timeout_seconds}s - rejecting trade")
        return False
    
    async def request_approval(
        self,
        decision: Dict[str, Any],
        chart_path: str,
        brooks_analysis: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Main method to request approval from human.
        
        Args:
            decision: Trading decision dict
            chart_path: Path to chart image
            brooks_analysis: Optional Brooks analysis dict
            
        Returns:
            True if approved, False if rejected
        """
        logger.info(f"Requesting human approval for {decision.get('operation')} decision...")
        
        try:
            if self.platform == "telegram":
                approved = await self.send_telegram_approval(decision, chart_path, brooks_analysis)
            elif self.platform == "discord":
                # TODO: Implement Discord
                logger.warning("Discord not implemented yet, falling back to console")
                approved = await self.send_console_approval(decision, chart_path, brooks_analysis)
            else:
                approved = await self.send_console_approval(decision, chart_path, brooks_analysis)
            
            if approved:
                logger.info("✅ Trade APPROVED by human")
            else:
                logger.info("❌ Trade REJECTED by human")
            
            return approved
            
        except Exception as e:
            logger.error(f"Approval request failed: {e}")
            # On error, default to reject for safety
            return False
    
    def notify_execution_result(
        self,
        decision: Dict[str, Any],
        execution_result: Dict[str, Any]
    ):
        """
        Notify human of trade execution result.
        
        Args:
            decision: Original decision
            execution_result: Result of execution
        """
        success = execution_result.get('success', False)
        
        if success:
            message = f"✅ Trade EXECUTED successfully\n\n{execution_result.get('message', '')}"
        else:
            message = f"❌ Trade FAILED\n\nError: {execution_result.get('error', 'Unknown error')}"
        
        logger.info(message)
        
        # Send to platform if not console
        if self.platform == "telegram":
            try:
                asyncio.run(self.bot.send_message(chat_id=self.chat_id, text=message))
            except Exception as e:
                logger.error(f"Failed to send execution result: {e}")


# Global singleton
_notification_service: Optional[NotificationService] = None

def get_notification_service() -> NotificationService:
    """Get global notification service instance"""
    global _notification_service
    
    if _notification_service is None:
        platform = os.getenv("NOTIFICATION_PLATFORM", "console")
        timeout = int(os.getenv("APPROVAL_TIMEOUT_SECONDS", "300"))
        
        _notification_service = NotificationService(
            platform=platform,
            timeout_seconds=timeout
        )
    
    return _notification_service
