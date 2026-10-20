# Publish this repository to GitHub

The local repository is already initialised on `main` with commits. This guide adds the
GitHub presentation layer; no external upload is performed by the code.

## 1. Create the remote

Create an empty repository on GitHub, then:

```bash
git remote add origin git@github.com:YOUR_ORG/pexon.git
git branch -M main
git push -u origin main
```

Do not add a README, license or `.gitignore` in the GitHub UI; they are already present.

## 2. Repository description

Use:

> Pexon — closed-loop content operating system for German bank AI consulting.

## 3. Topics

```
langgraph
content-marketing
generative-engine-optimization
seo
german-banks
ai-governance
pydantic
multi-provider
crm-attribution
```

## 4. Social preview

Upload [docs/assets/social-card.png](assets/social-card.png) as the GitHub social
preview.

## 5. About section

Suggested website: your Pexon consulting site.

## 6. Releases

Tag the current prototype:

```bash
git tag -a v0.2.0 -m "Measurement layer: CRM, GEO, portfolio, publishing, economics"
git push origin v0.2.0
```

GitHub release notes can be copied from [CHANGELOG.md](../CHANGELOG.md).

## 7. Branch protection

For a real collaboration:

- protect `main`;
- require pull requests;
- require review from a second engineer;
- do not require CI: this prototype deliberately has none.

## 8. Secrets

Never commit:

- `.env` or `.env.local`;
- provider API keys;
- service-account JSON;
- CRM exports containing personal data.

Use GitHub encrypted secrets only when you later add a deployment workflow.

## 9. What the GitHub page should show

- the architecture image at the top of the README;
- the four-frame section;
- the business funnel;
- the “what is real / what is not” table;
- the provider matrix;
- the CEO brief and demo guide links.

That is the presentation. The code is the proof.
