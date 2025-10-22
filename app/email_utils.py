from __future__ import annotations

from flask import current_app


def _parse_recipients(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return []
    recipients: list[dict[str, str]] = []
    for item in raw.split(","):
        email = item.strip()
        if email:
            recipients.append({"email": email})
    return recipients


def send_shipment_notification(shipment) -> tuple[bool, str | None]:
    """Send a shipment notification email via Brevo.

    Returns a tuple of (success, message). When sending fails the message contains
    a human readable reason that can be shown to the user.
    """

    app = current_app

    api_key = app.config.get("BREVO_API_KEY")
    sender_email = app.config.get("BREVO_SENDER_EMAIL")
    sender_name = app.config.get("BREVO_SENDER_NAME") or "Shipment Planner"
    recipient_config = app.config.get("BREVO_RECIPIENTS")

    recipients = _parse_recipients(recipient_config)

    if not api_key or not sender_email or not recipients:
        app.logger.info(
            "Skipping Brevo email send. Configured? api=%s sender=%s recipients=%s",
            bool(api_key),
            bool(sender_email),
            len(recipients),
        )
        return False, "Email settings are incomplete. Configure Brevo to send notifications."

    try:
        import sib_api_v3_sdk
        from sib_api_v3_sdk.rest import ApiException
    except ImportError:  # pragma: no cover - dependency should be installed in deployment
        app.logger.exception("sib_api_v3_sdk is not available")
        return False, "Brevo SDK is not installed on the server."

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = api_key
    api_client = sib_api_v3_sdk.ApiClient(configuration)
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(api_client)

    origin = shipment.origin
    destination = shipment.destination

    subject = f"New Shipment Created: {shipment.order_number}"

    def format_company(company) -> str:
        address = getattr(company, "formatted_address", None)
        if address:
            return f"{company.name} ({address})"
        return company.name

    html_content = f"""
        <h1>New Shipment Created</h1>
        <p>A shipment was created on {shipment.created_at.strftime('%Y-%m-%d %H:%M UTC')}.</p>
        <table style="border-collapse: collapse;">
          <tbody>
            <tr><th align="left" style="padding:4px 8px;">Origin</th><td style="padding:4px 8px;">{format_company(origin)}</td></tr>
            <tr><th align="left" style="padding:4px 8px;">Destination</th><td style="padding:4px 8px;">{format_company(destination)}</td></tr>
            <tr><th align="left" style="padding:4px 8px;">PO Number</th><td style="padding:4px 8px;">{shipment.po_number}</td></tr>
            <tr><th align="left" style="padding:4px 8px;">SAP Number</th><td style="padding:4px 8px;">{shipment.sap_number}</td></tr>
            <tr><th align="left" style="padding:4px 8px;">Order Number</th><td style="padding:4px 8px;">{shipment.order_number}</td></tr>
            <tr><th align="left" style="padding:4px 8px;">Order Date</th><td style="padding:4px 8px;">{shipment.order_date.strftime('%Y-%m-%d')}</td></tr>
            <tr><th align="left" style="padding:4px 8px;">Price</th><td style="padding:4px 8px;">{shipment.price:.2f}</td></tr>
            <tr><th align="left" style="padding:4px 8px;">Weight</th><td style="padding:4px 8px;">{shipment.weight:.2f}</td></tr>
            <tr><th align="left" style="padding:4px 8px;">Time Slot</th><td style="padding:4px 8px;">{shipment.time_slot}</td></tr>
          </tbody>
        </table>
    """

    text_content = (
        "New shipment created\n"
        f"Origin: {format_company(origin)}\n"
        f"Destination: {format_company(destination)}\n"
        f"PO Number: {shipment.po_number}\n"
        f"SAP Number: {shipment.sap_number}\n"
        f"Order Number: {shipment.order_number}\n"
        f"Order Date: {shipment.order_date.strftime('%Y-%m-%d')}\n"
        f"Price: {shipment.price:.2f}\n"
        f"Weight: {shipment.weight:.2f}\n"
        f"Time Slot: {shipment.time_slot}\n"
    )

    email = sib_api_v3_sdk.SendSmtpEmail(
        sender={"email": sender_email, "name": sender_name},
        to=recipients,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )

    try:
        api_instance.send_transac_email(email)
    except ApiException:  # pragma: no cover - depends on external API
        app.logger.exception("Failed to send shipment email via Brevo")
        return False, "Brevo rejected the email request. Check logs for details."
    except Exception:  # pragma: no cover - defensive safeguard for networking issues
        app.logger.exception("Unexpected error while sending email via Brevo")
        return False, "An unexpected error occurred while sending the Brevo email."

    app.logger.info("Shipment notification email sent via Brevo for shipment %s", shipment.id)
    return True, None
