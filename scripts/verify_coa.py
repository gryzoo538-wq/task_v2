"""Independent re-check of every deliverable.

Re-reads text PDFs with pypdf (the build used pdftotext), compares the scans against a second visual
reading (scripts/scan_recheck.csv), re-applies rules.md from scratch and cross-checks all files.
Prints PASS/FAIL per check and a total.
"""
import csv
import glob
import html.parser
import os
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import pypdf

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
results = []


def check(name, ok, detail=''):
    results.append(ok)
    print('PASS' if ok else 'FAIL', '|', name, '|', detail)


def num(s):
    m = re.search(r'\d+(?:[.,]\d+)?', s or '')
    return Decimal(m.group(0).replace(',', '.')) if m else None


def mg(s):
    if not s:
        return None
    v = num(s)
    if 'µg' in s:
        v = v / 1000
    elif re.search(r'\d\s*g\b', s):
        v = v * 1000
    return v


def isodate(s):
    m = re.fullmatch(r'(\d\d)/(\d\d)/(\d{4})', s or '')
    return f'{m[3]}-{m[2]}-{m[1]}' if m else (s or '')


# ------------------------------------------------------------ independent PDF read
def after(lines, label, stops):
    i = lines.index(label)
    nxt = lines[i + 1] if i + 1 < len(lines) else ''
    return '' if nxt in stops else nxt


MAL_LABELS = ['Product', 'Declared amount', 'Batch / lot number', 'Test date', 'Method', 'Appearance',
              'Purity (HPLC)', 'Identity: theoretical mass', 'Identity: observed mass (MS)', 'Results']
pdf_rows = []
for f in sorted(glob.glob('coa/*.pdf')):
    name = os.path.basename(f)
    text = pypdf.PdfReader(f).pages[0].extract_text()
    lines = [l.strip() for l in text.splitlines()]
    if not text.strip():
        continue                                        # scans handled below
    if 'Novalab' in text:
        g = lambda lab: after(lines, lab, [])
        pdf_rows.append(dict(pdf=name, product=g('Substance'), size=mg(g('Net content per vial')), batch=g('Lot No.'),
                             date=isodate(g('Date of analysis')), purity=num(g('Assay (HPLC-UV, 214 nm)')),
                             th=num(g('Mass calculated')), ob=num(g('Mass found (ESI-MS)')), valid=True, multi=False))
    elif 'multi-batch' in text:
        th = num(after(lines, 'Identity: theoretical mass', []))
        prod, size = after(lines, 'Product', []), mg(after(lines, 'Declared amount', []))
        for i, l in enumerate(lines):
            if re.fullmatch(r'PP-\d{4}-\d{3}', l):
                pdf_rows.append(dict(pdf=name, product=prod, size=size, batch=l, date=lines[i + 1],
                                     purity=num(lines[i + 2]), th=th, ob=num(lines[i + 3]), valid=True, multi=True))
    else:
        g = lambda lab: after(lines, lab, MAL_LABELS)
        pdf_rows.append(dict(pdf=name, product=g('Product'), size=mg(g('Declared amount')),
                             batch=g('Batch / lot number'), date=g('Test date'), purity=num(g('Purity (HPLC)')),
                             th=num(g('Identity: theoretical mass')), ob=num(g('Identity: observed mass (MS)')),
                             valid=not re.search('VOID|SUPERSEDED', text), multi=False))
first = {r['pdf_file']: r for r in csv.DictReader(open('scripts/scan_readings.csv', encoding='utf-8'))}
second = {r['pdf_file']: r for r in csv.DictReader(open('scripts/scan_recheck.csv', encoding='utf-8'))}
scan_files = sorted(os.path.basename(f) for f in glob.glob('coa/*.pdf')
                    if not pypdf.PdfReader(f).pages[0].extract_text().strip())
check('scanned PDFs (no text layer) = transcribed scans', scan_files == sorted(first) == sorted(second),
      ', '.join(scan_files))
for s in scan_files:
    keys = ['product', 'declared_amount_raw', 'batch', 'test_date_raw', 'purity_raw', 'theoretical_mass_raw',
            'observed_mass_raw', 'stamp']
    diffs = [k for k in keys if first[s][k] != second[s][k]]
    check(f'{s}: first and second visual reading agree', not diffs, ', '.join(diffs) or 'all 8 values equal')
    r = second[s]
    pdf_rows.append(dict(pdf=s, product=r['product'], size=mg(r['declared_amount_raw']), batch=r['batch'],
                         date=r['test_date_raw'], purity=num(r['purity_raw']), th=num(r['theoretical_mass_raw']),
                         ob=num(r['observed_mass_raw']), valid=not r['stamp'], multi=False))
