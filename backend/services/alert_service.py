"""Alert system service for monitoring."""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import aiosmtplib
import httpx

from backend.models.monitoring import Alert, AlertListResponse, AlertSeverity, AlertType, CreateAlertRule
from backend.services.database_adapter import DatabaseAdapter
from backend.services.metrics_service import MetricsService

LOGGER = logging.getLogger(__name__)


class AlertService:
    """Service for managing alerts with queue-based aggregation."""

    # Cache TTL for alert configurations (60 seconds)
    ALERT_CONFIG_CACHE_TTL = 60

    # Severity hierarchy for threshold comparisons
    SEVERITY_LEVELS = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}

    def __init__(self, database_adapter: DatabaseAdapter, metrics_service: MetricsService):
        """Initialize alert service."""
        self.adapter = database_adapter
        self.metrics_service = metrics_service
        self._alert_config_cache: list[dict[str, Any]] = []
        self._cache_timestamp: float = 0
        self.logger = LOGGER

    async def load_alert_configurations(self) -> list[dict[str, Any]]:
        """Load alert configurations from database."""
        try:
            # Query alert configurations using DatabaseAdapter
            query = """
                SELECT id, rule_name, description, is_enabled, error_types, stages,
                       severity_threshold, error_count_threshold, time_window_minutes,
                       aggregation_window_minutes, email_recipients, slack_webhooks
                FROM krai_system.alert_configurations
                WHERE is_enabled = true
                ORDER BY created_at DESC
            """
            response = await self.adapter.execute_query(query)

            # Initialize cache with current timestamp to respect TTL
            self._alert_config_cache = response or []
            self._cache_timestamp = time.time()

            self.logger.info(f"Loaded {len(self._alert_config_cache)} alert configurations")
            return self._alert_config_cache

        except Exception as e:
            self.logger.error(f"Failed to load alert configurations: {e}", exc_info=True)
            # Initialize empty cache on error
            self._alert_config_cache = []
            self._cache_timestamp = time.time()
            return self._alert_config_cache

    async def _get_alert_rules(self) -> list[dict[str, Any]]:
        """Get alert configurations with 60-second cache."""
        try:
            # Check if cache is valid
            if self._alert_config_cache and (time.time() - self._cache_timestamp < self.ALERT_CONFIG_CACHE_TTL):
                self.logger.debug("Loading alert configurations from cache")
                return self._alert_config_cache

            # Cache expired or empty, query database
            self.logger.debug("Loading alert configurations from database")
            query = """
                SELECT id, rule_name, description, is_enabled, error_types, stages,
                       severity_threshold, error_count_threshold, time_window_minutes,
                       aggregation_window_minutes, email_recipients, slack_webhooks
                FROM krai_system.alert_configurations
                WHERE is_enabled = true
            """
            response = await self.adapter.execute_query(query)

            # Update cache
            self._alert_config_cache = response or []
            self._cache_timestamp = time.time()

            return self._alert_config_cache

        except Exception as e:
            self.logger.error(f"Failed to get alert rules: {e}", exc_info=True)
            return []

    def _severity_meets_threshold(self, error_severity: str, threshold_severity: str) -> bool:
        """Check if error severity meets or exceeds threshold severity."""
        error_level = self.SEVERITY_LEVELS.get(error_severity.lower(), 0)
        threshold_level = self.SEVERITY_LEVELS.get(threshold_severity.lower(), 0)
        return error_level >= threshold_level

    def _matches_rule(self, error_data: dict[str, Any], rule_config: dict[str, Any]) -> bool:
        """Check if error data matches alert rule criteria."""
        try:
            # Check error_type match (None or empty array = match all)
            error_types = rule_config.get("error_types")
            if error_types and len(error_types) > 0:
                if error_data.get("error_type") not in error_types:
                    return False

            # Check stage match (None or empty array = match all)
            stages = rule_config.get("stages")
            if stages and len(stages) > 0:
                if error_data.get("stage_name") not in stages:
                    return False

            # Check severity threshold
            severity_threshold = rule_config.get("severity_threshold")
            if severity_threshold:
                error_severity = error_data.get("severity", "low")
                if not self._severity_meets_threshold(error_severity, severity_threshold):
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Error matching rule: {e}", exc_info=True)
            return False

    def _build_alert_message(self, error_data: dict[str, Any], rule_config: dict[str, Any]) -> str:
        """Build alert message from error data and rule configuration."""
        rule_name = rule_config.get("rule_name", "Unknown Rule")
        error_type = error_data.get("error_type", "unknown")
        stage_name = error_data.get("stage_name", "unknown")

        message = f"Alert: {rule_name} - {error_type} in {stage_name}"

        # Include error count if available
        error_count = rule_config.get("error_count_threshold")
        time_window = rule_config.get("time_window_minutes")
        if error_count and time_window:
            message += f" ({error_count} occurrences in {time_window} minutes)"

        return message

    def _build_alert_details(self, error_data: dict[str, Any]) -> dict[str, Any]:
        """Build alert details dictionary from error data."""
        details = {
            "document_id": error_data.get("document_id"),
            "error_message": error_data.get("error_message"),
            "stack_trace": error_data.get("stack_trace"),
            "context": error_data.get("context"),
            "correlation_id": error_data.get("correlation_id"),
            "occurred_at": error_data.get("timestamp", datetime.utcnow().isoformat()),
        }
        return details

    async def queue_alert(self, error_data: dict[str, Any]) -> str | None:
        """Queue alert for matching error data.

        Args:
            error_data: Dictionary containing error information with keys:
                - error_type: Type of error
                - stage_name: Pipeline stage where error occurred
                - severity: Error severity level
                - error_message: Error message
                - document_id: Related document ID
                - stack_trace: Stack trace if available
                - context: Additional context
                - correlation_id: Correlation ID for tracking

        Returns:
            Alert queue ID if alert was queued, None otherwise
        """
        try:
            # Get cached alert configurations
            alert_rules = await self._get_alert_rules()

            if not alert_rules:
                self.logger.debug("No alert rules configured")
                return None

            # Check each rule for matches
            for rule_config in alert_rules:
                if not self._matches_rule(error_data, rule_config):
                    continue

                # Generate aggregation key
                rule_name = rule_config.get("rule_name", "unknown")
                error_type = error_data.get("error_type", "unknown")
                stage_name = error_data.get("stage_name", "unknown")
                aggregation_key = f"{rule_name}:{error_type}:{stage_name}"

                # Check for existing alert in aggregation window
                aggregation_window = rule_config.get("aggregation_window_minutes", 5)
                check_query = f"""
                    SELECT id, aggregation_count FROM krai_system.alerts
                    WHERE aggregation_key = $1
                      AND status = 'pending'
                      AND created_at > NOW() - INTERVAL '{aggregation_window} minutes'
                    ORDER BY created_at DESC LIMIT 1
                """

                existing_alert = await self.adapter.execute_query(check_query, [aggregation_key])

                if existing_alert and len(existing_alert) > 0:
                    # Update existing alert
                    alert_id = existing_alert[0].get("id")
                    update_query = """
                        UPDATE krai_system.alerts
                        SET aggregation_count = aggregation_count + 1,
                            last_occurrence = CURRENT_TIMESTAMP
                        WHERE id = $1
                    """
                    await self.adapter.execute_query(update_query, [alert_id])
                    self.logger.info(
                        f"Updated aggregated alert {alert_id} for rule {rule_name} with key {aggregation_key}"
                    )
                    return str(alert_id)
                # Insert new alert
                alert_message = self._build_alert_message(error_data, rule_config)
                alert_details = self._build_alert_details(error_data)
                alert_type = error_data.get("error_type", "system_error")
                severity = error_data.get("severity", "medium")

                insert_query = """
                        INSERT INTO krai_system.alerts
                          (alert_type, severity, message, details, aggregation_key, status)
                        VALUES ($1, $2, $3, $4, $5, 'pending')
                        RETURNING id
                    """
                result = await self.adapter.execute_query(
                    insert_query, [alert_type, severity, alert_message, alert_details, aggregation_key]
                )

                if result and len(result) > 0:
                    alert_id = str(result[0].get("id"))
                    self.logger.info(f"Queued alert for rule {rule_name} with aggregation_key {aggregation_key}")
                    return alert_id

            # No rules matched
            error_type = error_data.get("error_type", "unknown")
            stage_name = error_data.get("stage_name", "unknown")
            self.logger.warning(f"No alert rules matched for error {error_type} in {stage_name}")
            return None

        except Exception as e:
            self.logger.error(f"Failed to queue alert: {e}", exc_info=True)
            return None

    async def send_email_alert(
        self, alert_data: dict[str, Any], recipients: list[str], rule_config: dict[str, Any]
    ) -> bool:
        """Send email alert notification.

        Args:
            alert_data: Dictionary containing alert information from alerts table
            recipients: List of email addresses to send to
            rule_config: Alert configuration from alert_configurations table

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Get SMTP configuration from environment
            smtp_host = os.getenv("SMTP_HOST")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            smtp_username = os.getenv("SMTP_USERNAME")
            smtp_password = os.getenv("SMTP_PASSWORD")
            smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "alerts@krai.local")
            smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

            if not smtp_host:
                self.logger.error("SMTP_HOST not configured, cannot send email")
                return False

            if not recipients:
                self.logger.warning("No email recipients configured")
                return False

            # Load and render email template
            template_path = Path(__file__).parent.parent / "templates" / "alert_email.html"

            if not template_path.exists():
                self.logger.error(f"Email template not found at {template_path}")
                return False

            with open(template_path, encoding="utf-8") as f:
                html_template = f.read()

            # Prepare template variables
            severity = alert_data.get("severity", "medium")
            severity_colors = {
                "critical": "#dc3545",
                "high": "#fd7e14",
                "medium": "#ffc107",
                "low": "#17a2b8",
                "info": "#6c757d",
            }

            details = alert_data.get("details", {})
            error_message = details.get("error_message", "")
            stack_trace = details.get("stack_trace", "")
            error_details = f"{error_message}\n\n{stack_trace}" if stack_trace else error_message

            # Render template with variables
            html_content = html_template.replace("{{ header_color }}", severity_colors.get(severity, "#6c757d"))
            html_content = html_content.replace("{{ rule_name }}", rule_config.get("rule_name", "Alert"))
            html_content = html_content.replace("{{ description }}", rule_config.get("description", ""))
            html_content = html_content.replace("{{ severity }}", severity.upper())
            html_content = html_content.replace("{{ alert_type }}", alert_data.get("alert_type", "system_error"))
            html_content = html_content.replace("{{ aggregation_count }}", str(alert_data.get("aggregation_count", 1)))
            html_content = html_content.replace("{{ first_occurrence }}", str(alert_data.get("first_occurrence", "")))
            html_content = html_content.replace("{{ last_occurrence }}", str(alert_data.get("last_occurrence", "")))
            html_content = html_content.replace("{{ message }}", alert_data.get("message", ""))
            html_content = html_content.replace("{{ timestamp }}", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))

            # Handle conditional error_details block
            if error_details:
                html_content = html_content.replace("{% if error_details %}", "")
                html_content = html_content.replace("{% endif %}", "")
                html_content = html_content.replace("{{ error_details }}", error_details)
            else:
                # Remove the entire error_details section
                import re

                html_content = re.sub(r"{% if error_details %}.*?{% endif %}", "", html_content, flags=re.DOTALL)

            # Create plain text version
            plain_text = f"""
