# Phase 2 — Python environment, Strands SDK and AWS/Bedrock setup

**Goal:** a reproducible local environment where a Strands agent can call Amazon Bedrock,
plus the diagnostics needed to prove it.

Status on this machine:

| Item | Result |
|---|---|
| Python | 3.13.17 (`py` launcher) |
| Virtual environment | `.venv` created |
| Strands Agents SDK | 1.63.0 installed |
| AWS CLI | 2.39.3 installed at `C:\Program Files\Amazon\AWSCLIV2\aws.exe` |
| Project package | `shambashield-ai` installed in editable mode |
| Tests | 13 passing (AWS-free) |
| Lint | `ruff` clean |
| AWS credentials | **Not configured yet — user action required** |
| Bedrock smoke test | **Blocked until credentials + model access exist** |

> The code is ready. The remaining Phase 2 steps need your AWS account; they cannot be
> completed from this machine without your credentials.

---

## 1. Open the project and activate the environment

```powershell
cd C:\Users\Korir\Downloads\shambashield-ai
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

You can also skip activation and prefix commands with `.\.venv\Scripts\python.exe`.

Verify:

```powershell
python --version          # 3.13.x
python -c "import strands, boto3; print('strands', strands.__version__ if hasattr(strands, '__version__') else 'ok'); print('boto3', boto3.__version__)"
```

Open a **new terminal** after installing the AWS CLI, or call it by full path:

```powershell
& "C:\Program Files\Amazon\AWSCLIV2\aws.exe" --version
```

---

## 2. Configure AWS credentials

Choose **one** option.

### Option A — IAM Identity Center / SSO (recommended)

```powershell
aws configure sso
```

Prompts:

| Prompt | Example |
|---|---|
| SSO session name | `shambashield` |
| SSO start URL | your organisation's URL |
| SSO region | `us-east-1` |
| Account | choose the hackathon account |
| Role | choose a role with Bedrock access |
| Default client Region | `us-east-1` |
| Default output format | `json` |

Then log in and verify:

```powershell
aws sso login --profile shambashield
aws sts get-caller-identity --profile shambashield
```

In `.env`:

```dotenv
AWS_REGION=us-east-1
AWS_PROFILE=shambashield
```

### Option B — IAM user access key (simpler, less secure)

```powershell
aws configure --profile shambashield
```

Use a dedicated user with only the permissions in §6. Do not use root credentials.
Then set `AWS_PROFILE=shambashield` in `.env`.

### Option C — Bedrock API key (runtime only)

Generate a key in the Bedrock console and put it in `.env`:

```dotenv
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=<a model ID you can invoke>
# BEDROCK_API_KEY=<your key>
```

This is convenient for a local demo, but:

- it cannot list models (`--list` needs IAM/SSO),
- it is a long-lived secret,
- it is not the right choice for a shared deployment.

Use SSO for anything beyond the hackathon.

> **Never commit `.env`.** It is already in `.gitignore`.

---

## 3. Enable model access in Amazon Bedrock

1. Open the AWS console in **`us-east-1`** (recommended for model availability).
2. Go to **Amazon Bedrock → Model access** (in newer consoles: **Model catalog → Model access**).
3. Request access to the model family you intend to use.
4. For Anthropic models, complete the use-case form if prompted.
5. Wait until the model status is **Access granted**.

Model access is regional. Access in `us-east-1` does not grant access in `eu-west-1`.

---

## 4. Discover a model ID

```powershell
python scripts/check_bedrock.py --identity
python scripts/check_bedrock.py --list
```

`--list` prints:

- foundation models with text output and on-demand support,
- active system inference profiles.

**Anthropic models usually require an inference profile ID** that begins with `us.`
(or `eu.` / `apac.` depending on region). Copy the full profile ID.

---

## 5. Configure and run the smoke test

Edit `.env`:

```dotenv
AWS_REGION=us-east-1
AWS_PROFILE=shambashield
BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0   # example only — use an ID from --list
# Optional stronger model for the orchestrator:
# BEDROCK_ORCHESTRATOR_MODEL_ID=us.amazon.nova-pro-v1:0
```

Then:

```powershell
python scripts/check_bedrock.py --smoke
```

Success looks like:

```
Region:      us-east-1
Model ID:    us.amazon.nova-lite-v1:0
Sending one request through Strands...

Response:
  ShambaShield Bedrock connection OK

Latency: 1.83s

Phase 2 Bedrock smoke test passed.
```

You can also test a specific ID without editing `.env`:

```powershell
python scripts/check_bedrock.py --smoke --model <id>
```

### Model choice for the hackathon

- Start with **one small, fast model** for all agents. Fewer variables, lower cost.
- Add a stronger orchestrator model later only if output quality needs it.
- Do not hard-code model IDs in source code; they vary by region and account.
- Record actual latency and token cost in Phase 10 — do not guess.

---

## 6. Minimal IAM permissions

For local development, a scoped policy like this is enough:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels",
        "bedrock:ListInferenceProfiles"
      ],
      "Resource": "*"
    }
  ]
}
```

`Resource: "*"` is acceptable for a hackathon sandbox but broad. For production, scope
`InvokeModel` to specific model and inference-profile ARNs, and add DynamoDB/S3 permissions
only in Phase 11.

---

## 7. Run the offline checks

```powershell
python -m pytest
python -m ruff check .
```

Expected:

```
13 passed
All checks passed!
```

These tests never call AWS. They cover configuration, secret handling, session creation,
the CLI's argument handling, and model construction.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No AWS credentials found` | No profile/keys configured | Run `aws configure sso`, set `AWS_PROFILE` in `.env` |
| `ProfileNotFound` | Wrong profile name | Check `~/.aws/config`; update `.env` |
| `AccessDenied` on `--list` | Missing `bedrock:ListFoundationModels` | Use a role with the policy in §6 |
| `AccessDenied` on `--smoke` | Model access not enabled, or no `InvokeModel` | Enable model access in the console; check IAM |
| `ValidationException` | Wrong/unsupported model ID | Use `--list`; Anthropic needs a `us.` inference profile |
| `ResourceNotFoundException` | Model not available in this region | Switch `AWS_REGION` to `us-east-1` |
| `UnrecognizedClientException` | Expired credentials | `aws sso login --profile shambashield` |
| `aws` not recognised | Terminal PATH not refreshed | Open a new terminal, or use the full path |
| Timeout | Network/proxy | Check connectivity; Bedrock is not in every region |
| Activation blocked | PowerShell policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

---

## 9. Cost and safety

- Bedrock charges per input/output token. The smoke test uses ~64 output tokens.
- A full assessment will make several model calls. Target ≤ US$0.03 per assessment in
  Phase 10; measure rather than assume.
- Set an AWS Budget alert before the demo.
- Keep `max_tokens` low for specialist agents.
- Never paste credentials into chat, screenshots, the README or the demo video.

---

## 10. Phase 2 acceptance checklist

- [x] Virtual environment created.
- [x] Strands Agents SDK and project dependencies installed.
- [x] AWS CLI installed.
- [x] Package installed in editable mode.
- [x] `ruff` clean.
- [x] AWS-free tests passing.
- [ ] AWS credentials configured (your action).
- [ ] Bedrock model access granted (your action).
- [ ] `--list` returns models.
- [ ] `--smoke` prints `ShambaShield Bedrock connection OK`.

Once the last four boxes are ticked, Phase 2 is complete and Phase 3 can begin.