check('25 PDFs in coa/', len(glob.glob('coa/*.pdf')) == 25, str(len(glob.glob('coa/*.pdf'))))

# ------------------------------------------------------------ coa_extracted.csv
ext = list(csv.DictReader(open('coa_extracted.csv', encoding='utf-8')))
check('coa_extracted.csv: one row per PDF row', len(ext) == len(pdf_rows), f'{len(ext)} vs {len(pdf_rows)}')
key = lambda pdf, batch: (pdf, batch)
by = {key(r['pdf'], r['batch']): r for r in pdf_rows}
for e in ext:
    r = by.get(key(e['pdf_file'], e['batch']))
    got = (e['product'], num(e['declared_amount_mg']), e['test_date'], num(e['purity_pct']),
           num(e['theoretical_mass_da']), num(e['observed_mass_da']), e['valid'] == 'yes')
    exp = r and (r['product'], r['size'], r['date'], r['purity'], r['th'], r['ob'], r['valid'])
    check(f"extract {e['pdf_file']} {e['batch'] or '(no batch)'}", got == exp, 'matches independent read' if got == exp else f'{got} vs {exp}')

# ------------------------------------------------------------ expected decisions (rules re-applied)
sheet = list(csv.DictReader(open('products.csv', encoding='utf-8')))
REF, CUR, SOON = date(2026, 9, 30), date(2025, 9, 30), date(2026, 12, 29)
exp = {}
for p in sheet:
    rows = [r for r in pdf_rows if r['product'] == p['Product']]
    good = [r for r in rows if r['valid'] and (not r['multi'] or r['batch'] == p['Batch_Listed'])]
    good.sort(key=lambda r: r['date'] or '', reverse=True)
    c = good[0] if good else None
    batch = (c['batch'] or p['Batch_Listed']) if c else ''
    tdate = (c['date'] or p['Test_Date_Listed']) if c else ''
    pur, size = (c['purity'], c['size']) if c else (None, None)
    if not rows:
        reason = 'no COA'
    elif not c:
        reason = 'no COA for listed batch'
    elif not (batch and tdate and pur is not None and size is not None):
        reason = 'missing field'
    elif size != Decimal(p['Size_mg']):
        reason = 'size conflict'
    elif pur < Decimal('98.0'):
        reason = 'purity below 98.0'
    elif abs(c['ob'] - c['th']) > Decimal('1.0'):
        reason = 'identity failed'
    elif date.fromisoformat(tdate) < CUR:
        reason = 'COA older than 12 months'
    else:
        reason = ''
    exp[p['SKU']] = dict(p=p, c=c, rows=rows, batch=batch, date=tdate, purity=pur, size=size, reason=reason,
                         status='draft' if reason else 'publish',
                         url=f"https://example-store.test/coa/{p['SKU'].lower()}-{batch.lower()}/" if c and batch else '')

# ------------------------------------------------------------ woocommerce_import.csv
imp = list(csv.DictReader(open('woocommerce_import.csv', encoding='utf-8')))
check('import: exactly 24 rows', len(imp) == 24, str(len(imp)))
check('import: columns', list(imp[0]) == ['SKU', 'Name', 'Regular price', 'Status', 'coa_batch', 'coa_test_date',
                                          'coa_purity', 'coa_size_mg', 'coa_pdf', 'coa_url', 'status_reason'])
check('import: SKUs and order match sheet', [r['SKU'] for r in imp] == [p['SKU'] for p in sheet])
for r in imp:
    e = exp[r['SKU']]
    got = (r['Name'], r['Regular price'], r['Status'], r['coa_batch'], r['coa_test_date'], num(r['coa_purity']),
           num(r['coa_size_mg']), r['coa_pdf'], r['coa_url'])
    want = (e['p']['Product'], e['p']['Price_USD'], e['status'], e['batch'], e['date'], e['purity'], e['size'],
            e['c']['pdf'] if e['c'] else '', e['url'])
    check(f"{r['SKU']} all import values", got == want, f"{r['Status']}, {r['coa_pdf'] or 'no COA'}" if got == want else f'{got} != {want}')
    want_reason = e['reason'] or 'all publish conditions met'
    check(f"{r['SKU']} status_reason", r['status_reason'] == want_reason, r['status_reason'])
    if r['coa_batch']:
        check(f"{r['SKU']} batch pattern", bool(re.fullmatch(r'PP-\d{4}-\d{3}', r['coa_batch'])), r['coa_batch'])
    check(f"{r['SKU']} URL blank only if batch missing or no COA", (r['coa_url'] == '') == (not r['coa_batch'] or not r['coa_pdf']))

