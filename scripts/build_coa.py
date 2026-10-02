"""Build all COA deliverables from coa/*.pdf, products.csv and rules.md (version 2).

Text-layer PDFs are parsed with pdftotext. Scanned PDFs have no text layer; their
values were read visually and transcribed into scripts/scan_readings.csv.
"""
import csv
import glob
import html
import os
import re
import subprocess
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
os.chdir(ROOT)

REF = date(2026, 9, 30)
CURRENT_FROM = date(2025, 9, 30)
DUE_SOON_BY = date(2026, 12, 29)
URL = 'https://example-store.test/coa/{}-{}/'
REASONS = ['no COA', 'no COA for listed batch', 'missing field', 'size conflict',
           'purity below 98.0', 'identity failed', 'COA older than 12 months']
ACTIONS = {
    'no COA': 'send the COA PDF',
    'no COA for listed batch': 'send the COA that covers the listed batch ({batch})',
    'missing field': 'send the missing field ({fields}) or a corrected COA',
    'size conflict': 'confirm the price for the size printed on the COA ({size} mg)',
    'purity below 98.0': 'send a new COA or confirm the batch is withdrawn',
    'identity failed': 'send a new identity (MS) result',
    'COA older than 12 months': 'send a current COA',
}


# ---------------------------------------------------------------- reading
def dec(s):
    """'99,5 %' / '1815.1 Da' -> Decimal, '' -> None (rule 3: decimal comma to point)."""
    m = re.search(r'\d+(?:[.,]\d+)?', s or '')
    return Decimal(m.group(0).replace(',', '.')) if m else None


def to_mg(s):
    """Rule 3: convert µg / mg / g to mg."""
    if not s:
        return None
    v, unit = dec(s), re.search(r'(µg|ug|mg|g)\b', s).group(1)
    mg = {'µg': v / 1000, 'ug': v / 1000, 'mg': v, 'g': v * 1000}[unit]
    return Decimal(format(mg.normalize(), 'f'))  # plain notation: 50, not 5E+1


def iso(s):
    """Rule 1/2: YYYY-MM-DD stays; DD/MM/YYYY (Novalab) becomes YYYY-MM-DD."""
    if not s:
        return ''
    m = re.fullmatch(r'(\d{2})/(\d{2})/(\d{4})', s)
    return f'{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else s


def field(txt, label):
    m = re.search(r'^[ \t]*' + re.escape(label) + r'[ \t]*(.*)$', txt, re.M)
    return m.group(1).strip() if m else ''


def text_rows(path):
    txt = subprocess.run(['pdftotext', '-layout', path, '-'], capture_output=True, text=True).stdout
    name = os.path.basename(path)
    if 'Novalab' in txt:
        return [dict(lab='NVL', report_id=field(txt, 'Ref.'), report_type='', product=field(txt, 'Substance'),
                     size_raw=field(txt, 'Net content per vial'), batch=field(txt, 'Lot No.'),
                     date_raw=field(txt, 'Date of analysis'), purity_raw=field(txt, 'Assay (HPLC-UV, 214 nm)'),
                     th_raw=field(txt, 'Mass calculated'), ob_raw=field(txt, 'Mass found (ESI-MS)'),
                     multi=False, stamp='', source='text layer')]
    base = dict(lab='MAL', report_id=field(txt, 'Report ID:'), report_type=field(txt, 'Report type:'),
                product=field(txt, 'Product'), size_raw=field(txt, 'Declared amount'), stamp='', source='text layer')
    if 'multi-batch' in txt:
        th = field(txt, 'Identity: theoretical mass')
        rows = []
        for b, d, p, o in re.findall(r'^\s*(PP-\d{4}-\d{3})\s+(\S+)\s+([\d.,]+ %)\s+([\d.,]+ Da)', txt, re.M):
            rows.append(dict(base, batch=b, date_raw=d, purity_raw=p, th_raw=th, ob_raw=o, multi=True))
        return rows
    return [dict(base, batch=field(txt, 'Batch / lot number'), date_raw=field(txt, 'Test date'),
                 purity_raw=cell(field(txt, 'Purity (HPLC)')), th_raw=cell(field(txt, 'Identity: theoretical mass')),
                 ob_raw=cell(field(txt, 'Identity: observed mass (MS)')), multi=False)]


def cell(s):
    """Result cell only, without the Notes column ('99.2 %   Area-normalised' -> '99.2 %')."""
    return re.split(r'\s{2,}', s)[0] if s else ''


