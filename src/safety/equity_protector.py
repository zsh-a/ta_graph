"""
资金保护器 - Equity Protector

防止过度亏损：
1. 每日亏损熔断
2. 连续亏损暂停
3. 账户保护
"""

from datetime import datetime, date, timedelta
from ..logger import get_logger
from ..notification.alerts import send_alert

logger = get_logger(__name__)


class EquityProtector:
    """
    资金保护器
    
    Brooks 风控原则：
    - 永远不要让一天的亏损超过账户的 2%
    - 连败后必须停下来思考
    """
    
    def __init__(
        self,
        max_daily_loss_pct: float = 2.0,
        max_consecutive_losses: int = 3,
        cooldown_hours: int = 2
    ):
        """
        初始化资金保护器
        
        Args:
            max_daily_loss_pct: 最大每日亏损百分比（默认 2%）
            max_consecutive_losses: 最大连续亏损次数（默认 3 次）
            cooldown_hours: 暂停交易时长（小时）
        """
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_hours = cooldown_hours
        
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.trading_enabled = True
        self.last_reset_date = date.today()
        self.cooldown_until = None
        
        self.trade_history = []  # 交易历史
    
    def update_trade_result(self, pnl: float, account_balance: float):
        """
        更新交易结果
        
        Args:
            pnl: 本次交易盈亏
            account_balance: 当前账户余额
        """
        # 记录交易
        self.trade_history.append({
            "timestamp": datetime.now(),
            "pnl": pnl,
            "balance": account_balance
        })
        
        # 更新每日 PnL
        self.daily_pnl += pnl
        
        # 更新连续亏损计数
        if pnl < 0:
            self.consecutive_losses += 1
            logger.warning(f"❌ Loss #{self.consecutive_losses}: ${pnl:.2f}")
        else:
            self.consecutive_losses = 0
            logger.info(f"✅ Win: ${pnl:.2f}")
        
        # 检查熔断条件
        self._check_circuit_breakers(account_balance)
    
    def _check_circuit_breakers(self, account_balance: float):
        """检查熔断条件"""
        
        # 1. 每日亏损熔断
        if self.daily_pnl < 0:
            daily_loss_pct = abs(self.daily_pnl / account_balance * 100)
            
            if daily_loss_pct >= self.max_daily_loss_pct:
                logger.critical(
                    f"🔴 CIRCUIT BREAKER: Daily loss {daily_loss_pct:.2f}% "
                    f">= {self.max_daily_loss_pct}%"
                )
                
                self.trading_enabled = False
                
                send_alert(
                    title="Daily Loss Limit Hit - Trading Stopped",
                    message=f"""
Daily PnL: ${self.daily_pnl:.2f}
Percentage: {daily_loss_pct:.2f}%
Limit: {self.max_daily_loss_pct}%

Trading is now DISABLED for today.
Will resume tomorrow.
                    """,
                    severity="critical"
                )
        
        # 2. 连续亏损暂停
        if self.consecutive_losses >= self.max_consecutive_losses:
            logger.warning(
                f"⚠️ {self.consecutive_losses} consecutive losses. "
                f"Entering cooldown for {self.cooldown_hours} hours."
            )
            
            self.trading_enabled = False
            self.cooldown_until = datetime.now() + timedelta(hours=self.cooldown_hours)
            
            send_alert(
                title=f"Consecutive Losses - {self.cooldown_hours}h Cooldown",
                message=f"""
Consecutive Losses: {self.consecutive_losses}
Recent PnL: ${self.daily_pnl:.2f}

Trading paused until: {self.cooldown_until.strftime('%Y-%m-%d %H:%M')}

Take time to review your strategy.
                """,
                severity="warning"
            )
    
    def can_trade(self) -> bool:
        """
        是否允许交易
        
        Returns:
            True 如果允许交易，False 如果被禁止
        """
        # 检查日期重置
        today = date.today()
        if today > self.last_reset_date:
            self.reset_daily()
        
        # 检查冷却时间
        if self.cooldown_until and datetime.now() >= self.cooldown_until:
            logger.info("⏰ Cooldown period ended. Resuming trading.")
            self.trading_enabled = True
            self.cooldown_until = None
        
        return self.trading_enabled
    
    def reset_daily(self):
        """每日重置"""
        logger.info("🔄 Daily reset: Resetting PnL and enabling trading")
        
        self.daily_pnl = 0.0
        self.trading_enabled = True
        self.last_reset_date = date.today()
    
    def force_enable(self):
        """强制启用交易（管理员操作）"""
        logger.warning("⚠️ Trading force-enabled by admin")
        self.trading_enabled = True
        self.cooldown_until = None
    
    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            "trading_enabled": self.trading_enabled,
            "daily_pnl": self.daily_pnl,
            "consecutive_losses": self.consecutive_losses,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "last_reset_date": self.last_reset_date.isoformat()
        }


# 全局单例
_equity_protector = None


def get_equity_protector(**kwargs) -> EquityProtector:
    """获取全局 Equity Protector 实例"""
    global _equity_protector
    if _equity_protector is None:
        _equity_protector = EquityProtector(**kwargs)
    return _equity_protector
