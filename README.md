# 🌱 ShambaShield AI

### AI-Powered Climate Resilience Assistant for Smallholder Farmers

ShambaShield AI is an intelligent multi-agent climate resilience assistant built using the **AWS Strands Agents SDK**.

The project aims to help underserved smallholder farmers in Kenya anticipate weather-related agricultural risks, understand potential crop impacts, and receive practical, accessible farming recommendations.

[![CI](https://github.com/Nicholas-Kipngetich/shambashield-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Nicholas-Kipngetich/shambashield-ai/actions/workflows/ci.yml)

## 🌍 The Problem

Smallholder farmers face increasing challenges from unpredictable rainfall, drought, extreme temperatures, and changing weather patterns.

Limited access to timely and understandable climate information makes it difficult to make informed farming decisions.

## 💡 Our Solution

ShambaShield AI uses a collaborative multi-agent architecture to:

- Analyse weather forecasts.
- Identify potential agricultural climate risks.
- Assess possible crop exposure.
- Generate practical preventive recommendations.
- Communicate insights in simple English and Kiswahili.

The language model interprets and communicates — it does **not** invent weather numbers or actions. Forecasts come from Open-Meteo, risk tiers come from an explicit, testable rules engine, and recommendations come from a curated action catalog.

## 🧠 Multi-Agent Architecture

The system consists of:

1. **Weather Intelligence Agent** – Analyses weather conditions and forecasts.
2. **Crop Risk Assessment Agent** – Evaluates potential climate-related crop risks.
3. **Agricultural Action Planner Agent** – Generates practical farming recommendations.
4. **Farmer Communication Agent** – Delivers accessible, multilingual advice.
5. **Main Orchestrator Agent** – Coordinates the specialist agents using Strands SDK.

## 🛠️ Technology Stack

- Python 3.13
- AWS Strands Agents SDK (1.63+)
- Amazon Bedrock
- Open-Meteo Weather API
- Streamlit
- AWS services (planned integrations)

## 🚀 Project Status

Currently under development as part of the AWS Building AI Agents with Strands SDK hackathon.

- **Phase 1 complete** — architecture, problem definition, requirements ([docs/PHASE1_ARCHITECTURE.md](docs/PHASE1_ARCHITECTURE.md))
- **Phase 2 in progress** — Python environment, Strands SDK setup, Bedrock diagnostics ([docs/PHASE2_SETUP.md](docs/PHASE2_SETUP.md))
- **13 offline tests passing**, ruff lint + format clean, scheduled CI

## 🚀 Quickstart (PowerShell)

```powershell
cd C:\Users\Korir\Downloads\shambashield-ai
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env

python scripts/check_bedrock.py --identity
python scripts/check_bedrock.py --list
python scripts/check_bedrock.py --smoke
python -m pytest
python -m ruff check .
```

AWS credentials and Bedrock model access are configured once; full walkthrough in
[docs/PHASE2_SETUP.md](docs/PHASE2_SETUP.md).

## 📚 Documentation

- [Phase 1 — architecture and requirements](docs/PHASE1_ARCHITECTURE.md)
- [Phase 2 — environment, Strands SDK and Bedrock setup](docs/PHASE2_SETUP.md)
- [Publishing this repository](docs/GITHUB_SETUP.md)

## 🎯 Social Impact

Our goal is to improve access to understandable climate-risk information and support better-informed agricultural decisions among underserved smallholder farming communities.

No impact statistics are claimed without actual validation.

## ⚠️ Disclaimer

ShambaShield AI provides advisory information and is not a replacement for qualified agricultural extension services. Weather forecasts and AI-generated assessments may contain uncertainty. Forecasts are county-level approximations and can change — always re-check before acting.

## 👨‍💻 Contribution

Contributions, feedback, and collaboration are welcome.

## 📄 License

MIT License
