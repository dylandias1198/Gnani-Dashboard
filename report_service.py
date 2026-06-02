import base64
import io
import os
import smtplib
import tempfile
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from graph_service import send_graph_mail


def get_report_recipients():
    raw = os.environ.get('REPORT_RECIPIENTS', 'dylan.dias@payufin.com')
    return [e.strip() for e in raw.split(',') if e.strip()]


def get_email_provider():
    explicit = os.environ.get('EMAIL_PROVIDER', '').strip().lower()
    if explicit:
        return explicit
    if (
        os.environ.get('AZURE_TENANT_ID', '').strip()
        and os.environ.get('AZURE_CLIENT_SECRET', '').strip()
    ):
        return 'graph'
    if os.environ.get('SENDGRID_API_KEY', '').strip():
        return 'sendgrid'
    if os.environ.get('RESEND_API_KEY', '').strip():
        return 'resend'
    if os.environ.get('SMTP_USER', '').strip() and os.environ.get('SMTP_PASSWORD', '').strip():
        return 'smtp'
    return None


def email_configured():
    provider = get_email_provider()
    if provider == 'graph':
        return bool(
            os.environ.get('AZURE_TENANT_ID', '').strip()
            and os.environ.get('AZURE_CLIENT_SECRET', '').strip()
            and os.environ.get('AZURE_CLIENT_ID', '').strip()
            and (
                os.environ.get('MAILBOX_USER', '').strip()
                or os.environ.get('EMAIL_FROM', '').strip()
            )
        )
    if provider == 'sendgrid':
        return bool(os.environ.get('SENDGRID_API_KEY', '').strip())
    if provider == 'resend':
        return bool(os.environ.get('RESEND_API_KEY', '').strip())
    if provider == 'smtp':
        return bool(os.environ.get('SMTP_USER', '').strip() and os.environ.get('SMTP_PASSWORD', '').strip())
    return False


def email_setup_hint():
    provider = get_email_provider()
    if provider == 'graph':
        return 'Using Microsoft Graph (Mail.Send). Set AZURE_* and MAILBOX_USER.'
    if provider == 'sendgrid':
        from_addr = os.environ.get('EMAIL_FROM', '').strip() or '(EMAIL_FROM not set)'
        return f'Using SendGrid. Sender: {from_addr}'
    if provider == 'resend':
        return 'Using Resend API.'
    if provider == 'smtp':
        return f"Using SMTP ({os.environ.get('SMTP_HOST', 'smtp.office365.com')}). SendGrid dashboard will show 0 requests."
    return (
        'Set Render env vars: SENDGRID_API_KEY + EMAIL_FROM + REPORT_RECIPIENTS. '
        'Optional: EMAIL_PROVIDER=sendgrid'
    )


def _trace_color(trace, default='#6366F1'):
    if trace.line and trace.line.color:
        return trace.line.color
    if trace.marker and trace.marker.color:
        return trace.marker.color
    return default


def _empty_figure_message(fig):
    if fig.layout.annotations:
        return str(fig.layout.annotations[0].text or 'No data available')
    return 'No data available'


def _trace_values(values):
    if values is None:
        return []
    return list(values)


