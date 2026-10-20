# Security policy

## Reporting

Do not open a public issue for a vulnerability. Use the repository's private security
advisory feature or contact the maintainers through the internal Pexon channel.

Include:

- affected version;
- reproduction steps;
- impact;
- whether credentials or bank data are involved;
- suggested mitigation.

## Scope

Pexon is a prototype. It has no authentication, authorization or multi-tenancy. Do not
expose the CLI or its filesystem to untrusted users.

Security-relevant controls that do exist:

- PII redaction before every LLM call;
- HTML/script/injection sanitization;
- structured JSON validation;
- no secrets in model cards;
- append-only audit events;
- optional human review;
- provider selection by environment.

See [SECURITY_AND_COMPLIANCE.md](docs/SECURITY_AND_COMPLIANCE.md) for the deployment
checklist.

## Secret handling

- Never commit `.env`, API keys, CRM exports or service-account files.
- `.env.example` must contain placeholders only.
- Use a secrets manager in any bank deployment.
- Rotate any key that has been exposed.
