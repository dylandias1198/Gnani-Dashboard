import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import base64
import io
import os

FONT = "Plus Jakarta Sans"
CHART_PALETTE = ['#6366F1', '#8B5CF6', '#06B6D4', '#10B981', '#F59E0B', '#EC4899']
STATUS_COLORS = {'SUCCESS': '#6366F1', 'FAILED': '#EC4899', 'PENDING': '#06B6D4'}
STATUS_LABELS = {'SUCCESS': 'Success', 'FAILED': 'Failed', 'PENDING': 'Pending'}
SF_HIERARCHY = {
    'problem': 'SF Final Problem',
    'detail': 'SF Final Detail',
    'subdetail': 'SF Final SubDetail',
}
GRAPH_CONFIG = {'displayModeBar': False, 'staticPlot': False}


def count_pct_label(count, total, decimals=0):
    if total <= 0:
        return f'{int(count):,} (0%)'
    pct = count / total * 100
    fmt = f'.{decimals}f' if decimals else '.0f'
    return f'{int(count):,} ({pct:{fmt}}%)'

app = Dash(__name__, external_stylesheets=[
    dbc.themes.BOOTSTRAP,
    "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"
])

app.title = "Gnani Dashboard"


def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        return df, filename, None
    except Exception as e:
        return None, filename, str(e)


def base_layout(**kwargs):
    defaults = dict(
        height=320,
        margin=dict(l=24, r=24, t=16, b=48),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family=FONT, size=12, color='#64748B'),
        hoverlabel=dict(bgcolor='#0F172A', font=dict(family=FONT, size=12, color='white')),
        transition=dict(duration=500, easing='cubic-in-out'),
        uirevision='gnani-dashboard',
    )
    defaults.update(kwargs)
    return defaults


def style_axes(fig, x_grid=False, y_grid=True):
    fig.update_xaxes(
        showline=False, linewidth=0, gridcolor='#E2E8F0', gridwidth=1,
        showgrid=x_grid, tickfont=dict(family=FONT, size=11, color='#64748B'),
        title_font=dict(family=FONT, size=12, color='#475569'),
    )
    fig.update_yaxes(
        showline=False, linewidth=0, gridcolor='#E2E8F0', gridwidth=1,
        showgrid=y_grid, tickfont=dict(family=FONT, size=11, color='#64748B'),
        title_font=dict(family=FONT, size=12, color='#475569'),
    )
    return fig


def create_empty_fig(msg="No data available"):
    fig = go.Figure()
    fig.add_annotation(
        text=msg, xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color="#94A3B8", family=FONT),
    )
    fig.update_layout(
        **base_layout(height=300),
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
    )
    return fig


def create_donut_chart(data_dict, colors=None, center_label="Total"):
    if not data_dict:
        return create_empty_fig("No data")
    labels = list(data_dict.keys())
    values = list(data_dict.values())
    total = sum(values)
    if colors is None:
        colors = [CHART_PALETTE[i % len(CHART_PALETTE)] for i in range(len(labels))]
    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.62,
        marker=dict(colors=colors, line=dict(color='white', width=2)),
        textinfo='percent', textposition='outside',
        textfont=dict(family=FONT, size=11, color='#475569'),
        hovertemplate='<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>',
        pull=[0.02] * len(labels),
    )])
    fig.update_layout(
        **base_layout(height=320, showlegend=True),
        legend=dict(
            orientation='h', yanchor='bottom', y=-0.22, xanchor='center', x=0.5,
            font=dict(family=FONT, size=11, color='#64748B'),
        ),
        annotations=[dict(
            text=f"<b>{total:,}</b><br><span style='font-size:11px;color:#94A3B8'>{center_label}</span>",
            x=0.5, y=0.5, font=dict(size=22, family=FONT, color='#0F172A'), showarrow=False,
        )],
    )
    return fig


def truncate_label(label, max_len=42):
    text = str(label)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + '...'


def create_horizontal_bar(values, labels, color_start='#6366F1', color_end='#8B5CF6', height=None):
    values = list(values)
    labels = [str(label) for label in labels]
    total = sum(values)
    bar_labels = [count_pct_label(v, total) for v in values]
    max_val = max(values) if values else 0
    max_label_len = max((len(label) for label in labels), default=0)
    max_bar_label_len = max((len(text) for text in bar_labels), default=8)
    use_vertical = max_label_len > 36

    if use_vertical:
        pairs = sorted(zip(labels, values, bar_labels), key=lambda item: item[1], reverse=True)
        labels, values, bar_labels = map(list, zip(*pairs))
        bar_height = height or max(380, min(560, 52 * len(labels) + 120))
        bottom_margin = max(110, min(240, int(max_label_len * 2.4)))
        fig = go.Figure(data=[go.Bar(
            x=labels,
            y=values,
            marker=dict(
                color=values,
                colorscale=[[0, color_start], [1, color_end]],
                line=dict(width=0),
                cornerradius=6,
            ),
            text=bar_labels,
            textposition='outside',
            cliponaxis=False,
            textfont=dict(family=FONT, size=10, color='#475569'),
            customdata=[[v / total * 100 if total > 0 else 0] for v in values],
            hovertemplate='<b>%{x}</b><br>%{y:,} cases (%{customdata[0]:.1f}%)<extra></extra>',
        )])
        fig.update_layout(
            **base_layout(
                height=bar_height,
                showlegend=False,
                margin=dict(l=24, r=24, t=20, b=bottom_margin),
            ),
            xaxis=dict(type='category', tickangle=-35),
            yaxis=dict(
                title='Count',
                range=[0, max_val + max(max_val * 0.16, max_bar_label_len * 8)] if max_val else None,
            ),
        )
        return style_axes(fig, x_grid=False, y_grid=True)

    pairs = sorted(zip(labels, values, bar_labels), key=lambda item: item[1])
    labels, values, bar_labels = map(list, zip(*pairs))
    display_labels = [truncate_label(label) for label in labels]
    bar_height = height or max(320, min(620, 44 * len(labels) + 100))
    left_margin = max(140, min(420, int(max_label_len * 5.8)))
    right_margin = max(72, min(140, int(max_bar_label_len * 7.5)))
    fig = go.Figure(data=[go.Bar(
        y=display_labels,
        x=values,
        orientation='h',
        marker=dict(
            color=values,
            colorscale=[[0, color_start], [1, color_end]],
            line=dict(width=0),
            cornerradius=6,
        ),
        text=bar_labels,
        textposition='outside',
        cliponaxis=False,
        textfont=dict(family=FONT, size=11, color='#475569'),
        customdata=list(zip(labels, [v / total * 100 if total > 0 else 0 for v in values])),
        hovertemplate='<b>%{customdata[0]}</b><br>%{x:,} cases (%{customdata[1]:.1f}%)<extra></extra>',
    )])
    fig.update_layout(
        **base_layout(
            height=bar_height,
            showlegend=False,
            margin=dict(l=left_margin, r=right_margin, t=16, b=48),
        ),
        yaxis=dict(
            type='category',
            categoryorder='array',
            categoryarray=display_labels,
            automargin=True,
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor='#E2E8F0',
            title='Count',
            range=[0, max_val + max(max_val * 0.14, max_bar_label_len * 9)] if max_val else None,
        ),
    )
    return style_axes(fig, x_grid=True, y_grid=False)


