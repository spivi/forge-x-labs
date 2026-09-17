"""Generates an animated high-resolution video and GIF showcasing Cloudforge vs. CloudGoat/TerraGoat.

Renders modern HTML5 slides via headless Chrome, captures pixel-perfect frames,
and compiles them into web-optimized MP4 and GIF using ffmpeg.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FFMPEG_PATH = "/opt/homebrew/bin/ffmpeg"

SLIDES = [
    # --- Slide 1: Title Card ---
    {
        "id": "01_title",
        "duration": 4.0,
        "html": """
        <div class="slide slide-center">
            <div class="badge ember">PARADIGM SHIFT IN CLOUD SECURITY TRAINING</div>
            <h1 class="hero-title"><span class="ember-text">cloudforge</span> vs. CloudGoat & TerraGoat</h1>
            <p class="subtitle">Why Local-First, Combinatorically Unique Cloud Labs Solve the Anti-Cheating & Infrastructure Cost Dilemma</p>
            <div class="tags-row">
                <span class="tag">Zero Cloud Credentials</span>
                <span class="tag">Per-Student Seeded Variation</span>
                <span class="tag">Instant Automated Grading</span>
                <span class="tag">12 Scenario Families</span>
            </div>
        </div>
        """,
    },
    # --- Slide 2: The Problem with Traditional Cloud Labs ---
    {
        "id": "02_the_problem",
        "duration": 5.0,
        "html": """
        <div class="slide">
            <div class="badge stop">THE STATUS QUO</div>
            <h2>The Pain of Traditional Cloud Labs (CloudGoat & TerraGoat)</h2>
            <div class="grid-3">
                <div class="card card-stop">
                    <div class="card-icon">💳</div>
                    <h3>Live Cloud Prerequisite</h3>
                    <p>Requires real AWS accounts, administrative IAM keys, and credit cards. Risky orphan resources (NAT gateways, RDS, ALBs) accumulate unexpected billing.</p>
                </div>
                <div class="card card-stop">
                    <div class="card-icon">📋</div>
                    <h3>Zero Student Variation</h3>
                    <p>Static HCL templates give every participant identical ARNs, resource names, and attack paths. Answers and flags are copied across cohorts instantly.</p>
                </div>
                <div class="card card-stop">
                    <div class="card-icon">⏳</div>
                    <h3>High Friction & Manual Grading</h3>
                    <p>15-minute <code>terraform apply</code> and fragile <code>destroy</code> steps. Instructors must manually review accounts or collect screenshots to grade.</p>
                </div>
            </div>
        </div>
        """,
    },
    # --- Slide 3: Cloudforge's Unique Value Proposition ---
    {
        "id": "03_value_prop",
        "duration": 5.5,
        "html": """
        <div class="slide">
            <div class="badge ember">THE SOLUTION</div>
            <h2>The Cloudforge Breakthrough: Local, Unique, Auto-Graded</h2>
            <div class="grid-3">
                <div class="card card-ember">
                    <div class="card-icon">🛡️</div>
                    <h3>100% Local-First ($0.00)</h3>
                    <p>Deterministic graph engine and static analysis. Evaluated locally via OPA and Checkov. <code>terraform apply</code> is blocked by contract. Zero cloud accounts needed.</p>
                </div>
                <div class="card card-ember">
                    <div class="card-icon">🎲</div>
                    <h3>Combinatoric Seed Uniqueness</h3>
                    <p><code>--seed &lt;N&gt;</code> generates distinct namespaces, decoys, intermediate IAM hops, and varying noise. No two students can copy ARNs or attack paths.</p>
                </div>
                <div class="card card-ember">
                    <div class="card-icon">⚡</div>
                    <h3>Sub-Second Auto-Grading</h3>
                    <p>Stripped student estate versus instructor key. Instant precision/recall grading via <code>cloudforge grade</code>.</p>
                </div>
            </div>
        </div>
        """,
    },
    # --- Slide 4: Step 1 Lab Generation & Stripping ---
    {
        "id": "04_lab_generate",
        "duration": 5.0,
        "html": """
        <div class="slide">
            <div class="badge pass">WORKFLOW STEP 1</div>
            <h2>Generating a Deterministic, Stripped Student Lab</h2>
            <div class="terminal-window">
                <div class="term-bar"><span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span><span class="term-title">terminal - bash</span></div>
                <div class="term-body">
                    <div class="cmd-line"><span class="prompt">$</span> cloudforge lab examples/ec2_imds_credential_exfil.yaml --seed 17 --out lab_alice/</div>
                    <div class="cmd-out pass-text">lab student=lab_alice/student instructor=lab_alice/instructor</div>
                </div>
            </div>
            <div class="split-cards">
                <div class="card">
                    <h4 class="pass-text">student/ (stripped pack)</h4>
                    <ul>
                        <li><code>brief.md</code>: Scenario investigation narrative (zero answer leaks)</li>
                        <li><code>estate.html</code>: Standalone interactive topology visualizer</li>
                        <li><code>estate.json</code>: Graph nodes & edges with all risk/security labels stripped</li>
                        <li><code>terraform/</code>: Valid syntax HCL (never applied)</li>
                    </ul>
                </div>
                <div class="card">
                    <h4 class="ember-text">instructor/ (Hidden Answer Key)</h4>
                    <ul>
                        <li><code>grade_key.json</code>: Ground-truth paths & finding signatures</li>
                        <li><code>ground_truth_paths.json</code>: Exact sequence of compromise</li>
                        <li><code>expected_findings.json</code>: Labeled findings with severity</li>
                        <li><code>report.md</code>: Complete executive & engineering risk briefing</li>
                    </ul>
                </div>
            </div>
        </div>
        """,
    },
    # --- Slide 5: Step 2 Student Investigation & Topology ---
    {
        "id": "05_student_investigation",
        "duration": 5.0,
        "html": """
        <div class="slide">
            <div class="badge ember">WORKFLOW STEP 2</div>
            <h2>Student Investigation: Attack Path & Submission</h2>
            <div class="grid-2">
                <div class="card">
                    <h3>Discovered Attack Path (Seed 17)</h3>
                    <div class="flow-chart">
                        <div class="flow-node highlight">Internet Ingress (0.0.0.0/0)</div>
                        <div class="flow-arrow">⬇️</div>
                        <div class="flow-node alert">EC2 Instance (IMDSv1 enabled)</div>
                        <div class="flow-arrow">⬇️ SSRF Metadata Exfiltration</div>
                        <div class="flow-node">IAM Role: WebAppInstanceRole</div>
                        <div class="flow-arrow">⬇️ s3:Get* / s3:List*</div>
                        <div class="flow-node danger">S3: customer-pii-records-000000000000</div>
                    </div>
                </div>
                <div class="terminal-window">
                    <div class="term-bar"><span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span><span class="term-title">student_submission.yaml</span></div>
                    <div class="term-body">
                        <pre><code>paths:
  - nodes:
      - core0/ec2-web-frontend
      - core0/role-web-app
      - core0/s3-customer-pii
      - core0/data-customer-pii
