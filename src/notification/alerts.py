"""
通知推送系统 - Notification & Alerts

支持多种推送方式：Telegram, 邮件, 日志
"""

import os
from typing import Literal
from datetime import datetime
from ..logger import get_logger

logger = get_logger(__name__)

AlertSeverity = Literal["info", "warning", "critical"]


def send_alert(
    title: str,
    message: str,
    severity: AlertSeverity = "info",
    image_url: str | None = None
):
    """
    发送交易警报
    
    Args:
        title: 警报标题
        message: 警报内容
        severity: 严重程度 (info, warning, critical)
        image_url: 可选的图表截图 URL
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 格式化消息
    formatted_message = f"""
{'='*60}
[{severity.upper()}] {title}
Time: {timestamp}
{'='*60}

{message}

{'='*60}
"""
    
    # 1. 日志记录（始终执行）
    if severity == "critical":
        logger.critical(formatted_message)
    elif severity == "warning":
        logger.warning(formatted_message)
    else:
        logger.info(formatted_message)
    
    # 2. Telegram 推送
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if telegram_token and telegram_chat_id:
        try:
            send_telegram_message(
                token=telegram_token,
                chat_id=telegram_chat_id,
                text=f"【{severity.upper()}】{title}\n\n{message}",
                image_url=image_url
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
    
    # 3. 邮件推送（仅 critical）
    if severity == "critical":
        email = os.getenv("ALERT_EMAIL")
        if email:
            try:
                send_email(
                    to_email=email,
                    subject=f"🔴 CRITICAL: {title}",
                    body=message
                )
            except Exception as e:
                logger.error(f"Failed to send email: {e}")


def send_telegram_message(
    token: str,
    chat_id: str,
    text: str,
    image_url: str | None = None
):
    """发送 Telegram 消息"""
    import requests
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    response = requests.post(url, json=data)
    response.raise_for_status()
    
    # 如果有图片，发送图片
    if image_url:
        photo_url = f"https://api.telegram.org/bot{token}/sendPhoto"
        photo_data = {
            "chat_id": chat_id,
            "photo": image_url
        }
        requests.post(photo_url, json=photo_data)


def send_email(to_email: str, subject: str, body: str):
    """发送邮件警报（使用 SMTP）"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_user or not smtp_password:
        logger.warning("SMTP credentials not configured")
        return
    
    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    
    msg.attach(MIMEText(body, "plain"))
    
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def notify_trade_event(
    event: Literal["entry", "exit", "stop_moved", "partial_exit"],
    state: dict,
    **kwargs
):
    """
    交易事件通知
    
    在关键交易时刻发送通知
    """
    symbol = state.get("symbol", "N/A")
    
    if event == "entry":
        position = state.get("position", {})
        send_alert(
            title=f"✅ Position Opened: {symbol}",
            message=f"""
Side: {position.get('side', 'N/A').upper()}
Entry Price: {position.get('entry_price', 0)}
Size: {position.get('size', 0)}
Stop Loss: {state.get('stop_loss', 'N/A')}
Leverage: {position.get('leverage', 'N/A')}x

Reasoning: {kwargs.get('reasoning', 'N/A')}
            """,
            severity="info"
        )
    
    elif event == "exit":
        pnl = kwargs.get("pnl", 0)
        send_alert(
            title=f"📊 Position Closed: {symbol}",
            message=f"""
PnL: ${pnl:.2f}
Exit Reason: {kwargs.get('reason', 'N/A')}
Duration: {kwargs.get('duration', 'N/A')} bars
Win/Loss: {'WIN ✅' if pnl > 0 else 'LOSS ❌'}
            """,
            severity="warning" if pnl < 0 else "info"
        )
    
    elif event == "stop_moved":
        send_alert(
            title=f"🔒 Stop Loss Moved: {symbol}",
            message=f"""
Old Stop: {kwargs.get('old_stop', 'N/A')}
New Stop: {kwargs.get('new_stop', 'N/A')}
Reason: {kwargs.get('reason', 'Trailing/Breakeven')}
            """,
            severity="info"
        )
    
    elif event == "partial_exit":
        send_alert(
            title=f"💰 Partial Profit Taken: {symbol}",
            message=f"""
Closed Size: {kwargs.get('size_closed', 0)}
Remaining Size: {kwargs.get('size_remaining', 0)}
Profit: ${kwargs.get('profit', 0):.2f}
Target Level: {kwargs.get('target_level', 'N/A')}
            """,
            severity="info"
        )