def scan_rows():
    out = {}
    for r in csv.DictReader(open('scripts/scan_readings.csv', encoding='utf-8')):
        out[r['pdf_file']] = [dict(lab='MAL', report_id=r['pdf_file'][:-4], report_type=r['report_type'],
                                   product=r['product'], size_raw=r['declared_amount_raw'], batch=r['batch'],
                                   date_raw=r['test_date_raw'], purity_raw=r['purity_raw'],
                                   th_raw=r['theoretical_mass_raw'], ob_raw=r['observed_mass_raw'],
                                   multi=False, stamp=r['stamp'], source='scan (read visually)')]
    return out


def has_text(path):
    return bool(subprocess.run(['pdftotext', path, '-'], capture_output=True, text=True).stdout.strip())


scans = scan_rows()
coa_rows = []
for f in sorted(glob.glob('coa/*.pdf')):
    name = os.path.basename(f)
    rows = text_rows(f) if has_text(f) else scans[name]
    for r in rows:
        r.update(pdf=name, size=to_mg(r['size_raw']), date=iso(r['date_raw']), purity=dec(r['purity_raw']),
                 th=dec(r['th_raw']), ob=dec(r['ob_raw']))
        r['valid'] = not re.search(r'VOID|SUPERSEDED', r['stamp'], re.I)  # rule 4
        coa_rows.append(r)

# ---------------------------------------------------------------- reconcile
sheet = list(csv.DictReader(open('products.csv', encoding='utf-8')))
covered_by = {}   # pdf row id -> SKU, filled below for coa_extracted notes
decisions = []
for p in sheet:
    sku, name = p['SKU'], p['Product']
    issues = []   # (issue, rule, action)
    all_rows = [r for r in coa_rows if r['product'] == name]
    for r in all_rows:
        if not r['valid']:
            issues.append((f"{r['pdf']} is stamped \"{r['stamp']}\" (tested {r['date']}, purity {r['purity']} %).",
                           'Rule 4 (VOID/SUPERSEDED COA is invalid)', 'COA ignored completely.'))
    valid = [r for r in all_rows if r['valid']]
    usable = [r for r in valid if not r['multi'] or r['batch'] == p['Batch_Listed']]   # rule 5
    for pdf in sorted({r['pdf'] for r in valid if r['multi']}):
        rows = [r for r in valid if r['pdf'] == pdf]
        hit = [r for r in rows if r['batch'] == p['Batch_Listed']]
        listed = ', '.join(r['batch'] for r in rows)
        if not hit:
            issues.append((f"Multi-batch COA {pdf} lists {listed}; none equals the listed batch {p['Batch_Listed']}.",
                           'Rule 5 (multi-batch COA: only the row matching Batch_Listed)',
                           'COA does not cover this product; ignored.'))
    chosen = None
    if usable:
        usable.sort(key=lambda r: r['date'] or '0000-00-00', reverse=True)   # rule 7
        chosen = usable[0]
        if len({r['pdf'] for r in usable}) > 1:
            others = '; '.join(f"{r['pdf']} (tested {r['date']})" for r in usable[1:])
            issues.append((f"More than one valid COA: {', '.join(r['pdf'] for r in usable)}.",
                           'Rule 7 (newest test date wins)',
                           f"Used {chosen['pdf']} (tested {chosen['date']}); ignored {others}."))

    final = dict(batch='', date='', purity=None, size=None)
    from_sheet = []
    if chosen:
        sheet_vals = dict(batch=p['Batch_Listed'], date=p['Test_Date_Listed'],
                          purity=Decimal(p['Purity_Listed_pct']), size=Decimal(p['Size_mg']))
        coa_vals = dict(batch=chosen['batch'], date=chosen['date'], purity=chosen['purity'], size=chosen['size'])
        label = dict(batch='batch', date='test date', purity='purity', size='size')
        for k in ('batch', 'date', 'purity', 'size'):
            cv, sv = coa_vals[k], sheet_vals[k]
            if cv not in (None, ''):
                final[k] = cv                                                   # rule 6
                if sv not in (None, '') and cv != sv:
                    unit = ' mg' if k == 'size' else (' %' if k == 'purity' else '')
                    rule = 'Rule 6 (COA overrides sheet)' + (' and rule 9c (size conflict)' if k == 'size' else '')
                    issues.append((f"Sheet and COA disagree on {label[k]}: sheet {sv}{unit}, COA {cv}{unit}.",
                                   rule, f"Used COA value {cv}{unit}."))
            elif k in ('batch', 'date') and sv:
                final[k] = sv                                                   # rule 8
                from_sheet.append(label[k])
                issues.append((f"COA leaves {label[k]} blank; sheet has {sv}.", 'Rule 8 (blank on COA, use sheet)',
                               f"Used sheet value {sv}, recorded as \"from sheet\"."))
            elif k in ('batch', 'date'):
                issues.append((f"{label[k].capitalize()} is blank on both the COA and the sheet.",
                               'Rule 8 (both blank, field missing)', 'Field left blank and treated as missing.'))

    # rule 9, in the stated order
    fails = []
    if not all_rows:
        fails.append(('no COA', 'no COA PDF names this product'))
    elif not chosen:
        fails.append(('no COA for listed batch', f"no valid COA covers listed batch {p['Batch_Listed']}"))
    else:
        missing = [k for k, lab in (('batch', 'batch'), ('date', 'test date'), ('purity', 'purity'), ('size', 'size'))
                   if final[k] in (None, '')]
        if missing:
            fails.append(('missing field', ', '.join(m.replace('date', 'test date') for m in missing)))
        if final['size'] is not None and final['size'] != Decimal(p['Size_mg']):
            fails.append(('size conflict', f"COA {final['size']} mg vs sheet {p['Size_mg']} mg"))
        if final['purity'] is not None and final['purity'] < Decimal('98.0'):
            fails.append(('purity below 98.0', f"purity {final['purity']} %"))
        diff = abs(chosen['ob'] - chosen['th'])
        if diff > Decimal('1.0'):
            fails.append(('identity failed', f"observed {chosen['ob']} Da vs theoretical {chosen['th']} Da, difference {diff} Da"))
        if final['date'] and date.fromisoformat(final['date']) < CURRENT_FROM:
            fails.append(('COA older than 12 months', f"tested {final['date']}, before {CURRENT_FROM}"))
    status = 'draft' if fails else 'publish'
    reason = fails[0][0] if fails else 'all publish conditions met'
    if fails:
        extra = f" Other failing checks: {'; '.join(f'{a} ({b})' for a, b in fails[1:])}." if len(fails) > 1 else ''
        issues.append((f"Draft: {fails[0][0]} ({fails[0][1]}).{extra}",
                       f"Rule 9 (first failing reason in the stated order)",
                       'Status set to draft; reason written to status_reason; listed in the client email.'))
    url = URL.format(sku.lower(), final['batch'].lower()) if chosen and final['batch'] else ''   # rule 10
    decisions.append(dict(p=p, chosen=chosen, final=final, status=status, reason=reason, fails=fails,
                          issues=issues, url=url, from_sheet=from_sheet,
                          multi_note=(chosen['pdf'] if chosen and chosen['multi'] else '')))
    if chosen:
        covered_by[(chosen['pdf'], chosen['batch'])] = sku


