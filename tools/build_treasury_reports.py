"""Build the two integrated reports from checked Markdown and sealed outputs."""
from pathlib import Path
import hashlib
import html
import json
import re

import fitz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                               TableStyle, KeepTogether, Image)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/integrated_20261019'
OUTPUT = ROOT / 'output/pdf'
QA = ROOT / 'tmp/pdfs/treasury'
OUTPUT.mkdir(parents=True, exist_ok=True)
QA.mkdir(parents=True, exist_ok=True)
NAVY = '#11283f'
TEAL = '#087e8b'
TEXT = '#243746'
MUTED = '#586b7b'


def checked_values():
    final = json.loads((ROOT / 'reports/treasury_20261019/final_results.json').read_text())
    case = json.loads((ROOT / 'reports/current_case_20261019/current_case.json').read_text())
    reproduction = json.loads((REPORT / 'full_study_reproduction.json').read_text())
    assert final['selected_method'] == 'covariance' and final['supported_superiority']
    assert reproduction['status'] == 'passed' and len(reproduction['scientific_outputs']) == 8
    assert case['base_liability_risk']['pv'] == 119380495.42258865
    assert round(final['final_scores']['covariance']['rmse'] * 10000, 2) == 6.50
    assert round(final['final_scores']['duration_match']['rmse'] * 10000, 2) == 15.87
    assert round((1-final['final_scores']['covariance']['rmse'] /
                  final['final_scores']['duration_match']['rmse']) * 100, 2) == 59.03
    assert [round(x*10000, 2) for x in final['primary_comparison']['ci95']] == [-12.34, -6.02]
    return final, case


def figure(final, case):
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 3.5), gridspec_kw={'width_ratios': [1, 1.12]})
    names = ['Duration match', 'Key-rate hedge', 'Covariance hedge']
    methods = ['duration_match', 'key_rate', 'covariance']
    values = [final['final_scores'][m]['rmse'] * 10000 for m in methods]
    axes[0].barh(names, values, color=[MUTED, '#80a8b2', TEAL], height=.54)
    axes[0].invert_yaxis(); axes[0].set_xlim(0, 19)
    for i, v in enumerate(values): axes[0].text(v+.2, i, f'{v:.2f}', va='center', color=TEXT)
    axes[0].set_xlabel('RMSE, bp of initial liability PV')
    axes[0].set_title('84 final monthly hedge tests', loc='left', color=NAVY, fontweight='bold')
    axes[0].text(0, -.31, 'Five-year benchmark: 203.21 bp (not shown).',
                 transform=axes[0].transAxes, fontsize=8.2, color=MUTED)
    rate = next(x for x in case['instantaneous_scenarios']
                if x['method']=='covariance' and x['scenario']=='parallel_-200bp')
    mortality = next(x for x in case['instantaneous_scenarios']
                     if x['method']=='covariance' and x['scenario']=='mortality_force_0.8')
    amounts = [-rate['surplus_usd']/1e6, -mortality['surplus_usd']/1e6]
    axes[1].barh(['200 bp rate fall', 'Mortality force 0.8'], amounts, color=[TEAL, '#c47947'], height=.5)
    axes[1].invert_yaxis();axes[1].set_xlim(0, 8.2)
    for i, v in enumerate(amounts): axes[1].text(v+.12, i, f'{v:.3f}', va='center', color=TEXT)
    axes[1].set_xlabel('Deficit, USD million; fixed covariance assets')
    axes[1].set_title('Separate deterministic current stresses', loc='left', color=NAVY, fontweight='bold')
    axes[1].text(0, -.31, 'Synthetic case; neither axis is a calibrated forecast.',
                 transform=axes[1].transAxes, fontsize=8.2, color=MUTED)
    fig.tight_layout(w_pad=3);fig.subplots_adjust(bottom=.25)
    fig.savefig(REPORT / 'diagnostics.png', dpi=180, facecolor='white')
    fig.savefig(REPORT / 'diagnostics.svg', facecolor='white')
    plt.close(fig)


def markup(text):
    text = html.escape(text)
    text = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    return text


STYLES = {
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=25, leading=29,
                            textColor=colors.HexColor(NAVY), spaceAfter=13),
    'h2': ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=13.2, leading=17,
                         textColor=colors.HexColor(TEAL), spaceBefore=15, spaceAfter=7,
                         keepWithNext=True),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=9.7, leading=14,
                           textColor=colors.HexColor(TEXT), spaceAfter=8,
                           splitLongWords=True, allowWidows=0, allowOrphans=0),
    'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8.1, leading=11.2,
                            textColor=colors.HexColor(TEXT), spaceAfter=4),
    'tablehead': ParagraphStyle('tablehead', fontName='Helvetica-Bold', fontSize=8.1,
                                leading=10.5, textColor=colors.white),
}


