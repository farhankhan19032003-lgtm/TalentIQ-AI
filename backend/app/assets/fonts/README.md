# Bundled fonts (PDF reports)

These fonts let the PDF reports show Hindi (Devanagari) text next to Latin text, fully offline.

| File | Font | Used for |
|---|---|---|
| `NotoSans-Regular.ttf`, `NotoSans-Bold.ttf`, `NotoSans-Italic.ttf` | Noto Sans | Latin, Greek, Cyrillic (all normal report text) |
| `NotoSansDevanagari-Regular.ttf`, `NotoSansDevanagari-Bold.ttf` | Noto Sans Devanagari | Hindi / Devanagari runs |

- **Licence:** SIL Open Font License 1.1 (see `OFL.txt`), (c) The Noto Project Authors. Redistribution with the project is allowed; the fonts must not be sold on their own.
- **Source:** the static, unhinted TrueType files published in the `notofonts/noto-fonts` repository (`unhinted/ttf/NotoSans` and `unhinted/ttf/NotoSansDevanagari`).
- **Shaping:** Devanagari needs vowel-sign reordering and conjunct formation. reportlab does this through the optional `uharfbuzz` package (in `requirements.txt`). Without it the PDFs still build, but Hindi is drawn unshaped (readable, not typographically correct).
- **Other scripts** (Arabic, Chinese, Japanese, emoji, ...) are not covered by these fonts and are shown as `?` in the PDFs.
- If a font file is missing the reports fall back to the built-in Helvetica (Latin only).
