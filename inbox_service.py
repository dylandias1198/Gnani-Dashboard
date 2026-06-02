import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from email import message_from_bytes
from email.header import decode_header
from imaplib import IMAP4_SSL
from urllib.parse import quote

import requests

from data_io import is_supported_attachment, load_dataframe_from_bytes
from graph_service import graph_headers, graph_token, today_received_bounds_utc


@dataclass
class InboxAttachment:
    message_id: str
    subject: str
    sender: str
    received_at: str
    filename: str
    content: bytes


def _processed_ids_path():
    return os.environ.get('PROCESSED_IDS_PATH', 'data/processed_message_ids.json')


def load_processed_ids():
    path = _processed_ids_path()
    if not os.path.exists(path):
        return set()
    try:
        with open(path, encoding='utf-8') as handle:
            return set(json.load(handle))
    except (json.JSONDecodeError, OSError):
        return set()


def save_processed_ids(ids):
    path = _processed_ids_path()
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(sorted(ids), handle, indent=2)


def mark_processed(message_id, processed_ids):
    processed_ids.add(message_id)
    save_processed_ids(processed_ids)


def _env_list(name, default=''):
    raw = os.environ.get(name, default)
    return [item.strip().lower() for item in raw.split(',') if item.strip()]


def sender_matches(from_address, allowed_senders):
    from_address = (from_address or '').strip().lower()
    for sender in allowed_senders:
        sender = sender.strip().lower()
        if from_address == sender:
            return True
        if sender in from_address:
            return True
    return False


def _graph_token():
    return graph_token()


def _graph_headers(token):
    return graph_headers(token)


def fetch_inbox_attachments_graph():
    from graph_service import mailbox_user

    mailbox = mailbox_user()
    allowed_senders = _env_list('MAIL_SENDER_FILTER')
    if not allowed_senders:
        raise RuntimeError('Set MAIL_SENDER_FILTER to the sender email address to watch.')

    only_unread = os.environ.get('INBOX_ONLY_UNREAD', 'true').lower() != 'false'
    today_only = os.environ.get('INBOX_TODAY_ONLY', 'true').lower() != 'false'
    max_messages = int(os.environ.get('INBOX_MAX_MESSAGES', '20'))
    processed_ids = load_processed_ids()
    token = graph_token()
    headers = graph_headers(token)

    filters = [f"from/emailAddress/address eq '{allowed_senders[0]}'"]
    if only_unread:
        filters.append('isRead eq false')
    if today_only:
        start_utc, end_utc, _day_label = today_received_bounds_utc()
        filters.append(f"receivedDateTime ge {start_utc}")
        filters.append(f"receivedDateTime lt {end_utc}")
    filter_query = ' and '.join(filters)
    url = (
        f"https://graph.microsoft.com/v1.0/users/{quote(mailbox)}/mailFolders/inbox/messages"
        f"?$filter={quote(filter_query)}&$top={max_messages}"
        f"&$select=id,subject,from,receivedDateTime,hasAttachments,isRead"
        f"&$orderby=receivedDateTime desc"
    )
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(f'Graph inbox error ({response.status_code}): {response.text[:300]}')

    results = []
    for message in response.json().get('value', []):
        message_id = message['id']
        if message_id in processed_ids:
            continue
        sender = message.get('from', {}).get('emailAddress', {}).get('address', '')
        if not sender_matches(sender, allowed_senders):
            continue
        if not message.get('hasAttachments'):
            continue

        attach_url = (
            f"https://graph.microsoft.com/v1.0/users/{quote(mailbox)}"
            f"/messages/{quote(message_id)}/attachments"
        )
        attach_resp = requests.get(attach_url, headers=headers, timeout=30)
        if attach_resp.status_code >= 400:
            continue

        message_had_file = False
        for attachment in attach_resp.json().get('value', []):
            if attachment.get('@odata.type') != '#microsoft.graph.fileAttachment':
                continue
            filename = attachment.get('name', '')
            if not is_supported_attachment(filename):
                continue
            content = attachment.get('contentBytes')
            if content is None:
                continue
            file_bytes = base64.b64decode(content)
            results.append(InboxAttachment(
                message_id=message_id,
                subject=message.get('subject', ''),
                sender=sender,
                received_at=message.get('receivedDateTime', ''),
                filename=filename,
                content=file_bytes,
            ))
            message_had_file = True

        if message_had_file:
            if os.environ.get('MARK_PROCESSED', 'true').lower() != 'false':
                patch_url = (
                    f"https://graph.microsoft.com/v1.0/users/{quote(mailbox)}"
                    f"/messages/{quote(message_id)}"
                )
                requests.patch(patch_url, headers=headers, json={'isRead': True}, timeout=30)
            mark_processed(message_id, processed_ids)

    return results