def column_options(series):
    if series is None:
        return [{'label': 'All', 'value': 'ALL'}]
    vals = series.dropna().astype(str).str.strip()
    vals = vals[vals != ''].unique()
    return [{'label': 'All', 'value': 'ALL'}] + [{'label': v, 'value': v} for v in sorted(vals)]


def apply_global_filters(df, status, start_date, end_date):
    fdf = df.copy()
    if status != 'ALL' and 'Overall Status' in fdf.columns:
        fdf = fdf[fdf['Overall Status'] == status]
    if start_date and end_date and 'Date' in fdf.columns:
        start = pd.to_datetime(start_date).normalize()
        end = pd.to_datetime(end_date).normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        fdf = fdf[fdf['Date'].notna() & (fdf['Date'] >= start) & (fdf['Date'] <= end)]
    return fdf


def create_hierarchy_bar(fdf, group_by, problem_f, detail_f, subdetail_f):
    group_col = SF_HIERARCHY.get(group_by)
    if not group_col or group_col not in fdf.columns:
        return create_empty_fig("Hierarchy columns not found")

    hdf = fdf.copy()
    if problem_f != 'ALL' and 'SF Final Problem' in hdf.columns:
        hdf = hdf[hdf['SF Final Problem'].astype(str) == problem_f]
    if detail_f != 'ALL' and 'SF Final Detail' in hdf.columns:
        hdf = hdf[hdf['SF Final Detail'].astype(str) == detail_f]
    if subdetail_f != 'ALL' and 'SF Final SubDetail' in hdf.columns:
        hdf = hdf[hdf['SF Final SubDetail'].astype(str) == subdetail_f]

    hdf = hdf[hdf[group_col].notna()]
    hdf[group_col] = hdf[group_col].astype(str).str.strip()
    hdf = hdf[hdf[group_col] != '']
    counts = hdf[group_col].value_counts().head(15).sort_values(ascending=True)
    if counts.empty:
        return create_empty_fig("No matches for selected filters")

    labels = counts.index.tolist()
    values = counts.values.tolist()
    total = sum(values)
    bar_labels = [count_pct_label(v, total) for v in values]
    max_val = max(values)
    max_bar_label_len = max(len(t) for t in bar_labels)
    max_y_label_len = max(len(str(label)) for label in labels)

    bar_height = max(300, min(720, 48 * len(labels) + 110))
    left_margin = max(150, min(340, int(max_y_label_len * 6.2)))
    right_margin = max(72, min(130, int(max_bar_label_len * 7.5)))
    x_upper = max_val + max(max_val * 0.14, max_bar_label_len * 9)

    fig = go.Figure(data=[go.Bar(
        y=labels,
        x=values,
        orientation='h',
        marker=dict(
            color=values,
            colorscale=[[0, '#6366F1'], [1, '#A78BFA']],
            line=dict(width=0),
            cornerradius=6,
        ),
        text=bar_labels,
        textposition='outside',
        cliponaxis=False,
        textfont=dict(family=FONT, size=11, color='#475569'),
        customdata=[v / total * 100 for v in values],
        hovertemplate='<b>%{y}</b><br>%{x:,} cases (%{customdata:.1f}%)<extra></extra>',
    )])
    fig.update_layout(
        height=bar_height,
        autosize=True,
        margin=dict(l=left_margin, r=right_margin, t=20, b=52),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family=FONT, size=12, color='#64748B'),
        showlegend=False,
        uirevision=f'{group_by}|{problem_f}|{detail_f}|{subdetail_f}|{"|".join(labels)}',
    )
    fig.update_yaxes(
        type='category',
        categoryorder='array',
        categoryarray=labels,
        automargin=True,
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor='#E2E8F0',
        title='Count',
        range=[0, x_upper],
        automargin=True,
    )
    return style_axes(fig, x_grid=True, y_grid=False)