def fig_to_png_matplotlib(fig, width=880, height=360):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    dpi = 100
    fig_mpl, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)

    if not fig.data:
        ax.text(0.5, 0.5, _empty_figure_message(fig), ha='center', va='center')
        ax.axis('off')
    else:
        pie_drawn = False
        for trace in fig.data:
            trace_type = trace.type
            name = trace.name or ''
            if trace_type == 'scatter':
                x_vals = _trace_values(trace.x)
                y_vals = _trace_values(trace.y)
                if not x_vals or not y_vals:
                    continue
                mode = trace.mode or 'lines'
                color = _trace_color(trace)
                if 'lines' in mode:
                    ax.plot(x_vals, y_vals, label=name, color=color, linewidth=2, marker='o', markersize=4)
                elif 'markers' in mode:
                    ax.plot(x_vals, y_vals, 'o', label=name, color=color)
                if trace.text:
                    for x_val, y_val, label in zip(_trace_values(trace.x), _trace_values(trace.y), _trace_values(trace.text)):
                        if label:
                            ax.annotate(str(label), (x_val, y_val), fontsize=7, ha='center', va='bottom')
            elif trace_type == 'bar':
                if getattr(trace, 'orientation', None) == 'h':
                    ax.barh(_trace_values(trace.y), _trace_values(trace.x), label=name, color=_trace_color(trace, '#818CF8'))
                else:
                    x_vals = _trace_values(trace.x)
                    y_vals = _trace_values(trace.y)
                    ax.bar(range(len(x_vals)), y_vals, label=name, color=_trace_color(trace, '#818CF8'))
                    tick_fs = 5 if max((len(str(x)) for x in x_vals), default=0) > 28 else 7
                    ax.set_xticks(range(len(x_vals)))
                    ax.set_xticklabels(x_vals, rotation=40, ha='right', fontsize=tick_fs)
            elif trace_type == 'pie' and not pie_drawn:
                labels = _trace_values(trace.labels)
                values = _trace_values(trace.values)
                if not values:
                    continue
                colors = trace.marker.colors if trace.marker and trace.marker.colors else None
                hole = trace.hole or 0
                wedgeprops = {'width': 1 - hole} if hole else None
                ax.pie(values, labels=labels, colors=colors, startangle=90, wedgeprops=wedgeprops)
                pie_drawn = True

        if not pie_drawn:
            x_title = fig.layout.xaxis.title.text if fig.layout.xaxis and fig.layout.xaxis.title else ''
            y_title = fig.layout.yaxis.title.text if fig.layout.yaxis and fig.layout.yaxis.title else ''
            if x_title:
                ax.set_xlabel(x_title)
            if y_title:
                ax.set_ylabel(y_title)
            if fig.layout.yaxis and fig.layout.yaxis.ticksuffix:
                ax.yaxis.set_major_formatter(
                    plt.FuncFormatter(lambda val, _: f'{val:.0f}{fig.layout.yaxis.ticksuffix}')
                )
            handles, labels = ax.get_legend_handles_labels()
            if labels:
                ax.legend(loc='best', fontsize=8)
            ax.grid(True, alpha=0.25)
            if not any(getattr(t, 'type', None) == 'bar' and getattr(t, 'orientation', None) != 'h' for t in fig.data):
                plt.xticks(rotation=25, ha='right', fontsize=8)

    buf = io.BytesIO()
    fig_mpl.savefig(buf, format='png', bbox_inches='tight', facecolor='white', pad_inches=0.15)
    plt.close(fig_mpl)
    return buf.getvalue()


def fig_to_png(fig, width=880, height=360):
    try:
        return fig.to_image(format='png', width=width, height=height, engine='kaleido')
    except Exception:
        return fig_to_png_matplotlib(fig, width=width, height=height)


# Bar charts with long category labels need full width + taller export in PDF.
PDF_FULL_WIDTH_CHARTS = frozenset({
    'SF Final Categories',
    'SF Final Problems',
    'Resolution Status',
    'Error Types',
})


def _pdf_compact_layout():
    """Layout tuning for multi-chart pages (mm). Override via env if needed."""
    margin = float(os.environ.get('PDF_MARGIN_MM', '8'))
    cols = int(os.environ.get('PDF_CHART_COLUMNS', '2'))
    col_w = float(os.environ.get('PDF_CHART_WIDTH_MM', '92'))
    max_col_h = float(os.environ.get('PDF_CHART_MAX_HEIGHT_MM', '52'))
    max_wide_h = float(os.environ.get('PDF_WIDE_CHART_MAX_HEIGHT_MM', '78'))
    title_h = float(os.environ.get('PDF_CHART_TITLE_MM', '4'))
    return margin, max(1, cols), col_w, max_col_h, max_wide_h, title_h


def _png_height_mm(png_bytes, width_mm, max_height_mm):
    """Preserve PNG aspect ratio so vertical bar charts are not squashed flat."""
    import struct
    if len(png_bytes) >= 24 and png_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        width_px = struct.unpack('>I', png_bytes[16:20])[0]
        height_px = struct.unpack('>I', png_bytes[20:24])[0]
        if width_px > 0 and height_px > 0:
            height_mm = width_mm * height_px / width_px
            return min(height_mm, max_height_mm)
    return min(width_mm * 0.45, max_height_mm)


def _write_pdf_chart_block(pdf, x, y, title, png_bytes, img_w, max_img_h, title_h):
    pdf.set_xy(x, y)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(img_w, title_h, title[:48], ln=0)
    img_h = _png_height_mm(png_bytes, img_w, max_img_h)
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp.write(png_bytes)
        tmp_path = tmp.name
    try:
        pdf.image(tmp_path, x=x, y=y + title_h, w=img_w, h=img_h)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return title_h + img_h


