"""
PARI Spain — HTML Dashboard Generator
======================================
Genera el archivo index.html para GitHub Pages.
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
        # Fallback para evitar que el script falle si no hay datos aún
        return {"generated_at": str(datetime.datetime.now()), "issues": []}, {}, {}
    
    summary = json.loads(summary_file.read_text(encoding='utf-8'))
    
    histories = {}
    details = {}
    for issue in summary.get("issues", []):
        issue_id = issue['id']
        # Carga historiales
        h_file = DATA_DIR / f"{issue_id}_history.json"
        if h_file.exists():
            histories[issue_id] = json.loads(h_file.read_text(encoding='utf-8'))
        
        # Carga detalles completos
        d_file = DATA_DIR / f"{issue_id}_latest.json"
        if d_file.exists():
            details[issue_id] = json.loads(d_file.read_text(encoding='utf-8'))
    
    return summary, histories, details

def build_history_sparkline(history, pillar=None, width=120, height=32):
    """Genera un SVG sparkline."""
    if not history or len(history) < 2:
        return f'<svg width="{width}" height="{height}"></svg>'
    
    values = [h.get(pillar or "pari", 50) for h in history[-30:]]
    n = len(values)
    v_min, v_max = 0, 100
    
    pts = []
    for i, v in enumerate(values):
        x = i / (n - 1) * width if n > 1 else 0
        y = height - (v - v_min) / (v_max - v_min) * height
        pts.append(f"{x:.1f},{y:.1f}")
    
    polyline = " ".join(pts)
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
    bg_map = {"Mínimo":"#DCFCE7","Bajo":"#D9F99D","Moderado":"#FEF9C3","Elevado":"#FFEDD5","Alto":"#FEE2E2","Crítico":"#F3E8FF"}
    text_map = {"Mínimo":"#166534","Bajo":"#3F6212","Moderado":"#854D0E","Elevado":"#9A3412","Alto":"#991B1B","Crítico":"#6B21A8"}
    bg = bg_map.get(level, "#F3F4F6")
    txt = text_map.get(level, "#374151")
    return f'<span style="background:{bg};color:{txt};padding:2px 10px;border-radius:12px;font-size:9px;font-weight:700;letter-spacing:1px;text-transform:uppercase">{level}</span>'

def generate_html():
    summary, histories, details = load_data()
    generated = summary.get("generated_at", "")[:10]
    issues = summary.get("issues", [])
    
    if not issues:
        OUT_FILE.write_text("No data available yet.", encoding='utf-8')
        return

    main = issues[0]
    main_id = main.get("id", "")
    main_hist = histories.get(main_id, [])
    main_det = details.get(main_id, {})
    
    cases_js = json.dumps([{
        "id": iss["id"],
        "name": iss["name"],
        "pari": iss["pari"],
        "risk": iss["risk_level"],
        "velocity": iss["velocity"],
        "scores": iss["scores"],
        "history": histories.get(iss["id"], []),
    } for iss in issues], ensure_ascii=False)
    
    sparkline_svg = build_history_sparkline(main_hist, width=200, height=40)
    
    tracker_rows = ""
    for iss in issues:
        h = histories.get(iss["id"], [])
        spark = build_history_sparkline(h, width=80, height=24)
        tracker_rows += f'''
        <div class="card" style="display:flex;align-items:center;gap:12px;margin-bottom:7px;padding:10px 14px">
          <div style="flex:1">
            <div style="font-size:12px;font-weight:600;font-family:Lora,serif">{iss["name"]}</div>
            <div style="font-size:8px;color:#9CA3AF;letter-spacing:1px">{iss.get("date","")} · {format_velocity(iss["velocity"])}</div>
          </div>
          <div>{spark}</div>
          <div style="text-align:right">
            <div style="font-size:20px;font-weight:700;color:{iss["risk_color"]};font-family:Lora,serif">{iss["pari"]}</div>
            {risk_badge(iss["risk_level"], iss["risk_color"])}
          </div>
        </div>'''

    # Usamos f-string con llaves dobles {{ }} para escapar el CSS/JS
    full_html = f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>PARI Spain — Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Lora:wght@400;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
:root {{ --bg:#F8F6F1; --gold:#9A6F3A; --text:#1A1A2E; --border:rgba(0,0,0,0.09); }}
body {{ background:var(--bg); color:var(--text); font-family:'IBM Plex Mono',monospace; margin:0; }}
header {{ background:#fff; padding:14px 28px; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; }}
.app {{ display:grid; grid-template-columns:300px 1fr; min-height:100vh; }}
.left {{ background:#fff; border-right:1px solid var(--border); padding:20px; }}
.card {{ background:#fff; border:1px solid var(--border); border-radius:8px; padding:15px; box-shadow:0 2px 4px rgba(0,0,0,0.02); }}
.section-label {{ font-size:8px; letter-spacing:2px; color:#6B7280; margin-bottom:10px; text-transform:uppercase; }}
.btn {{ padding:6px 12px; font-size:10px; cursor:pointer; border:1px solid var(--border); background:#F0EDE6; border-radius:4px; }}
.btn.active {{ background:rgba(154,111,58,0.1); color:var(--gold); border-color:var(--gold); }}
</style>
</head>
<body>
<header>
  <div>
    <div style="font-size:8px;letter-spacing:3px;color:#6B7280">PUBLIC AFFAIRS RISK INDEX</div>
    <div style="font-family:Lora,serif;font-size:20px;font-weight:700">PARI Spain <span style="font-size:10px;color:#9CA3AF">Beta</span></div>
  </div>
  <div style="font-size:10px;background:#F0EDE6;padding:4px 10px;border-radius:12px">🔄 {generated}</div>
</header>
<div class="app">
  <div class="left">
    <div class="section-label">Issue Activo</div>
    <div class="card" id="issueName" style="font-weight:600;margin-bottom:20px">{main.get("name","")}</div>
    
    <div class="section-label">Puntuación Compuesta</div>
    <div class="card" style="text-align:center;margin-bottom:20px">
        <div style="font-size:48px;font-family:Lora,serif;font-weight:700;color:{main.get("risk_color")}">{main.get("pari")}</div>
        <div style="font-size:10px;font-weight:700">{main.get("risk_level").upper()}</div>
    </div>

    <div class="section-label">Tendencia</div>
    <div class="card">{sparkline_svg}</div>
  </div>
  
  <div style="padding:20px">
    <div class="section-label">Listado de Riesgos</div>
    <div id="trackerList">{tracker_rows}</div>
  </div>
</div>

<script>
const CASES = {cases_js};
console.log("Datos cargados:", CASES);
// Aquí puedes añadir la lógica de Chart.js si la necesitas
</script>
</body>
</html>'''

    OUT_FILE.write_text(full_html, encoding='utf-8')
    print(f"✅ Dashboard generado en: {OUT_FILE}")

if __name__ == "__main__":
    generate_html()
