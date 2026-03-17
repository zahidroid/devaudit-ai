import gradio as gr
from huggingface_hub import InferenceClient
import os
import requests
import base64
import tempfile
import json
import re

hf_client = InferenceClient("Qwen/Qwen2.5-72B-Instruct", token=os.environ.get("HF_TOKEN"))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

SYSTEM_PROMPT = """You are DevAudit AI, an expert DevOps security and code quality auditor.
Analyze the provided code files and return a JSON response with exactly this structure:
{
  "summary": "2-3 sentence overall assessment",
  "severity_score": 5,
  "issues": [
    {
      "file": "filename",
      "severity": "CRITICAL",
      "category": "Security",
      "title": "short title",
      "description": "detailed explanation",
      "fix": "how to fix it"
    }
  ],
  "good_practices": ["thing done well 1", "thing done well 2"],
  "recommendations": ["recommendation 1", "recommendation 2", "recommendation 3"]
}
IMPORTANT RULES:
- Return ONLY the JSON object, nothing else
- No markdown, no backticks, no explanation
- All string values must use double quotes
- No newlines inside string values
- Keep descriptions under 200 characters
- Keep fix under 200 characters"""

def get_github_files(repo_url):
    try:
        parts = repo_url.rstrip("/").replace("https://github.com/", "").split("/")
        owner, repo = parts[0], parts[1]
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
        tree_resp = requests.get(api_url, headers=headers).json()
        if "tree" not in tree_resp:
            return None, "Could not access repo. Make sure it's public!"
        code_extensions = ['.py', '.js', '.ts', '.java', '.go', '.rb', '.php',
                          '.cpp', '.c', '.yml', '.yaml', '.sh', 'Dockerfile', '.tf']
        files = {}
        count = 0
        for item in tree_resp["tree"]:
            if count >= 10:
                break
            if any(item["path"].endswith(ext) for ext in code_extensions):
                file_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{item['path']}"
                file_resp = requests.get(file_url, headers=headers).json()
                if "content" in file_resp:
                    content = base64.b64decode(file_resp["content"]).decode("utf-8", errors="ignore")
                    if len(content) > 100:
                        files[item["path"]] = content[:2000]
                        count += 1
        return files, None
    except Exception as e:
        return None, f"Error: {str(e)}"

def safe_parse_json(raw):
    clean = raw.strip()
    clean = re.sub(r'```json', '', clean)
    clean = re.sub(r'```', '', clean)
    clean = clean.strip()
    start = clean.find("{")
    end = clean.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    clean = clean[start:end]
    try:
        return json.loads(clean)
    except:
        clean = re.sub(r'[\x00-\x1f\x7f]', ' ', clean)
        clean = re.sub(r',\s*}', '}', clean)
        clean = re.sub(r',\s*]', ']', clean)
        try:
            return json.loads(clean)
        except:
            return None

