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


def get_report_recipients():
    raw = os.environ.get('REPORT_RECIPIENTS', 'dylan.dias@payufin.com')
    return [e.strip() for e in raw.split(',') if e.strip()]


def get_email_provider():
    explicit = os.environ.get('EMAIL_PROVIDER', '').strip().lower()
    if explicit:
        return explicit
    if os.environ.get('SENDGRID_API_KEY'):
        return 'sendgrid'
    if os.environ.get('RESEND_API_KEY'):
        return 'resend'
    if os.environ.get('SMTP_USER') and os.environ.get('SMTP_PASSWORD'):
        return 'smtp'
    return None


def email_configured():
    return get_email_provider() is not None


def email_setup_hint():
    provider = get_email_provider()
    if provider == 'sendgrid':
        return 'SendGrid API is configured.'
    if provider == 'resend':
        return 'Resend API is configured.'
    if provider == 'smtp':
        return 'SMTP is configured.'
    return (
        'Set one option in Render → Environment: '
        'SENDGRID_API_KEY, RESEND_API_KEY, or SMTP_USER + SMTP_PASSWORD.'
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
                    ax.bar(_trace_values(trace.x), _trace_values(trace.y), label=name, color=_trace_color(trace, '#818CF8'))
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
            plt.xticks(rotation=25, ha='right', fontsize=8)

    buf = io.BytesIO()
    fig_mpl.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
    plt.close(fig_mpl)
    return buf.getvalue()


def fig_to_png(fig, width=880, height=360):
    try:
        return fig.to_image(format='png', width=width, height=height, engine='kaleido')
    except Exception:
        return fig_to_png_matplotlib(fig, width=width, height=height)


def build_pdf_report(summary, charts, filters=None):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(0, 10, 'Gnani Dashboard Report', ln=True)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, f"Generated: {summary.get('generated_at', datetime.now().strftime('%b %d, %Y %H:%M'))}", ln=True)
    pdf.ln(4)
    pdf.set_text_color(15, 23, 42)

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, 'Summary', ln=True)
    pdf.set_font('Helvetica', '', 11)
    for label, value in summary.get('metrics', []):
        pdf.cell(0, 7, f'{label}: {value}', ln=True)

    if filters:
        pdf.ln(2)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Filters Applied', ln=True)
        pdf.set_font('Helvetica', '', 10)
        for label, value in filters.items():
            pdf.cell(0, 6, f'{label}: {value}', ln=True)

    for title, png_bytes in charts:
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 13)
        pdf.cell(0, 8, title, ln=True)
        pdf.ln(2)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(png_bytes)
            tmp_path = tmp.name
        try:
            pdf.image(tmp_path, w=190)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

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


def send_via_sendgrid(pdf_bytes, recipients, subject, body):
    api_key = os.environ['SENDGRID_API_KEY']
    sender = os.environ.get('EMAIL_FROM', os.environ.get('SMTP_FROM', 'noreply@payufin.com'))

    payload = {
        'personalizations': [{'to': [{'email': email} for email in recipients]}],
        'from': {'email': sender},
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
    if response.status_code >= 400:
        raise RuntimeError(f'SendGrid error ({response.status_code}): {response.text[:300]}')


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


def send_report_email(pdf_bytes, subject=None, body=None):
    provider = get_email_provider()
    if not provider:
        raise RuntimeError(email_setup_hint())

    recipients = get_report_recipients()
    if not recipients:
        raise RuntimeError('No report recipients configured.')

    subject = subject or _default_subject()
    body = body or _default_body()

    if provider == 'sendgrid':
        send_via_sendgrid(pdf_bytes, recipients, subject, body)
    elif provider == 'resend':
        send_via_resend(pdf_bytes, recipients, subject, body)
    else:
        send_via_smtp(pdf_bytes, recipients, subject, body)

    return recipients