def draw_page(canvas, doc):
    width, height = A4
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor(TEAL));canvas.setLineWidth(1)
    canvas.line(43, height-31, width-43, height-31)
    canvas.setFont('Helvetica', 8);canvas.setFillColor(colors.HexColor(MUTED))
    canvas.drawString(43, height-24, 'PRASANNA K  /  TREASURY ALM RESEARCH')
    canvas.drawString(43, 25, '19 October 2026  |  Pinned revised curve vintage; synthetic contracts')
    canvas.drawRightString(width-43, 25, str(doc.page))
    canvas.restoreState()


def build(markdown_name, filename, technical=False):
    styles = dict(STYLES)
    if not technical:
        styles['body'] = ParagraphStyle('brief-body', parent=STYLES['body'],
            fontSize=9.25, leading=12.5, spaceAfter=5)
        styles['h2'] = ParagraphStyle('brief-h2', parent=STYLES['h2'],
            fontSize=12, leading=15, spaceBefore=8, spaceAfter=5)
    lines = (REPORT / markdown_name).read_text().splitlines()
    flow = []; i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1;continue
        if line.startswith('# '):
            flow.append(Paragraph(markup(line[2:]), styles['title']));i += 1;continue
        if line.startswith('## '):
            if technical and line.startswith('## 4.'):
                flow.append(Image(str(REPORT / 'diagnostics.png'), width=508, height=168))
                flow.append(Spacer(1, 8))
            flow.append(Paragraph(markup(line[3:]), styles['h2']));i += 1;continue
        if line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[-: ]+', x) for x in cells): rows.append(cells)
                i += 1
            count = len(rows[0])
            widths = ([178, 330] if count==2 else
                      [118, 176, 214] if count==3 else
                      [126]+[(508-126)/(count-1)]*(count-1))
            cells = [[Paragraph(markup(x), STYLES['tablehead'] if r==0 else STYLES['small'])
                      for x in row] for r, row in enumerate(rows)]
            table = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(NAVY)),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f1f6f7'),colors.white]),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),7 if technical else 5),
                ('BOTTOMPADDING',(0,0),(-1,-1),7 if technical else 5),('LEFTPADDING',(0,0),(-1,-1),7),
                ('RIGHTPADDING',(0,0),(-1,-1),7),
                ('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#c4d7dc'))]))
            flow.extend([table, Spacer(1, 8)]);continue
        paragraph = [line];i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','- ')):
            paragraph.append(lines[i].strip());i += 1
        text = ' '.join(paragraph)
        if text.startswith('- '): text = '&#8226; ' + markup(text[2:])
        else: text = markup(text)
        flow.append(Paragraph(text, styles['body']))
    path = OUTPUT / filename
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=43, leftMargin=43,
        topMargin=46, bottomMargin=44, title='Treasury ALM - '+('Technical report' if technical else 'Decision brief'),
        author='Prasanna K', subject='Interest-rate hedge evaluation, longevity sensitivity and liquidity runoff')
    doc.build(flow, onFirstPage=draw_page, onLaterPages=draw_page)
    pdf = fitz.open(path)
    texts = []
    for n, page in enumerate(pdf):
        text = page.get_text();texts.append(text)
        require_text = 'PRASANNA K' in text and '19 October 2026' in text
        assert require_text, 'Missing page header/footer'
        for block in page.get_text('blocks'):
            x0,y0,x1,y1=block[:4]
            assert x0>=20 and y0>=10 and x1<=A4[0]-15 and y1<=A4[1]-10, (n,block)
        page.get_pixmap(matrix=fitz.Matrix(1.35,1.35)).save(QA / (filename.replace('.pdf','')+f'-{n+1}.png'))
    all_text='\n'.join(texts)
    for token in ('6.50','15.87','59.03','12.34','6.02','0.705'):
        assert token in all_text, ('Missing key result', token)
    assert '119.38' in all_text or '119,380,495.42' in all_text
    assert '\ufffd' not in all_text and len(texts)>=(3 if technical else 1)
    if not technical:
        assert len(texts)==1, 'The decision brief must fit one readable page'
    return {'file':str(path.relative_to(ROOT)), 'pages':len(pdf), 'bytes':path.stat().st_size,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'extracted_key_results_and_page_boundaries_checked':True,
            'rendered_pages':len(pdf), 'visual_review':'pending'}


if __name__ == '__main__':
    final, case = checked_values();figure(final, case)
    records = [build('TECHNICAL_REPORT.md','Treasury_ALM_Technical_Report.pdf',True),
               build('DECISION_MEMO.md','Treasury_ALM_Decision_Brief.pdf')]
    (REPORT/'report_build_verification.json').write_text(json.dumps({'status':'generated; visual review pending',
        'inputs_checked_against_sealed_evidence':True,'outputs':records},indent=2)+'\n')
    print(json.dumps(records))
