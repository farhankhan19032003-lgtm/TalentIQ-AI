# Security review (interview summary)

Controls and tests: `../docs/SECURITY.md`. Talking points:

- **Threat model:** a recruiter uploads untrusted files; the server must not be hurt by them and must not leak candidate data.
- **Upload defence in depth:** extension allow-list → magic bytes → size/page limits → PDF active-content markers → DOCX macro and zip-bomb checks → random storage name → sanitised display name.
- **Prompt injection:** there is no LLM in the pipeline; resume text is data. Instruction-like phrases are still flagged to the recruiter, so the control also protects anyone who later pipes the text into an LLM.
- **Privacy:** protected-attribute lines are scrubbed before storage/matching; blind mode masks identity in API output; audit log has IDs only; deletion removes rows and files; retention purge exists.
- **Output safety:** CSV/Excel formula-injection neutralisation; error envelope hides internals.
- **Auth:** single optional shared key, constant-time comparison. Fine for a demo, **inadequate** for multi-user production.
- **Biggest honest gaps:** in-process parsing (no sandbox), no AV scanning, no TLS/rate limiting, unencrypted file storage, no legal/compliance work, proxy bias not measured.