pub = [r for r in imp if r['Status'] == 'publish']
drafts = [r for r in imp if r['Status'] == 'draft']
mean = (sum(Decimal(r['coa_purity']) for r in pub) / len(pub)).quantize(Decimal('0.01'), ROUND_HALF_UP)
raw_mean = sum(Decimal(r['coa_purity']) for r in pub) / len(pub)


# ------------------------------------------------------------ coa_library.html
class Lib(html.parser.HTMLParser):
    def __init__(s):
        super().__init__(); s.rows, s.links, s.spans, s.cell, s.row, s.span = [], [], {}, None, None, None
    def handle_starttag(s, t, a):
        a = dict(a)
        if t == 'tr': s.row = []
        if t == 'td': s.cell = ''
        if t == 'a': s.links.append(a['href'])
        if t == 'span': s.span = a.get('id')
    def handle_endtag(s, t):
        if t == 'td': s.row.append(s.cell); s.cell = None
        if t == 'tr' and s.row: s.rows.append(s.row)
        if t == 'span': s.span = None
    def handle_data(s, d):
        if s.cell is not None: s.cell += d
        if s.span: s.spans[s.span] = d


lib = Lib(); lib.feed(open('coa_library.html', encoding='utf-8').read())
order = sorted(pub, key=lambda r: r['coa_test_date'], reverse=True)
check('library: row count = published count', len(lib.rows) == len(pub), f'{len(lib.rows)} vs {len(pub)}')
check('library: only published products', {r[0] for r in lib.rows} == {r['Name'] for r in pub})
check('library: newest test date first', [r[2] for r in lib.rows] == [r['coa_test_date'] for r in order],
      ' > '.join(r[2] for r in lib.rows))
for row, r, link in zip(lib.rows, order, lib.links):
    ok = row == [r['Name'], r['coa_batch'], r['coa_test_date'], f"{r['coa_purity']} %"] + [r['coa_pdf']] \
         and link == 'coa/' + r['coa_pdf'] and os.path.exists(link)
    check(f"library row {r['SKU']} = import row, link exists", ok, link)
check('teaser: count = published in import', lib.spans.get('published-count') == str(len(pub)), lib.spans.get('published-count'))
check('teaser: mean purity (2 dp, half-up) = import', lib.spans.get('mean-purity') == str(mean),
      f"{lib.spans.get('mean-purity')} (exact mean {raw_mean})")

# ------------------------------------------------------------ retest_schedule.csv
rs = list(csv.DictReader(open('retest_schedule.csv', encoding='utf-8')))
check('retest: columns', list(rs[0]) == ['SKU', 'Name', 'test_date', 'retest_due', 'days_remaining', 'due_soon'])
check('retest: exactly the published products', sorted(r['SKU'] for r in rs) == sorted(r['SKU'] for r in pub), f'{len(rs)} rows')
for r in rs:
    t = date.fromisoformat(r['test_date'])
    due = date(t.year + 1, t.month, t.day)
    ok = (r['test_date'] == next(i['coa_test_date'] for i in imp if i['SKU'] == r['SKU']) and r['retest_due'] == due.isoformat()
          and int(r['days_remaining']) == (due - REF).days and r['due_soon'] == ('yes' if due <= SOON else 'no'))
    check(f"retest {r['SKU']} due/days/flag", ok, f"{r['retest_due']}, {r['days_remaining']} d, due_soon={r['due_soon']}")
check('retest: sorted by due date', [r['retest_due'] for r in rs] == sorted(r['retest_due'] for r in rs))
soon = {r['SKU'] for r in rs if r['due_soon'] == 'yes'}

# ------------------------------------------------------------ featured_products.md
cand = sorted([r for r in pub if r['SKU'] not in soon],
              key=lambda r: (-Decimal(r['coa_purity']), -date.fromisoformat(r['coa_test_date']).toordinal(), r['SKU']))[:3]
