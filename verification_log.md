# Verification log

- **Reference date:** 2026-09-30. A COA is current if it was tested on or after 2025-09-30, and a product is due soon if its retest date is on or before 2026-12-29.
- **Re-run:** `python3 scripts/build_coa.py && python3 scripts/verify_coa.py`
- **Final result: 213 of 213 checks pass, with no unresolved mismatch.**

## How the values were read and re-checked

| Source | First read (build) | Second, independent read (verify) |
|---|---|---|
| 13 Meridian (MAL) text PDFs, 3 of them multi-batch with 3 rows each | `pdftotext -layout` | `pypdf` text extraction, parsed separately |
| 5 Novalab (NVL) text PDFs | `pdftotext`, then µg/g → mg, comma → point, DD/MM/YYYY → YYYY-MM-DD | `pypdf`, with the conversions coded again from scratch |
| 7 scans (no text layer) | Read visually from 150 dpi renders → `scripts/scan_readings.csv` | Re-read visually from 200 dpi crops → `scripts/scan_recheck.csv` |
| VOID / SUPERSEDED stamps | Searched the text layer for stamp words; counted red pixels on every rendered page | Same, plus the stamp column in both scan readings |

The stamp search found red pixels on one page only: **scan_2542.pdf** (1,599 red pixels), which carries a "VOID - SUPERSEDED" stamp. All other 24 pages have 0 red pixels.

## Checks run

| # | Check | Result |
|---|---|---|
| 1 | The scans (no text layer) are exactly the 7 transcribed files | PASS |
| 2 | For each scan, the first and second visual readings agree on all 8 values (product, amount, batch, date, purity, both masses, stamp) | PASS (7/7) |
| 3 | `coa_extracted.csv` has one row per PDF row (31 rows from 25 PDFs). Product, size in mg, ISO date, purity, both masses and validity all equal the independent read | PASS (31/31) |
| 4 | Import file: 24 rows, the required columns, SKU order the same as the sheet | PASS |
| 5 | For each SKU: name, price, status, batch, test date, purity, size, COA PDF and URL equal the rules re-applied from scratch | PASS (24/24) |
| 6 | For each SKU: `status_reason` is the first failing reason, using the exact wording and order of rule 9 | PASS (24/24) |
| 7 | Batches match `PP-YYMM-NNN`. Each URL follows rule 10 and is blank only when the batch is missing or there is no usable COA (P03, P17, P24) | PASS |
| 8 | Library: 16 rows = 16 published, only published products, newest test date first, every cell equal to the import row, every PDF link exists | PASS |
| 9 | Teaser: count 16 = import. Mean purity 99.03 = import (exact mean 1584.4 / 16 = 99.025, rounded half-up) | PASS |
| 10 | Retest schedule covers exactly the 16 published products. Due date = test date + 1 year, days remaining = due date − 2026-09-30, due-soon flag correct, sorted by due date | PASS (16/16) |
| 11 | Featured products: rule 14 recomputed (P06, P14, P19). Purity and date match the import; none is due soon | PASS |
| 12 | Client email lists all 8 drafts in SKU order, each with the correct reason, the rule-15 action (P17 names batch PP-2605-019) and its price | PASS (8/8) |
| 13 | Email totals: 16 published, 8 drafts, USD 444.00 | PASS |
| 14 | Exceptions report lists exactly the products that are not clean publishes: P02, P03, P04, P05, P07, P08, P09, P11, P12, P13, P17, P22, P23, P24 | PASS |
| 15 | Every condition per product is present in the report: from sheet, each disagreement, several or ignored COAs, and the draft reason | PASS |

## Key comparisons

