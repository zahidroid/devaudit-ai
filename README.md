# DevAudit AI — AI-Powered Code Security Auditor

> Paste any GitHub repo URL → AI scans every file for security vulnerabilities, DevOps issues & bad practices → generates a full audit report

🔗 **[Live Demo → https://huggingface.co/spaces/zahidmohd/devaudit-ai](https://huggingface.co/spaces/zahidmohd/devaudit-ai)**

## What it does
- Fetches all code files from any public GitHub repository
- AI analyzes every file for Security, Performance, DevOps & Code Quality issues
- Generates severity-rated report: CRITICAL / HIGH / MEDIUM / LOW
- Downloadable full audit report (.html)
- Bilingual ready — built for enterprise DevOps teams

## Tech Stack
- Model: Qwen2.5-72B-Instruct (via HuggingFace Inference API)
- UI: Gradio 6
- GitHub API: repo file fetching
- Deployment: HuggingFace Spaces

## Run Locally
pip install gradio huggingface_hub requests
export HF_TOKEN=your_token
export GITHUB_TOKEN=your_token
python app.py

## Built By
Zahid Mohammed | Made for JTP Placement 2026