def _normalize_chart_entry(entry):
    if len(entry) == 3:
        title, png_bytes, meta = entry
        return title, png_bytes, meta or {}
    title, png_bytes = entry
    full_width = title in PDF_FULL_WIDTH_CHARTS
    return title, png_bytes, {'full_width': full_width}


def build_pdf_report(summary, charts, filters=None):
    from fpdf import FPDF

    margin, cols, col_img_w, max_col_h, max_wide_h, title_h = _pdf_compact_layout()
    col_gap = 4
    row_gap = 4
    page_bottom = 287

    pdf = FPDF()
    pdf.set_margins(margin, margin, margin)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, 'Gnani Dashboard Report', ln=True)
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 4, f"Generated: {summary.get('generated_at', datetime.now().strftime('%b %d, %Y %H:%M'))}", ln=True)
    pdf.ln(2)
    pdf.set_text_color(15, 23, 42)

    metrics = summary.get('metrics', [])
    if metrics:
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, 'Summary', ln=True)
        pdf.set_font('Helvetica', '', 8)
        half = (len(metrics) + 1) // 2
        left_x = margin
        right_x = margin + (pdf.w - 2 * margin) / 2
        y0 = pdf.get_y()
        for index, (label, value) in enumerate(metrics):
            x = left_x if index < half else right_x
            row = index if index < half else index - half
            pdf.set_xy(x, y0 + row * 4.5)
            pdf.cell(85, 4.5, f'{label}: {value}', ln=0)
        pdf.set_y(y0 + half * 4.5 + 2)

    if filters:
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(0, 5, 'Filters', ln=True)
        pdf.set_font('Helvetica', '', 7)
        filter_line = '  |  '.join(f'{label}: {value}' for label, value in filters.items())
        pdf.multi_cell(0, 3.5, filter_line)
        pdf.ln(1)

    usable_w = pdf.w - 2 * margin
    col_img_w = min(col_img_w, (usable_w - (cols - 1) * col_gap) / cols)
    x_cols = [margin + i * (col_img_w + col_gap) for i in range(cols)]
    row_y = pdf.get_y() + 2
    col_idx = 0
    row_block_h = 0

    def ensure_space(needed_h):
        nonlocal row_y, col_idx, row_block_h
        if row_y + needed_h > page_bottom:
            pdf.add_page()
            row_y = margin + 2
            col_idx = 0
            row_block_h = 0

    for entry in charts:
        title, png_bytes, meta = _normalize_chart_entry(entry)
        full_width = meta.get('full_width', title in PDF_FULL_WIDTH_CHARTS)

        if full_width:
            if col_idx != 0:
                row_y += row_block_h + row_gap
                col_idx = 0
                row_block_h = 0
            est_h = title_h + _png_height_mm(png_bytes, usable_w, max_wide_h)
            ensure_space(est_h)
            block_h = _write_pdf_chart_block(
                pdf, margin, row_y, title, png_bytes, usable_w, max_wide_h, title_h,
            )
            row_y += block_h + row_gap
            col_idx = 0
            row_block_h = 0
            continue

        est_h = title_h + _png_height_mm(png_bytes, col_img_w, max_col_h) + 2
        if col_idx == 0:
            ensure_space(est_h)
        x = x_cols[col_idx]
        block_h = _write_pdf_chart_block(
            pdf, x, row_y, title, png_bytes, col_img_w, max_col_h, title_h,
        )
        row_block_h = max(row_block_h, block_h)
        col_idx += 1
        if col_idx >= cols:
            row_y += row_block_h + row_gap
            col_idx = 0
            row_block_h = 0

    if col_idx != 0:
        row_y += row_block_h

    out = io.BytesIO()
    pdf.output(out)
    return out.getvalue()


def _pdf_attachment_name():
    return f"gnani-dashboard-report-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"


def _default_subject():
    return f"Gnani Dashboard Report — {datetime.now().strftime('%b %d, %Y')}"


def _default_body():
    return (
        'Please find the Gnani Dashboard report attached.\n\n'
        'This report reflects the current dashboard filters and uploaded data.'
    )


def send_via_smtp(pdf_bytes, recipients, subject, body):
    host = os.environ.get('SMTP_HOST', 'smtp.office365.com')
    port = int(os.environ.get('SMTP_PORT', '587'))
    user = os.environ['SMTP_USER']
    password = os.environ['SMTP_PASSWORD']
    sender = os.environ.get('SMTP_FROM', user)

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    attachment = MIMEApplication(pdf_bytes, _subtype='pdf')
    attachment.add_header('Content-Disposition', 'attachment', filename=_pdf_attachment_name())
    msg.attach(attachment)

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(sender, recipients, msg.as_string())


