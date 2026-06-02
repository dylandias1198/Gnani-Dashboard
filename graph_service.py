"""Microsoft Graph: token, mailbox helpers, and send mail."""
import base64
import os
from datetime import datetime, time, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests


def mailbox_user():
    user = os.environ.get('MAILBOX_USER', os.environ.get('EMAIL_FROM', '')).strip()
    if '<' in user and user.endswith('>'):
        user = user.rsplit('<', 1)[1].rstrip('>').strip()
    if not user:
        raise RuntimeError('Set MAILBOX_USER to the mailbox used for inbox and sending.')
    return user


def graph_token():
    tenant = os.environ['AZURE_TENANT_ID']
    client_id = os.environ['AZURE_CLIENT_ID']
    client_secret = os.environ['AZURE_CLIENT_SECRET']
    response = requests.post(
        f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token',
        data={
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'https://graph.microsoft.com/.default',
            'grant_type': 'client_credentials',
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f'Azure token error ({response.status_code}): {response.text[:300]}')
    return response.json()['access_token']


def graph_headers(token=None):
    token = token or graph_token()
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def mailbox_timezone():
    return os.environ.get('MAILBOX_TIMEZONE', os.environ.get('SCHEDULE_TIMEZONE', 'Asia/Kolkata'))


def today_received_bounds_utc():
    """Start/end of 'today' in mailbox timezone, as UTC ISO strings for Graph filters."""
    tz = ZoneInfo(mailbox_timezone())
    now_local = datetime.now(tz)
    start_local = datetime.combine(now_local.date(), time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    fmt = '%Y-%m-%dT%H:%M:%SZ'
    return start_utc.strftime(fmt), end_utc.strftime(fmt), now_local.strftime('%d %b %Y')


def send_graph_mail(recipients, subject, body, attachments=None, save_to_sent=True):
    """
    Send email via Graph application permission (Mail.Send).
    attachments: list of dicts with keys name, content_bytes, content_type
    """
    mailbox = mailbox_user()
    token = graph_token()
    headers = graph_headers(token)

    to_recipients = [{'emailAddress': {'address': addr}} for addr in recipients]
    message = {
        'subject': subject,
        'body': {'contentType': 'Text', 'content': body},
        'toRecipients': to_recipients,
    }
    if attachments:
        message['attachments'] = []
        for item in attachments:
            message['attachments'].append({
                '@odata.type': '#microsoft.graph.fileAttachment',
                'name': item['name'],
                'contentType': item.get('content_type', 'application/octet-stream'),
                'contentBytes': base64.b64encode(item['content_bytes']).decode('ascii'),
            })

    url = f'https://graph.microsoft.com/v1.0/users/{quote(mailbox)}/sendMail'
    payload = {'message': message, 'saveToSentItems': save_to_sent}
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if response.status_code >= 400:
        raise RuntimeError(f'Graph sendMail error ({response.status_code}): {response.text[:400]}')
    return {'provider': 'graph', 'recipients': recipients, 'message_id': ''}
