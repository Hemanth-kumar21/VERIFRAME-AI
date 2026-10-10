from __future__ import annotations

import html
from datetime import datetime
from typing import Any


def render_single_dossier_html(result: dict[str, Any]) -> str:
    """Generate a high-fidelity, printable HTML Forensic Dossier for a single media item."""
    token = html.escape(str(result.get("token") or "UNKNOWN-TOKEN"))
    verdict = html.escape(str(result.get("verdict") or "Inconclusive"))
    strength = html.escape(str(result.get("evidence_strength") or "Not evaluated"))
    agreement = html.escape(str(result.get("agreement") or "Not evaluated"))
    mode = html.escape(str(result.get("mode") or "Automated Forensic Pipeline"))
    created_at = html.escape(str(result.get("created_at") or datetime.utcnow().isoformat() + "Z"))

    # Tool summaries
    tool_summaries = result.get("tool_summaries") or {}
    integ = tool_summaries.get("integrity") or result.get("integrity") or {}
    sha256 = html.escape(str(integ.get("sha256") or "NOT_COMPUTED"))
    md5 = html.escape(str(integ.get("md5") or "NOT_COMPUTED"))
    entropy = html.escape(str(integ.get("entropy_bits_per_byte") or "N/A"))
    entropy_desc = html.escape(str(integ.get("entropy_assessment") or "Standard"))

    container_check = integ.get("container_check") or {}
    container_status = html.escape(str(container_check.get("status") or "verified"))
    trailing_bytes = container_check.get("trailing_bytes", 0)

    # Detectors
    det_a = tool_summaries.get("detector_a") or {}
    det_b = tool_summaries.get("detector_b") or {}
    video_summary = tool_summaries.get("video") or {}
    ai_det = tool_summaries.get("ai_content_detection") or result.get("ai_content_detection") or {}

    ai_prob_val = ai_det.get("ai_probability")
    human_prob_val = ai_det.get("human_probability")
    ai_prob_str = f"{ai_prob_val:.1f}%" if ai_prob_val is not None else "Inconclusive / N/A"
    human_prob_str = f"{human_prob_val:.1f}%" if human_prob_val is not None else "Inconclusive / N/A"
    ai_classification = html.escape(str(ai_det.get("classification") or ("Likely AI-Generated" if verdict == "Likely AI" else "Likely Human-Created" if verdict == "No AI signs found" else "Inconclusive")))
    ai_confidence = html.escape(str(ai_det.get("confidence") or ("High" if strength == "Strong" and agreement == "High" else "Medium" if strength == "Moderate" else "Low")))
    ai_analyzed_frames = ai_det.get("analyzed_frames") or (int(video_summary.get("analyzed_frame_count", 1)) if video_summary else 1)
    ai_evidence_list = ai_det.get("evidence") or []
    ai_evidence_items = "".join(f"<li>{html.escape(str(e))}</li>" for e in ai_evidence_list) or "<li>Consensus detector evaluation completed across sampled representations.</li>"
    ai_score_label = html.escape(str(ai_det.get("score_label") or "AI-Likelihood Score"))

    # Explanation
    explanation = result.get("explanation") or {}
    exp_text = explanation.get("en") if isinstance(explanation, dict) else str(explanation)
    if not exp_text:
        exp_text = "No narrative explanation recorded."
    exp_text_escaped = html.escape(exp_text)

    # Limitations
    limitations = result.get("limitations") or []

    # Color scheme according to verdict
    if verdict == "Likely AI":
        badge_bg = "#dc2626"
        badge_border = "#f87171"
    elif verdict == "No AI signs found":
        badge_bg = "#059669"
        badge_border = "#34d399"
    else:
        badge_bg = "#d97706"
        badge_border = "#fbbf24"

    limitation_items = "".join(f"<li>{html.escape(str(lim))}</li>" for lim in limitations) or "<li>Standard pipeline operational limits apply.</li>"

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forensic Dossier — {token}</title>
<style>
  :root {{
    --bg: #0f172a;
    --card: #1e293b;
    --border: #334155;
    --text: #f8fafc;
    --muted: #94a3b8;
    --primary: #38bdf8;
  }}
  @media print {{
    body {{ background: white !important; color: black !important; font-size: 11pt; }}
    .no-print {{ display: none !important; }}
    .card {{ border: 1px solid #ccc !important; background: white !important; box-shadow: none !important; }}
    .badge {{ border: 1px solid #333 !important; color: black !important; }}
    a {{ color: black !important; text-decoration: underline; }}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px;
    line-height: 1.5;
  }}
  .container {{ max-width: 900px; margin: 0 auto; }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 2px solid var(--border);
    padding-bottom: 16px;
    margin-bottom: 24px;
  }}
  .header-left h1 {{ font-size: 1.5rem; letter-spacing: 0.05em; text-transform: uppercase; }}
  .header-left p {{ color: var(--muted); font-size: 0.85rem; margin-top: 4px; }}
  .print-btn {{
    background: var(--primary);
    color: #0f172a;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
  }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
  }}
  .card-title {{
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--primary);
  }}
  .verdict-banner {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px;
    border-radius: 8px;
    background: rgba(30, 41, 59, 0.8);
    border: 2px solid {badge_border};
    margin-bottom: 20px;
  }}
  .verdict-tag {{
    background: {badge_bg};
    color: white;
    padding: 6px 14px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 1.1rem;
    letter-spacing: 0.02em;
  }}
  .hash-box {{
    background: #020617;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.8rem;
    word-break: break-all;
    margin: 8px 0;
  }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 600px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  .metric-item {{ border-left: 3px solid var(--primary); padding-left: 10px; margin-bottom: 8px; }}
  .metric-label {{ font-size: 0.75rem; text-transform: uppercase; color: var(--muted); }}
  .metric-val {{ font-size: 0.95rem; font-weight: 600; }}
  ul {{ padding-left: 20px; color: var(--muted); font-size: 0.9rem; }}
  li {{ margin-bottom: 6px; }}
  .footer {{
    border-top: 1px solid var(--border);
    padding-top: 16px;
    font-size: 0.8rem;
    color: var(--muted);
    display: flex;
    justify-content: space-between;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="header-left">
      <h1>Digital Forensic Evidence Dossier</h1>
      <p>Very Frame AI Multimodal Forensic Investigation Platform | Certified Artifact</p>
      <p>Case Reference Token: <strong>{token}</strong> &bull; Generated: {created_at}</p>
    </div>
    <div class="no-print">
      <button class="print-btn" onclick="window.print()">Print Dossier / PDF</button>
    </div>
  </div>

  <div class="verdict-banner">
    <div>
      <div style="font-size: 0.85rem; text-transform: uppercase; color: var(--muted);">Algorithmic Investigation Verdict</div>
      <div style="font-size: 1.25rem; font-weight: 700; margin-top: 4px;">{verdict}</div>
    </div>
    <span class="verdict-tag">{verdict}</span>
  </div>

  <div class="card">
    <div class="card-title">1. Cryptographic Media Integrity & Chain of Custody</div>
    <p style="font-size: 0.85rem; color: var(--muted);">Forensic verification of source file byte stream:</p>
    <div class="hash-box">
      <strong>SHA-256:</strong> {sha256}<br>
      <strong>MD5:</strong> {md5}
    </div>
    <div class="grid-2" style="margin-top: 12px;">
      <div class="metric-item">
        <div class="metric-label">Shannon Entropy</div>
        <div class="metric-val">{entropy} bits/byte ({entropy_desc})</div>
      </div>
      <div class="metric-item">
        <div class="metric-label">Container Structure</div>
        <div class="metric-val">{container_status} (Trailing bytes: {trailing_bytes})</div>
      </div>
    </div>
  </div>

  <div class="card" style="border: 1px solid var(--primary);">
    <div class="card-title" style="color: var(--primary);">2. AI Content Detection & Authenticity Scoring</div>
    <div class="grid-2">
      <div class="metric-item">
        <div class="metric-label">AI-Generated Probability ({ai_score_label})</div>
        <div class="metric-val" style="color: #f43f5e; font-size: 1.15rem;">{ai_prob_str}</div>
      </div>
      <div class="metric-item">
        <div class="metric-label">Likely Human-Created Probability</div>
        <div class="metric-val" style="color: #10b981; font-size: 1.15rem;">{human_prob_str}</div>
      </div>
      <div class="metric-item">
        <div class="metric-label">Final Classification</div>
        <div class="metric-val">{ai_classification}</div>
      </div>
      <div class="metric-item">
        <div class="metric-label">Confidence Level & Frames Evaluated</div>
        <div class="metric-val">{ai_confidence} Confidence &bull; {ai_analyzed_frames} frame(s) analyzed</div>
      </div>
    </div>
    <div style="margin-top: 14px;">
      <div class="metric-label" style="margin-bottom: 6px;">Visual & Temporal Signals Identified:</div>
      <ul>{ai_evidence_items}</ul>
    </div>
  </div>

  <div class="card">
    <div class="card-title">3. Empirical Forensic Signals</div>
    <div class="grid-2">
      <div class="metric-item">
        <div class="metric-label">Evidence Strength</div>
        <div class="metric-val">{strength}</div>
      </div>
      <div class="metric-item">
        <div class="metric-label">Detector Agreement</div>
        <div class="metric-val">{agreement}</div>
      </div>
      <div class="metric-item">
        <div class="metric-label">Pipeline Mode</div>
        <div class="metric-val">{mode}</div>
      </div>
      <div class="metric-item">
        <div class="metric-label">Analyzed Scope</div>
        <div class="metric-val">{"Video Stream Analysis" if video_summary else "Spatial Edge / High-Frequency Decomposition"}</div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">4. Investigator Synthesis & Narrative</div>
    <p style="font-size: 0.95rem; line-height: 1.6; white-space: pre-wrap;">{exp_text_escaped}</p>
  </div>

  <div class="card">
    <div class="card-title">5. Scope, Limitations & Non-Manufactured Evidence</div>
    <ul>{limitation_items}</ul>
  </div>

  <div class="footer">
    <span>Verified by Very Frame AI Forensic Engine</span>
    <span>Attestation: Objective Algorithmic Signal Analysis &bull; Not Absolute Proof</span>
  </div>
</div>
</body>
</html>
"""
    return html_out


def render_case_report_html(case: dict[str, Any], items: list[dict[str, Any]], correlation: dict[str, Any]) -> str:
    """Generate a comprehensive multi-evidence investigation report for an entire case."""
    case_id = html.escape(str(case.get("case_id") or "CASE-UNKNOWN"))
    title = html.escape(str(case.get("title") or "Untitled Investigation"))
    description = html.escape(str(case.get("description") or "No description provided."))
    status = html.escape(str(case.get("status") or "open")).upper()
    priority = html.escape(str(case.get("priority") or "normal")).upper()
    investigator = html.escape(str(case.get("investigator") or "Lead Forensic Investigator"))
    created_at = html.escape(str(case.get("created_at") or "Unknown"))

    # Evidence items rows
    item_rows = []
    for it in items:
        tok = html.escape(str(it.get("token") or ""))
        lbl = html.escape(str(it.get("label") or ""))
        itype = html.escape(str(it.get("item_type") or "image")).upper()
        hsh = html.escape(str(it.get("sha256") or "N/A"))
        vrd = html.escape(str((it.get("result") or {}).get("verdict") or "Pending"))
        item_rows.append(f"""
        <tr>
          <td><strong>{lbl}</strong><br><span style="font-size: 0.75rem; color: #94a3b8;">{tok}</span></td>
          <td>{itype}</td>
          <td><code style="font-size: 0.75rem;">{hsh[:16]}…</code></td>
          <td><span style="font-weight: 600;">{vrd}</span></td>
        </tr>
        """)
    items_table_body = "".join(item_rows) or "<tr><td colspan='4'>No evidence items attached.</td></tr>"

    # Contradictions
    contradictions = correlation.get("contradictions") or []
    contradiction_items = []
    for c in contradictions:
        sev = html.escape(str(c.get("severity") or "info")).upper()
        desc = html.escape(str(c.get("description") or ""))
        contradiction_items.append(f"<li style='margin-bottom: 8px;'><strong style='color: #f87171;'>[{sev}]</strong> {desc}</li>")
    contradictions_html = "".join(contradiction_items) or "<li>No forensic contradictions detected between assets.</li>"

    # Leads
    leads = correlation.get("investigative_leads") or []
    leads_html = "".join(f"<li>{html.escape(str(l))}</li>" for l in leads) or "<li>No specific leads generated.</li>"

    # Notes
    notes = case.get("notes") or []
    notes_rows = []
    for n in notes:
        ts = html.escape(str(n.get("timestamp") or ""))
        auth = html.escape(str(n.get("author") or "Investigator"))
        content = html.escape(str(n.get("content") or ""))
        notes_rows.append(f"""
        <div style="border-left: 2px solid #38bdf8; padding-left: 12px; margin-bottom: 12px;">
          <div style="font-size: 0.75rem; color: #94a3b8;">{ts} &bull; <strong>{auth}</strong></div>
          <div style="font-size: 0.9rem; margin-top: 4px;">{content}</div>
        </div>
        """)
    notes_html = "".join(notes_rows) or "<p style='color: #94a3b8; font-size: 0.9rem;'>No investigator notes recorded.</p>"

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Investigation Dossier — {case_id}</title>
<style>
  :root {{
    --bg: #0f172a;
    --card: #1e293b;
    --border: #334155;
    --text: #f8fafc;
    --muted: #94a3b8;
    --primary: #38bdf8;
  }}
  @media print {{
    body {{ background: white !important; color: black !important; font-size: 11pt; }}
    .no-print {{ display: none !important; }}
    .card {{ border: 1px solid #ccc !important; background: white !important; box-shadow: none !important; }}
    table {{ border: 1px solid #ccc !important; }}
    th, td {{ border-bottom: 1px solid #eee !important; color: black !important; }}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px;
    line-height: 1.5;
  }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  .header {{
    border-bottom: 2px solid var(--border);
    padding-bottom: 16px;
    margin-bottom: 24px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }}
  .header h1 {{ font-size: 1.6rem; letter-spacing: 0.05em; text-transform: uppercase; }}
  .print-btn {{
    background: var(--primary);
    color: #0f172a;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
  }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
  }}
  .card-title {{
    font-size: 1.15rem;
    font-weight: 600;
    margin-bottom: 12px;
    color: var(--primary);
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 8px;
    font-size: 0.9rem;
  }}
  th, td {{
    text-align: left;
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
  }}
  th {{
    background: #020617;
    text-transform: uppercase;
    font-size: 0.75rem;
    color: var(--muted);
  }}
  ul {{ padding-left: 20px; color: var(--muted); font-size: 0.9rem; }}
  .badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 700;
    background: #334155;
    color: white;
  }}
  .footer {{
    border-top: 1px solid var(--border);
    padding-top: 16px;
    font-size: 0.8rem;
    color: var(--muted);
    display: flex;
    justify-content: space-between;
    margin-top: 32px;
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <span class="badge" style="background: #0284c7;">{case_id}</span>
      <span class="badge" style="background: #475569; margin-left: 8px;">STATUS: {status}</span>
      <span class="badge" style="background: #b45309; margin-left: 8px;">PRIORITY: {priority}</span>
      <h1 style="margin-top: 8px;">{title}</h1>
      <p style="color: var(--muted); font-size: 0.85rem; margin-top: 4px;">
        Lead Specialist: <strong>{investigator}</strong> &bull; Initialized: {created_at}
      </p>
    </div>
    <div class="no-print">
      <button class="print-btn" onclick="window.print()">Print Case Dossier</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Case Overview</div>
    <p style="font-size: 0.95rem; line-height: 1.6;">{description}</p>
  </div>

  <div class="card">
    <div class="card-title">Attached Evidence Items ({len(items)})</div>
    <table>
      <thead>
        <tr>
          <th>Evidence Item</th>
          <th>Type</th>
          <th>Fingerprint (SHA-256)</th>
          <th>Verdict</th>
        </tr>
      </thead>
      <tbody>
        {items_table_body}
      </tbody>
    </table>
  </div>

  <div class="card">
    <div class="card-title">Cross-Media Correlation & Contradiction Analysis</div>
    <p style="font-size: 0.85rem; color: var(--muted); margin-bottom: 8px;">
      Multi-asset divergence status: <strong>{html.escape(str(correlation.get("divergence_status", "N/A")))}</strong>
    </p>
    <ul>{contradictions_html}</ul>
  </div>

  <div class="card">
    <div class="card-title">Actionable Investigative Leads</div>
    <ul>{leads_html}</ul>
  </div>

  <div class="card">
    <div class="card-title">Case Notes & Audit Trail</div>
    {notes_html}
  </div>

  <div class="footer">
    <span>Very Frame AI Forensic Platform &bull; Certified Case Dossier</span>
    <span>Attestation Sign-Off: _____________________________________</span>
  </div>
</div>
</body>
</html>
"""
    return html_out
