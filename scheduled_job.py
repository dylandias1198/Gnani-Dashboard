#!/usr/bin/env python3
"""
Scheduled pipeline (Microsoft Graph only):
  1. At cron time, check inbox for TODAY's mail from MAIL_SENDER_FILTER with Excel/CSV
  2. If found: load data, generate PDF, email REPORT_RECIPIENTS via Graph
  3. If not found: email recipients "No data found" for today

Run:
  python scheduled_job.py

Dry run (no email):
  SCHEDULE_DRY_RUN=true python scheduled_job.py
"""
import os
import sys
from datetime import datetime

from dashboard import add_date_column, generate_report_pdf
from graph_service import mailbox_timezone, today_received_bounds_utc
from inbox_service import attachments_to_dataframe, fetch_inbox_attachments
from report_service import send_no_data_email, send_report_email


def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] {message}', flush=True)


def _require_graph_config():
    required = ['AZURE_TENANT_ID', 'AZURE_CLIENT_ID', 'AZURE_CLIENT_SECRET', 'MAILBOX_USER', 'MAIL_SENDER_FILTER']
    missing = [name for name in required if not os.environ.get(name, '').strip()]
    if missing:
        raise RuntimeError(f'Missing env vars for Azure Graph: {", ".join(missing)}')
    provider = os.environ.get('EMAIL_PROVIDER', 'graph').strip().lower()
    if provider not in ('', 'graph'):
        raise RuntimeError('Scheduled job requires EMAIL_PROVIDER=graph (Azure only).')


def run_scheduled_report():
    _require_graph_config()
    _, _, day_label = today_received_bounds_utc()
    tz = mailbox_timezone()
    log(f'Starting scheduled Gnani report ({day_label}, {tz})')

    attachments = fetch_inbox_attachments()
    dry_run = os.environ.get('SCHEDULE_DRY_RUN', 'false').lower() == 'true'

    if not attachments:
        log(f'No data found — no mail from sender with attachment received today ({day_label}).')
        if dry_run:
            log('Dry run — would send "No data found" email; skipping send')
            return 0
        result = send_no_data_email()
        log(f'No-data notification sent via {result["provider"]} to {", ".join(result["recipients"])}')
        return 0

    log(f'Found {len(attachments)} attachment(s): {", ".join(a.filename for a in attachments)}')

    df = attachments_to_dataframe(attachments)
    if df is None or df.empty:
        log('Attachment had no rows — sending no-data notification.')
        if not dry_run:
            send_no_data_email()
        return 0

    df = add_date_column(df)
    log(f'Loaded {len(df):,} rows from inbox file(s)')

    records = df.to_dict('records')
    status = os.environ.get('REPORT_STATUS_FILTER', 'ALL')
    time_grp = os.environ.get('REPORT_TIME_GROUPING', 'daily')

    pdf_bytes, filename = generate_report_pdf(
        records,
        status,
        time_grp,
        start_date=None,
        end_date=None,
        use_full_data_range=True,
    )
    log(f'Generated PDF: {filename} ({len(pdf_bytes):,} bytes)')

    if dry_run:
        out_path = os.environ.get('DRY_RUN_OUTPUT', filename)
        with open(out_path, 'wb') as handle:
            handle.write(pdf_bytes)
        log(f'Dry run — saved {out_path}, email not sent')
        return 0

    result = send_report_email(pdf_bytes)
    log(f'Report sent via {result["provider"]} to {", ".join(result["recipients"])}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(run_scheduled_report())
    except Exception as exc:
        log(f'FAILED: {exc}')
        sys.exit(1)
