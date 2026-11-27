"""Render the fixed research draft with ReportLab; use the bundled document runtime."""
from collections import Counter
from html import escape
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'output/pdf/nepali_english_asr_research_report_draft.pdf'
SOURCE = ROOT / 'reports/research_report_draft.md'
VERSION = '0.6'
REPORT_DATE = '27 November 2026'


def verify_structure(text):
    if not text.startswith('<!-- cover -->') or text.count('<!-- contents -->') != 1:
        raise ValueError('Report requires one cover and one generated contents page.')
    for heading in ['## Plain-language summary', '## Abstract',
                    '## Appendix A Exact versions and review provenance',
                    '## Appendix B Reproduction and release status',
                    '## Appendix C Glossary and how to read the scores']:
        if heading not in text:
            raise ValueError(f'Report reader structure is incomplete: {heading}')
    main_text = text.split('## Appendix A ')[0]
    visible_text = re.sub(r'https://[^\s)]+', '', main_text)
    if re.search(r'\b[a-f0-9]{40,64}\b', visible_text):
        raise ValueError('Long revision IDs and checksums belong in the technical appendix.')


def verify_numbers(text):
    cmi_bytes = (ROOT / 'results/metrics/cmi_analysis_20261116.json').read_bytes()
    result = json.loads(cmi_bytes)
    # Every printed band score and denominator is checked against saved edit counts.
    for band, group in result['bands'].items():
        scores = [f"{100 * group['systems'][s][m]:.2f}%" for m in ['wer', 'cer'] for s in ['local', 'whisper_api']]
        expected = f"| {band} | {group['clips']:,} | {group['videos']} | {group['systems']['local']['reference_words']:,} | " + ' | '.join(scores) + ' |'
        if expected not in text:
            raise ValueError(f'Report band table differs: {band}')
    for system in ['local', 'whisper_api']:
        score = result['overall']['systems'][system]
        label = 'Local Whisper Large V2' if system == 'local' else 'Hosted Whisper API'
        summary_row = f"| {label} | {100*score['wer']:.2f}% | {100*score['cer']:.2f}% |"
        if summary_row not in text:
            raise ValueError('Report plain-language summary scores differ.')
        for field in ['wer', 'cer']:
            if f'{100 * score[field]:.2f}%' not in text:
                raise ValueError('Report overall score differs.')
        for field in ['wer', 'cer']:
            if f"{result['overall']['spearman'][f'cmi_vs_{system}_{field}']:.4f}" not in text:
                raise ValueError('Report association differs.')
    uncertainty_bytes = (ROOT / 'results/metrics/paired_uncertainty_20261119.json').read_bytes()
    verified = json.loads((ROOT / 'results/metrics/paired_uncertainty_20261119_verified.json').read_bytes())
    comparison_bytes = (ROOT / 'results/metrics/audited_reference_comparison_20261116.json').read_bytes()
    if (not verified['passed'] or hashlib.sha256(uncertainty_bytes).hexdigest() != verified['result_sha256']
            or hashlib.sha256(cmi_bytes).hexdigest() != verified['cmi_analysis_sha256']
            or hashlib.sha256(comparison_bytes).hexdigest() != verified['reference_comparison_sha256']):
        raise ValueError('Report inputs differ from verified uncertainty results.')
    uncertainty = json.loads(uncertainty_bytes)
    if any(uncertainty['source_sha256'][k] != v for k, v in result['source_sha256'].items()):
        raise ValueError('CMI and uncertainty input provenance differs.')
    def interval(values):
        return f'[{values[0]:+.2f}, {values[1]:+.2f}]'
    for name, group in {'Overall': uncertainty['overall'], **uncertainty['bands']}.items():
        gaps, limits = group['local_minus_api_pp'], group['interval_95_pp']
        expected = (f"| {name} | {group['clips']} | {group['videos']} | {gaps['wer']:+.2f} | "
                    f"{interval(limits['wer'])} | {gaps['cer']:+.2f} | {interval(limits['cer'])} |")
        if expected not in text:
            raise ValueError(f'Report uncertainty table differs: {name}')
    for condition, group in uncertainty['audit_sensitivity'].items():
        point = group['overall']
        expected = f"{point['local_minus_api_pp']['wer']:+.2f} pp with {condition} references, interval {interval(point['interval_95_pp']['wer'])}"
        if expected not in text:
            raise ValueError('Report audit interval differs.')
    ranges = uncertainty['influence']['leave_one_video_out_range_pp']
    expected = (f"WER gaps between {ranges['wer'][0]:+.2f} and {ranges['wer'][1]:+.2f} pp, "
                f"and CER gaps between {ranges['cer'][0]:+.2f} and {ranges['cer'][1]:+.2f} pp.")
    if expected not in text:
        raise ValueError('Report influence range differs.')
    follow_up = json.loads((ROOT / 'results/metrics/review_follow_up_20261123.json').read_bytes())
    qualitative_bytes = (ROOT / 'data/annotations/error_examples_20261120.json').read_bytes()
    variants_bytes = (ROOT / 'data/annotations/word_variants_20261122.json').read_bytes()
    variant_result = json.loads((ROOT / 'results/metrics/variant_sensitivity_20261122.json').read_bytes())
    verified_variant = follow_up['variant_result']
    # A rerun can have a new computation date; every other field must still match.
    variant_content = {k: v for k, v in variant_result.items() if k != 'computed_on'}
    verified_content = {k: v for k, v in verified_variant.items() if k != 'computed_on'}
    if (hashlib.sha256(qualitative_bytes).hexdigest() != follow_up['qualitative_annotation_sha256']
            or hashlib.sha256(variants_bytes).hexdigest() != follow_up['variant_annotation_sha256']
            or variant_content != verified_content
            or not follow_up['numerical_counts_verified']
            or follow_up['independent_shortest_path_checks'] != 40):
        raise ValueError('Report diagnostic inputs differ from verified follow-up records.')
    for name, expected_hash in follow_up['protected_source_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f'Report frozen diagnostic source differs: {name}')
    qualitative = json.loads(qualitative_bytes)
    if len(qualitative['reviews']) != 10 or any(
            r['status'] != 'reviewed' or r.get('listened') is not True for r in qualitative['reviews']):
        raise ValueError('Report qualitative review is incomplete.')
    categories = {'script_or_spelling_difference': 'Script or spelling difference',
                  'missing_speech': 'Missing speech', 'wrong_language_output': 'Wrong language output',
                  'wrong_word': 'Wrong word', 'extra_or_repeated_text': 'Extra or repeated text',
                  'no_clear_error': 'No clear error', 'uncertain': 'Uncertain category'}
    counts = {s: Counter(c for r in qualitative['reviews'] for c in r['systems'][s]['categories'])
              for s in ['local', 'whisper_api']}
    for category, label in categories.items():
        if f"| {label} | {counts['local'][category]} | {counts['whisper_api'][category]} |" not in text:
            raise ValueError('Report qualitative category table differs.')
    variants = json.loads(variants_bytes)
    decisions = Counter(d for r in variants['reviews'] for d in r['decisions'].values())
    expected = (f"Current decisions are {decisions['same']} same, {decisions['different']} different, "
                f"{decisions['reference_issue']} reference/alignment issue and {decisions['unsure']} unsure.")
    if expected not in text or dict(decisions) != variant_result['pair_decision_counts']:
        raise ValueError('Report variant decision counts differ.')
    for system, label in [('local', 'Local Large V2'), ('whisper_api', 'Hosted whisper-1')]:
        values = variant_result['systems'][system]
        strict, tolerant = values['strict'], values['approved_variants_only']
        expected = (f"| {label} | {strict['word_errors']} / {strict['reference_words']} | {100*strict['wer']:.2f}% | "
                    f"{tolerant['word_errors']} / {tolerant['reference_words']} | {100*tolerant['wer']:.2f}% |")
        if expected not in text:
            raise ValueError('Report variant score table differs.')
    if len(result['per_clip']) != 1198:
        raise ValueError('Unexpected report population.')
    verify_extension_numbers(text)
    verify_structure(text)


def verify_extension_numbers(text):
    receipt = json.loads((ROOT / 'results/metrics/report_extension_inputs_20261127_verified.json').read_bytes())
    for name, expected in receipt['files_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Report extension inputs differ from their checked receipt.')
    for name, expected in receipt['result_content_sha256'].items():
        content = json.loads((ROOT / name).read_bytes())
        content.pop('computed_at_utc', None)
        encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        if hashlib.sha256(encoded).hexdigest() != expected:
            raise ValueError('Report extension result content differs from its checked receipt.')
    specialist = json.loads((ROOT / 'results/metrics/codemix_turbo_comparison_20261127.json').read_bytes())
    verified = json.loads((ROOT / 'results/metrics/test_codemix_turbo_20261127_verified.json').read_bytes())
    if verified['coverage'] != {'expected': 1198, 'received': 1198, 'complete': True}:
        raise ValueError('Report specialist coverage differs.')
    scores = specialist['specialist_scores']
    if any(scores[k] != v for k, v in verified['independent_edit_counts'].items()):
        raise ValueError('Report specialist counts differ from independent verification.')
    expected = f"| Code-mix-specialized Large V3 Turbo | {100*scores['wer']:.2f}% | {100*scores['cer']:.2f}% |"
    if expected not in text:
        raise ValueError('Report specialist summary scores differ.')
    expected = f"| Code-mix specialist | {scores['word_errors']:,} | {100*scores['wer']:.2f}% | {scores['character_errors']:,} | {100*scores['cer']:.2f}% |"
    if expected not in text:
        raise ValueError('Report specialist edit-count table differs.')
    for band, group in specialist['bands'].items():
        s = group['specialist']
        if f"| {band} | {group['clips']} | {100*s['wer']:.2f}% | {100*s['cer']:.2f}% |" not in text:
            raise ValueError('Report specialist CMI table differs.')
    for key, label in [('automatic_local', 'Specialist minus local'), ('automatic_api', 'Specialist minus hosted')]:
        g = specialist['comparisons'][key]
        d, i = g['specialist_minus_baseline_pp'], g['interval_95_pp']
        expected = f"| {label} | {d['wer']:+.2f} | [{i['wer'][0]:+.2f}, {i['wer'][1]:+.2f}] | {d['cer']:+.2f} | [{i['cer'][0]:+.2f}, {i['cer'][1]:+.2f}] |"
        if expected not in text:
            raise ValueError('Report specialist uncertainty table differs.')
    for metric in ['wer', 'cer']:
        expected = f"| CMI versus specialist {metric.upper()} | {specialist['spearman']['cmi_vs_'+metric]:+.4f} |"
        if expected not in text:
            raise ValueError('Report specialist correlation differs.')
    a, b = [specialist['audit_sensitivity'][v]['automatic_local']['specialist'] for v in ['published', 'corrected']]
    expected = f"| Code-mix specialist | {100*a['wer']:.2f}% | {100*b['wer']:.2f}% | {100*a['cer']:.2f}% | {100*b['cer']:.2f}% |"
    if expected not in text:
        raise ValueError('Report specialist reference sensitivity differs.')
    forced = json.loads((ROOT / 'results/metrics/forced_ne_comparison_20261124.json').read_bytes())
    for key, label in [('local', 'Local Large V2'), ('whisper_api', 'Hosted whisper-1')]:
        s = forced['overall']['systems'][key]
        i = s['interval_95_pp']['wer']
        expected = f"| {label} | {100*s['auto']['wer']:.2f}% | {100*s['forced_ne']['wer']:.2f}% | {s['forced_minus_auto_pp']['wer']:+.2f} | [{i[0]:+.2f}, {i[1]:+.2f}] |"
        if expected not in text:
            raise ValueError('Report forced-language sensitivity differs.')
    audit = json.loads((ROOT / 'results/metrics/codemix_training_overlap_audit_20261127.json').read_bytes())
    counts = Counter(row['evidence'] for row in audit['per_clip_evidence'])
    for key, label in [('unique_public_test_candidate', 'Unique normalized-text and duration candidate'),
                       ('no_exact_public_test_candidate', 'No exact candidate'),
                       ('ambiguous_public_test_candidates', 'Ambiguous candidates')]:
        if f'| {label} | {counts[key]} |' not in text:
            raise ValueError('Report overlap evidence counts differ.')
    if (len(audit['per_clip_evidence']) != 1198 or audit['number_of_our_clips_in_author_training'] is not None
            or '**Training exclusion remains unverified.**' not in text
            or 'exploratory' not in text.lower()):
        raise ValueError('Report must retain the unresolved training-exclusion disclosure.')


def markup(text):
    text = escape(text)
    text = re.sub(r'\[([^\]]+)\]\((https://[^)]+)\)', r'<link href="\2" color="#1769aa">\1</link>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    return text.replace('`', '')


def main():
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.platypus.tableofcontents import TableOfContents

    class ResearchDocTemplate(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            if hasattr(flowable, 'toc_entry'):
                level, label, key = flowable.toc_entry
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(label, key, level=level, closed=False)
                self.notify('TOCEntry', (level, escape(label), self.page, key))

    text = SOURCE.read_text(encoding='utf-8')
    verify_numbers(text)
    for name, filename in [('Body', 'arial.ttf'), ('Body-Bold', 'arialbd.ttf'), ('Body-Italic', 'ariali.ttf'), ('Body-BoldItalic', 'arialbi.ttf')]:
        pdfmetrics.registerFont(TTFont(name, str(Path('C:/Windows/Fonts') / filename)))
    pdfmetrics.registerFontFamily('Body', normal='Body', bold='Body-Bold', italic='Body-Italic', boldItalic='Body-BoldItalic')
    styles = {
        'body': ParagraphStyle('body', fontName='Body', fontSize=10.2, leading=14.3, spaceAfter=8, alignment=TA_LEFT),
        'title': ParagraphStyle('title', fontName='Body-Bold', fontSize=24, leading=29, spaceAfter=14),
        'h2': ParagraphStyle('h2', fontName='Body-Bold', fontSize=14, leading=18, textColor=colors.HexColor('#17334c'), spaceBefore=10, spaceAfter=9, keepWithNext=True),
        'h3': ParagraphStyle('h3', fontName='Body-Bold', fontSize=11, leading=15, spaceBefore=8, spaceAfter=7, keepWithNext=True),
        'cell': ParagraphStyle('cell', fontName='Body', fontSize=8.2, leading=11),
        'cover_title': ParagraphStyle('cover_title', fontName='Body-Bold', fontSize=31, leading=37,
                                     textColor=colors.HexColor('#17334c'), spaceAfter=20),
        'cover_subtitle': ParagraphStyle('cover_subtitle', fontName='Body', fontSize=17, leading=23,
                                        textColor=colors.HexColor('#267a83'), spaceAfter=25),
        'cover_body': ParagraphStyle('cover_body', fontName='Body', fontSize=11.5, leading=17, spaceAfter=15),
        'eyebrow': ParagraphStyle('eyebrow', fontName='Body-Bold', fontSize=9, leading=13,
                                 textColor=colors.HexColor('#267a83'), spaceAfter=25),
        'summary': ParagraphStyle('summary', fontName='Body', fontSize=10.8, leading=15.2, spaceAfter=9),
        'glossary': ParagraphStyle('glossary', fontName='Body', fontSize=9, leading=12),
    }
    width = A4[0] - 100
    story = []
    cover = False
    summary = False
    heading_number = 0
    blocks = re.split(r'\n\s*\n', text.strip())
    for block in blocks:
        if block == '<!-- cover -->':
            cover = True
            story.extend([Spacer(1, 60), Paragraph('INDEPENDENT RESEARCH REPORT', styles['eyebrow'])])
        elif block == '<!-- contents -->':
            toc = TableOfContents()
            toc.tableStyle = TableStyle([
                ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ])
            toc.levelStyles = [
                ParagraphStyle('toc_main', fontName='Body-Bold', fontSize=10.2, leading=13,
                               spaceBefore=5, leftIndent=0, firstLineIndent=0),
                ParagraphStyle('toc_sub', fontName='Body', fontSize=9.2, leading=12,
                               spaceBefore=0, leftIndent=13, firstLineIndent=0),
            ]
            story.append(toc)
        elif block == '<!-- pagebreak -->':
            story.append(PageBreak())
            cover = False
            summary = False
        elif block.startswith('# '):
            story.append(Paragraph(markup(block[2:]), styles['cover_title' if cover else 'title']))
        elif block.startswith(('## ', '### ')):
            level = 1 if block.startswith('### ') else 0
            label = block[4:] if level else block[3:]
            if label == 'Plain-language summary':
                summary = True
            style = 'cover_subtitle' if cover else ('h3' if level else 'h2')
            heading = Paragraph(markup(label), styles[style])
            if not cover and label != 'Contents':
                heading_number += 1
                heading.toc_entry = (level, label, f'heading-{heading_number}')
            story.append(heading)
        elif block.startswith('|'):
            lines = block.splitlines()
            cells = [line.strip('|').split('|') for line in lines if not re.match(r'^\|[\s:|\-]+\|$', line)]
            count = len(cells[0])
            widths = [width/count] * count
            if count in [2, 3]:
                widths = [width * .48] + [width * .52/(count-1)] * (count-1)
            glossary = cells[0][0].strip() == 'Term'
            if glossary:
                widths = [width * .26, width * .74]
            if cover:
                widths = [width/count] * count
            cell_style = styles['cover_body' if cover else ('glossary' if glossary else 'cell')]
            content = [[Paragraph(markup(cell.strip()), cell_style) for cell in row] for row in cells]
            table = Table(content, colWidths=widths, hAlign='LEFT', repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9eff4')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('TOPPADDING', (0, 0), (-1, -1), 3 if glossary else 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3 if glossary else 6),
                ('LINEBELOW', (0, 0), (-1, 0), .6, colors.HexColor('#aab8c3')),
                ('LINEBELOW', (0, 1), (-1, -1), .3, colors.HexColor('#dbe2e8'))]))
            block = [table, Spacer(1, 10)]
            story.extend([KeepTogether(block)] if len(cells) <= 10 else block)
        elif block.startswith('!['):
            match = re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)', block)
            path = (SOURCE.parent / match[2]).resolve()
            image = Image(str(path))
            image.drawWidth, image.drawHeight = width, width * image.imageHeight / image.imageWidth
            assert image.drawWidth == width and image.drawHeight < A4[1] - 100
            image.hAlign = 'CENTER'
            story.extend([image, Spacer(1, 6)])
        else:
            style = 'cover_body' if cover else ('summary' if summary else 'body')
            story.append(Paragraph(markup(block.replace('\n', ' ')), styles[style]))

    def frame(canvas, doc):
        canvas.saveState()
        canvas.setFont('Body', 8)
        canvas.setFillColor(colors.HexColor('#596978'))
        if doc.page == 1:
            canvas.setFillColor(colors.HexColor('#267a83'))
            canvas.rect(50, A4[1]-75, 52, 4, fill=1, stroke=0)
            canvas.setFillColor(colors.HexColor('#596978'))
        else:
            canvas.drawString(50, A4[1]-30, 'NEPALI ENGLISH ASR  /  RESEARCH REPORT')
        canvas.drawString(50, 27, f'Sanskar Ananta Tiwari  |  Revised report v{VERSION}  |  {REPORT_DATE}')
        canvas.drawRightString(A4[0]-50, 27, str(doc.page))
        canvas.restoreState()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = ResearchDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=50, rightMargin=50, topMargin=51, bottomMargin=46,
                            title='Code Mixing and Transcription Errors in Nepali English Speech',
                            author='Sanskar Ananta Tiwari', subject='General and specialized Whisper systems; exploratory source-bounded evaluation')
    doc.multiBuild(story, onFirstPage=frame, onLaterPages=frame)
    print(OUTPUT)


if __name__ == '__main__':
    main()