def add_period_labels(tdf, time_grp):
    tdf = tdf.copy()
    if time_grp == 'monthly':
        tdf['_sort'] = tdf['Date'].dt.to_period('M').astype(int)
        tdf['Period'] = tdf['Date'].dt.strftime('%b %Y')
    else:
        tdf['_sort'] = tdf['Date'].dt.normalize().astype('int64') // 10**9
        tdf['Period'] = tdf['Date'].dt.strftime('%b %d, %Y')
    return tdf


def create_trend_chart(tc, time_grp='daily'):
    periods = tc['Period'].tolist()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=periods, y=tc['Count'], mode='lines+markers', name='Cases',
        line=dict(color='#6366F1', width=3, shape='linear'),
        marker=dict(size=8, color='#6366F1', line=dict(color='white', width=2)),
        hovertemplate='<b>%{x}</b><br>%{y:,} cases<extra></extra>',
    ))
    layout = base_layout(height=320, showlegend=False)
    layout['uirevision'] = f'trend-{time_grp}-{"|".join(periods)}'
    fig.update_layout(**layout)
    fig.update_xaxes(
        type='category',
        tickangle=-30 if len(periods) > 6 else 0,
        categoryorder='array',
        categoryarray=periods,
    )
    if time_grp == 'monthly' and len(periods) == 1:
        fig.add_annotation(
            text='Single month in range — switch to Daily for day-by-day detail',
            xref='paper', yref='paper', x=0.5, y=1.08, showarrow=False,
            font=dict(size=11, color='#94A3B8', family=FONT),
        )
    return style_axes(fig, x_grid=False, y_grid=True)


def create_status_line_chart(tc, time_grp='daily'):
    period_order = tc.drop_duplicates('_sort').sort_values('_sort')
    periods = period_order['Period'].tolist()
    line_statuses = [s for s in ['SUCCESS', 'FAILED'] if s in tc['Overall Status'].unique()]

    totals_by_period = {}
    for period in periods:
        totals_by_period[period] = int(tc[tc['Period'] == period]['Count'].sum())

    fig = go.Figure()
    for status in line_statuses:
        subset = tc[tc['Overall Status'] == status].set_index('Period').reindex(periods, fill_value=0)
        counts = [int(v) for v in subset['Count'].tolist()]
        pcts = [
            c / totals_by_period[period] * 100 if totals_by_period[period] > 0 else 0
            for period, c in zip(periods, counts)
        ]
        point_labels = [count_pct_label(c, totals_by_period[period], decimals=0) for period, c in zip(periods, counts)]
        label = STATUS_LABELS.get(status, status)
        color = STATUS_COLORS.get(status, CHART_PALETTE[0])
        fig.add_trace(go.Scatter(
            x=periods,
            y=pcts,
            mode='lines+markers+text',
            name=label,
            text=point_labels,
            textposition='top center',
            textfont=dict(family=FONT, size=10, color='#475569'),
            line=dict(color=color, width=3, shape='linear'),
            marker=dict(size=8, color=color, line=dict(color='white', width=2)),
            customdata=counts,
            hovertemplate=f'<b>%{{x}}</b><br>{label}: %{{customdata:,}} (%{{y:.1f}}%)<extra></extra>',
        ))

    fig.update_layout(
        **base_layout(height=340, showlegend=True),
        uirevision=f'status-{time_grp}-{"|".join(periods)}',
        legend=dict(
            title='',
            orientation='h',
            yanchor='bottom',
            y=-0.22,
            xanchor='center',
            x=0.5,
            font=dict(family=FONT, size=11, color='#64748B'),
        ),
    )
    fig.update_xaxes(
        type='category',
        tickangle=-30 if len(periods) > 6 else 0,
        categoryorder='array',
        categoryarray=periods,
    )
    fig.update_yaxes(title='Percent', ticksuffix='%', range=[0, 105])
    return style_axes(fig, x_grid=False, y_grid=True)


def create_resolution_donut(res, unr):
    if res + unr == 0:
        return create_empty_fig("No resolution data")
    return create_donut_chart(
        {'Resolved': res, 'Unresolved': unr},
        colors=['#6366F1', '#F59E0B'],
        center_label='Cases',
    )


def create_error_bar(e):
    total = e.values.sum()
    colors = [CHART_PALETTE[i % len(CHART_PALETTE)] for i in range(len(e))]
    bar_labels = [count_pct_label(v, total) for v in e.values]
    fig = go.Figure(data=[go.Bar(
        x=e.index, y=e.values,
        marker=dict(color=colors, cornerradius=6, line=dict(width=0)),
        text=bar_labels,
        textposition='outside',
        cliponaxis=False,
        textfont=dict(family=FONT, size=10, color='#475569'),
        customdata=[v / total * 100 if total > 0 else 0 for v in e.values],
        hovertemplate='<b>%{x}</b><br>%{y:,} errors (%{customdata:.1f}%)<extra></extra>',
    )])
    max_val = e.values.max() if len(e) else 0
    fig.update_layout(**base_layout(height=320, showlegend=False), xaxis=dict(tickangle=-35))
    if max_val:
        fig.update_yaxes(range=[0, max_val * 1.18])
    return style_axes(fig, x_grid=False, y_grid=True)