def _decode_mime_header(value):
    if not value:
        return ''
    parts = []
    for chunk, encoding in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(encoding or 'utf-8', errors='replace'))
        else:
            parts.append(chunk)
    return ''.join(parts)


def fetch_inbox_attachments_imap():
    host = os.environ.get('IMAP_HOST', 'outlook.office365.com')
    user = os.environ['IMAP_USER']
    password = os.environ['IMAP_PASSWORD']
    folder = os.environ.get('IMAP_FOLDER', 'INBOX')
    allowed_senders = _env_list('MAIL_SENDER_FILTER')
    if not allowed_senders:
        raise RuntimeError('Set MAIL_SENDER_FILTER to the sender email address to watch.')

    only_unread = os.environ.get('INBOX_ONLY_UNREAD', 'true').lower() != 'false'
    processed_ids = load_processed_ids()
    results = []

    with IMAP4_SSL(host) as client:
        client.login(user, password)
        client.select(folder)
        for sender in allowed_senders:
            criteria = f'(FROM "{sender}"'
            if only_unread:
                criteria += ' UNSEEN'
            criteria += ')'
            status, data = client.search(None, criteria)
            if status != 'OK':
                continue
            for num in data[0].split():
                status, msg_data = client.fetch(num, '(RFC822)')
                if status != 'OK':
                    continue
                raw = msg_data[0][1]
                msg = message_from_bytes(raw)
                message_id = msg.get('Message-ID', num.decode())
                if message_id in processed_ids:
                    continue
                sender_addr = _decode_mime_header(msg.get('From', ''))
                subject = _decode_mime_header(msg.get('Subject', ''))
                received_at = msg.get('Date', '')

                found_attachment = False
                for part in msg.walk():
                    if part.get_content_disposition() != 'attachment':
                        continue
                    filename = part.get_filename()
                    if filename:
                        filename = _decode_mime_header(filename)
                    if not filename or not is_supported_attachment(filename):
                        continue
                    file_bytes = part.get_payload(decode=True) or b''
                    results.append(InboxAttachment(
                        message_id=message_id,
                        subject=subject,
                        sender=sender_addr,
                        received_at=received_at,
                        filename=filename,
                        content=file_bytes,
                    ))
                    found_attachment = True

                if found_attachment:
                    mark_processed(message_id, processed_ids)
                    if os.environ.get('MARK_PROCESSED', 'true').lower() != 'false':
                        client.store(num, '+FLAGS', '\\Seen')

    return results


def fetch_inbox_attachments():
    provider = os.environ.get('INBOX_PROVIDER', 'graph').strip().lower()
    if provider == 'graph' or os.environ.get('AZURE_TENANT_ID'):
        return fetch_inbox_attachments_graph()
    if provider == 'imap':
        return fetch_inbox_attachments_imap()
    raise RuntimeError('Set INBOX_PROVIDER=graph with Azure credentials (recommended).')


def attachments_to_dataframe(attachments):
    import pandas as pd
    frames = []
    for item in attachments:
        frames.append(load_dataframe_from_bytes(item.content, item.filename))
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)
