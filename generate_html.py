"""
PARI Spain — HTML Dashboard Generator - Rosanna Michele Alvarez Diaz (RMAD)
======================================
Lee los datos calculados por collect_data.py y genera
el archivo index.html listo para publicar en GitHub Pages.

Ejecutar después de collect_data.py:
    python generate_html.py
"""

import json
import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
OUT_FILE = Path(__file__).parent / "docs" / "index.html"
OUT_FILE.parent.mkdir(exist_ok=True)

def load_data():
    """Carga el resumen y el detalle de cada issue."""
    summary_file = DATA_DIR / "summary.json"
    if not summary_file.exists():
        raise FileNotFoundError("Ejecuta collect_data.py primero.")
    summary = json.loads(summary_file.read_text())
    
    # Carga historiales
    histories = {}
    for issue in summary["issues"]:
        h_file = DATA_DIR / f"{issue['id']}_history.json"
        if h_file.exists():
            histories[issue["id"]] = json.loads(h_file.read_text())
    
    # Carga detalles completos (para la pestaña de análisis)
    details = {}
    for issue in summary["issues"]:
        d_file = DATA_DIR / f"{issue['id']}_latest.json"
        if d_file.exists():
            details[issue["id"]] = json.loads(d_file.read_text())
    
    return summary, histories, details

def build_history_sparkline(history, pillar=None, width=120, height=32):
    """Genera un SVG sparkline del PARI o de un pilar."""
    if not history or len(history) < 2:
        return ""
    
    values = [h.get(pillar or "pari", 50) for h in history[-30:]]
    n = len(values)
    v_min, v_max = 0, 100
    
    pts = []
    for i, v in enumerate(values):
        x = i / (n - 1) * width
        y = height - (v - v_min) / (v_max - v_min) * height
        pts.append(f"{x:.1f},{y:.1f}")
    
    polyline = " ".join(pts)
    
    # Color según último valor
    last = values[-1]
    if last <= 40:   color = "#16A34A"
    elif last <= 60: color = "#CA8A04"
    elif last <= 75: color = "#EA580C"
    else:            color = "#DC2626"
    
    return f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="display:block">
  <polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" opacity="0.8"/>
  <circle cx="{pts[-1].split(',')[0]}" cy="{pts[-1].split(',')[1]}" r="2.5" fill="{color}"/>
