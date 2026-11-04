# Publishing to GitHub

The local repository is initialised on `main`, but it has **no commits and no remote yet**.
The GitHub CLI (`gh`) and Git are installed.

> Replace `YOUR_USERNAME` with your real GitHub username. The URL
> `https://github.com/YOUR_USERNAME/shambashield-ai.git` is only a placeholder.

---

## 1. Authenticate the GitHub CLI

Open a **new PowerShell window** (so `gh` is on PATH):

```powershell
gh auth login --hostname github.com --git-protocol https --web
```

Choose:

- **GitHub.com**
- **HTTPS**
- **Login with a web browser**
- Copy the one-time code, press Enter, and approve in the browser.

Verify:

```powershell
gh auth status
```

If `gh` is still not on PATH:

```powershell
& "C:\Program Files\GitHub CLI\gh.exe" auth login --hostname github.com --git-protocol https --web
```

---

## 2. Set the commit identity

Use your real name and the GitHub noreply address so commits link to your profile:

```powershell
$login = gh api user --jq .login
$id    = gh api user --jq .id
git config user.name  $login
git config user.email "$id+$login@users.noreply.github.com"
```

Verify:

```powershell
git config user.name
git config user.email
```

These are repository-local settings; they do not change your global Git identity.

---

## 3. Check for secrets before the first commit

```powershell
git add -A
git status --short
git ls-files | Select-String -Pattern "^\.env$"
git check-ignore -v .env
```

- `git ls-files` must return **nothing** for `.env`.
- `git check-ignore` should print the `.gitignore` rule.

If `.env` appears in `git status`, stop and run:

```powershell
git rm --cached .env
```

`.env.example` is safe to commit; it contains placeholders only.

---

## 4. Commit

```powershell
git commit -m "Phase 1-2: architecture, environment and Bedrock diagnostics"
```

---

## 5. Create the public repository and push

```powershell
gh repo create shambashield-ai --public --source=. --remote=origin --push
```

This creates `https://github.com/<your-login>/shambashield-ai` and pushes `main`.

If the repository **already exists** (for example, you created it in the browser):

```powershell
git remote add origin https://github.com/YOUR_USERNAME/shambashield-ai.git
git push -u origin main
```

If a remote already exists with the wrong URL:

```powershell
git remote set-url origin https://github.com/YOUR_USERNAME/shambashield-ai.git
```

---

## 6. Polish the repository page

```powershell
gh repo edit --description "Multi-agent climate resilience assistant for smallholder farmers in Kenya (AWS Strands + Amazon Bedrock)"
gh repo edit --add-topic aws --add-topic strands-agents --add-topic amazon-bedrock --add-topic climate-tech --add-topic kenya --add-topic streamlit --add-topic hackathon
gh repo view --web
```

After the first push, add the CI badge to the top of `README.md`:

```markdown
![CI](https://github.com/YOUR_USERNAME/shambashield-ai/actions/workflows/ci.yml/badge.svg)
```

---

## 7. What is intentionally not committed

| Path | Reason |
|---|---|
| `.env` | Real credentials and model IDs |
| `.venv/` | Local virtual environment |
| `*.egg-info/` | Build metadata |
| `reports/` | Generated assessment reports (future) |
| `logs/` | Local logs |

`requirements.lock.txt` is committed for reproducible Windows development. CI uses
`pyproject.toml` because the lock includes Windows-only packages.

---

## If a secret is ever committed

1. **Rotate it immediately** — revoke the AWS access key, Bedrock API key, or GitHub token.
2. Remove it from history with `git filter-repo` or the BFG Repo-Cleaner.
3. Force-push the cleaned history.
4. Assume the secret was public from the moment it was pushed.

Deleting the file in a new commit is **not** enough; the old commit still contains it.
