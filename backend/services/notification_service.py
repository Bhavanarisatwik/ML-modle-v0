import logging
import os
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

    def _build_alert_html(self, alert_dict: dict) -> str:
        """Build a beautiful HTML email that mirrors the ThreatModal card design."""
        attack_type = str(alert_dict.get('attack_type', 'Unknown Attack')).replace('_', ' ').title()
        risk_score  = alert_dict.get('risk_score', 'N/A')
        confidence  = alert_dict.get('confidence')
        confidence_str = f"{confidence * 100:.1f}%" if confidence is not None else "N/A"
        status      = str(alert_dict.get('status', 'open')).upper()
        source_ip   = alert_dict.get('source_ip', 'Unknown')
        node_id     = alert_dict.get('node_id', 'Unknown')
        service     = alert_dict.get('service', 'Unknown')
        activity    = alert_dict.get('activity', 'Unknown')
        alert_id    = alert_dict.get('alert_id', '—')
        payload     = str(alert_dict.get('payload', ''))[:500]
        ts_raw      = alert_dict.get('timestamp', '')
        try:
            from datetime import datetime
            ts = datetime.fromisoformat(ts_raw).strftime('%b %d, %Y %H:%M:%S UTC') if ts_raw else 'Unknown'
        except Exception:
            ts = ts_raw or 'Unknown'

        risk_label = f"{risk_score} / 10" if isinstance(risk_score, (int, float)) else str(risk_score)

        DARK_BG = '#0f1117'; CARD_BG = '#1a1d27'; BORDER = '#2a2d3a'
        RED = '#ef4444'; RED_DIM = '#7f1d1d'; RED_BG = '#1c0a0a'
        GOLD = '#f59e0b'; MUTED = '#6b7280'; WHITE = '#f9fafb'
        MONO = 'Courier New, Courier, monospace'
        SANS = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif'

        import os
        dashboard_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')

        payload_block = ""
        if payload:
            payload_block = f"""
            <div style="border-radius:10px;overflow:hidden;border:1px solid {BORDER}">
              <div style="background:#0d1117;padding:8px 14px;border-bottom:1px solid {BORDER};
                          font-size:10px;color:{MUTED};letter-spacing:.06em;text-transform:uppercase">
                &#x2022; Target Asset / Payload Fragment
              </div>
              <div style="background:#0a0a0f;padding:16px">
                <code style="font-family:{MONO};font-size:12px;color:#a8ff78;word-break:break-all;white-space:pre-wrap">{payload}</code>
              </div>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>DecoyVerse Alert</title></head>
<body style="margin:0;padding:0;background:{DARK_BG};font-family:{SANS}">
<table width="100%" cellpadding="0" cellspacing="0" style="background:{DARK_BG};padding:32px 16px">
  <tr><td align="center">
  <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:16px;overflow:hidden;border:1px solid {BORDER}">

    <!-- Wordmark -->
    <tr><td style="background:{CARD_BG};padding:18px 28px;border-bottom:1px solid {BORDER}">
      <span style="font-size:20px;font-weight:800;color:{GOLD};letter-spacing:-.5px">&#x2756; DecoyVerse</span>
      <span style="font-size:11px;color:{MUTED};margin-left:8px">Security Platform</span>
    </td></tr>

    <!-- Alert Header -->
    <tr><td style="background:{RED_BG};border-bottom:1px solid {RED_DIM};padding:20px 28px">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td>
          <div style="font-size:11px;color:{RED};text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px">
            &#x26A0; Critical Threat Detected
          </div>
          <div style="font-size:22px;font-weight:800;color:{WHITE}">Security Alert Triggered</div>
          <div style="font-size:12px;color:{MUTED};margin-top:4px">Alert ID: <span style="font-family:{MONO};color:{WHITE}">{alert_id}</span></div>
        </td>
        <td align="right" style="vertical-align:top">
          <div style="background:{RED};color:#fff;font-size:11px;font-weight:700;
                      padding:4px 12px;border-radius:20px;text-transform:uppercase;
                      letter-spacing:.08em;display:inline-block">{status}</div>
        </td>
      </tr></table>
    </td></tr>

    <!-- Body -->
    <tr><td style="background:{DARK_BG};padding:24px 28px">

      <!-- Stats grid -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px"><tr>
        <td width="25%" style="padding:4px">
          <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px">
            <div style="font-size:10px;color:{MUTED};text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">&#x26A1; Attack Type</div>
            <div style="font-size:14px;font-weight:700;color:{WHITE}">{attack_type}</div>
          </div>
        </td>
        <td width="25%" style="padding:4px">
          <div style="background:{RED_BG};border:2px solid {RED};border-radius:10px;padding:14px">
            <div style="font-size:10px;color:{MUTED};text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">&#x1F6E1; Risk Score</div>
            <div style="font-size:18px;font-weight:800;color:{RED}">{risk_label}</div>
          </div>
        </td>
        <td width="25%" style="padding:4px">
          <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px">
            <div style="font-size:10px;color:{MUTED};text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">&#x1F9EC; Confidence</div>
            <div style="font-size:14px;font-weight:700;color:{WHITE}">{confidence_str}</div>
          </div>
        </td>
        <td width="25%" style="padding:4px">
          <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:10px;padding:14px">
            <div style="font-size:10px;color:{MUTED};text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">&#x1F4CB; Status</div>
            <div style="font-size:14px;font-weight:700;color:{WHITE}">{status}</div>
          </div>
        </td>
      </tr></table>

      <!-- Intelligence Payload -->
      <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:12px;padding:20px;margin-bottom:20px">
        <div style="font-size:10px;color:{MUTED};text-transform:uppercase;letter-spacing:.1em;
                    border-bottom:1px solid {BORDER};padding-bottom:10px;margin-bottom:14px">
          &#x1F9E0; Intelligence Payload
        </div>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding:6px 0;width:40%;vertical-align:top"><span style="font-size:11px;color:{MUTED};text-transform:uppercase;letter-spacing:.06em">Source IP</span></td>
            <td style="padding:6px 0;vertical-align:top"><code style="font-family:{MONO};font-size:12px;color:{WHITE};background:#0d1117;border:1px solid {BORDER};border-radius:4px;padding:2px 6px">{source_ip}</code></td>
          </tr>
          <tr>
            <td style="padding:6px 0;vertical-align:top"><span style="font-size:11px;color:{MUTED};text-transform:uppercase;letter-spacing:.06em">Node ID</span></td>
            <td style="padding:6px 0;vertical-align:top"><code style="font-family:{MONO};font-size:12px;color:{WHITE}">{node_id}</code></td>
          </tr>
          <tr>
            <td style="padding:6px 0;vertical-align:top"><span style="font-size:11px;color:{MUTED};text-transform:uppercase;letter-spacing:.06em">Service</span></td>
            <td style="padding:6px 0;vertical-align:top"><span style="font-size:13px;color:{WHITE}">{service}</span></td>
          </tr>
          <tr>
            <td style="padding:6px 0;vertical-align:top"><span style="font-size:11px;color:{MUTED};text-transform:uppercase;letter-spacing:.06em">Activity</span></td>
            <td style="padding:6px 0;vertical-align:top"><span style="font-size:13px;color:{WHITE}">{activity}</span></td>
          </tr>
          <tr>
            <td style="padding:6px 0;vertical-align:top"><span style="font-size:11px;color:{MUTED};text-transform:uppercase;letter-spacing:.06em">Timestamp</span></td>
            <td style="padding:6px 0;vertical-align:top"><span style="font-size:13px;color:{WHITE}">{ts}</span></td>
          </tr>
        </table>
      </div>

      {payload_block}

    </td></tr>

    <!-- CTA -->
    <tr><td style="background:{CARD_BG};padding:20px 28px;border-top:1px solid {BORDER};text-align:center">
      <a href="{dashboard_url}/dashboard"
         style="display:inline-block;background:{RED};color:#fff;font-weight:700;
                font-size:14px;padding:12px 32px;border-radius:8px;text-decoration:none;
                letter-spacing:.04em;box-shadow:0 0 16px rgba(239,68,68,.4)">
        Open Dashboard &rarr;
      </a>
    </td></tr>

    <!-- Footer -->
    <tr><td style="background:{DARK_BG};padding:16px 28px;border-top:1px solid {BORDER};text-align:center">
      <p style="font-size:11px;color:{MUTED};margin:0">You are receiving this because a threat was detected on your monitored node.</p>
      <p style="font-size:11px;color:{MUTED};margin:6px 0 0">DecoyVerse &bull; Cybersecurity Deception Platform</p>
    </td></tr>

  </table>
  </td></tr>
</table>
</body></html>"""

    async def send_email_alert(self, alert_dict: dict, message: str, alert_to: Optional[str]) -> Optional[bool]:
        """Returns True on success, False on failure, None if skipped (not configured)."""
        target_to = alert_to or ALERT_EMAIL_TO
        target_server = SMTP_SERVER
        target_port = SMTP_PORT
        target_user = SMTP_USER
        target_pass = SMTP_PASS

        if not target_to:
            logger.info("Skipping Email alert: no recipient configured.")
            return None

        # Relay through Express/NodeMailer so all email uses the same IPv4-safe sender
        express_url = os.getenv('EXPRESS_API_URL', 'http://localhost:5000')
        internal_secret = os.getenv('INTERNAL_SECRET', '')

        alert_data = {
            'alert_id':   str(alert_dict.get('_id', '')),
            'attack_type': alert_dict.get('attack_type'),
            'risk_score':  alert_dict.get('risk_score'),
            'confidence':  alert_dict.get('confidence'),
            'status':      alert_dict.get('status', 'open'),
            'source_ip':   alert_dict.get('source_ip'),
            'node_id':     str(alert_dict.get('node_id', '')),
            'service':     alert_dict.get('service'),
            'activity':    alert_dict.get('activity'),
            'timestamp':   str(alert_dict.get('timestamp', '')),
            'payload':     alert_dict.get('payload'),
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{express_url}/api/auth/internal/send-alert-email",
                    json={'to': target_to, 'alertData': alert_data},
                    headers={'x-internal-secret': internal_secret},
                )
                response.raise_for_status()
            logger.info("✅ Email alert relayed via Express/NodeMailer")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to relay Email alert to Express: {e}")
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
