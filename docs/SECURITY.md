# Security & privacy review

Scope: local/demo deployment. **Not independently audited. Not production-ready.**

| Area | Control | Verified by |
|---|---|---|
| Upload type | extension allow-list (.pdf/.docx) + magic-byte check | `test_security`, `test_api` |
| Size / volume | `MAX_UPLOAD_MB` (5), `MAX_PDF_PAGES` (30), `MAX_BATCH_FILES` (60) | tests |
| Malicious PDFs | rejects JavaScript / Launch / OpenAction / embedded files | test |
| Malicious DOCX | rejects macros (`vbaProject.bin`), zip-bomb ratio/size check | test |
| Filenames | sanitised; storage uses random names; read/delete are path-traversal safe | test |
| Prompt injection | resume text is never executed or sent to an LLM; instruction-like text is flagged and ignored | test |
| Access control | optional shared `API_KEY` (constant-time compare); `/health` open | test |
| Errors | uniform envelope, no stack traces or paths to clients | test |
| CSV/Excel export | cells starting `= + - @` are neutralised (formula injection) | test |
| PII in logs | audit log stores action + ids only (no names/emails) | test |
| Deletion | per-candidate delete removes DB rows and the stored file; retention purge by age | test |
| Fairness | protected-attribute lines scrubbed before matching/storage; blind mode; twin test | tests |
| CORS | restricted to configured origins | code review |

## Known gaps
- PDF/DOCX parsing runs in the API process: a parser exploit would hit the server. No sandbox, no antivirus scanning.
- No user accounts, roles or per-recruiter data isolation; one shared key.
- No rate limiting, no TLS (put behind a reverse proxy for any shared use).
- Original resume files are stored unencrypted on disk (`STORE_ORIGINAL_FILES=false` disables this).
- Scrubbing removes only *labelled* lines (e.g. `Date of birth: …`, `Gender: …`), not free-text mentions inside sentences; proxies (e.g. names of schools, locations, career gaps) can still correlate with protected groups. No statistical fairness audit on real data has been done.
- Resume text is personal data: GDPR/DPDP compliance (consent, lawful basis, DPIA) is not addressed by this code.