def fmt(d):
    return '' if d is None else str(d)


# ---------------------------------------------------------------- coa_extracted.csv
with open('coa_extracted.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['pdf_file', 'lab', 'report_id', 'source', 'product', 'declared_amount_raw', 'declared_amount_mg',
                'batch', 'test_date_raw', 'test_date', 'purity_raw', 'purity_pct', 'theoretical_mass_da',
                'observed_mass_da', 'mass_diff_da', 'valid', 'notes'])
    for r in coa_rows:
        notes = []
        if r['report_type']:
            notes.append(f"report type: {r['report_type']}")
        if r['stamp']:
            notes.append(f"stamped {r['stamp']}: invalid (rule 4)")
        if r['multi']:
            notes.append('multi-batch COA row')
        if r['lab'] == 'NVL':
            notes.append('Novalab: DD/MM/YYYY date and decimal comma converted')
        if not r['batch']:
            notes.append('batch blank on COA')
        if not r['date_raw']:
            notes.append('test date blank on COA')
        used = covered_by.get((r['pdf'], r['batch']))
        skip = [d['p']['SKU'] for d in decisions if d['p']['Product'] == r['product'] and r['multi']
                and not d['chosen'] and r['valid']]
        notes.append(f'used for {used}' if used else
                     (f"not used: does not match listed batch of {skip[0]} (rule 5)" if skip else 'not used'))
        w.writerow([r['pdf'], r['lab'], r['report_id'], r['source'], r['product'], r['size_raw'], fmt(r['size']),
                    r['batch'], r['date_raw'], r['date'], r['purity_raw'], fmt(r['purity']), fmt(r['th']),
                    fmt(r['ob']), fmt(abs(r['ob'] - r['th'])), 'yes' if r['valid'] else 'no', '; '.join(notes)])