def generate_html_report(repo_url, result, file_count):
    score = result.get("severity_score", 5)
    score_color = "#ff4444" if score >= 7 else "#ff8800" if score >= 4 else "#44bb44"
    severity_color = {"CRITICAL": "#ff4444", "HIGH": "#ff8800", "MEDIUM": "#ffcc00", "LOW": "#44bb44"}

    issues_html = ""
    for issue in result.get("issues", []):
        color = severity_color.get(issue.get("severity", "LOW"), "#888")
        issues_html += f"""
        <div style="border-left:4px solid {color};padding:12px;margin:10px 0;background:#1a1a2e;border-radius:4px;">
            <div style="display:flex;justify-content:space-between;flex-wrap:wrap;">
                <b style="color:{color};">[{issue.get("severity","?")}] {issue.get("title","")}</b>
                <span style="color:#888;font-size:12px;">{issue.get("file","")} | {issue.get("category","")}</span>
            </div>
            <p style="color:#ccc;margin:8px 0;">{issue.get("description","")}</p>
            <div style="background:#0d0d1a;padding:8px;border-radius:4px;">
                <b style="color:#4fc3f7;">Fix:</b> <span style="color:#a5d6a7;">{issue.get("fix","")}</span>
            </div>
        </div>"""

    good_html = "".join([f"<li style='color:#4caf50;margin:4px 0;'>✅ {g}</li>" for g in result.get("good_practices", [])])
    rec_html = "".join([f"<li style='color:#4fc3f7;margin:4px 0;'>💡 {r}</li>" for r in result.get("recommendations", [])])

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>DevAudit AI Report</title>
<style>
  body {{ font-family: monospace; background: #0d0d1a; color: white; padding: 30px; }}
  h1 {{ color: #4fc3f7; text-align: center; }}
  h2 {{ color: #4fc3f7; }}
  h3 {{ color: #ff8800; }}
  a {{ color: #4fc3f7; }}
  .score {{ font-size: 36px; font-weight: bold; color: {score_color}; }}
  .summary-box {{ background: #1a1a2e; padding: 16px; border-radius: 8px; margin: 16px 0; }}
  ul {{ padding-left: 20px; }}
  .footer {{ text-align:center; color:#666; margin-top:40px; font-size:12px; }}
</style>
</head>
<body>
<h1>⚙️ DevAudit AI — Security & Code Report</h1>
<p style="text-align:center;color:#888;">Repository: <a href="{repo_url}">{repo_url}</a> | Files Analyzed: {file_count}</p>
<div class="summary-box">
  <h2>Overall Risk Score: <span class="score">{score}/10</span></h2>
  <p style="color:#ccc;">{result.get("summary","")}</p>
</div>
<h2 style="color:#ff8800;">Issues Found ({len(result.get("issues",[]))})</h2>
{issues_html}
<h2 style="color:#4caf50;">Good Practices</h2>
<ul>{good_html}</ul>
<h2 style="color:#4fc3f7;">Top Recommendations</h2>
<ul>{rec_html}</ul>
<div class="footer">Generated by DevAudit AI | huggingface.co/spaces/zahidmohd/devaudit-ai</div>
</body>
</html>"""

    path = "/tmp/DevAuditAI_Report.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

def analyze_repo(repo_url, progress=gr.Progress()):
    if not repo_url.strip():
        return "Please enter a GitHub URL!", "", None
    progress(0.1, desc="Fetching repository files...")
    files, error = get_github_files(repo_url)
    if error:
        return error, "", None
    if not files:
        return "No code files found in this repo!", "", None
    progress(0.4, desc=f"Analyzing {len(files)} files with AI...")
    file_contents = ""
    for fname, content in files.items():
        file_contents += f"\n=== {fname} ===\n{content}\n"
    result = None
    for attempt in range(3):
        try:
            response = hf_client.chat_completion(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze this GitHub repo: {repo_url}\n\nCode files:\n{file_contents[:6000]}"}
                ],
                max_tokens=2000,
                temperature=0.1
            )
            raw = response.choices[0].message.content
            result = safe_parse_json(raw)
            if result:
                break
        except Exception as e:
            if attempt == 2:
                return f"AI Error: {str(e)}", "", None
    if not result:
        return "Could not parse AI response. Please try again!", "", None
    progress(0.8, desc="Generating report...")
    severity_color = {"CRITICAL": "#ff4444", "HIGH": "#ff8800", "MEDIUM": "#ffcc00", "LOW": "#44bb44"}
    score = result.get("severity_score", 5)
    if isinstance(score, str):
        score = int(re.findall(r'\d+', score)[0]) if re.findall(r'\d+', score) else 5
    score_color = "#ff4444" if score >= 7 else "#ff8800" if score >= 4 else "#44bb44"
    issues_html = ""
    for issue in result.get("issues", []):
        color = severity_color.get(issue.get("severity", "LOW"), "#888")
        issues_html += f"""
        <div style='border-left:4px solid {color};padding:12px;margin:10px 0;background:#1a1a2e;border-radius:4px;'>
            <div style='display:flex;justify-content:space-between;flex-wrap:wrap;'>
                <b style='color:{color};'>[{issue.get("severity","?")}] {issue.get("title","")}</b>
                <span style='color:#888;font-size:12px;'>{issue.get("file","")} | {issue.get("category","")}</span>
            </div>
            <p style='color:#ccc;margin:8px 0;'>{issue.get("description","")}</p>
            <div style='background:#0d0d1a;padding:8px;border-radius:4px;'>
                <b style='color:#4fc3f7;'>Fix:</b> <span style='color:#a5d6a7;'>{issue.get("fix","")}</span>
            </div>
        </div>"""
    good_html = "".join([f"<li style='color:#4caf50;margin:4px 0;'>✅ {g}</li>" for g in result.get("good_practices", [])])
    rec_html = "".join([f"<li style='color:#4fc3f7;margin:4px 0;'>💡 {r}</li>" for r in result.get("recommendations", [])])
    html_report = f"""
    <div style='font-family:monospace;background:#0d0d1a;padding:20px;border-radius:8px;color:white;'>
        <h2 style='color:#4fc3f7;'>DevAudit AI — Security & Code Report</h2>
        <p style='color:#888;'>Repository: <a href='{repo_url}' style='color:#4fc3f7;'>{repo_url}</a></p>
        <p style='color:#888;'>Files Analyzed: {len(files)}</p>
        <div style='background:#1a1a2e;padding:16px;border-radius:8px;margin:16px 0;'>
            <h3 style='color:white;'>Overall Risk Score: <span style='color:{score_color};font-size:28px;'>{score}/10</span></h3>
            <p style='color:#ccc;'>{result.get("summary","")}</p>
        </div>
        <h3 style='color:#ff8800;'>Issues Found ({len(result.get("issues",[]))})</h3>
        {issues_html}
        <h3 style='color:#4caf50;'>Good Practices</h3>
        <ul>{good_html}</ul>
        <h3 style='color:#4fc3f7;'>Top Recommendations</h3>
        <ul>{rec_html}</ul>
    </div>"""
    progress(0.9, desc="Generating downloadable report...")
    report_path = generate_html_report(repo_url, result, len(files))
    progress(1.0, desc="Done!")
    return html_report, f"✅ Analyzed {len(files)} files | {len(result.get('issues',[]))} issues found | Risk Score: {score}/10", report_path

with gr.Blocks() as demo:
    gr.HTML("""
    <div style='text-align:center;padding:20px;background:#0d0d1a;border-radius:8px;margin-bottom:10px;'>
        <h1 style='color:#4fc3f7;'>DevAudit AI</h1>
        <p style='color:#888;'>AI-Powered GitHub Repository Security & Code Quality Auditor</p>
        <p style='color:#666;font-size:12px;'>Powered by Qwen2.5-72B | Built for DevOps Engineers</p>
    </div>
    """)
    with gr.Row():
        repo_input = gr.Textbox(
            placeholder="https://github.com/username/repository",
            label="GitHub Repository URL",
            scale=4
        )
        analyze_btn = gr.Button("Audit Repo", variant="primary", scale=1)
    status = gr.Textbox(label="Status", interactive=False)
    report = gr.HTML(label="Audit Report")
    file_output = gr.File(label="⬇️ Download Full Report (.html)")
    gr.Examples(
        examples=[
            ["https://github.com/zahidmohd/sysai-log-analyzer"],
            ["https://github.com/tiangolo/full-stack-fastapi-template"],
        ],
        inputs=repo_input
    )
    analyze_btn.click(
        analyze_repo,
        inputs=[repo_input],
        outputs=[report, status, file_output]
    )

demo.launch()