| SKU | COA used | What was checked | COA value | Sheet value | Outcome |
|---|---|---|---|---|---|
| P02 | MAL-26-8629 | test date | *(blank)* | 2026-03-10 | From sheet (rule 8) → publish |
| P03 | MAL-26-8402 | batch | *(blank)* | *(blank)* | missing field → draft, URL blank |
| P04 | MAL-26-9320 | batch | PP-2604-021 | PP-2604-012 | COA batch kept as printed (rule 6) → publish |
| P05 | scan_4025 vs MAL-26-4111 | newest valid COA | 2026-09-04 (98.6 %) vs 2026-07-02 (98.2 %) | 2026-07-02 / 99.1 % | Re-analysis wins (rule 7) → publish |
| P08 | MAL-26-4050; scan_2542 ignored | stamp | scan_2542: VOID - SUPERSEDED, 96.0 % | 99.2 % | Void COA ignored even though it is newer (rule 4) → publish at 99.2 % |
| P09 | MAL-26-8316 | purity | 97.4 % | 98.5 % | purity below 98.0 → draft |
| P11 | NVL-26-3323 | date, size | 14/08/2025 → 2025-08-14; 10000 µg → 10 mg | 2025-08-14, 10 mg | COA older than 12 months → draft |
| P12 | NVL-26-2485 | identity | 851,3 vs 848,8 Da (2.5 Da) | n/a | identity failed → draft |
| P13 | NVL-26-9825 | size | 0,01 g → 10 mg | 5 mg | size conflict → draft |
| P14 | NVL-26-1686 | size, date | 5000 µg → 5 mg; 21/07/2026 → 2026-07-21 | 5 mg, 2026-07-21 | Agree → publish |
| P16 | MAL-26-8421 row PP-2604-031 | multi-batch row | 99.0 %, 2026-04-22 | same | Matching row only (rule 5) → publish |
| P17 | MAL-26-3580 (rows 018, 020, 021) | multi-batch row | no row for PP-2605-019 | PP-2605-019 | no COA for listed batch → draft |
| P18 | MAL-26-1245 row PP-2602-007 | purity | 98.0 % | 98.0 % | 98.0 is "98.0 or higher" → publish |
| P20 | scan_2034 | identity | 5136.9 vs 5135.9 Da = exactly 1.0 | n/a | Passes (rule 9e) → publish |
| P21 | scan_1975 | date | 2025-09-30 | 2025-09-30 | Current (on the cut-off); retest due 2026-09-30, 0 days, due soon |
| P22 | scan_1584 | batch | *(blank)* | PP-2607-011 | From sheet (rule 8) → publish; URL uses the sheet batch |
| P23 | scan_4116 | identity | 548.1 vs 546.7 Da (1.4 Da) | n/a | identity failed → draft |
| P24 | none | COA | none of the 25 PDFs names Humanin | n/a | no COA → draft |

## Mismatches found and changes made

1. **`coa_size_mg` printed in scientific notation.** Reviewing the first build showed `5E+1` (P03) and `1E+1` (P06, P09, P11, P13, P20) instead of 50 and 10. The same values also appeared in the client email ("COA 1E+1 mg").
   - Cause: `Decimal.normalize()` in the unit conversion.
   - Fix: the conversion now returns plain notation.
   - Rebuilt: import, extract, email, exceptions report.
   - Re-check: no `E+` remains in any deliverable, and sizes are 50 / 10 as printed.
2. **Meridian purity cells in `coa_extracted.csv` included the Notes column** (e.g. `99.2 %   Area-normalised`).
   - Fix: the parser now keeps only the Result cell.
   - Rebuilt: the extract file. Values in other files were unaffected, because purity was already parsed numerically.
3. **The GHRP-6 multi-batch rows said only "not used"** without saying why.
   - Fix: they now say they don't match P17's listed batch (rule 5).
   - Rebuilt: the extract file.

After these fixes, every deliverable was rebuilt from the same script, and the independent verifier then ran clean (213/213).

## Decisions worth flagging

- **Mean purity rounding.** The exact mean is 99.025. Rounded half-up to 2 decimals, that gives **99.03**. Binary floating point would have printed 99.02, so exact decimal arithmetic is used throughout.
- **P17 (GHRP-6).** Its only COA does not cover the listed batch, so there is no usable COA. `coa_batch`, the test date, purity, size, `coa_pdf` and `coa_url` are left blank: the URL by rule 10, and the other values because no COA supplies them. P24 is treated the same way.
- **Publish rows.** `status_reason` reads "all publish conditions met". Drafts use the exact rule-9 wording.