findings:
  - ec2_imdsv1_enabled
  - iam_excessive_privilege</code></pre>
                    </div>
                </div>
            </div>
        </div>
        """,
    },
    # --- Slide 6: Step 3 Instant Automated Grading ---
    {
        "id": "06_auto_grading",
        "duration": 5.0,
        "html": """
        <div class="slide">
            <div class="badge pass">WORKFLOW STEP 3</div>
            <h2>Instant Automated Grading in &lt; 50 Milliseconds</h2>
            <div class="terminal-window">
                <div class="term-bar"><span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span><span class="term-title">terminal - instructor grade</span></div>
                <div class="term-body">
                    <div class="cmd-line"><span class="prompt">$</span> cloudforge grade lab_alice/ --submission student_submission.yaml</div>
                    <div class="cmd-out pass-text">paths hit 1 miss 0  findings hit 2 miss 1  extras 0</div>
                </div>
            </div>
            <div class="grid-3 stats-row">
                <div class="stat-box pass-border">
                    <div class="stat-number pass-text">100%</div>
                    <div class="stat-label">Attack Path Precision</div>
                </div>
                <div class="stat-box pass-border">
                    <div class="stat-number pass-text">0.03s</div>
                    <div class="stat-label">Grading Execution Time</div>
                </div>
                <div class="stat-box ember-border">
                    <div class="stat-number ember-text">$0.00</div>
                    <div class="stat-label">Cloud Infrastructure Cost</div>
                </div>
            </div>
        </div>
        """,
    },
    # --- Slide 7: Step 4 Cohort Management ---
    {
        "id": "07_cohort_orchestration",
        "duration": 5.0,
        "html": """
        <div class="slide">
            <div class="badge ember">WORKFLOW STEP 4</div>
            <h2>Team Cohort Orchestration (Scale to 30+ Analysts)</h2>
            <div class="terminal-window">
                <div class="term-bar"><span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span><span class="term-title">terminal - cohort automation</span></div>
                <div class="term-body">
                    <div class="cmd-line"><span class="prompt">$</span> cloudforge lab-cohort examples/ci_cd_iam_chain.yaml --roster team.txt --out cohort_spring/</div>
                    <div class="cmd-out pass-text">wrote 12 student packs across 12 distinct seeds to cohort_spring/</div>
                    <div class="cmd-line" style="margin-top:12px;"><span class="prompt">$</span> cloudforge grade-cohort --labs cohort_spring/ --submissions submissions/ --out retro.md</div>
                    <div class="cmd-out pass-text">wrote class grade roster (12 students) to retro.md</div>
                </div>
            </div>
            <div class="card roster-card">
                <h3>Auto-Generated Class Roster (<code>retro.md</code>)</h3>
                <table class="roster-table">
                    <thead><tr><th>Student</th><th>Seed</th><th>Path Hits</th><th>Finding Hits</th><th>Score</th><th>Status</th></tr></thead>
                    <tbody>
                        <tr><td>alice</td><td>seed-42</td><td>1/1</td><td>4/4</td><td>100%</td><td class="pass-text">PASS</td></tr>
                        <tr><td>bob</td><td>seed-108</td><td>1/1</td><td>3/4</td><td>85%</td><td class="pass-text">PASS</td></tr>
                        <tr><td>charlie</td><td>seed-771</td><td>1/1</td><td>4/4</td><td>100%</td><td class="pass-text">PASS</td></tr>
                        <tr><td>dave</td><td>seed-904</td><td>0/1</td><td>2/4</td><td>40%</td><td class="stop-text">RETRY</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        """,
    },
    # --- Slide 8: Head-to-Head Comparison Matrix ---
    {
        "id": "08_comparison_matrix",
        "duration": 5.5,
        "html": """
        <div class="slide">
            <div class="badge ember">HEAD-TO-HEAD</div>
            <h2>Comprehensive Comparison: CloudGoat vs. TerraGoat vs. Cloudforge</h2>
            <table class="matrix-table">
                <thead>
                    <tr><th>Capability / Feature</th><th>CloudGoat (Rhino)</th><th>TerraGoat (Bridgecrew)</th><th>Cloudforge (v1)</th></tr>
                </thead>
                <tbody>
                    <tr><td>AWS Account Required</td><td class="cell-stop">Yes (Live AWS)</td><td class="cell-stop">Yes (Live AWS)</td><td class="cell-pass">None (100% Local)</td></tr>
                    <tr><td>Cloud Infrastructure Billing</td><td class="cell-stop">$$$ Uncapped</td><td class="cell-stop">$$ Uncapped</td><td class="cell-pass">$0.00 Forever</td></tr>
                    <tr><td>Per-Student Uniqueness</td><td class="cell-stop">Static (Same ARNs)</td><td class="cell-stop">Static (Same ARNs)</td><td class="cell-pass">Combinatoric (--seed)</td></tr>
                    <tr><td>Setup & Teardown Time</td><td class="cell-stop">15 min apply / 10 min destroy</td><td class="cell-stop">10 min apply / 10 min destroy</td><td class="cell-pass">&lt; 100 ms (Instant)</td></tr>
                    <tr><td>Automated Path Grading</td><td class="cell-stop">None (Manual)</td><td class="cell-stop">None (Manual)</td><td class="cell-pass">Built-in (cloudforge grade)</td></tr>
                    <tr><td>Cohort / Class Management</td><td class="cell-stop">Manual scripting</td><td class="cell-stop">None</td><td class="cell-pass">Built-in (lab-cohort)</td></tr>
                    <tr><td>Answer Key Separation</td><td class="cell-stop">None</td><td class="cell-stop">None</td><td class="cell-pass">Strict seam</td></tr>
                    <tr><td>Scenario Catalog (v1)</td><td>~10 scenarios</td><td>~8 scenarios</td><td class="cell-pass">12 Validated Families</td></tr>
                </tbody>
            </table>
        </div>
        """,
    },
    # --- Slide 9: 12 Families & Call to Action ---
    {
        "id": "09_catalog_cta",
        "duration": 4.5,
        "html": """
        <div class="slide slide-center">
            <div class="badge ember">v1 RELEASE READY</div>
            <h2>12 Complete Cloud Misconfiguration Families</h2>
            <div class="catalog-tags">
                <span class="c-tag">IAM PrivEsc Versioning</span>
                <span class="c-tag">EC2 IMDSv1 SSRF Exfil</span>
                <span class="c-tag">Lambda Public Function URLs</span>
                <span class="c-tag">Secrets Manager Wildcards</span>
                <span class="c-tag">Public RDS Database</span>
                <span class="c-tag">ECR Public Container Read</span>
                <span class="c-tag">SQS Queue Policy Leak</span>
                <span class="c-tag">KMS Overbroad Decrypt</span>
                <span class="c-tag">Public EBS Snapshots</span>
                <span class="c-tag">Cross-Account Trust</span>
                <span class="c-tag">CI/CD IAM PassRole Chain</span>
                <span class="c-tag">Public S3 Data Exposure</span>
            </div>
            <div class="cta-box">
                <div class="cta-cmd"><code>pip install cloudforge</code></div>
                <p class="cta-sub">Open Source · Apache-2.0 License · github.com/spivi/forge-x-labs</p>
            </div>
        </div>
        """,
    },
]

CSS = """
:root {
    --bg: #17150f;
    --bg-raise: #201d15;
    --bg-panel: #262218;
    --ink: #f2ede1;
    --ink-soft: #c4bca8;
    --ink-faint: #8b8371;
    --rule: #3a352a;
    --ember: #e8873a;
    --ember-deep: #c96a22;
    --pass: #6fbf73;
    --pass-bg: rgba(111,191,115,.12);
    --stop: #d6705f;
    --stop-bg: rgba(214,112,95,.11);
    --code-bg: #0d0c08;
    --font-sans: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --font-mono: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    width: 1280px;
    height: 720px;
    background: var(--bg);
    color: var(--ink);
    font-family: var(--font-sans);
    overflow: hidden;
    position: relative;
}