app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Plus Jakarta Sans', sans-serif;
                background: linear-gradient(135deg, #F8FAFC 0%, #EEF2FF 50%, #F8FAFC 100%);
                color: #1E293B;
                min-height: 100vh;
            }
            .sidebar {
                position: fixed; left: 0; top: 0; bottom: 0; width: 260px;
                background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
                padding: 28px 20px; z-index: 1000;
                border-right: 1px solid rgba(255,255,255,0.06);
                box-shadow: 4px 0 24px rgba(15, 23, 42, 0.15);
            }
            .logo-section { padding-bottom: 36px; border-bottom: 1px solid rgba(255,255,255,0.08); margin-bottom: 28px; }
            .logo-container { display: flex; align-items: center; gap: 12px; }
            .logo-icon {
                width: 42px; height: 42px;
                background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
                border-radius: 12px; display: flex; align-items: center; justify-content: center;
                color: white; font-weight: 800; font-size: 18px;
                box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
            }
            .logo-text { font-size: 17px; font-weight: 700; color: #F8FAFC; letter-spacing: -0.02em; }
            .logo-sub { font-size: 11px; color: #64748B; margin-top: 2px; font-weight: 500; }
            .menu-label {
                font-size: 10px; font-weight: 700; color: #475569;
                text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 12px;
            }
            .menu-item {
                display: flex; align-items: center; gap: 12px;
                padding: 12px 14px; margin: 2px 0; border-radius: 10px;
                color: #94A3B8; transition: all 0.25s ease; cursor: pointer;
                font-size: 14px; font-weight: 500; position: relative;
            }
            .menu-item:hover { background: rgba(99, 102, 241, 0.12); color: #C7D2FE; }
            .menu-item.active {
                background: rgba(99, 102, 241, 0.18); color: #E0E7FF; font-weight: 600;
            }
            .menu-item.active::before {
                content: ''; position: absolute; left: 0; top: 50%; transform: translateY(-50%);
                width: 3px; height: 20px; background: linear-gradient(180deg, #6366F1, #8B5CF6);
                border-radius: 0 3px 3px 0;
            }
            .menu-item i { width: 20px; text-align: center; font-size: 16px; }
            .main-content { margin-left: 260px; padding: 32px 40px 48px; min-height: 100vh; }
            .page-header { margin-bottom: 28px; animation: fadeInDown 0.5s ease; }
            .page-title { font-size: 28px; font-weight: 800; color: #0F172A; letter-spacing: -0.03em; line-height: 1.2; }
            .page-subtitle { font-size: 14px; color: #64748B; margin-top: 6px; font-weight: 500; }
            .upload-card {
                background: rgba(255,255,255,0.85); backdrop-filter: blur(8px);
                border-radius: 14px; padding: 28px 32px; margin-bottom: 24px;
                border: 2px dashed #CBD5E1; transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
                animation: fadeInUp 0.5s ease 0.1s both;
            }
            .upload-card:hover {
                border-color: #6366F1;
                box-shadow: 0 8px 24px rgba(99, 102, 241, 0.12);
                transform: translateY(-1px);
            }
            .upload-inner { text-align: center; cursor: pointer; }
            .upload-icon {
                font-size: 36px; color: #6366F1; margin-bottom: 12px;
                transition: transform 0.3s ease;
            }
            .upload-card:hover .upload-icon { transform: scale(1.08); }
            .upload-title { font-size: 15px; font-weight: 700; color: #0F172A; margin-bottom: 4px; }
            .upload-hint { font-size: 13px; color: #64748B; font-weight: 500; }
            .stats-grid {
                display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 24px;
            }
            .stat-card {
                background: white; border-radius: 14px; padding: 22px 24px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03);
                transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative; overflow: hidden;
                animation: fadeInUp 0.5s ease both;
            }
            .stat-card:nth-child(1) { animation-delay: 0.15s; }
            .stat-card:nth-child(2) { animation-delay: 0.2s; }
            .stat-card:nth-child(3) { animation-delay: 0.25s; }
            .stat-card:nth-child(4) { animation-delay: 0.3s; }
            .stat-card::before {
                content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
            }
            .stat-card.primary::before { background: linear-gradient(90deg, #6366F1, #8B5CF6); }
            .stat-card.success::before { background: linear-gradient(90deg, #10B981, #059669); }
            .stat-card.danger::before { background: linear-gradient(90deg, #EF4444, #DC2626); }
            .stat-card.warning::before { background: linear-gradient(90deg, #F59E0B, #D97706); }
            .stat-card:hover { transform: translateY(-4px) scale(1.02); box-shadow: 0 12px 28px rgba(0,0,0,0.08); }
            .stat-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
            .stat-icon {
                width: 44px; height: 44px; border-radius: 11px;
                display: flex; align-items: center; justify-content: center; font-size: 20px;
            }
            .stat-icon.primary { background: rgba(99, 102, 241, 0.12); color: #6366F1; }
            .stat-icon.success { background: rgba(16, 185, 129, 0.12); color: #10B981; }
            .stat-icon.danger { background: rgba(239, 68, 68, 0.12); color: #EF4444; }
            .stat-icon.warning { background: rgba(245, 158, 11, 0.12); color: #F59E0B; }
            .stat-label { font-size: 13px; font-weight: 600; color: #64748B; letter-spacing: -0.01em; }
            .stat-value {
                font-size: 32px; font-weight: 800; color: #0F172A; line-height: 1;
                letter-spacing: -0.03em; transition: all 0.3s ease;
            }
            .filter-bar {
                background: white; border-radius: 14px; padding: 20px 24px; margin-bottom: 24px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04);
                display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;
                animation: fadeInUp 0.5s ease 0.35s both;
                position: relative;
                z-index: 200;
                overflow: visible !important;
            }
            .filter-bar > div { overflow: visible !important; position: relative; z-index: 200; }
            .filter-bar > div:focus-within { z-index: 300; }
            .DateRangePickerInput, .DateInput_input, .DateInput, .DateRangePicker {
                font-family: 'Plus Jakarta Sans', sans-serif !important;
                font-size: 13px !important;
                font-weight: 500 !important;
                color: #475569 !important;
            }
            .DateRangePickerInput {
                border: 1px solid #E2E8F0 !important;
                border-radius: 10px !important;
                overflow: hidden;
                min-height: 40px;
                display: flex;
                align-items: center;
            }
            .DateInput_input {
                border: none !important;
                padding: 9px 12px !important;
                background: transparent !important;
                font-family: 'Plus Jakarta Sans', sans-serif !important;
                font-size: 13px !important;
                font-weight: 500 !important;
                color: #475569 !important;
                line-height: 1.4 !important;
            }
            .DateRangePickerInput__display-text {
                font-family: 'Plus Jakarta Sans', sans-serif !important;
                font-size: 13px !important;
                font-weight: 500 !important;
                color: #475569 !important;
            }
            .DateRangePickerInput_arrow {
                padding-right: 10px;
            }
            .date-range-filter .DateRangePickerInput { width: 100% !important; }
            .date-range-filter .DateInput { width: 100% !important; }
            .filter-label {
                font-size: 12px; font-weight: 700; color: #475569;
                margin-bottom: 8px; display: block; letter-spacing: -0.01em;
                text-transform: uppercase; letter-spacing: 0.04em;
            }
            .Select-control, .dash-dropdown .Select-control {
                border-radius: 10px !important; border-color: #E2E8F0 !important;
                box-shadow: none !important; min-height: 40px !important;
                transition: border-color 0.2s, box-shadow 0.2s !important;
            }
            .Select-control:hover, .dash-dropdown .Select-control:hover {
                border-color: #6366F1 !important;
            }
            .is-focused .Select-control, .dash-dropdown .is-focused .Select-control {
                border-color: #6366F1 !important;
                box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
            }
            .Select-menu-outer, .Select-menu, div[class*="-menu"] {
                z-index: 10000 !important;
            }
            .DateRangePicker_picker, .SingleDatePicker_picker {
                z-index: 10000 !important;
            }
            .pill-toggle { display: flex; gap: 6px; background: #F1F5F9; border-radius: 10px; padding: 4px; }
            .pill-toggle label {
                flex: 1; text-align: center; padding: 8px 12px; border-radius: 8px;
                font-size: 13px; font-weight: 600; color: #64748B; cursor: pointer;
                transition: all 0.25s ease; margin: 0 !important;
            }
            .pill-toggle input { display: none; }
            .pill-toggle label:has(input:checked) {
                background: white; color: #6366F1;
                box-shadow: 0 2px 6px rgba(0,0,0,0.08);
            }
            .chart-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px; position: relative; z-index: 1; }
            .chart-card {
                background: white; border-radius: 14px; padding: 22px 24px 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.02);
                transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
                animation: fadeInUp 0.55s ease both;
                position: relative;
                z-index: 1;
            }
            .chart-card:hover { box-shadow: 0 8px 24px rgba(0,0,0,0.06); }
            .chart-card.full-width { grid-column: 1 / -1; }
            .chart-card .dash-graph { width: 100%; overflow: visible; }
            .chart-card .js-plotly-plot, .chart-card .plot-container { width: 100% !important; }
            .chart-header { margin-bottom: 8px; }
            .chart-title { font-size: 16px; font-weight: 700; color: #0F172A; letter-spacing: -0.02em; }
            .chart-subtitle { font-size: 12px; color: #94A3B8; margin-top: 2px; font-weight: 500; }
            .chart-filter-row {
                display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
                margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid #F1F5F9;
            }
            .alert {
                border-radius: 12px; border: none; padding: 14px 18px; margin-bottom: 20px;
                font-weight: 500; font-size: 13px;
                animation: slideIn 0.4s ease;
            }
            .alert-success {
                background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.06) 100%);
                color: #065F46; border-left: 3px solid #10B981;
            }
            .alert-info {
                background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.06) 100%);
                color: #4338CA; border-left: 3px solid #6366F1;
            }
            .alert-danger {
                background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.06) 100%);
                color: #991B1B; border-left: 3px solid #EF4444;
            }
            @keyframes fadeInUp {
                from { opacity: 0; transform: translateY(16px); }
                to { opacity: 1; transform: translateY(0); }
            }
            @keyframes fadeInDown {
                from { opacity: 0; transform: translateY(-12px); }
                to { opacity: 1; transform: translateY(0); }
            }
            @keyframes slideIn {
                from { opacity: 0; transform: translateX(-12px); }
                to { opacity: 1; transform: translateX(0); }
            }
            @media (max-width: 1200px) {
                .stats-grid, .filter-bar { grid-template-columns: repeat(2, 1fr); }
                .chart-grid { grid-template-columns: 1fr; }
                .chart-filter-row { grid-template-columns: repeat(2, 1fr); }
            }
            @media (max-width: 768px) {
                .sidebar { width: 72px; padding: 20px 12px; }
                .logo-text, .logo-sub, .menu-label, .menu-item span { display: none; }
                .main-content { margin-left: 72px; padding: 20px; }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>{%config%}{%scripts%}{%renderer%}</footer>
    </body>
</html>
"""

dropdown_style = {'borderRadius': '10px', 'fontFamily': FONT, 'fontSize': '13px'}


def chart_card(title, subtitle, graph_id, full_width=False):
    cls = 'chart-card full-width' if full_width else 'chart-card'
    return html.Div([
        html.Div([
            html.Div(title, className='chart-title'),
            html.Div(subtitle, className='chart-subtitle'),
        ], className='chart-header'),
        dcc.Graph(id=graph_id, config=GRAPH_CONFIG),
    ], className=cls)


app.layout = html.Div([
    dcc.Store(id='stored-data'),
    html.Div([
        html.Div([
            html.Div([
                html.Div('G', className='logo-icon'),
                html.Div([
                    html.Div('Gnani', className='logo-text'),
                    html.Div('Analytics', className='logo-sub'),
                ]),
            ], className='logo-container'),
        ], className='logo-section'),
        html.Div([
            html.Div('Navigation', className='menu-label'),
            html.Div([
                html.I(className='fas fa-chart-line'),
                html.Span('Dashboard'),
            ], className='menu-item active'),
        ], className='menu-section'),
    ], className='sidebar'),
    html.Div([
        html.Div([
            html.H1('Dashboard', className='page-title'),
            html.P('Upload CSV files to analyze case metrics and trends', className='page-subtitle'),
        ], className='page-header'),
        html.Div([
            dcc.Upload(
                id='upload-data',
                children=html.Div([
                    html.I(className='fas fa-cloud-upload-alt upload-icon'),
                    html.Div('Drag & drop or click to upload', className='upload-title'),
                    html.Div('Supports multiple CSV files', className='upload-hint'),
                ], className='upload-inner'),
                multiple=True,
            ),
            html.Div(id='upload-status', style={'marginTop': '16px'}),
        ], className='upload-card'),
        html.Div(id='data-alert'),
        html.Div([
            html.Div([
                html.Div([
                    html.Div(html.I(className='fas fa-ticket-alt'), className='stat-icon primary'),
                ], className='stat-top'),
                html.Div('Total Cases', className='stat-label'),
                html.Div(id='total-cases', children='0', className='stat-value'),
            ], className='stat-card primary'),
            html.Div([
                html.Div([
                    html.Div(html.I(className='fas fa-check-circle'), className='stat-icon success'),
                ], className='stat-top'),
                html.Div('Success Rate', className='stat-label'),
                html.Div(id='success-rate', children='0%', className='stat-value'),
            ], className='stat-card success'),
            html.Div([
                html.Div([
                    html.Div(html.I(className='fas fa-times-circle'), className='stat-icon danger'),
                ], className='stat-top'),
                html.Div('Failed Cases', className='stat-label'),
                html.Div(id='failed-cases', children='0', className='stat-value'),
            ], className='stat-card danger'),
            html.Div([
                html.Div([
                    html.Div(html.I(className='fas fa-clock'), className='stat-icon warning'),
                ], className='stat-top'),
                html.Div('Unresolved', className='stat-label'),
                html.Div(id='unresolved-cases', children='0', className='stat-value'),
            ], className='stat-card warning'),
        ], className='stats-grid'),
        html.Div([
            html.Div([
                html.Label('Status', className='filter-label'),
                dcc.Dropdown(
                    id='status-filter',
                    options=[
                        {'label': 'All', 'value': 'ALL'},
                        {'label': 'Success', 'value': 'SUCCESS'},
                        {'label': 'Failed', 'value': 'FAILED'},
                    ],
                    value='ALL', clearable=False, style=dropdown_style,
                ),
            ]),
            html.Div([
                html.Label('Time Grouping', className='filter-label'),
                dcc.Dropdown(
                    id='time-grouping',
                    options=[
                        {'label': 'Daily', 'value': 'daily'},
                        {'label': 'Monthly', 'value': 'monthly'},
                    ],
                    value='daily',
                    clearable=False,
                    style=dropdown_style,
                ),
            ]),
            html.Div([
                html.Label('Date Range', className='filter-label'),
                dcc.DatePickerRange(
                    id='date-range-filter',
                    display_format='MMM D, YYYY',
                    minimum_nights=0,
                    disabled=True,
                ),
            ], className='date-range-filter'),
        ], className='filter-bar'),
        html.Div([
            chart_card('Cases Trend', 'Volume over time', 'trend-line-chart', full_width=True),
        ], className='chart-grid'),
        html.Div([
            chart_card('Status Distribution', 'Success vs failed share over time (%)', 'time-bar-chart', full_width=True),
        ], className='chart-grid'),
        html.Div([
            chart_card('Overall Status', 'Breakdown by outcome', 'status-pie-chart'),
            chart_card('CTA Status', 'Call-to-action outcomes', 'cta-status-chart'),
        ], className='chart-grid'),
        html.Div([
            chart_card('SF Final Categories', 'Top 10 categories', 'category-chart', full_width=True),
        ], className='chart-grid'),
        html.Div([
            chart_card('SF Final Problems', 'Top 10 problems', 'problem-chart', full_width=True),
        ], className='chart-grid'),
        html.Div([
            chart_card('Resolution Status', 'Resolved vs unresolved', 'resolution-chart'),
            chart_card('Error Types', 'Top 10 error types', 'error-chart'),
        ], className='chart-grid'),
        html.Div([
            html.Div([
                html.Div('Case Breakdown', className='chart-title'),
                html.Div(
                    'Drill into Problem → Detail → SubDetail with chart-only filters',
                    className='chart-subtitle',
                ),
            ], className='chart-header'),
            html.Div([
                html.Div([
                    html.Label('Group By', className='filter-label'),
                    dcc.Dropdown(
                        id='sf-group-by',
                        options=[
                            {'label': 'SF Final Problem', 'value': 'problem'},
                            {'label': 'SF Final Detail', 'value': 'detail'},
                            {'label': 'SF Final SubDetail', 'value': 'subdetail'},
                        ],
                        value='problem',
                        clearable=False,
                        style=dropdown_style,
                    ),
                ]),
                html.Div([
                    html.Label('Problem', className='filter-label'),
                    dcc.Dropdown(
                        id='sf-problem-filter',
                        options=[{'label': 'All', 'value': 'ALL'}],
                        value='ALL',
                        clearable=False,
                        style=dropdown_style,
                    ),
                ]),
                html.Div([
                    html.Label('Detail', className='filter-label'),
                    dcc.Dropdown(
                        id='sf-detail-filter',
                        options=[{'label': 'All', 'value': 'ALL'}],
                        value='ALL',
                        clearable=False,
                        style=dropdown_style,
                    ),
                ]),
                html.Div([
                    html.Label('SubDetail', className='filter-label'),
                    dcc.Dropdown(
                        id='sf-subdetail-filter',
                        options=[{'label': 'All', 'value': 'ALL'}],
                        value='ALL',
                        clearable=False,
                        style=dropdown_style,
                    ),
                ]),
            ], className='chart-filter-row'),
            dcc.Graph(id='sf-hierarchy-chart', config=GRAPH_CONFIG, style={'width': '100%'}),
        ], className='chart-card full-width'),
    ], className='main-content'),
])


@app.callback(
    [Output('stored-data', 'data'), Output('upload-status', 'children')],
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
)
def store_files(contents, names):
    if contents is None:
        return None, html.Div()
    dfs, errors = [], []
    for c, n in zip(contents, names):
        df, fn, err = parse_contents(c, n)
        if err:
            errors.append(html.Div(f"Error loading {fn}: {err}", className='alert alert-danger'))
        else:
            dfs.append(df)
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        file_label = 'file' if len(dfs) == 1 else 'files'
        summary = html.Div(
            f"Loaded {len(dfs)} {file_label} — {len(combined):,} total rows",
            className='alert alert-success',
        )
        return combined.to_dict('records'), html.Div(errors + [summary])
    return None, html.Div(errors)


@app.callback(
    [
        Output('date-range-filter', 'min_date_allowed'),
        Output('date-range-filter', 'max_date_allowed'),
        Output('date-range-filter', 'start_date'),
        Output('date-range-filter', 'end_date'),
        Output('date-range-filter', 'disabled'),
    ],
    Input('stored-data', 'data'),
    prevent_initial_call=False,
)
def update_date_range(data):
    if data is None:
        return None, None, None, None, True
    try:
        df = pd.DataFrame(data)
        if 'Last Updated (IST)' not in df.columns:
            return None, None, None, None, True
        dates = pd.to_datetime(df['Last Updated (IST)'], errors='coerce').dropna()
        if dates.empty:
            return None, None, None, None, True
        min_d = dates.min().date()
        max_d = dates.max().date()
        return min_d, max_d, min_d, max_d, False
    except Exception:
        return None, None, None, None, True


@app.callback(
    [
        Output('data-alert', 'children'),
        Output('total-cases', 'children'),
        Output('success-rate', 'children'),
        Output('failed-cases', 'children'),
        Output('unresolved-cases', 'children'),
        Output('trend-line-chart', 'figure'),
        Output('time-bar-chart', 'figure'),
        Output('status-pie-chart', 'figure'),
        Output('cta-status-chart', 'figure'),
        Output('category-chart', 'figure'),
        Output('problem-chart', 'figure'),
        Output('resolution-chart', 'figure'),
        Output('error-chart', 'figure'),
    ],
    [
        Input('stored-data', 'data'),
        Input('status-filter', 'value'),
        Input('time-grouping', 'value'),
        Input('date-range-filter', 'start_date'),
        Input('date-range-filter', 'end_date'),
    ],
    prevent_initial_call=False,
)
def update_dash(data, status, time_grp, start_date, end_date):
    empty = (
        create_empty_fig(), create_empty_fig(), create_empty_fig(), create_empty_fig(),
        create_empty_fig(), create_empty_fig(), create_empty_fig(), create_empty_fig(),
    )
    try:
        if data is None:
            return (
                html.Div([
                    html.Strong('No data loaded'),
                    html.Div('Upload one or more CSV files to get started', style={'marginTop': '4px'}),
                ], className='alert alert-info'),
                "0", "0%", "0", "0", *empty,
            )
        df = pd.DataFrame(data)
        if 'Last Updated (IST)' in df.columns:
            df['Date'] = pd.to_datetime(df['Last Updated (IST)'], errors='coerce')
        fdf = apply_global_filters(df, status, start_date, end_date)
        tot = len(fdf)
        if tot == 0:
            return (
                html.Div('No cases match the current filters', className='alert alert-success'),
                "0", "0%", "0", "0", *tuple(create_empty_fig("No matches") for _ in range(8)),
            )
        succ = len(fdf[fdf['Overall Status'] == 'SUCCESS']) if 'Overall Status' in fdf.columns else 0
        fail = len(fdf[fdf['Overall Status'] == 'FAILED']) if 'Overall Status' in fdf.columns else 0
        unres = len(fdf[fdf['SF Final Action'] == 'Unresolved']) if 'SF Final Action' in fdf.columns else 0
        sr = f"{(succ / tot * 100):.1f}%" if tot > 0 else "0%"

        if 'Date' in fdf.columns:
            tdf = fdf[fdf['Date'].notna()].copy()
            if len(tdf) > 0:
                tdf = add_period_labels(tdf, time_grp)
                tc = tdf.groupby(['_sort', 'Period']).size().reset_index(name='Count')
                tc = tc.sort_values('_sort')
                trend = create_trend_chart(tc, time_grp)
            else:
                trend = create_empty_fig()
        else:
            trend = create_empty_fig()

        if 'Date' in fdf.columns and 'Overall Status' in fdf.columns:
            tdf = fdf[fdf['Date'].notna()].copy()
            if len(tdf) > 0:
                tdf = add_period_labels(tdf, time_grp)
                tc = tdf.groupby(['_sort', 'Period', 'Overall Status']).size().reset_index(name='Count')
                tc = tc.sort_values('_sort')
                tbar = create_status_line_chart(tc, time_grp)
            else:
                tbar = create_empty_fig()
        else:
            tbar = create_empty_fig()

        if 'Overall Status' in fdf.columns:
            c = fdf['Overall Status'].value_counts()
            status_colors = [STATUS_COLORS.get(k, CHART_PALETTE[i % len(CHART_PALETTE)])
                             for i, k in enumerate(c.index)]
            spie = create_donut_chart(c.to_dict(), colors=status_colors, center_label='Cases')
        else:
            spie = create_empty_fig()

        if 'CTA Status' in fdf.columns:
            c = fdf['CTA Status'].value_counts()
            cpie = create_donut_chart(c.to_dict(), center_label='CTA')
        else:
            cpie = create_empty_fig()

        if 'SF Final Category' in fdf.columns:
            c = fdf['SF Final Category'].value_counts().head(10)
            catbar = create_horizontal_bar(c.values, c.index, '#6366F1', '#818CF8')
        else:
            catbar = create_empty_fig()

        if 'SF Final Problem' in fdf.columns:
            c = fdf['SF Final Problem'].value_counts().head(10)
            pbar = create_horizontal_bar(c.values, c.index, '#8B5CF6', '#A78BFA')
        else:
            pbar = create_empty_fig()

        if 'SF Final Action' in fdf.columns:
            res = len(fdf[fdf['SF Final Action'] == 'Resolved'])
            unr = len(fdf[fdf['SF Final Action'] == 'Unresolved'])
            resbar = create_resolution_donut(res, unr)
        else:
            resbar = create_empty_fig()

        if 'SF Error Type' in fdf.columns:
            e = fdf['SF Error Type'].dropna().value_counts().head(10)
            ebar = create_error_bar(e) if len(e) > 0 else create_empty_fig()
        else:
            ebar = create_empty_fig()

        return (
            html.Div(f"Analyzing {tot:,} cases", className='alert alert-success'),
            f"{tot:,}", sr, f"{fail:,}", f"{unres:,}",
            trend, tbar, spie, cpie, catbar, pbar, resbar, ebar,
        )
    except Exception as e:
        return (
            html.Div([html.Strong('Error'), html.Div(str(e))], className='alert alert-danger'),
            "—", "—", "—", "—", *empty,
        )


@app.callback(
    [
        Output('sf-hierarchy-chart', 'figure'),
        Output('sf-problem-filter', 'options'),
        Output('sf-detail-filter', 'options'),
        Output('sf-subdetail-filter', 'options'),
        Output('sf-detail-filter', 'value'),
        Output('sf-subdetail-filter', 'value'),
    ],
    [
        Input('stored-data', 'data'),
        Input('status-filter', 'value'),
        Input('date-range-filter', 'start_date'),
        Input('date-range-filter', 'end_date'),
        Input('sf-group-by', 'value'),
        Input('sf-problem-filter', 'value'),
        Input('sf-detail-filter', 'value'),
        Input('sf-subdetail-filter', 'value'),
    ],
    prevent_initial_call=False,
)
def update_hierarchy_chart(data, status, start_date, end_date,
                           group_by, problem_f, detail_f, subdetail_f):
    empty_opts = [{'label': 'All', 'value': 'ALL'}]
    if data is None:
        return create_empty_fig("Upload data to explore hierarchy"), empty_opts, empty_opts, empty_opts, 'ALL', 'ALL'

    try:
        df = pd.DataFrame(data)
        if 'Last Updated (IST)' in df.columns:
            df['Date'] = pd.to_datetime(df['Last Updated (IST)'], errors='coerce')
        fdf = apply_global_filters(df, status, start_date, end_date)

        if not any(col in fdf.columns for col in SF_HIERARCHY.values()):
            return create_empty_fig("Hierarchy columns not found"), empty_opts, empty_opts, empty_opts, 'ALL', 'ALL'

        problem_opts = column_options(fdf.get('SF Final Problem'))
        detail_df = fdf if problem_f == 'ALL' else fdf[fdf['SF Final Problem'].astype(str) == problem_f]
        detail_opts = column_options(detail_df.get('SF Final Detail'))

        subdetail_df = detail_df
        if detail_f != 'ALL' and 'SF Final Detail' in subdetail_df.columns:
            subdetail_df = subdetail_df[subdetail_df['SF Final Detail'].astype(str) == detail_f]
        subdetail_opts = column_options(subdetail_df.get('SF Final SubDetail'))

        detail_values = {o['value'] for o in detail_opts}
        subdetail_values = {o['value'] for o in subdetail_opts}
        detail_f = detail_f if detail_f in detail_values else 'ALL'
        subdetail_f = subdetail_f if subdetail_f in subdetail_values else 'ALL'

        fig = create_hierarchy_bar(fdf, group_by, problem_f, detail_f, subdetail_f)
        return fig, problem_opts, detail_opts, subdetail_opts, detail_f, subdetail_f
    except Exception:
        return create_empty_fig("Unable to build hierarchy chart"), empty_opts, empty_opts, empty_opts, 'ALL', 'ALL'


server = app.server


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8050))
    debug = os.environ.get('DASH_DEBUG', 'false').lower() == 'true'
    print("\n Gnani Dashboard")
    print(f" URL: http://127.0.0.1:{port}/\n")
    app.run(debug=debug, dev_tools_ui=False, port=port, host='0.0.0.0')