</svg>'''

def format_velocity(v):
    if v > 0:  return f'<span style="color:#DC2626">▲ +{v}</span>'
    if v < 0:  return f'<span style="color:#16A34A">▼ {v}</span>'
    return f'<span style="color:#9CA3AF">→ 0</span>'

def risk_badge(level, color):
    bg_map = {
        "Mínimo":   "#DCFCE7", "Bajo":   "#D9F99D",
        "Moderado": "#FEF9C3", "Elevado":"#FFEDD5",
        "Alto":     "#FEE2E2", "Crítico":"#F3E8FF",
    }
    text_map = {
        "Mínimo":   "#166534", "Bajo":   "#3F6212",
        "Moderado": "#854D0E", "Elevado":"#9A3412",
        "Alto":     "#991B1B", "Crítico":"#6B21A8",
    }
    bg  = bg_map.get(level, "#F3F4F6")
    txt = text_map.get(level, "#374151")
    return f'<span style="background:{bg};color:{txt};padding:2px 10px;border-radius:12px;font-size:9px;font-weight:700;letter-spacing:1px;text-transform:uppercase">{level}</span>'

def pillar_row_html(abbr, name, score, color, weight):
    risk = "Mínimo" if score<=20 else "Bajo" if score<=40 else "Moderado" if score<=60 else "Elevado" if score<=75 else "Alto" if score<=90 else "Crítico"
    r_colors = {"Mínimo":"#16A34A","Bajo":"#65A30D","Moderado":"#CA8A04","Elevado":"#EA580C","Alto":"#DC2626","Crítico":"#9333EA"}
    rc = r_colors.get(risk, "#6B7280")
    contrib = round(weight * score, 1)
    return f'''
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
      <span style="font-size:8px;color:#9CA3AF;width:28px;text-align:right">{int(weight*100)}%</span>
      <div style="flex:1;height:6px;background:#F3F4F6;border-radius:3px;overflow:hidden">
        <div style="width:{score}%;height:100%;background:{color};border-radius:3px;transition:width .4s"></div>
      </div>
      <span style="font-size:9px;font-weight:700;color:{rc};width:26px;text-align:right">{contrib}</span>
      <span style="font-size:8px;color:#9CA3AF;width:38px">{abbr}</span>
    </div>'''

def generate_html(summary, histories, details):
    generated = summary.get("generated_at", "")[:10]
    issues    = summary.get("issues", [])
    
    # ── Datos del issue principal (primer issue de la lista)
    main = issues[0] if issues else {}
    main_id   = main.get("id", "")
    main_hist = histories.get(main_id, [])
    main_det  = details.get(main_id, {})
    
    # Construye el JSON de todos los issues para el JS del dashboard
    cases_js = json.dumps([{
        "id":       iss["id"],
        "name":     iss["name"],
        "pari":     iss["pari"],
        "risk":     iss["risk_level"],
        "velocity": iss["velocity"],
        "scores":   iss["scores"],
        "history":  histories.get(iss["id"], []),
    } for iss in issues], ensure_ascii=False)
    
    # Sparkline del issue principal
    sparkline_svg = build_history_sparkline(main_hist, width=200, height=40)
    
    # ── Pillar breakdown del issue principal
    pillar_info = [
        ("mai",   "MAI", "Media Attention",     main.get("scores",{}).get("mai",50),   "#9A6F3A", 0.20),
        ("pai",   "PAI", "Political Activity",  main.get("scores",{}).get("pai",50),   "#1E5A9A", 0.30),
        ("spi",   "SPI", "Stakeholder Press.",  main.get("scores",{}).get("spi",50),   "#1A6B45", 0.20),
        ("pubai","PubAI","Public Attention",    main.get("scores",{}).get("pubai",50), "#8B3A6A", 0.15),
        ("nsi",  "NSI",  "Narrative Shift",     main.get("scores",{}).get("nsi",50),   "#7A7A20", 0.15),
    ]
    
    pillar_rows_html = "".join(
        pillar_row_html(abbr, name, score, color, weight)
        for _, abbr, name, score, color, weight in pillar_info
    )
    
    pillar_cards_html = ""
    for pid, abbr, name, score, color, weight in pillar_info:
        r = "Mínimo" if score<=20 else "Bajo" if score<=40 else "Moderado" if score<=60 else "Elevado" if score<=75 else "Alto" if score<=90 else "Crítico"
        r_colors = {"Mínimo":"#16A34A","Bajo":"#65A30D","Moderado":"#CA8A04","Elevado":"#EA580C","Alto":"#DC2626","Crítico":"#9333EA"}
        rc = r_colors.get(r, "#6B7280")
        sub_detail = main_det.get("pillar_detail", {}).get(pid, {}).get("sub", {})
        sub_rows = ""
        for k, v in sub_detail.items():
            label = k.replace("_", " ").title()
            sub_rows += f'''<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid #F3F4F6">
              <span style="font-size:9px;color:#6B7280">{label}</span>
              <div style="display:flex;align-items:center;gap:6px">
                <div style="width:60px;height:4px;background:#F3F4F6;border-radius:2px">
                  <div style="width:{v}%;height:100%;background:{color};border-radius:2px"></div>
                </div>
                <span style="font-size:9px;font-weight:600;color:{rc};width:22px;text-align:right">{v}</span>
              </div>
            </div>'''
        
        pillar_cards_html += f'''
        <div style="background:#fff;border:1px solid #E5E7EB;border-radius:10px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.04);border-top:3px solid {color}">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">
            <div>
              <div style="font-size:15px;font-weight:700;color:{color};font-family:Lora,Georgia,serif">{abbr}</div>
              <div style="font-size:10px;color:#374151;font-weight:500">{name}</div>
              <div style="font-size:8px;color:#9CA3AF;letter-spacing:1px">PESO {int(weight*100)}%</div>
            </div>
            <div style="text-align:right">
              <div style="font-size:28px;font-weight:700;color:{rc};font-family:Lora,Georgia,serif">{score}</div>
              <div style="font-size:7px;color:{rc};letter-spacing:1px;font-weight:700">{r.upper()}</div>
            </div>
          </div>
          <div style="height:4px;background:#F3F4F6;border-radius:2px;margin-bottom:14px">
            <div style="width:{score}%;height:100%;background:{color};border-radius:2px"></div>
          </div>
          {sub_rows if sub_rows else '<div style="font-size:9px;color:#9CA3AF;text-align:center;padding:8px">Datos detallados no disponibles</div>'}
        </div>'''
    
    # ── Trend chart data (últimos 30 días)
    trend_data_js = json.dumps({
        "labels": [h["date"][5:] for h in main_hist[-30:]],  # "MM-DD"
        "pari":   [h["pari"] for h in main_hist[-30:]],
        "mai":    [h.get("mai", 50) for h in main_hist[-30:]],
        "pai":    [h.get("pai", 50) for h in main_hist[-30:]],
        "spi":    [h.get("spi", 50) for h in main_hist[-30:]],
        "pubai":  [h.get("pubai", 50) for h in main_hist[-30:]],
        "nsi":    [h.get("nsi", 50) for h in main_hist[-30:]],
    }, ensure_ascii=False)
    
    # ── Issue tracker rows
    tracker_rows = ""
    for iss in issues:
        hist = histories.get(iss["id"], [])
        spark = build_history_sparkline(hist, width=80, height=24)
        tracker_rows += f'''
        <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:#fff;border:1px solid #E5E7EB;border-radius:8px;margin-bottom:7px;box-shadow:0 1px 3px rgba(0,0,0,.03)">
          <div style="flex:1">
            <div style="font-size:12px;font-weight:600;color:#1A1A2E;font-family:Lora,Georgia,serif">{iss["name"]}</div>
            <div style="font-size:8px;color:#9CA3AF;letter-spacing:1px;margin-top:2px">{iss["date"]} · {format_velocity(iss["velocity"])}</div>
          </div>
          <div>{spark}</div>
          <div style="text-align:right">
            <div style="font-size:20px;font-weight:700;color:{iss["risk_color"]};font-family:Lora,Georgia,serif">{iss["pari"]}</div>
            {risk_badge(iss["risk_level"], iss["risk_color"])}
          </div>
        </div>'''
    
    main_pari  = main.get("pari", 50)
    main_risk  = main.get("risk_level", "Moderado")
    main_color = main.get("risk_color", "#CA8A04")
    main_vel   = main.get("velocity", 0)
    main_name  = main.get("name", "")
    
    # ═══════════════════════════════════════════════════════════
    # HTML COMPLETO
    # ═══════════════════════════════════════════════════════════
    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>PARI Spain — Public Affairs Risk Index</title>
<link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;0,700;1,400&family=IBM+Plex+Mono:wght@300;400;500&display=swap" rel="stylesheet"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#F8F6F1;--surface:#fff;--surface2:#F0EDE6;
  --border:rgba(0,0,0,0.09);--text:#1A1A2E;--muted:#6B7280;
  --gold:#9A6F3A;
  --font-serif:'Lora',Georgia,serif;
  --font-mono:'IBM Plex Mono',monospace;
}}
body{{background:var(--bg);color:var(--text);font-family:var(--font-mono);min-height:100vh}}
header{{display:flex;justify-content:space-between;align-items:center;padding:14px 28px;
  background:var(--surface);border-bottom:1px solid var(--border);
  position:sticky;top:0;z-index:50;box-shadow:0 1px 8px rgba(0,0,0,.06);flex-wrap:wrap;gap:10px}}
.wordmark{{font-family:var(--font-serif);font-size:20px;font-weight:700;color:var(--text)}}
.wordmark span{{color:rgba(0,0,0,.25);font-size:12px;font-family:var(--font-mono);letter-spacing:2px}}
.update-badge{{font-size:8px;color:var(--muted);letter-spacing:1px;
  background:var(--surface2);padding:3px 10px;border-radius:12px;border:1px solid var(--border)}}
.issue-btns{{display:flex;gap:5px;flex-wrap:wrap}}
.issue-btn{{padding:5px 12px;background:var(--surface2);border:1px solid var(--border);
  color:var(--muted);border-radius:5px;cursor:pointer;font-size:8px;letter-spacing:1px;
  font-family:var(--font-mono);transition:all .2s}}
.issue-btn:hover{{background:rgba(0,0,0,.07);color:var(--text)}}
.issue-btn.active{{background:rgba(154,111,58,.1);border-color:rgba(154,111,58,.4);color:var(--gold)}}
.app{{display:grid;grid-template-columns:290px 1fr;min-height:calc(100vh - 57px)}}
.left{{background:var(--surface);border-right:1px solid var(--border);padding:20px 18px;
  display:flex;flex-direction:column;gap:16px;overflow-y:auto}}
.right{{overflow-y:auto;display:flex;flex-direction:column}}
.tabs{{display:flex;border-bottom:1px solid var(--border);background:var(--surface);padding:0 24px;flex-shrink:0}}
.tab{{padding:10px 14px;background:none;border:none;border-bottom:2px solid transparent;
  color:var(--muted);cursor:pointer;font-size:8px;letter-spacing:2px;font-family:var(--font-mono);
  margin-bottom:-1px;transition:all .2s;white-space:nowrap}}
.tab.active{{color:var(--gold);border-bottom-color:var(--gold)}}
.tab-pane{{display:none;padding:22px 24px}}
.tab-pane.active{{display:block}}
.section-label{{font-size:8px;letter-spacing:3px;color:var(--muted);margin-bottom:8px}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;
  padding:18px;box-shadow:0 1px 4px rgba(0,0,0,.05)}}
.gauge-wrap{{text-align:center}}
.risk-pill{{text-align:center;padding:5px 14px;border-radius:20px;
  font-size:8px;letter-spacing:3px;border:1px solid transparent;transition:all .4s}}
.scoring-helper{{background:linear-gradient(135deg,#FFF8F0,#FEF3E2);
  border:1px solid rgba(154,111,58,.2);border-radius:8px;padding:12px}}
.sh-title{{font-size:8px;letter-spacing:2px;color:var(--gold);margin-bottom:8px;font-weight:600}}
.sh-row{{font-size:9px;color:#4B5563;margin-bottom:5px;padding:5px 8px;
  background:rgba(255,255,255,.6);border-radius:4px;border-left:2px solid rgba(154,111,58,.3);line-height:1.5}}
.sh-row strong{{color:var(--text)}}
.pillars-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.score-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px}}
.scale-wrap{{margin-top:4px}}
.scale-bar{{display:flex;height:7px;border-radius:4px;overflow:hidden;margin-bottom:8px}}
.scale-seg{{flex:1}}
.scale-labels{{display:flex;gap:3px}}
.scale-lbl{{flex:1;text-align:center;padding:3px 1px;border-radius:3px;transition:all .3s}}
.scale-lbl .ln{{font-size:7px;letter-spacing:1px;font-weight:600}}
.scale-lbl .lr{{font-size:6px;color:var(--muted)}}
.flag{{display:flex;gap:11px;padding:11px 13px;border-radius:8px;margin-bottom:9px}}
.flag.h{{background:#FEF2F2;border:1px solid #FECACA}}
.flag.m{{background:#FFFBEB;border:1px solid #FDE68A}}
.flag.l{{background:#EFF6FF;border:1px solid #BFDBFE}}
.flag-dot{{width:6px;height:6px;border-radius:50%;flex-shrink:0;margin-top:4px}}
.flag.h .flag-dot{{background:#DC2626}}.flag.m .flag-dot{{background:#D97706}}.flag.l .flag-dot{{background:#2563EB}}
.flag-title{{font-size:11px;font-weight:600;margin-bottom:3px}}
.flag.h .flag-title{{color:#991B1B}}.flag.m .flag-title{{color:#92400E}}.flag.l .flag-title{{color:#1E40AF}}
.flag-text{{font-size:9px;color:#4B5563;line-height:1.65}}
.tl-item{{display:flex;gap:9px;align-items:flex-start;padding:6px 0;border-bottom:1px solid var(--border)}}
.tl-item:last-child{{border-bottom:none}}
.tl-dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0;margin-top:3px}}
.tl-dot.done{{background:#16A34A}}.tl-dot.active{{background:#CA8A04}}.tl-dot.pending{{background:#D1D5DB}}
.tl-date{{font-size:8px;color:var(--muted);min-width:68px;flex-shrink:0;padding-top:1px;letter-spacing:1px}}
.tl-text{{font-size:9px;color:var(--text);line-height:1.5}}
.tl-badge{{display:inline-block;font-size:7px;padding:1px 5px;border-radius:3px;margin-left:4px;vertical-align:middle;font-weight:700}}
.tl-badge.done{{background:#DCFCE7;color:#166534}}
.tl-badge.active{{background:#FEF9C3;color:#854D0E}}
.tl-badge.pending{{background:#F3F4F6;color:#6B7280}}
canvas{{display:block}}
@media(max-width:820px){{
  .app{{grid-template-columns:1fr}}
  .left{{border-right:none;border-bottom:1px solid var(--border)}}
  .score-grid,.pillars-grid{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>

<header>
  <div style="display:flex;align-items:center;gap:14px">
    <div>
      <div style="font-size:8px;letter-spacing:4px;color:var(--muted);margin-bottom:2px">PUBLIC AFFAIRS RISK INDEX · SPAIN</div>
      <div class="wordmark">PARI <span>Beta · ES</span></div>
    </div>
    <span class="update-badge">🔄 Actualizado: {generated}</span>
  </div>
  <div class="issue-btns" id="issueBtns">
    {"".join(f'<button class="issue-btn{" active" if i==0 else ""}" onclick="loadIssue({i})">{iss["name"].split("(")[0].strip()[:28]}</button>' for i, iss in enumerate(issues))}
  </div>
</header>

<div class="app">
  <!-- ══ LEFT PANEL ══ -->
  <div class="left">
    <div>
      <div class="section-label">ISSUE ACTIVO</div>
      <div id="issueNameDisplay" style="font-family:var(--font-serif);font-size:13px;font-weight:600;
        color:var(--text);padding:8px 10px;background:var(--surface2);border-radius:6px;
        border:1px solid var(--border)">{main_name}</div>
    </div>

    <div class="gauge-wrap">
      <canvas id="gaugeCanvas" width="220" height="120"></canvas>
    </div>

    <div class="risk-pill" id="riskPill"></div>

    <div>
      <div class="section-label">PILLAR SCORES</div>
      <div id="pillarSliders"></div>
    </div>

    <div style="display:flex;align-items:center;gap:8px">
      <div class="section-label" style="margin:0">VELOCITY</div>
      <span id="velDisplay" style="font-size:12px;font-weight:600"></span>
      <span style="font-size:8px;color:var(--muted)">Δ vs. ayer</span>
    </div>

    <div>
      <div class="section-label">TENDENCIA 30 DÍAS</div>
      <div id="sparklineWrap">{sparkline_svg}</div>
    </div>

    <div class="scoring-helper">
      <div class="sh-title">💡 REFERENCIA DE ESCORES</div>
      <div class="sh-row"><strong>0–20:</strong> Sin señales observables</div>
      <div class="sh-row"><strong>21–40:</strong> Señales aisladas o débiles</div>
      <div class="sh-row"><strong>41–60:</strong> Señales activas, seguimiento</div>
      <div class="sh-row"><strong>61–75:</strong> Señales convergentes, riesgo real</div>
      <div class="sh-row"><strong>76–100:</strong> Escalada en curso o inminente</div>
    </div>
  </div>

  <!-- ══ RIGHT PANEL ══ -->
  <div class="right">
    <div class="tabs">
      <button class="tab active" onclick="switchTab('score',this)">SCORE</button>
      <button class="tab" onclick="switchTab('pillars',this)">PILARES</button>
      <button class="tab" onclick="switchTab('trend',this)">TENDENCIA</button>
      <button class="tab" onclick="switchTab('analysis',this)">ANÁLISIS</button>
      <button class="tab" onclick="switchTab('tracker',this)">TRACKER</button>
    </div>

    <!-- SCORE -->
    <div class="tab-pane active" id="pane-score">
      <div class="score-grid">
        <div class="card">
          <div class="section-label">RADAR OVERVIEW</div>
          <canvas id="radarChart" width="240" height="240"></canvas>
        </div>
        <div class="card">
          <div class="section-label">FÓRMULA COMPUESTA</div>
          <div id="formulaRows"></div>
          <div style="border-top:1px solid var(--border);padding-top:10px;margin-top:10px;
            display:flex;justify-content:space-between;align-items:center">
            <span style="font-size:8px;letter-spacing:2px;color:var(--muted)">PARI COMPUESTO</span>
            <span id="formulaTotal" style="font-family:var(--font-serif);font-size:24px;font-weight:700"></span>
          </div>
        </div>
      </div>
      <div class="card scale-wrap">
        <div class="section-label">ESCALA DE RIESGO</div>
        <div class="scale-bar" id="scaleBar"></div>
        <div class="scale-labels" id="scaleLabels"></div>
      </div>
    </div>

    <!-- PILLARS -->
    <div class="tab-pane" id="pane-pillars">
      <div class="pillars-grid" id="pillarsGrid">{pillar_cards_html}</div>
    </div>

    <!-- TREND -->
    <div class="tab-pane" id="pane-trend">
      <div class="card" style="margin-bottom:16px">
        <div class="section-label">EVOLUCIÓN PARI — ÚLTIMOS 30 DÍAS</div>
        <div style="position:relative;height:220px;margin-top:8px">
          <canvas id="trendChart"></canvas>
        </div>
      </div>
      <div class="card">
        <div class="section-label">EVOLUCIÓN POR PILAR</div>
        <div style="position:relative;height:200px;margin-top:8px">
          <canvas id="pillarTrendChart"></canvas>
        </div>
      </div>
    </div>

    <!-- ANALYSIS -->
    <div class="tab-pane" id="pane-analysis">
      <div style="margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid var(--border)">
        <div style="font-size:8px;letter-spacing:2px;color:var(--muted);margin-bottom:5px">ANÁLISIS ESTRATÉGICO · ES / UE · {generated}</div>
        <div style="font-family:var(--font-serif);font-size:19px;font-weight:700;margin-bottom:3px">{main_name}</div>
        <div style="font-size:10px;color:var(--muted)">Perspectiva registral, derecho de propiedad y alquileres de corta duración</div>
        <div style="display:flex;align-items:baseline;gap:10px;margin:10px 0 3px">
          <div style="font-family:var(--font-serif);font-size:44px;font-weight:700;color:{main_color}">{main_pari}</div>
          <div>
            <div style="font-size:9px;color:var(--muted);letter-spacing:2px">PARI COMPUESTO</div>
            <div style="font-size:10px;color:{"#DC2626" if main_vel>0 else "#16A34A" if main_vel<0 else "#9CA3AF"}">{"▲ +" + str(main_vel) if main_vel > 0 else "▼ " + str(main_vel) if main_vel < 0 else "→ 0"} · {main_risk.upper()} · {"TENDENCIA ALCISTA" if main_vel > 0 else "TENDENCIA BAJISTA" if main_vel < 0 else "ESTABLE"}</div>
          </div>
        </div>
      </div>

      <div style="font-size:8px;letter-spacing:3px;color:var(--muted);margin-bottom:10px">SEÑALES DE RIESGO — PERSPECTIVA REGISTRAL</div>

      <div class="flag h">
        <div class="flag-dot"></div>
        <div>
          <div class="flag-title">Affordable Housing Act: riesgo de intromisión en derechos reales e hipoteca</div>
          <div class="flag-text">Propuesta legislativa prevista finales 2026. Naturaleza jurídica sin determinar (reglamento vs. directiva). Si es reglamento → aplicación directa sin margen nacional. Riesgo: mecanismos que intervengan sobre el derecho de propiedad y la hipoteca, invadiendo la esfera del sistema registral español.</div>
        </div>
      </div>
      <div class="flag h">
        <div class="flag-dot"></div>
        <div>
          <div class="flag-title">Iniciativa alquiler corta duración: impacto sobre sistema NRUA ya implantado</div>
          <div class="flag-text">España tiene operativo desde julio 2025 el NRUA gestionado por los Registros de la Propiedad (RD 1312/2024). Si la nueva iniciativa altera la gobernanza de datos, puede desestabilizar o solaparse con el sistema ya en funcionamiento, generando duplicidad normativa.</div>
        </div>
      </div>
      <div class="flag m">
        <div class="flag-dot"></div>
        <div>
          <div class="flag-title">Informe HOUS en Pleno (marzo 2026): votación pendiente</div>
          <div class="flag-text">Aprobado en Comisión Especial el 9 de febrero de 2026 (23-6-4). Votación en pleno pendiente. España es el único país con ley orgánica integral de vivienda, lo que la convierte en referencia y objeto de atención regulatoria europea.</div>
        </div>
      </div>
      <div class="flag m">
        <div class="flag-dot"></div>
        <div>
          <div class="flag-title">Desplazamiento narrativo: de "mercado" a "derecho humano"</div>
          <div class="flag-text">El Comisario Jørgensen usa explícitamente el lenguaje de "derecho humano". Cuando la narrativa se establece en estos términos, la presión por instrumentos de intervención vinculantes sobre la propiedad aumenta significativamente.</div>
        </div>
      </div>
      <div class="flag l">
        <div class="flag-dot"></div>
        <div>
          <div class="flag-title">Oportunidad: el sistema NRUA como buena práctica exportable</div>
          <div class="flag-text">La arquitectura del Registro Único de Arrendamientos español es un modelo avanzado de implementación del Reglamento (UE) 2024/1028. La estrategia de envío de buenas prácticas debe posicionar este sistema como referencia para la futura Affordable Housing Act.</div>
        </div>
      </div>

      <div style="font-size:8px;letter-spacing:3px;color:var(--muted);margin:18px 0 10px">CALENDARIO LEGISLATIVO</div>
      <div>
        <div class="tl-item"><div class="tl-dot done"></div><div class="tl-date">ABR 2024</div><div class="tl-text">Reglamento (UE) 2024/1028 — datos alquiler corta duración <span class="tl-badge done">VIGENTE</span></div></div>
        <div class="tl-item"><div class="tl-dot done"></div><div class="tl-date">DIC 2025</div><div class="tl-text">Plan Europeo de Vivienda Asequible presentado por la Comisión <span class="tl-badge done">PUBLICADO</span></div></div>
        <div class="tl-item"><div class="tl-dot done"></div><div class="tl-date">ENE 2026</div><div class="tl-text">RD 1312/2024 — NRUA obligatorio en España vía Registro de la Propiedad <span class="tl-badge done">EN VIGOR</span></div></div>
        <div class="tl-item"><div class="tl-dot done"></div><div class="tl-date">FEB 2026</div><div class="tl-text">Informe HOUS aprobado en Comisión Especial del PE (23-6-4) <span class="tl-badge done">APROBADO</span></div></div>
        <div class="tl-item"><div class="tl-dot active"></div><div class="tl-date">MAR 2026</div><div class="tl-text">Votación informe HOUS en Pleno del Parlamento Europeo <span class="tl-badge active">EN CURSO</span></div></div>
        <div class="tl-item"><div class="tl-dot active"></div><div class="tl-date">MAY 2026</div><div class="tl-text">Aplicación plena Reglamento (UE) 2024/1028 en todos los EEMM <span class="tl-badge active">PRÓXIMO</span></div></div>
        <div class="tl-item"><div class="tl-dot pending"></div><div class="tl-date">2026 (tf)</div><div class="tl-text">Affordable Housing Act — propuesta legislativa de la Comisión <span class="tl-badge pending">PENDIENTE</span></div></div>
        <div class="tl-item"><div class="tl-dot pending"></div><div class="tl-date">2026</div><div class="tl-text">Iniciativa alquileres corta duración — naturaleza jurídica sin determinar <span class="tl-badge pending">SIN DEFINIR</span></div></div>
        <div class="tl-item"><div class="tl-dot pending"></div><div class="tl-date">2027</div><div class="tl-text">Housing Simplification Package <span class="tl-badge pending">PREVISTO</span></div></div>
      </div>
    </div>

    <!-- TRACKER -->
    <div class="tab-pane" id="pane-tracker">
      <div id="trackerList">{tracker_rows if tracker_rows else '<div style="text-align:center;padding:40px;color:var(--muted);font-size:12px">No hay issues cargados.</div>'}</div>
    </div>
  </div>
</div>

<script>
// ── DATA ──────────────────────────────────────────────────────────────
const CASES = {cases_js};
const TREND_DATA = {trend_data_js};

const PILLARS = [
  {{id:"mai",   abbr:"MAI",   label:"Media Attention",     weight:.20, color:"#9A6F3A"}},
  {{id:"pai",   abbr:"PAI",   label:"Political Activity",  weight:.30, color:"#1E5A9A"}},
  {{id:"spi",   abbr:"SPI",   label:"Stakeholder Pressure",weight:.20, color:"#1A6B45"}},
  {{id:"pubai", abbr:"PubAI", label:"Public Attention",    weight:.15, color:"#8B3A6A"}},
  {{id:"nsi",   abbr:"NSI",   label:"Narrative Shift",     weight:.15, color:"#7A7A20"}},
];
const RISKS = [
  {{min:0,  max:20,  label:"Mínimo",   color:"#16A34A", bg:"#DCFCE7", tc:"#166534"}},
  {{min:21, max:40,  label:"Bajo",     color:"#65A30D", bg:"#D9F99D", tc:"#3F6212"}},
  {{min:41, max:60,  label:"Moderado", color:"#CA8A04", bg:"#FEF9C3", tc:"#854D0E"}},
  {{min:61, max:75,  label:"Elevado",  color:"#EA580C", bg:"#FFEDD5", tc:"#9A3412"}},
  {{min:76, max:90,  label:"Alto",     color:"#DC2626", bg:"#FEE2E2", tc:"#991B1B"}},
  {{min:91, max:100, label:"Crítico",  color:"#9333EA", bg:"#F3E8FF", tc:"#6B21A8"}},
];

let currentIdx = 0;
let scores = {{...CASES[0].scores}};
let currentVelocity = CASES[0].velocity || 0;

function getRisk(s) {{ return RISKS.find(r=>s>=r.min&&s<=r.max)||RISKS[0]; }}
function computePARI() {{ return Math.round(PILLARS.reduce((a,p)=>a+p.weight*(scores[p.id]||0),0)); }}

// ── GAUGE ─────────────────────────────────────────────────────────────
let animScore=0,rafId;
function animateGauge(t){{cancelAnimationFrame(rafId);function s(){{animScore+=(t-animScore)*.14;if(Math.abs(animScore-t)<.5)animScore=t;drawGauge(Math.round(animScore));if(Math.round(animScore)!==t)rafId=requestAnimationFrame(s);}}rafId=requestAnimationFrame(s);}}
function drawGauge(score){{
  const cv=document.getElementById('gaugeCanvas'),ctx=cv.getContext('2d');
  const W=cv.width,H=cv.height,cx=W/2,cy=H-6,r=72;
  ctx.clearRect(0,0,W,H);
  ctx.beginPath();ctx.arc(cx,cy,r,Math.PI,2*Math.PI);
  ctx.strokeStyle='rgba(0,0,0,.1)';ctx.lineWidth=10;ctx.lineCap='round';ctx.stroke();
  const g=ctx.createLinearGradient(cx-r,cy,cx+r,cy);
  g.addColorStop(0,'#16A34A');g.addColorStop(.4,'#CA8A04');g.addColorStop(.7,'#EA580C');g.addColorStop(1,'#9333EA');
  const ea=Math.PI+(score/100)*Math.PI;
  ctx.beginPath();ctx.arc(cx,cy,r,Math.PI,ea);ctx.strokeStyle=g;ctx.lineWidth=10;ctx.lineCap='round';ctx.stroke();
  const risk=getRisk(score);
  const nx=cx+r*Math.cos(ea),ny=cy+r*Math.sin(ea);
  ctx.beginPath();ctx.arc(nx,ny,6,0,2*Math.PI);ctx.fillStyle=risk.color;ctx.fill();
  ctx.fillStyle=risk.color;ctx.font="bold 28px 'Lora',Georgia,serif";ctx.textAlign='center';
  ctx.fillText(score,cx,cy-14);
  ctx.fillStyle='#9CA3AF';ctx.font="9px 'IBM Plex Mono',monospace";ctx.fillText(risk.label.toUpperCase(),cx,cy-1);
}}

// ── RADAR ─────────────────────────────────────────────────────────────
let radarChart=null;
function drawRadar(){{
  const cv=document.getElementById('radarChart');if(!cv)return;
  const ctx=cv.getContext('2d');
  if(radarChart)radarChart.destroy();
  radarChart=new Chart(ctx,{{
    type:'radar',
    data:{{
      labels:PILLARS.map(p=>p.abbr),
      datasets:[{{
        data:PILLARS.map(p=>scores[p.id]||0),
        fill:true,backgroundColor:'rgba(154,111,58,.12)',
        borderColor:'#9A6F3A',borderWidth:2,pointBackgroundColor:PILLARS.map(p=>p.color),
        pointRadius:4,pointHoverRadius:6,
      }}]
    }},
    options:{{responsive:false,plugins:{{legend:{{display:false}}}},
      scales:{{r:{{min:0,max:100,ticks:{{stepSize:25,font:{{size:8}},color:'#9CA3AF'}},
        grid:{{color:'rgba(0,0,0,.06)'}},pointLabels:{{font:{{size:9,family:"IBM Plex Mono"}},color:PILLARS.map(p=>p.color)}}}}}}}}
  }});
}}

// ── TREND CHARTS ──────────────────────────────────────────────────────
let trendChart=null,pillarChart=null;
function drawTrends(){{
  const data=CASES[currentIdx].history||[];
  const labels=data.map(h=>h.date?h.date.slice(5):'');
  const pariVals=data.map(h=>h.pari||0);

  // PARI trend
  const ctx1=document.getElementById('trendChart');
  if(ctx1){{
    if(trendChart)trendChart.destroy();
    trendChart=new Chart(ctx1,{{
      type:'line',
      data:{{labels,datasets:[{{label:'PARI',data:pariVals,borderColor:'#9A6F3A',
        backgroundColor:'rgba(154,111,58,.08)',fill:true,tension:.4,borderWidth:2.5,
        pointRadius:3,pointBackgroundColor:'#9A6F3A'}}]}},
      options:{{responsive:true,maintainAspectRatio:false,
        plugins:{{legend:{{display:false}}}},
        scales:{{y:{{min:0,max:100,ticks:{{stepSize:25,color:'#9CA3AF',font:{{size:8}}}},
          grid:{{color:'rgba(0,0,0,.05)'}}}},
          x:{{ticks:{{color:'#9CA3AF',font:{{size:8}},maxRotation:45}},grid:{{display:false}}}}}}}}
    }});
  }}

  // Pillar trends
  const ctx2=document.getElementById('pillarTrendChart');
  if(ctx2){{
    if(pillarChart)pillarChart.destroy();
    pillarChart=new Chart(ctx2,{{
      type:'line',
      data:{{labels,datasets:PILLARS.map(p=>({
        label:p.abbr,data:data.map(h=>h[p.id]||0),
        borderColor:p.color,backgroundColor:'transparent',
        fill:false,tension:.4,borderWidth:1.5,pointRadius:2,
      }}))}}  ,
      options:{{responsive:true,maintainAspectRatio:false,
        plugins:{{legend:{{position:'bottom',labels:{{font:{{size:8,family:'IBM Plex Mono'}},
          boxWidth:10,padding:10}}}}}},
        scales:{{y:{{min:0,max:100,ticks:{{stepSize:25,color:'#9CA3AF',font:{{size:8}}}},
          grid:{{color:'rgba(0,0,0,.05)'}}}},
          x:{{ticks:{{color:'#9CA3AF',font:{{size:8}},maxRotation:45}},grid:{{display:false}}}}}}}}
    }});
  }}
}}

// ── SLIDERS ───────────────────────────────────────────────────────────
function buildSliders(){{
  const el=document.getElementById('pillarSliders');if(!el)return;
  el.innerHTML=PILLARS.map(p=>`
    <div style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;margin-bottom:3px">
        <span style="font-size:9px;color:#9CA3AF"><span style="color:${{p.color}};margin-right:4px">●</span>${{p.abbr}}</span>
        <span id="sv-${{p.id}}" style="font-family:Lora,Georgia,serif;font-size:13px;font-weight:700;color:${{p.color}}">${{scores[p.id]||0}}</span>
      </div>
      <input type="range" min="0" max="100" value="${{scores[p.id]||0}}"
        style="width:100%;accent-color:${{p.color}};height:3px" oninput="updatePillar('${{p.id}}',this.value)"/>
      <div style="height:2px;background:rgba(0,0,0,.07);border-radius:1px;margin-top:3px">
        <div id="sb-${{p.id}}" style="width:${{scores[p.id]||0}}%;height:100%;background:${{p.color}};border-radius:1px;transition:width .3s"></div>
      </div>
    </div>`).join('');
}}

function updatePillar(id,val){{
  scores[id]=parseInt(val);
  const sv=document.getElementById(`sv-${{id}}`);
  const sb=document.getElementById(`sb-${{id}}`);
  if(sv)sv.textContent=val;
  if(sb)sb.style.width=val+'%';
  refreshAll();
}}

// ── REFRESH ───────────────────────────────────────────────────────────
function refreshAll(){{
  const pari=computePARI();const risk=getRisk(pari);
  animateGauge(pari);
  const pill=document.getElementById('riskPill');
  if(pill){{pill.textContent=`RIESGO — ${{risk.label.toUpperCase()}}`;pill.style.color=risk.color;
    pill.style.borderColor=risk.color+'50';pill.style.background=risk.color+'15';}}
  buildFormula(pari,risk);buildScaleLabels(pari);drawRadar();updateVelocityDisplay();
}}

function buildFormula(pari,risk){{
  const el=document.getElementById('formulaRows');if(!el)return;
  el.innerHTML=PILLARS.map(p=>`
    <div style="display:flex;align-items:center;gap:7px;margin-bottom:7px">
      <span style="width:22px;font-size:8px;color:#9CA3AF;text-align:right">${{(p.weight*100).toFixed(0)}}%</span>
      <div style="flex:1;height:4px;background:#F3F4F6;border-radius:2px">
        <div style="width:${{scores[p.id]||0}}%;height:100%;background:${{p.color}};border-radius:2px;transition:width .3s"></div>
      </div>
      <span style="font-size:9px;font-weight:700;color:${{p.color}};width:26px;text-align:right">${{(p.weight*(scores[p.id]||0)).toFixed(1)}}</span>
      <span style="font-size:8px;color:#9CA3AF;width:32px">${{p.abbr}}</span>
    </div>`).join('');
  const tot=document.getElementById('formulaTotal');
  if(tot){{tot.textContent=pari;tot.style.color=risk.color;}}
}}

function buildScaleLabels(pari){{
  const bar=document.getElementById('scaleBar');const lbl=document.getElementById('scaleLabels');
  if(!bar||!lbl)return;
  bar.innerHTML=RISKS.map(r=>`<div class="scale-seg" style="background:${{r.color}};flex:${{r.max-r.min}}"></div>`).join('');
  lbl.innerHTML=RISKS.map(r=>{{
    const a=pari>=r.min&&pari<=r.max;
    return `<div class="scale-lbl" style="background:${{a?r.bg:'transparent'}};border:1px solid ${{a?r.color+'60':'transparent'}};border-radius:3px">
      <div class="ln" style="color:${{r.color}}">${{r.label.toUpperCase()}}</div>
      <div class="lr">${{r.min}}–${{r.max}}</div>
    </div>`;
  }}).join('');
}}

function updateVelocityDisplay(){{
  const el=document.getElementById('velDisplay');if(!el)return;
  const v=currentVelocity;
  if(v>0){{el.textContent=`▲ +${{v}}`;el.style.color='#DC2626';}}
  else if(v<0){{el.textContent=`▼ ${{v}}`;el.style.color='#16A34A';}}
  else{{el.textContent='→ 0';el.style.color='#9CA3AF';}}
}}

// ── LOAD ISSUE ────────────────────────────────────────────────────────
function loadIssue(idx){{
  currentIdx=idx;
  const c=CASES[idx];if(!c)return;
  scores={{...c.scores}};
  currentVelocity=c.velocity||0;
  document.getElementById('issueNameDisplay').textContent=c.name;
  document.querySelectorAll('.issue-btn').forEach((b,i)=>b.classList.toggle('active',i===idx));
  buildSliders();refreshAll();drawTrends();
}}

// ── TABS ──────────────────────────────────────────────────────────────
function switchTab(name,btn){{
  document.querySelectorAll('.tab-pane').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));
  document.getElementById('pane-'+name).classList.add('active');
  btn.classList.add('active');
  if(name==='score')drawRadar();
  if(name==='trend')drawTrends();
}}

// ── INIT ──────────────────────────────────────────────────────────────
loadIssue(0);
</script>
</body>
</html>'''
    
    return html

if __name__ == "__main__":
    print("📄 PARI Spain — Generando dashboard HTML...")
    summary, histories, details = load_data()
    html = generate_html(summary, histories, details)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"✅ Dashboard generado: {OUT_FILE}")
    print(f"   Issues: {len(summary['issues'])}")
    print(f"   Tamaño: {OUT_FILE.stat().st_size // 1024} KB")