# ---------------------------------------------------------------- woocommerce_import.csv
with open('woocommerce_import.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['SKU', 'Name', 'Regular price', 'Status', 'coa_batch', 'coa_test_date', 'coa_purity', 'coa_size_mg',
                'coa_pdf', 'coa_url', 'status_reason'])
    for d in decisions:
        f = d['final']
        w.writerow([d['p']['SKU'], d['p']['Product'], d['p']['Price_USD'], d['status'], f['batch'], f['date'],
                    fmt(f['purity']), fmt(f['size']), d['chosen']['pdf'] if d['chosen'] else '', d['url'], d['reason']])

pub = [d for d in decisions if d['status'] == 'publish']
drafts = [d for d in decisions if d['status'] == 'draft']
mean = (sum(d['final']['purity'] for d in pub) / len(pub)).quantize(Decimal('0.01'), ROUND_HALF_UP)   # rule 12

# ---------------------------------------------------------------- coa_library.html (rules 11, 12)
lib = sorted(pub, key=lambda d: (d['final']['date'], d['p']['SKU']), reverse=True)
trs = '\n'.join(
    f"      <tr><td>{html.escape(d['p']['Product'])}</td><td>{d['final']['batch']}</td><td>{d['final']['date']}</td>"
    f"<td>{d['final']['purity']} %</td><td><a href=\"coa/{d['chosen']['pdf']}\">{d['chosen']['pdf']}</a></td></tr>"
    for d in lib)
