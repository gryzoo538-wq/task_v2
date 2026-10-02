# Exceptions report

Reference date 2026-09-30 (a COA is current if tested on or after 2025-09-30). Lists every product where a value came from the sheet, the sheet and COA disagree, more than one COA exists or a COA was ignored, or the product is a draft.

| SKU | Product | COA used | Final status | Issue | Rule used | Action taken |
|---|---|---|---|---|---|---|
| P02 | TB-500 | MAL-26-8629.pdf | publish | COA leaves test date blank; sheet has 2026-03-10. | Rule 8 (blank on COA, use sheet) | Used sheet value 2026-03-10, recorded as "from sheet". |
| P03 | GHK-Cu | MAL-26-8402.pdf | draft | Batch is blank on both the COA and the sheet. | Rule 8 (both blank, field missing) | Field left blank and treated as missing. |
| P03 | GHK-Cu | MAL-26-8402.pdf | draft | Draft: missing field (batch). | Rule 9 (first failing reason in the stated order) | Status set to draft; reason written to status_reason; listed in the client email. |
| P04 | Ipamorelin | MAL-26-9320.pdf | publish | Sheet and COA disagree on batch: sheet PP-2604-012, COA PP-2604-021. | Rule 6 (COA overrides sheet) | Used COA value PP-2604-021. |
| P05 | CJC-1295 (no DAC) | scan_4025.pdf | publish | More than one valid COA: scan_4025.pdf, MAL-26-4111.pdf. | Rule 7 (newest test date wins) | Used scan_4025.pdf (tested 2026-09-04); ignored MAL-26-4111.pdf (tested 2026-07-02). |
| P05 | CJC-1295 (no DAC) | scan_4025.pdf | publish | Sheet and COA disagree on test date: sheet 2026-07-02, COA 2026-09-04. | Rule 6 (COA overrides sheet) | Used COA value 2026-09-04. |
| P05 | CJC-1295 (no DAC) | scan_4025.pdf | publish | Sheet and COA disagree on purity: sheet 99.1 %, COA 98.6 %. | Rule 6 (COA overrides sheet) | Used COA value 98.6 %. |
| P07 | Selank | MAL-26-8794.pdf | publish | Sheet and COA disagree on purity: sheet 98.9 %, COA 99.3 %. | Rule 6 (COA overrides sheet) | Used COA value 99.3 %. |
| P08 | Semax | MAL-26-4050.pdf | publish | scan_2542.pdf is stamped "VOID - SUPERSEDED" (tested 2026-08-20, purity 96.0 %). | Rule 4 (VOID/SUPERSEDED COA is invalid) | COA ignored completely. |
| P09 | MOTS-c | MAL-26-8316.pdf | draft | Sheet and COA disagree on purity: sheet 98.5 %, COA 97.4 %. | Rule 6 (COA overrides sheet) | Used COA value 97.4 %. |
| P09 | MOTS-c | MAL-26-8316.pdf | draft | Draft: purity below 98.0 (purity 97.4 %). | Rule 9 (first failing reason in the stated order) | Status set to draft; reason written to status_reason; listed in the client email. |
| P11 | PT-141 | NVL-26-3323.pdf | draft | Draft: COA older than 12 months (tested 2025-08-14, before 2025-09-30). | Rule 9 (first failing reason in the stated order) | Status set to draft; reason written to status_reason; listed in the client email. |
| P12 | DSIP | NVL-26-2485.pdf | draft | Draft: identity failed (observed 851.3 Da vs theoretical 848.8 Da, difference 2.5 Da). | Rule 9 (first failing reason in the stated order) | Status set to draft; reason written to status_reason; listed in the client email. |
| P13 | KPV | NVL-26-9825.pdf | draft | Sheet and COA disagree on size: sheet 5 mg, COA 10 mg. | Rule 6 (COA overrides sheet) and rule 9c (size conflict) | Used COA value 10 mg. |
| P13 | KPV | NVL-26-9825.pdf | draft | Draft: size conflict (COA 10 mg vs sheet 5 mg). | Rule 9 (first failing reason in the stated order) | Status set to draft; reason written to status_reason; listed in the client email. |
| P17 | GHRP-6 | (none) | draft | Multi-batch COA MAL-26-3580.pdf lists PP-2605-018, PP-2605-020, PP-2606-021; none equals the listed batch PP-2605-019. | Rule 5 (multi-batch COA: only the row matching Batch_Listed) | COA does not cover this product; ignored. |
| P17 | GHRP-6 | (none) | draft | Draft: no COA for listed batch (no valid COA covers listed batch PP-2605-019). | Rule 9 (first failing reason in the stated order) | Status set to draft; reason written to status_reason; listed in the client email. |
| P22 | Gonadorelin | scan_1584.pdf | publish | COA leaves batch blank; sheet has PP-2607-011. | Rule 8 (blank on COA, use sheet) | Used sheet value PP-2607-011, recorded as "from sheet". |
| P23 | Dihexa | scan_4116.pdf | draft | Draft: identity failed (observed 548.1 Da vs theoretical 546.7 Da, difference 1.4 Da). | Rule 9 (first failing reason in the stated order) | Status set to draft; reason written to status_reason; listed in the client email. |
| P24 | Humanin | (none) | draft | Draft: no COA (no COA PDF names this product). | Rule 9 (first failing reason in the stated order) | Status set to draft; reason written to status_reason; listed in the client email. |

## Clean publishes (no exception)

P01 BPC-157, P06 Epitalon, P10 Thymosin Alpha-1, P14 AOD-9604, P15 Kisspeptin-10, P16 LL-37, P18 Hexarelin, P19 Sermorelin, P20 Tesamorelin, P21 Oxytocin.

## Audit notes on clean publishes (no action needed)

- P14 AOD-9604: Novalab values converted: "5000 µg" = 5 mg, "21/07/2026" = 2026-07-21 (rules 2-3).
- P15 Kisspeptin-10: Novalab values converted: "2 mg" = 2 mg, "05/11/2025" = 2025-11-05 (rules 2-3).
- P16 LL-37: taken from the PP-2604-031 row of multi-batch COA MAL-26-8421.pdf (rule 5).
- P18 Hexarelin: taken from the PP-2602-007 row of multi-batch COA MAL-26-1245.pdf (rule 5).
- P19 Sermorelin: read from a scanned PDF.
- P20 Tesamorelin: identity difference is exactly 1.0 Da (5136.9 vs 5135.9), which passes (rule 9e); read from a scanned PDF.
- P21 Oxytocin: tested exactly on 2025-09-30, which is still current; read from a scanned PDF.