fm = open('featured_products.md', encoding='utf-8').read()
frows = re.findall(r'^\| (\d) \| (P\d\d) \| ([^|]+) \| ([\d.]+) % \| ([\d-]+) \|', fm, re.M)
check('featured: 3 products, rule-14 order', [f[1] for f in frows] == [r['SKU'] for r in cand], ', '.join(f[1] for f in frows))
for f, r in zip(frows, cand):
    check(f'featured {f[1]} purity/date = import', (f[3], f[4]) == (r['coa_purity'], r['coa_test_date']) and f[1] not in soon)

# ------------------------------------------------------------ client_email.md
em = open('client_email.md', encoding='utf-8').read()
erows = re.findall(r'^\| (P\d\d) \| ([^|]+) \| ([\d.]+) \| ([^|]+) \| ([^|]+) \|', em, re.M)
check('email: every draft, SKU order', [e[0] for e in erows] == [r['SKU'] for r in drafts], ', '.join(e[0] for e in erows))
ACT = {'no COA': 'send the COA PDF', 'no COA for listed batch': 'send the COA that covers the listed batch',
       'missing field': 'send the missing field', 'size conflict': 'confirm the price for the size printed on the COA',
       'purity below 98.0': 'send a new COA or confirm the batch is withdrawn',
       'identity failed': 'send a new identity (MS) result', 'COA older than 12 months': 'send a current COA'}
for e in erows:
    r = next(i for i in imp if i['SKU'] == e[0])
    ok = e[3].strip().startswith(r['status_reason'] + ' (') and e[5 - 1].strip().lower().startswith(ACT[r['status_reason']].lower()) \
         and e[2] == r['Regular price']
    if r['status_reason'] == 'no COA for listed batch':
        ok = ok and exp[e[0]]['p']['Batch_Listed'] in e[4]
    check(f'email {e[0]} reason/action/price', ok, f"{r['status_reason']} -> {e[4].strip()}")
total = sum(Decimal(r['Regular price']) for r in drafts)
check('email: published count', f'**Published products:** {len(pub)}' in em, str(len(pub)))
check('email: draft count', f'**Draft products:** {len(drafts)}' in em, str(len(drafts)))
check('email: draft total USD', f'USD {total:.2f}' in em, f'USD {total:.2f}')

# ------------------------------------------------------------ exceptions_report.md
rep = open('exceptions_report.md', encoding='utf-8').read()
rrows = [l.split(' | ') for l in rep.splitlines() if re.match(r'\| P\d\d \|', l)]
in_rep = {r[0].strip('| ') for r in rrows}
need, detail = set(), {}
for sku, e in exp.items():
    p, c, why = e['p'], e['c'], []
    if c and (not c['batch'] and p['Batch_Listed'] or not c['date'] and p['Test_Date_Listed']):
        why.append('from sheet')
    if c:
        for lab, cv, sv in (('batch', c['batch'], p['Batch_Listed']), ('test date', c['date'], p['Test_Date_Listed']),
                            ('purity', c['purity'], Decimal(p['Purity_Listed_pct'])), ('size', c['size'], Decimal(p['Size_mg']))):
            if cv not in (None, '') and sv not in (None, '') and cv != sv:
                why.append(f'disagree on {lab}')
    if len({r['pdf'] for r in e['rows']}) > 1 or any(not r['valid'] for r in e['rows']) or (e['rows'] and not c):
        why.append('several/ignored COA')
    if e['status'] == 'draft':
        why.append('draft')
    if why:
        need.add(sku); detail[sku] = why
check('exceptions: exactly the non-clean products', in_rep == need, f'need {sorted(need)}; report {sorted(in_rep)}')
for sku, why in sorted(detail.items()):
    text = ' '.join(' | '.join(r) for r in rrows if r[0].strip('| ') == sku)
    for w in why:
        if w == 'from sheet':
            ok = '"from sheet"' in text
        elif w.startswith('disagree'):
            ok = w in text
        elif w == 'draft':
            ok = f"Draft: {exp[sku]['reason']} (" in text
        else:
            ok = 'Rule 4' in text or 'Rule 5' in text or 'Rule 7' in text
        check(f'exceptions {sku}: {w}', ok)

print(f'\nTOTAL {len(results)} checks, {results.count(False)} failed')
print(f'published={len(pub)} drafts={len(drafts)} mean={mean} (exact {raw_mean}) draft_total=USD {total:.2f} '
      f'featured={[r["SKU"] for r in cand]}')
