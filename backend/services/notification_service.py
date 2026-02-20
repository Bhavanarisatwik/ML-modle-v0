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

    async def send_slack_alert(self, message: str, webhook_url: Optional[str] = None):
        target_url = webhook_url or SLACK_WEBHOOK_URL
        if not target_url:
            logger.info("Skipping Slack alert: Webhook URL is not set.")
            return
            
        try:
            payload = {"text": message}
            response = await self.client.post(target_url, json=payload)
            response.raise_for_status()
            logger.info("✅ Slack alert sent successfully")
        except Exception as e:
            logger.error(f"❌ Failed to send Slack alert: {e}")

    async def send_email_alert(self, alert_dict: dict, message: str, alert_to: Optional[str]):
        target_to = alert_to or ALERT_EMAIL_TO
        target_server = SMTP_SERVER
        target_port = SMTP_PORT
        target_user = SMTP_USER
        target_pass = SMTP_PASS

        if not all([target_server, target_user, target_pass, target_to]):
            logger.info("Skipping Email alert: SMTP config or Recipient is not fully set.")
            return

        try:
            def _send_email():
                msg = MIMEMultipart()
                msg['From'] = target_user
                msg['To'] = target_to
                attack = alert_dict.get('attack_type', 'Threat')
                msg['Subject'] = f"[DecoyVerse Alert] Critical {attack} Detected"

                body = message.replace('*', '') # Remove markdown bold for plain text email
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
        except Exception as e:
            logger.error(f"❌ Failed to send Email alert: {e}")

    async def send_whatsapp_alert(self, message: str, target_number: Optional[str] = None):
        final_target = target_number or ALERT_WHATSAPP_TO
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER, final_target]):
            logger.info("Skipping WhatsApp alert: Twilio config or Target Number is not fully set.")
            return

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
        except Exception as e:
            logger.error(f"❌ Failed to send WhatsApp alert: {e}")

    async def broadcast_alert(self, alert: Any):
        """
        Takes an alert object, formats it, looks up user preferences if available, 
        and broadcasts to all configured channels.
        """
        try:
            message = self.format_alert_message(alert)
            alert_dict = alert.dict() if hasattr(alert, 'dict') else alert
            user_id = alert_dict.get('user_id')

            # Default credentials
            slack_url = None
            email_to = None
            whatsapp_num = None

            # Look up dynamic credentials if user exists
            if user_id:
                # We need to import db_service here to avoid circular dependencies locally
                from backend.services.db_service import db_service
                user_record = await db_service.get_user_by_id(user_id)
                if user_record and "notifications" in user_record:
                    notifs = user_record["notifications"]
                    if notifs:
                        slack_url = notifs.get("slackWebhook")
                        email_to = notifs.get("emailAlertTo")
                        whatsapp_num = notifs.get("whatsappNumber")
            
            # Fire all configurations concurrently
            await asyncio.gather(
                self.send_slack_alert(message, slack_url),
                self.send_email_alert(alert_dict, message, email_to),
                self.send_whatsapp_alert(message, whatsapp_num),
                return_exceptions=True # Don't let one failure stop others
            )
        except Exception as e:
            logger.error(f"❌ Critical error in alert broadcasting: {e}")

# Create singleton instance
notification_service = NotificationService()