open('coa_library.html', 'w', encoding='utf-8').write(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>COA Library</title>
<style>
  :root {{ --bg:#fff; --fg:#1d1d1f; --muted:#6b6b70; --line:#e3e3e8; --accent:#1a5fb4; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#16161a; --fg:#ececf1; --muted:#9a9aa3; --line:#2e2e35; --accent:#78aeed; }} }}
  body {{ margin:0; padding:24px 16px; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui,sans-serif; }}
  main {{ max-width:860px; margin:0 auto; }}
  .teaser {{ font-size:1.05rem; padding:12px 14px; border:1px solid var(--line); border-radius:8px; }}
  .wrap {{ overflow-x:auto; }}
  table {{ width:100%; border-collapse:collapse; margin-top:16px; }}
  th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }}
  th {{ color:var(--muted); font-weight:600; }}
  a {{ color:var(--accent); }}
</style>
</head>
<body>
<main>
  <p class="teaser" id="teaser"><strong><span id="published-count">{len(pub)}</span> published COAs</strong> &middot; mean purity <strong><span id="mean-purity">{mean}</span> %</strong></p>
  <h1>Certificate of Analysis library</h1>
  <p>Published products only, newest test date first.</p>
  <div class="wrap">
  <table>
    <thead><tr><th>Product</th><th>Batch</th><th>Test date</th><th>Purity</th><th>COA PDF</th></tr></thead>
    <tbody>
{trs}
    </tbody>
  </table>
  </div>
</main>
</body>
</html>
""")

# ---------------------------------------------------------------- retest_schedule.csv (rule 13)
sched = []
for d in pub:
    t = date.fromisoformat(d['final']['date'])
    due = t.replace(year=t.year + 1)
    sched.append((due, d['p']['SKU'], d['p']['Product'], t, (due - REF).days, due <= DUE_SOON_BY))
sched.sort()
with open('retest_schedule.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.writer(fh)
    w.writerow(['SKU', 'Name', 'test_date', 'retest_due', 'days_remaining', 'due_soon'])
    for due, sku, name, t, days, soon in sched:
        w.writerow([sku, name, t.isoformat(), due.isoformat(), days, 'yes' if soon else 'no'])
due_soon = {s[1] for s in sched if s[5]}

# ---------------------------------------------------------------- featured_products.md (rule 14)
cands = [d for d in pub if d['p']['SKU'] not in due_soon]
cands.sort(key=lambda d: (-d['final']['purity'], -date.fromisoformat(d['final']['date']).toordinal(), d['p']['SKU']))
feat = cands[:3]
L = ['# Featured products', '',
     'Rule 14: 3 published products that are not "due soon" for retest, highest purity first; '
     'ties broken by newest test date, then lower SKU.', '',
     '| Rank | SKU | Name | Purity | Test date | Why chosen |', '|---|---|---|---|---|---|']
for i, d in enumerate(feat, 1):
    f = d['final']
    ties = [c for c in cands if c['final']['purity'] == f['purity'] and c is not d]
    if ties:
        why = (f"Ties at {f['purity']} % with {', '.join(c['p']['SKU'] for c in ties)}; "
               f"it has the newest test date ({f['date']}) of the tied products.")
    else:
        rank_word = {1: 'highest', 2: 'second-highest', 3: 'third-highest'}[i]
        why = f"Its {f['purity']} % purity is the {rank_word} among published products that are not due soon."
    L.append(f"| {i} | {d['p']['SKU']} | {d['p']['Product']} | {f['purity']} % | {f['date']} | {why} |")
excluded = [d for d in pub if d['p']['SKU'] in due_soon]
L += ['', 'Excluded as "due soon" (retest due on or before 2026-12-29): ' +
      ', '.join(f"{d['p']['SKU']} {d['p']['Product']} ({d['final']['purity']} %)" for d in excluded) + '.']
open('featured_products.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n')

# ---------------------------------------------------------------- client_email.md (rule 15)
total = sum(Decimal(d['p']['Price_USD']) for d in drafts)
E = ['**Subject:** COA follow-up: products on hold (draft)', '', 'Hello,', '',
     f"We have reviewed the Certificates of Analysis for all {len(decisions)} products. "
     f"{len(pub)} products are published and {len(drafts)} are on hold as drafts. "
     'Below is each draft product (in SKU order), the reason it is on hold and what we need from you to publish it.', '',
     '| SKU | Product | Price (USD) | Reason | What we need |', '|---|---|---|---|---|']
for d in drafts:
    reason, detail = d['fails'][0]
    action = ACTIONS[reason].format(batch=d['p']['Batch_Listed'], size=d['final']['size'],
                                    fields=detail)
    E.append(f"| {d['p']['SKU']} | {d['p']['Product']} | {d['p']['Price_USD']} | {reason} ({detail}) | {action[0].upper() + action[1:]}. |")
E += ['', f"**Published products:** {len(pub)}  ", f"**Draft products:** {len(drafts)}  ",
      f"**Total price of draft products:** USD {total:.2f} (sum of their regular prices)", '',
      'Once we receive these items we will re-check each product and publish it.', '', 'Kind regards,', '',
      'The store team']
open('client_email.md', 'w', encoding='utf-8').write('\n'.join(E) + '\n')

# ---------------------------------------------------------------- exceptions_report.md
R = ['# Exceptions report', '',
     'Reference date 2026-09-30 (a COA is current if tested on or after 2025-09-30). Lists every product where a value '
     'came from the sheet, the sheet and COA disagree, more than one COA exists or a COA was ignored, or the product '
     'is a draft.', '',
     '| SKU | Product | COA used | Final status | Issue | Rule used | Action taken |', '|---|---|---|---|---|---|---|']
for d in decisions:
    for iss, rule, act in d['issues']:
        R.append(f"| {d['p']['SKU']} | {d['p']['Product']} | {d['chosen']['pdf'] if d['chosen'] else '(none)'} | "
                 f"{d['status']} | {iss} | {rule} | {act} |")
clean = [d for d in decisions if not d['issues']]
R += ['', '## Clean publishes (no exception)', '',
      ', '.join(f"{d['p']['SKU']} {d['p']['Product']}" for d in clean) + '.', '',
      '## Audit notes on clean publishes (no action needed)', '']
for d in clean:
    c, f = d['chosen'], d['final']
    n = []
    if c['multi']:
        n.append(f"taken from the {f['batch']} row of multi-batch COA {c['pdf']} (rule 5)")
    if c['lab'] == 'NVL':
        n.append(f"Novalab values converted: \"{c['size_raw']}\" = {f['size']} mg, \"{c['date_raw']}\" = {f['date']} (rules 2-3)")
    if abs(c['ob'] - c['th']) == Decimal('1.0'):
        n.append(f"identity difference is exactly 1.0 Da ({c['ob']} vs {c['th']}), which passes (rule 9e)")
    if f['date'] == CURRENT_FROM.isoformat():
        n.append(f"tested exactly on {CURRENT_FROM}, which is still current")
    if c['source'].startswith('scan'):
        n.append('read from a scanned PDF')
    if n:
        R.append(f"- {d['p']['SKU']} {d['p']['Product']}: " + '; '.join(n) + '.')
open('exceptions_report.md', 'w', encoding='utf-8').write('\n'.join(R) + '\n')

print(f"rows={len(coa_rows)} published={len(pub)} drafts={len(drafts)} mean={mean} "
      f"draft_total={total} featured={[d['p']['SKU'] for d in feat]}")