.slide {
    width: 1280px;
    height: 720px;
    padding: 48px 64px;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
}

.slide-center {
    justify-content: center;
    align-items: center;
    text-align: center;
}

.badge {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 4px 12px;
    border-radius: 999px;
    margin-bottom: 16px;
    width: fit-content;
}
.badge.ember { background: rgba(232,135,58,0.18); color: var(--ember); border: 1px solid var(--ember); }
.badge.pass { background: var(--pass-bg); color: var(--pass); border: 1px solid var(--pass); }
.badge.stop { background: var(--stop-bg); color: var(--stop); border: 1px solid var(--stop); }

h1.hero-title {
    font-size: 44px;
    font-weight: 800;
    line-height: 1.15;
    margin-bottom: 16px;
    letter-spacing: -0.02em;
}

h2 {
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 24px;
    letter-spacing: -0.01em;
}

.ember-text { color: var(--ember); }
.pass-text { color: var(--pass); }
.stop-text { color: var(--stop); }

.subtitle {
    font-size: 20px;
    color: var(--ink-soft);
    max-width: 800px;
    line-height: 1.5;
    margin-bottom: 32px;
}

.tags-row {
    display: flex;
    gap: 12px;
    justify-content: center;
}

.tag {
    background: var(--bg-panel);
    border: 1px solid var(--rule);
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    color: var(--ink-soft);
}

.grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
}

.grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
}

.card {
    background: var(--bg-raise);
    border: 1px solid var(--rule);
    border-radius: 12px;
    padding: 24px;
}

.card h3 {
    font-size: 18px;
    margin-bottom: 12px;
}

.card p {
    font-size: 14px;
    color: var(--ink-soft);
    line-height: 1.6;
}

.card-icon {
    font-size: 28px;
    margin-bottom: 12px;
}

.card-stop { border-top: 3px solid var(--stop); }
.card-ember { border-top: 3px solid var(--ember); }

.terminal-window {
    background: var(--code-bg);
    border: 1px solid var(--rule);
    border-radius: 10px;
    overflow: hidden;
    font-family: var(--font-mono);
    margin-bottom: 20px;
}

.term-bar {
    background: var(--bg-panel);
    padding: 8px 14px;
    display: flex;
    align-items: center;
    border-bottom: 1px solid var(--rule);
}

.dot { width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
.dot.red { background: #e06c75; }
.dot.yellow { background: #e5c07b; }
.dot.green { background: #98c379; }
.term-title { font-size: 11px; color: var(--ink-faint); margin-left: 8px; }

.term-body {
    padding: 16px 20px;
    font-size: 13px;
    line-height: 1.5;
}

.prompt { color: var(--ember); font-weight: 700; margin-right: 8px; }
.cmd-line { color: #abb2bf; font-weight: 600; }
.cmd-out { margin-top: 6px; font-size: 13px; }

.split-cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}

.split-cards ul {
    list-style: none;
    margin-top: 12px;
}

.split-cards li {
    font-size: 13px;
    color: var(--ink-soft);
    line-height: 1.6;
    margin-bottom: 6px;
}

.split-cards code {
    background: var(--code-bg);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: var(--font-mono);
    color: var(--ink);
    font-size: 12px;
}

.flow-chart {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    margin-top: 12px;
}

.flow-node {
    background: var(--bg-panel);
    border: 1px solid var(--rule);
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    width: 100%;
    text-align: center;
}

.flow-node.highlight { border-color: var(--ember); color: var(--ember); }
.flow-node.alert { border-color: var(--stop); color: var(--stop); }
.flow-node.danger { background: var(--stop-bg); border-color: var(--stop); color: var(--stop); }
.flow-arrow { font-size: 11px; color: var(--ink-faint); }

.stats-row {
    margin-top: 16px;
}

.stat-box {
    background: var(--bg-raise);
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    border: 1px solid var(--rule);
}
.stat-box.pass-border { border-color: rgba(111,191,115,0.4); }
.stat-box.ember-border { border-color: rgba(232,135,58,0.4); }

.stat-number { font-size: 36px; font-weight: 800; font-family: var(--font-mono); margin-bottom: 4px; }
.stat-label { font-size: 13px; color: var(--ink-soft); }

.roster-card { padding: 16px 20px; }
.roster-card h3 { font-size: 15px; margin-bottom: 12px; }

.roster-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

.roster-table th, .roster-table td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid var(--rule);
}

.roster-table th { color: var(--ink-faint); font-weight: 600; font-size: 11px; text-transform: uppercase; }

.matrix-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    background: var(--bg-raise);
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid var(--rule);
}

.matrix-table th, .matrix-table td {
    padding: 10px 16px;
    text-align: left;
    border-bottom: 1px solid var(--rule);
}

.matrix-table th {
    background: var(--bg-panel);
    color: var(--ink-soft);
    font-size: 12px;
    font-weight: 700;
}

.cell-stop { color: var(--stop); font-weight: 600; }
.cell-pass { color: var(--pass); font-weight: 700; background: var(--pass-bg); }

.catalog-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    justify-content: center;
    max-width: 900px;
    margin: 20px auto 32px;
}

.c-tag {
    background: var(--bg-panel);
    border: 1px solid var(--rule);
    padding: 8px 14px;
    border-radius: 6px;
    font-size: 13px;
    color: var(--ink-soft);
    font-weight: 600;
}

.cta-box { margin-top: 10px; }
.cta-cmd {
    display: inline-block;
    background: var(--code-bg);
    border: 1px solid var(--ember);
    padding: 12px 28px;
    border-radius: 8px;
    font-family: var(--font-mono);
    font-size: 18px;
    color: var(--ember);
    margin-bottom: 12px;
}
.cta-sub { font-size: 14px; color: var(--ink-faint); }
"""


def render_html(body: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


def capture_slides(work_dir: Path) -> list[tuple[Path, float]]:
    slide_files: list[tuple[Path, float]] = []
    for idx, slide in enumerate(SLIDES):
        html_file = work_dir / f"slide_{idx:02d}_{slide['id']}.html"
        png_file = work_dir / f"frame_{idx:02d}.png"
        html_content = render_html(slide["html"])
        html_file.write_text(html_content, encoding="utf-8")

        cmd = [
            CHROME_PATH,
            "--headless",
            "--disable-gpu",
            "--force-color-profile=srgb",
            "--window-size=1280,720",
            f"--screenshot={png_file}",
            f"file://{html_file}",
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        slide_files.append((png_file, slide["duration"]))
    return slide_files


def encode_video(slide_files: list[tuple[Path, float]], out_mp4: Path, out_gif: Path) -> None:
    # Create an ffmpeg concat demuxer input file
    temp_dir = slide_files[0][0].parent
    concat_file = temp_dir / "slides.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for png_path, duration in slide_files:
            f.write(f"file '{png_path.resolve()}'\n")
            f.write(f"duration {duration}\n")
        # Concat demuxer needs last file repeated without duration to display it properly
        f.write(f"file '{slide_files[-1][0].resolve()}'\n")

    # Encode MP4 (H.264, 30fps)
    mp4_cmd = [
        FFMPEG_PATH,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-vf",
        "fps=30,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        str(out_mp4),
    ]
    subprocess.run(mp4_cmd, check=True, capture_output=True)

    # Encode GIF (High-quality 2-pass palette generation)
    gif_palette = temp_dir / "palette.png"
    palette_cmd = [
        FFMPEG_PATH,
        "-y",
        "-i",
        str(out_mp4),
        "-vf",
        "fps=12,scale=960:-1:flags=lanczos,palettegen",
        str(gif_palette),
    ]
    subprocess.run(palette_cmd, check=True, capture_output=True)

    gif_cmd = [
        FFMPEG_PATH,
        "-y",
        "-i",
        str(out_mp4),
        "-i",
        str(gif_palette),
        "-lavfi",
        "fps=12,scale=960:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=4",
        str(out_gif),
    ]
    subprocess.run(gif_cmd, check=True, capture_output=True)


def main() -> None:
    out_dir = Path("docs/demo")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = out_dir / "cloudforge-vs-cloudgoat.mp4"
    out_gif = out_dir / "cloudforge-vs-cloudgoat.gif"

    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        slides = capture_slides(work_dir)
        encode_video(slides, out_mp4, out_gif)

    print(f"Generated: {out_mp4} ({os.path.getsize(out_mp4)} bytes)")
    print(f"Generated: {out_gif} ({os.path.getsize(out_gif)} bytes)")


if __name__ == "__main__":
    main()