def _parse_email_address(value, default_name=None):
    value = (value or '').strip()
    if not value:
        raise RuntimeError('EMAIL_FROM is not configured.')
    if '<' in value and value.endswith('>'):
        name, email = value.rsplit('<', 1)
        return email.rstrip('>').strip(), name.strip().strip('"') or default_name
    return value, default_name


def send_via_sendgrid(pdf_bytes, recipients, subject, body):
    api_key = os.environ['SENDGRID_API_KEY']
    sender = os.environ.get('EMAIL_FROM', os.environ.get('SMTP_FROM', ''))
    email, name = _parse_email_address(sender, 'Gnani Dashboard')

    payload = {
        'personalizations': [{'to': [{'email': email_addr} for email_addr in recipients]}],
        'from': {'email': email, 'name': name},
        'reply_to': {'email': email, 'name': name},
        'subject': subject,
        'content': [{'type': 'text/plain', 'value': body}],
        'attachments': [{
            'content': base64.b64encode(pdf_bytes).decode(),
            'filename': _pdf_attachment_name(),
            'type': 'application/pdf',
            'disposition': 'attachment',
        }],
    }
    response = requests.post(
        'https://api.sendgrid.com/v3/mail/send',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json=payload,
        timeout=30,
    )
    print(
        f'[gnani-email] SendGrid status={response.status_code} '
        f'to={recipients} from={email} message_id={response.headers.get("X-Message-Id", "")}',
        flush=True,
    )
    if response.status_code >= 400:
        raise RuntimeError(f'SendGrid error ({response.status_code}): {response.text[:300]}')
    return response.headers.get('X-Message-Id', '')


def send_via_resend(pdf_bytes, recipients, subject, body):
    api_key = os.environ['RESEND_API_KEY']
    sender = os.environ.get('EMAIL_FROM', 'Gnani Dashboard <onboarding@resend.dev>')

    payload = {
        'from': sender,
        'to': recipients,
        'subject': subject,
        'text': body,
        'attachments': [{
            'filename': _pdf_attachment_name(),
            'content': base64.b64encode(pdf_bytes).decode(),
        }],
    }
    response = requests.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f'Resend error ({response.status_code}): {response.text[:300]}')


def send_via_graph(pdf_bytes, recipients, subject, body):
    attachments = [{
        'name': _pdf_attachment_name(),
        'content_bytes': pdf_bytes,
        'content_type': 'application/pdf',
    }]
    return send_graph_mail(recipients, subject, body, attachments=attachments)


def send_no_data_email():
    """Notify recipients when today's data email was not found in the inbox."""
    from graph_service import mailbox_timezone, today_received_bounds_utc

    _, _, day_label = today_received_bounds_utc()
    sender = os.environ.get('MAIL_SENDER_FILTER', 'the configured sender')
    tz = mailbox_timezone()
    subject = f'Gnani Dashboard — No data found ({day_label})'
    body = (
        f'No data file was found for today ({day_label}, timezone {tz}).\n\n'
        f'The scheduled job checked the inbox for mail from:\n  {sender}\n\n'
        'Expected: an Excel or CSV attachment received today.\n'
        'No report PDF is attached.\n'
    )
    recipients = get_report_recipients()
    if not recipients:
        raise RuntimeError('No report recipients configured.')
    return send_graph_mail(recipients, subject, body)


def send_report_email(pdf_bytes, subject=None, body=None):
    provider = get_email_provider()
    if not provider:
        raise RuntimeError(email_setup_hint())

    recipients = get_report_recipients()
    if not recipients:
        raise RuntimeError('No report recipients configured.')

    subject = subject or _default_subject()
    body = body or _default_body()
    message_id = ''

    if provider == 'graph':
        result = send_via_graph(pdf_bytes, recipients, subject, body)
        return {**result, 'message_id': message_id}
    if provider == 'sendgrid':
        message_id = send_via_sendgrid(pdf_bytes, recipients, subject, body)
    elif provider == 'resend':
        send_via_resend(pdf_bytes, recipients, subject, body)
    else:
        send_via_smtp(pdf_bytes, recipients, subject, body)

    return {
        'recipients': recipients,
        'provider': provider,
        'message_id': message_id,
    }
