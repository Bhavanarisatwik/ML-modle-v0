import logging
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
import httpx

from backend.config import (
    SLACK_WEBHOOK_URL,
    SMTP_SERVER,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASS,
    ALERT_EMAIL_TO,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_WHATSAPP_NUMBER,
    ALERT_WHATSAPP_TO
)

logger = logging.getLogger(__name__)

class NotificationService:
    """Service to handle broadcasting alerts cleanly over multiple channels"""

    def __init__(self):
        # httpx client for async HTTP requests
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def close(self):
        """Clean up HTTP client"""
        await self.client.aclose()

    def format_alert_message(self, alert: Any) -> str:
        """Standardizes the text format across channels"""
        try:
            # If it's a Pydantic model
            alert_dict = alert.dict() if hasattr(alert, 'dict') else alert
            
            risk = alert_dict.get('risk_score', 'N/A')
            attack = alert_dict.get('attack_type', 'Unknown Attack')
            ip = alert_dict.get('source_ip', 'Unknown IP')
            node = alert_dict.get('node_id', 'Unknown Node')
            action = alert_dict.get('activity', 'activity detected')
            
            msg = f"🚨 *DECOYVERSE ALERT* 🚨\n\n"
            msg += f"*Threat Detected:* {attack}\n"
            msg += f"*Risk Score:* {risk}/10\n"
            msg += f"*Source IP:* {ip}\n"
            msg += f"*Affected Node:* {node}\n"
            msg += f"*Action Taken:* {action}\n"
            return msg
        except Exception as e:
            return f"🚨 DecoyVerse Alert: Threat detected, but failed to format message: {e}"

    async def send_slack_alert(self, message: str, webhook_url: Optional[str] = None) -> Optional[bool]:
        """Returns True on success, False on failure, None if skipped (not configured)."""
        target_url = webhook_url or SLACK_WEBHOOK_URL
        if not target_url:
            logger.info("Skipping Slack alert: Webhook URL is not set.")
            return None

        try:
            payload = {"text": message}
            response = await self.client.post(target_url, json=payload)
            response.raise_for_status()
            logger.info("✅ Slack alert sent successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send Slack alert: {e}")
            return False

    async def send_email_alert(self, alert_dict: dict, message: str, alert_to: Optional[str]) -> Optional[bool]:
        """Returns True on success, False on failure, None if skipped (not configured)."""
        target_to = alert_to or ALERT_EMAIL_TO
        target_server = SMTP_SERVER
        target_port = SMTP_PORT
        target_user = SMTP_USER
        target_pass = SMTP_PASS

        if not all([target_server, target_user, target_pass, target_to]):
            logger.info("Skipping Email alert: SMTP config or Recipient is not fully set.")
            return None

        try:
            def _send_email():
                msg = MIMEMultipart()
                msg['From'] = target_user
                msg['To'] = target_to
                attack = alert_dict.get('attack_type', 'Threat')
                msg['Subject'] = f"[DecoyVerse Alert] Critical {attack} Detected"

                body = message.replace('*', '')  # Remove markdown bold for plain text email
                msg.attach(MIMEText(body, 'plain'))

                server = smtplib.SMTP(target_server, target_port)
                server.starttls()
                server.login(target_user, target_pass)
                text = msg.as_string()
                server.sendmail(target_user, target_to, text)
                server.quit()

            # Run blocking SMTP calls in thread
            await asyncio.to_thread(_send_email)
            logger.info("✅ Email alert sent successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send Email alert: {e}")
            return False

    async def send_whatsapp_alert(self, message: str, target_number: Optional[str] = None) -> Optional[bool]:
        """Returns True on success, False on failure, None if skipped (not configured)."""
        final_target = target_number or ALERT_WHATSAPP_TO
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER, final_target]):
            logger.info("Skipping WhatsApp alert: Twilio config or Target Number is not fully set.")
            return None

        try:
            # Twilio REST API URL
            url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

            # Twilio expects url-encoded form data
            data = {
                "From": f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
                "To": f"whatsapp:{final_target}",
                "Body": message
            }

            response = await self.client.post(
                url,
                data=data,
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            )
            response.raise_for_status()
            logger.info("✅ WhatsApp alert sent successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send WhatsApp alert: {e}")
            return False

    async def broadcast_alert(self, alert: Any):
        """
        Formats and broadcasts an alert to all configured channels.

        Deduplication: if alert.notified is already True, skips silently.
        After sending, updates notified + notification_status in the DB.
        """
        try:
            alert_dict = alert.dict() if hasattr(alert, 'dict') else dict(alert)

            # --- Deduplication check ---
            if alert_dict.get('notified', False):
                logger.info("⏭️  Alert already notified — skipping broadcast")
                return

            alert_id = alert_dict.get('alert_id')
            message = self.format_alert_message(alert)
            user_id = alert_dict.get('user_id')

            # Default per-user channel credentials (fall back to env vars inside each send_* method)
            slack_url = None
            email_to = None
            whatsapp_num = None

            # Look up user's saved notification preferences
            if user_id:
                from backend.services.db_service import db_service
                user_record = await db_service.get_user_by_id(user_id)
                if user_record:
                    notifs = user_record.get("notifications") or {}
                    slack_url = notifs.get("slackWebhook") or None
                    email_to = notifs.get("emailAlertTo") or None
                    whatsapp_num = notifs.get("whatsappNumber") or None

            # Fire all channels concurrently; capture individual results
            results = await asyncio.gather(
                self.send_slack_alert(message, slack_url),
                self.send_email_alert(alert_dict, message, email_to),
                self.send_whatsapp_alert(message, whatsapp_num),
                return_exceptions=True
            )

            # Determine outcome
            # None  → channel skipped (not configured)
            # True  → sent successfully
            # False / Exception → failed
            active = [r for r in results if r is not None]
            if not active:
                notified = False
                notification_status = "no_channels"
            elif any(r is True for r in active):
                notified = True
                notification_status = "sent"
            else:
                notified = False
                notification_status = "failed"

            logger.info(f"📣 Broadcast complete — notified={notified}, status={notification_status}")

            # Persist tracking fields to DB
            if alert_id:
                from backend.services.db_service import db_service
                await db_service.update_alert_notification(alert_id, notified, notification_status)
            else:
                logger.warning("broadcast_alert: alert_id is None — cannot persist notification status")

        except Exception as e:
            logger.error(f"❌ Critical error in alert broadcasting: {e}")

# Create singleton instance
notification_service = NotificationService()