KRAI Alert Notification

Rule: {rule_config.get('rule_name', 'Alert')}
Description: {rule_config.get('description', '')}

Severity: {severity.upper()}
Alert Type: {alert_data.get('alert_type', 'system_error')}
Occurrences: {alert_data.get('aggregation_count', 1)}
First Occurrence: {alert_data.get('first_occurrence', '')}
Last Occurrence: {alert_data.get('last_occurrence', '')}

Message:
{alert_data.get('message', '')}

{f'Error Details:{chr(10)}{error_details}' if error_details else ''}

---
This is an automated alert from KRAI Pipeline Monitoring System
Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
            """.strip()

            # Create multipart message
            message = MIMEMultipart("alternative")
            message["Subject"] = f"[KRAI Alert - {severity.upper()}] {rule_config.get('rule_name', 'Alert')}"
            message["From"] = smtp_from_email
            message["To"] = ", ".join(recipients)

            # Attach both plain text and HTML versions
            part1 = MIMEText(plain_text, "plain")
            part2 = MIMEText(html_content, "html")
            message.attach(part1)
            message.attach(part2)

            # Send email via SMTP
            self.logger.info(f"Sending email alert to {len(recipients)} recipients via {smtp_host}:{smtp_port}")

            # Determine TLS mode based on port and configuration
            # Port 587: STARTTLS (start_tls=True, use_tls=False)
            # Port 465: Implicit SSL (use_tls=True, start_tls=False)
            # Other ports: Follow SMTP_USE_TLS setting
            if smtp_use_tls and smtp_port == 587:
                # Standard STARTTLS on port 587
                use_tls = False
                start_tls = True
            elif smtp_port == 465:
                # Implicit SSL on port 465
                use_tls = True
                start_tls = False
            else:
                # Legacy behavior for other ports
                use_tls = smtp_use_tls
                start_tls = False

            async with aiosmtplib.SMTP(
                hostname=smtp_host, port=smtp_port, use_tls=use_tls, start_tls=start_tls, timeout=30
            ) as smtp:
                if smtp_username and smtp_password:
                    await smtp.login(smtp_username, smtp_password)

                await smtp.send_message(message)

            self.logger.info(f"Email alert sent successfully to {recipients}")
            return True

        except aiosmtplib.SMTPException as e:
            self.logger.error(f"SMTP error sending email alert: {e}", exc_info=True)
            return False
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}", exc_info=True)
            return False

    async def send_slack_alert(
        self, alert_data: dict[str, Any], webhook_urls: list[str], rule_config: dict[str, Any]
    ) -> bool:
        """Send Slack alert notification using Block Kit API.

        Args:
            alert_data: Dictionary containing alert information from alerts table
            webhook_urls: List of Slack webhook URLs to send to
            rule_config: Alert configuration from alert_configurations table

        Returns:
            True if at least one webhook succeeds, False if all fail
        """
        try:
            # Get Slack configuration from environment
            default_webhook = os.getenv("SLACK_WEBHOOK_URL")
            timeout_seconds = int(os.getenv("SLACK_TIMEOUT_SECONDS", "10"))
            max_retries = int(os.getenv("SLACK_MAX_RETRIES", "3"))

            # Validate webhook URLs
            if not webhook_urls:
                if default_webhook:
                    webhook_urls = [default_webhook]
                else:
                    self.logger.warning("No Slack webhook URLs configured")
                    return False

            # Validate webhook URL format
            valid_webhooks = []
            for url in webhook_urls:
                if isinstance(url, str) and url.startswith("https://hooks.slack.com/"):
                    valid_webhooks.append(url)
                else:
                    # Safely log invalid entries without slicing None or non-strings
                    safe_repr = repr(url) if not isinstance(url, str) else f"{url[:20]}..."
                    self.logger.warning(f"Invalid Slack webhook URL format: {safe_repr}")

            if not valid_webhooks:
                self.logger.error("No valid Slack webhook URLs found")
                return False

            # Prepare alert data
            severity = alert_data.get("severity", "medium")
            rule_name = rule_config.get("rule_name", "Alert")
            description = rule_config.get("description", "")
            alert_type = alert_data.get("alert_type", "system_error")
            message = alert_data.get("message", "")
            aggregation_count = alert_data.get("aggregation_count", 1)
            first_occurrence = str(alert_data.get("first_occurrence", ""))
            last_occurrence = str(alert_data.get("last_occurrence", ""))

            # Get error details
            details = alert_data.get("details", {})
            error_message = details.get("error_message", "")
            stack_trace = details.get("stack_trace", "")
            error_details = f"{error_message}\n\n{stack_trace}" if stack_trace else error_message

            # Severity emoji mapping
            severity_emojis = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}
            severity_emoji = severity_emojis.get(severity, "⚪")

            # Severity color mapping for attachments
            severity_colors = {
                "critical": "danger",
                "high": "warning",
                "medium": "warning",
                "low": "#17a2b8",
                "info": "#6c757d",
            }
            severity_color = severity_colors.get(severity, "#6c757d")

            # Sanitize message content to prevent injection
            def sanitize(text: str) -> str:
                """Escape special characters for Slack."""
                if not text:
                    return ""
                return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            # Build Slack Block Kit message
            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{severity_emoji} KRAI Alert: {rule_name}", "emoji": True},
                },
                {"type": "context", "elements": [{"type": "mrkdwn", "text": sanitize(description)}]},
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Severity:*\n{severity.upper()}"},
                        {"type": "mrkdwn", "text": f"*Alert Type:*\n{sanitize(alert_type)}"},
                        {"type": "mrkdwn", "text": f"*Occurrences:*\n{aggregation_count}"},
                        {"type": "mrkdwn", "text": f"*First:*\n{sanitize(first_occurrence)}"},
                        {"type": "mrkdwn", "text": f"*Last:*\n{sanitize(last_occurrence)}"},
                    ],
                },
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*Message:*\n{sanitize(message)}"}},
            ]

            # Add error details block if available
            if error_details:
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Error Details:*\n```{sanitize(error_details[:2000])}```",  # Limit to 2000 chars
                        },
                    }
                )

            # Add footer
            blocks.extend(
                [
                    {"type": "divider"},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"KRAI Pipeline Monitoring | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                            }
                        ],
                    },
                ]
            )

            # Build complete payload
            payload = {
                "blocks": blocks,
                "attachments": [{"color": severity_color, "fallback": f"{rule_name} - {severity.upper()}"}],
            }

            # Send to multiple webhooks
            success_count = 0
            total_webhooks = len(valid_webhooks)

            self.logger.info(f"Sending Slack alert to {total_webhooks} webhook(s)")

            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                for idx, webhook_url in enumerate(valid_webhooks, 1):
                    # Mask webhook URL for logging (show only last 8 characters)
                    masked_url = f"...{webhook_url[-8:]}" if len(webhook_url) > 8 else "***"
                    self.logger.debug(f"Slack webhook {idx}/{total_webhooks}: {masked_url}")

                    # Retry logic with exponential backoff
                    retry_count = 0
                    webhook_success = False

                    while retry_count < max_retries and not webhook_success:
                        try:
                            # Send POST request
                            response = await client.post(
                                webhook_url, json=payload, headers={"Content-Type": "application/json"}
                            )
                            response.raise_for_status()

                            # Success
                            self.logger.info(f"Slack alert sent successfully to webhook {idx}")
                            webhook_success = True
                            success_count += 1

                            # Rate limiting: wait 1 second between webhooks
                            if idx < total_webhooks:
                                await asyncio.sleep(1)

                        except httpx.HTTPStatusError as e:
                            # Don't retry on 4xx errors (except 429 rate limit)
                            if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                                self.logger.error(
                                    f"Slack webhook {idx} failed with {e.response.status_code}: {e.response.text}"
                                )
                                break  # Don't retry

                            # Retry on 5xx or 429
                            retry_count += 1
                            if retry_count < max_retries:
                                # Exponential backoff with jitter: 1s, 2s, 4s + random 0-500ms
                                delay = (2 ** (retry_count - 1)) + (random.randint(0, 500) / 1000)
                                self.logger.warning(
                                    f"Slack webhook {idx} failed (attempt {retry_count}/{max_retries}): "
                                    f"HTTP {e.response.status_code}. Retrying in {delay:.2f}s..."
                                )
                                await asyncio.sleep(delay)
                            else:
                                self.logger.error(
                                    f"Slack webhook {idx} failed after {max_retries} retries: "
                                    f"HTTP {e.response.status_code}"
                                )

                        except httpx.TimeoutException:
                            retry_count += 1
                            if retry_count < max_retries:
                                delay = (2 ** (retry_count - 1)) + (random.randint(0, 500) / 1000)
                                self.logger.warning(
                                    f"Slack webhook {idx} timeout (attempt {retry_count}/{max_retries}). "
                                    f"Retrying in {delay:.2f}s..."
                                )
                                await asyncio.sleep(delay)
                            else:
                                self.logger.error(f"Slack webhook {idx} failed after {max_retries} retries: Timeout")

                        except httpx.RequestError as e:
                            retry_count += 1
                            if retry_count < max_retries:
                                delay = (2 ** (retry_count - 1)) + (random.randint(0, 500) / 1000)
                                self.logger.warning(
                                    f"Slack webhook {idx} connection error (attempt {retry_count}/{max_retries}): {e}. "
                                    f"Retrying in {delay:.2f}s..."
                                )
                                await asyncio.sleep(delay)
                            else:
                                self.logger.error(
                                    f"Slack webhook {idx} failed after {max_retries} retries: Connection error"
                                )

            # Return success if at least one webhook succeeded
            if success_count > 0:
                self.logger.info(f"Slack alert sent to {success_count}/{total_webhooks} webhook(s)")
                return True
            self.logger.error(f"All Slack webhooks failed for alert {alert_data.get('id', 'unknown')}")
            return False

        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {e}", exc_info=True)
            return False

    async def add_alert_configuration(self, rule: CreateAlertRule) -> str:
        """Add new alert configuration."""
        try:
            # Map CreateAlertRule fields to actual alert_configurations columns
            rule_data = {
                "rule_name": rule.name,
                "description": getattr(rule, "description", None),
                "is_enabled": rule.enabled,
                "error_types": getattr(rule, "error_types", None),
                "stages": getattr(rule, "stages", None),
                "severity_threshold": rule.severity.value,
                "error_count_threshold": getattr(rule, "error_count_threshold", 5),
                "time_window_minutes": getattr(rule, "time_window_minutes", 15),
                "aggregation_window_minutes": getattr(rule, "aggregation_window_minutes", 5),
                "email_recipients": getattr(rule, "email_recipients", None),
                "slack_webhooks": getattr(rule, "slack_webhooks", None),
                "created_by": getattr(rule, "created_by", None),
            }

            # Build INSERT query for alert configuration
            columns = list(rule_data.keys())
            placeholders = [f"${i+1}" for i in range(len(columns))]
            values = list(rule_data.values())

            query = f"""
                INSERT INTO krai_system.alert_configurations ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING id
            """

            result = await self.adapter.execute_query(query, values)

            if result and len(result) > 0:
                config_id = str(result[0].get("id", ""))
                # Update cache timestamp to keep cache consistent
                self._cache_timestamp = time.time()
                self.logger.info(f"Added alert configuration: {rule.name} (ID: {config_id})")
                return config_id

            raise RuntimeError("Failed to insert alert configuration")

        except Exception as e:
            self.logger.error(f"Failed to add alert configuration: {e}", exc_info=True)
            raise

    async def update_alert_configuration(self, config_id: str, updates: dict[str, Any]) -> bool:
        """Update existing alert configuration."""
        try:
            # Build dynamic UPDATE query
            set_clauses = [f"{key} = ${i+2}" for i, key in enumerate(updates.keys())]
            query = f"""
                UPDATE krai_system.alert_configurations
                SET {', '.join(set_clauses)}, updated_at = NOW()
                WHERE id = $1
            """

            result = await self.adapter.execute_query(query, [config_id] + list(updates.values()))

            if result and hasattr(result, "rowcount") and result.rowcount > 0:
                # Clear cache
                self._cache_timestamp = 0
                self.logger.info(f"Updated alert configuration: {config_id}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to update alert configuration: {e}", exc_info=True)
            return False

    async def delete_alert_configuration(self, config_id: str) -> bool:
        """Delete alert configuration."""
        try:
            query = "DELETE FROM krai_system.alert_configurations WHERE id = $1"
            result = await self.adapter.execute_query(query, [config_id])

            if result and hasattr(result, "rowcount") and result.rowcount > 0:
                # Clear cache
                self._cache_timestamp = 0
                self.logger.info(f"Deleted alert configuration: {config_id}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to delete alert configuration: {e}", exc_info=True)
            return False

    # Deprecated methods - replaced by queue_alert() and background worker
    # Kept for backward compatibility but will be removed in future version

    async def get_alerts(
        self,
        limit: int = 50,
        severity_filter: AlertSeverity | None = None,
        status_filter: str | None = None,
    ) -> AlertListResponse:
        """Get alerts from queue with optional filtering."""
        try:
            # Build query dynamically
            conditions = []
            params = []
            param_count = 0

            if severity_filter:
                param_count += 1
                conditions.append(f"severity = ${param_count}")
                params.append(severity_filter.value)

            if status_filter is not None:
                param_count += 1
                conditions.append(f"status = ${param_count}")
                params.append(status_filter)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            query = f"""
                SELECT id, alert_type, severity, message, details, aggregation_key,
                       aggregation_count, first_occurrence, last_occurrence, status, sent_at,
                       created_at
                FROM krai_system.alerts
                {where_clause}
                ORDER BY last_occurrence DESC
                LIMIT ${param_count + 1}
            """
            params.append(limit)

            alerts_data = await self.adapter.execute_query(query, params)
            alerts_data = alerts_data or []

            alerts = [
                Alert(
                    id=str(alert.get("id", "")),
                    alert_type=AlertType(alert.get("alert_type", "system_error")),
                    severity=AlertSeverity(alert.get("severity", "medium")),
                    title=alert.get("aggregation_key", ""),
                    message=alert.get("message", ""),
                    metadata={
                        "details": alert.get("details", {}),
                        "aggregation_key": alert.get("aggregation_key"),
                        "aggregation_count": alert.get("aggregation_count", 1),
                        "first_occurrence": alert.get("first_occurrence"),
                        "last_occurrence": alert.get("last_occurrence"),
                        "status": alert.get("status"),
                    },
                    triggered_at=(
                        alert["created_at"]
                        if isinstance(alert.get("created_at"), datetime)
                        else (
                            datetime.fromisoformat(alert["created_at"].replace("Z", "+00:00"))
                            if alert.get("created_at")
                            else datetime.utcnow()
                        )
                    ),
                    acknowledged=alert.get("status") == "sent",
                    acknowledged_at=(
                        alert["sent_at"]
                        if isinstance(alert.get("sent_at"), datetime)
                        else (
                            datetime.fromisoformat(alert["sent_at"].replace("Z", "+00:00"))
                            if alert.get("sent_at")
                            else None
                        )
                    ),
                    acknowledged_by=None,
                )
                for alert in alerts_data
            ]

            # Count pending alerts
            pending_query = "SELECT COUNT(*) as count FROM krai_system.alerts WHERE status = 'pending'"
            pending_result = await self.adapter.execute_query(pending_query)
            unacknowledged_count = pending_result[0].get("count", 0) if pending_result else 0

            return AlertListResponse(
                alerts=alerts,
                total=len(alerts),
                unacknowledged_count=unacknowledged_count,
            )

        except Exception as e:
            self.logger.error(f"Failed to get alerts: {e}", exc_info=True)
            return AlertListResponse(alerts=[], total=0, unacknowledged_count=0)

    async def acknowledge_alert(self, alert_id: str, user_id: str) -> bool:
        """Acknowledge an alert (mark as sent)."""
        try:
            query = """
                UPDATE krai_system.alerts
                SET status = 'sent', sent_at = CURRENT_TIMESTAMP
                WHERE id = $1
            """

            result = await self.adapter.execute_query(query, [alert_id])

            if result and hasattr(result, "rowcount") and result.rowcount > 0:
                self.logger.info(f"Acknowledged alert: {alert_id} by user {user_id}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to acknowledge alert: {e}", exc_info=True)
            return False

    async def dismiss_alert(self, alert_id: str) -> bool:
        """Dismiss (delete) an alert from queue."""
        try:
            query = "DELETE FROM krai_system.alerts WHERE id = $1"
            result = await self.adapter.execute_query(query, [alert_id])

            if result and hasattr(result, "rowcount") and result.rowcount > 0:
                self.logger.info(f"Dismissed alert: {alert_id}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Failed to dismiss alert: {e}", exc_info=True)
            return False

    async def notify_alert(self, alert: Alert) -> None:
        """Notify about alert (placeholder for external notifications)."""
        # Log alert
        self.logger.warning(f"ALERT TRIGGERED: [{alert.severity.value.upper()}] {alert.title} - {alert.message}")

        # Broadcast over WebSocket
        try:
            from api.websocket import broadcast_alert

            await broadcast_alert(alert)
        except Exception as e:
            self.logger.error(f"Failed to broadcast alert via WebSocket: {e}")

    async def alert_aggregation_worker(self, interval_seconds: int = 60) -> None:
        """Background worker for alert aggregation and notification dispatch.

        Runs every interval_seconds (default 60s), queries pending alerts older than
        the aggregation window (5 minutes default), groups by aggregation_key, checks
        thresholds, dispatches notifications via email/Slack, marks alerts as sent,
        and cleans up old alerts (7+ days).

        Args:
            interval_seconds: Interval between worker iterations (default: 60)
        """
        self.logger.info(f"Starting alert aggregation worker (interval: {interval_seconds}s)")

        cleanup_counter = 0

        try:
            while True:
                # Sleep at start to allow other startup tasks to complete
                await asyncio.sleep(interval_seconds)

                try:
                    # Query pending alerts ready to be sent (older than 5 minutes)
                    query = """
                        SELECT aggregation_key, alert_type, severity,
                               COUNT(*) as alert_count,
                               MIN(first_occurrence) as first_occurrence,
                               MAX(last_occurrence) as last_occurrence,
                               (ARRAY_AGG(message ORDER BY last_occurrence DESC NULLS LAST, created_at DESC))[1] as message,
                               (ARRAY_AGG(details ORDER BY last_occurrence DESC NULLS LAST, created_at DESC))[1] as details,
                               ARRAY_AGG(id) as alert_ids
                        FROM krai_system.alerts
                        WHERE status = 'pending'
                          AND created_at <= NOW() - INTERVAL '5 minutes'
                        GROUP BY aggregation_key, alert_type, severity
                    """

                    pending_alerts = await self.adapter.execute_query(query)

                    if not pending_alerts or len(pending_alerts) == 0:
                        self.logger.debug("No pending alerts ready to send")
                    else:
                        self.logger.info(f"Processing {len(pending_alerts)} alert groups")

                        # Get alert configurations (cached)
                        alert_rules = await self._get_alert_rules()

                        if not alert_rules:
                            self.logger.warning("No alert rules configured, skipping alert processing")
                        else:
                            # Process each aggregated alert group
                            for alert_group in pending_alerts:
                                aggregation_key = alert_group.get("aggregation_key")
                                alert_count = alert_group.get("alert_count", 0)
                                alert_ids = alert_group.get("alert_ids", [])

                                # Find matching rule by extracting rule_name from aggregation_key and exact match
                                # aggregation_key format: "rule_name:error_type:stage_name"
                                matching_rule = None
                                extracted_rule_name = (
                                    aggregation_key.split(":", 1)[0] if ":" in aggregation_key else aggregation_key
                                )
                                for rule in alert_rules:
                                    rule_name = rule.get("rule_name", "")
                                    if rule_name and rule_name == extracted_rule_name:
                                        matching_rule = rule
                                        break

                                if not matching_rule:
                                    self.logger.warning(f"No matching rule for aggregation_key {aggregation_key}")
                                    continue

                                # Check threshold before sending
                                error_count_threshold = matching_rule.get("error_count_threshold", 1)
                                if alert_count < error_count_threshold:
                                    self.logger.info(
                                        f"Alert {aggregation_key} count {alert_count} below threshold {error_count_threshold}"
                                    )
                                    continue

                                # Prepare alert data for sending
                                alert_data = {
                                    "id": alert_ids[0] if alert_ids else None,
                                    "alert_type": alert_group.get("alert_type"),
                                    "severity": alert_group.get("severity"),
                                    "message": alert_group.get("message"),
                                    "details": alert_group.get("details", {}),
                                    "aggregation_key": aggregation_key,
                                    "aggregation_count": alert_count,
                                    "first_occurrence": alert_group.get("first_occurrence"),
                                    "last_occurrence": alert_group.get("last_occurrence"),
                                }

                                # Dispatch to email and Slack
                                notification_success = await self.send_aggregated_alert(alert_data, matching_rule)

                                if notification_success:
                                    # Mark alerts as sent
                                    update_query = """
                                        UPDATE krai_system.alerts
                                        SET status = 'sent', sent_at = CURRENT_TIMESTAMP
                                        WHERE id = ANY($1)
                                    """
                                    await self.adapter.execute_query(update_query, [alert_ids])
                                    self.logger.info(f"Marked {len(alert_ids)} alerts as sent for {aggregation_key}")
                                    self.logger.info(
                                        f"Sent aggregated alert for {aggregation_key}: {alert_count} occurrences"
                                    )
                                else:
                                    self.logger.error(f"Failed to send alert for {aggregation_key}")

                    # Cleanup old alerts every 10th iteration (600 seconds)
                    cleanup_counter += 1
                    if cleanup_counter >= 10:
                        cleanup_counter = 0
                        self.logger.info("Cleaning up alerts older than 7 days")

                        cleanup_query = """
                            DELETE FROM krai_system.alerts
                            WHERE created_at < NOW() - INTERVAL '7 days'
                        """

                        try:
                            result = await self.adapter.execute_query(cleanup_query)
                            # Log cleanup result if rowcount is available
                            if result and hasattr(result, "rowcount"):
                                self.logger.info(f"Deleted {result.rowcount} old alerts")
                            else:
                                self.logger.info("Cleanup completed")
                        except Exception as cleanup_error:
                            self.logger.error(f"Failed to cleanup old alerts: {cleanup_error}", exc_info=True)

                except Exception as e:
                    # Log error but continue running
                    self.logger.error(f"Error in alert aggregation worker iteration: {e}", exc_info=True)

        except asyncio.CancelledError:
            # Graceful shutdown
            self.logger.info("Alert aggregation worker stopped")
        except Exception as e:
            self.logger.error(f"Fatal error in alert aggregation worker: {e}", exc_info=True)

    async def send_aggregated_alert(self, alert_data: dict[str, Any], rule_config: dict[str, Any]) -> bool:
        """Send aggregated alert via email and Slack.

        Args:
            alert_data: Dictionary containing alert information from aggregated query
            rule_config: Alert configuration from alert_configurations table

        Returns:
            True if at least one notification channel succeeds, False if all fail
        """
        aggregation_key = alert_data.get("aggregation_key", "unknown")
        email_success = False
        slack_success = False

        # Check if any notification channels are configured
        email_recipients = rule_config.get("email_recipients")
        slack_webhooks = rule_config.get("slack_webhooks")
        has_email = email_recipients and len(email_recipients) > 0
        has_slack = slack_webhooks and len(slack_webhooks) > 0

        # If no channels configured, log once and return True to mark as sent (prevent infinite retries)
        if not has_email and not has_slack:
            self.logger.warning(
                f"No notification channels configured for {aggregation_key} - "
                f"marking as sent to prevent infinite retries"
            )
            return True

        # Email notification
        if has_email:
            try:
                email_success = await self.send_email_alert(alert_data, email_recipients, rule_config)
                status = "sent" if email_success else "failed"
                self.logger.info(f"Email notification {status} for {aggregation_key}")
            except Exception as e:
                self.logger.error(f"Email notification failed for {aggregation_key}: {e}", exc_info=True)

        # Slack notification
        if has_slack:
            try:
                slack_success = await self.send_slack_alert(alert_data, slack_webhooks, rule_config)
                status = "sent" if slack_success else "failed"
                self.logger.info(f"Slack notification {status} for {aggregation_key}")
            except Exception as e:
                self.logger.error(f"Slack notification failed for {aggregation_key}: {e}", exc_info=True)

        # Return success if at least one channel succeeded
        if email_success or slack_success:
            return True
        self.logger.warning(f"All notification channels failed for {aggregation_key}")
        return False

    async def start_alert_monitoring(self, interval_seconds: int = 60) -> None:
        """Start background alert monitoring.

        Loads alert configurations and starts the alert aggregation worker.

        Args:
            interval_seconds: Interval for aggregation worker (default: 60)
        """
        # Load configurations on startup
        await self.load_alert_configurations()

        # Start the aggregation worker
        asyncio.create_task(self.alert_aggregation_worker(interval_seconds))

        self.logger.info("Alert monitoring started: configurations loaded, aggregation worker running")

    async def start_background_workers(self):
        """Start background alert processing workers."""
        if not self._background_tasks or self._background_tasks.done():
            self._background_tasks = asyncio.create_task(self.alert_aggregation_worker())
            self.logger.info("Alert aggregation worker started")
