"""
PARI Spain — HTML Generator v4
================================
Lee analysis JSON por issue e inyecta el análisis cualitativo
dinámicamente en el dashboard, junto con los scores calculados.
"""

import json
import re
import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DOCS_DIR = Path(__file__).parent / "docs"
DOCS_DIR.mkdir(exist_ok=True)
OUT_FILE = DOCS_DIR / "index.html"
TEMPLATE = Path(__file__).parent / "data" / "PARI_Standalone.html"
TODAY    = datetime.date.today().isoformat()

WEIGHTS = {"mai": .20, "pai": .30, "spi": .20, "pubai": .15, "nsi": .15}

# ── Helpers HTML ──────────────────────────────────────────────────────

def flag_html(flag):
    level = flag.get("level", "low")
    cls_map   = {"high": "h", "medium": "m", "low": "l"}
    color_map = {"high": "#991B1B", "medium": "#92400E", "low": "#1E40AF"}
    dot_map   = {"high": "#DC2626", "medium": "#D97706", "low": "#2563EB"}
    bg_map    = {"high": "#FEF2F2", "medium": "#FFFBEB", "low": "#EFF6FF"}
    bd_map    = {"high": "#FECACA", "medium": "#FDE68A", "low": "#BFDBFE"}
    cls   = cls_map.get(level, "l")
    color = color_map.get(level, "#1E40AF")
    dot   = dot_map.get(level, "#2563EB")
    bg    = bg_map.get(level, "#EFF6FF")
    bd    = bd_map.get(level, "#BFDBFE")
    return f'''<div style="display:flex;gap:11px;padding:11px 13px;border-radius:8px;
        background:{bg};border:1px solid {bd};margin-bottom:9px">
      <div style="width:6px;height:6px;border-radius:50%;flex-shrink:0;margin-top:4px;background:{dot}"></div>
      <div>
        <div style="font-size:11px;font-weight:600;margin-bottom:3px;color:{color}">{flag["title"]}</div>
        <div style="font-size:9px;color:#4B5563;line-height:1.65">{flag["text"]}</div>
      </div>
    </div>'''

def timeline_html(items):
    parts = []
    dot_colors = {"done": "#16A34A", "active": "#CA8A04", "pending": "#D1D5DB"}
    badge_styles = {
        "done":    "background:#DCFCE7;color:#166534",
        "active":  "background:#FEF9C3;color:#854D0E",
        "pending": "background:#F3F4F6;color:#6B7280",
    }
    for item in items:
        st  = item.get("status", "pending")
        dot = dot_colors.get(st, "#D1D5DB")
        bst = badge_styles.get(st, badge_styles["pending"])
        badge = f'<span style="display:inline-block;font-size:7px;letter-spacing:1px;padding:1px 5px;border-radius:3px;margin-left:4px;vertical-align:middle;font-weight:700;{bst}">{item.get("badge","")}</span>'
        parts.append(f'''<div style="display:flex;gap:9px;align-items:flex-start;padding:6px 0;border-bottom:1px solid rgba(0,0,0,.07)">
      <div style="width:7px;height:7px;border-radius:50%;flex-shrink:0;margin-top:3px;background:{dot}"></div>
      <div style="font-size:8px;color:#6B7280;min-width:68px;flex-shrink:0;padding-top:1px;letter-spacing:1px">{item.get("date","")}</div>
      <div style="font-size:9px;color:#1A1A2E;line-height:1.5">{item.get("text","")} {badge}</div>
    </div>''')
    return "\n".join(parts)

def position_html(pos):
    adopted = pos.get("adopted", [])
    pending = pos.get("pending", [])
    approach = pos.get("strategic_approach", "")
    level = pos.get("strategic_level", "preventive")

    level_styles = {
        "preventive": ("PREVENTIVO", "#DBEAFE", "#166534", "#1E40AF"),
        "proactive":  ("PROACTIVO",  "#DCFCE7", "#166534", "#16A34A"),
        "reactive":   ("REACTIVO",   "#FEE2E2", "#991B1B", "#DC2626"),
        "monitoring": ("MONITOREO",  "#F3F4F6", "#374151", "#6B7280"),
    }
    lbl, lbg, ltc, lbc = level_styles.get(level, level_styles["preventive"])

    adopted_rows = "".join(
        f'<div style="font-size:9px;color:#6B7280;line-height:1.6;padding:3px 0;border-bottom:1px solid rgba(0,0,0,.04)">'
        f'<span style="color:#16A34A;font-weight:700;margin-right:5px">✓</span>{a}</div>'
        for a in adopted
    )
    pending_rows = "".join(
        f'<div style="font-size:9px;color:#6B7280;line-height:1.6;padding:3px 0;border-bottom:1px solid rgba(0,0,0,.04)">'
        f'<span style="color:#CA8A04;font-weight:700;margin-right:5px">◎</span>{p}</div>'
        for p in pending
    )

    return f'''<div style="display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:16px">
    <div style="padding:12px;background:#fff;border:1px solid rgba(0,0,0,.09);border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
      <div style="font-size:7px;letter-spacing:2px;color:#6B7280;margin-bottom:5px">POSICIÓN ADOPTADA</div>
      <span style="display:inline-block;font-size:7px;letter-spacing:1px;padding:2px 7px;border-radius:3px;margin-bottom:6px;font-weight:700;background:#DCFCE7;color:#166534">COMPLETADO</span>
      {adopted_rows}
    </div>
    <div style="padding:12px;background:#fff;border:1px solid rgba(0,0,0,.09);border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
      <div style="font-size:7px;letter-spacing:2px;color:#6B7280;margin-bottom:5px">PENDIENTE</div>
      <span style="display:inline-block;font-size:7px;letter-spacing:1px;padding:2px 7px;border-radius:3px;margin-bottom:6px;font-weight:700;background:#FEF9C3;color:#854D0E">PENDIENTE</span>
      {pending_rows}
    </div>
  </div>
  <div style="padding:12px;background:#fff;border:1px solid rgba(0,0,0,.09);border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
    <div style="font-size:7px;letter-spacing:2px;color:#6B7280;margin-bottom:5px">ENFOQUE ESTRATÉGICO</div>
    <span style="display:inline-block;font-size:7px;letter-spacing:1px;padding:2px 7px;border-radius:3px;margin-bottom:6px;font-weight:700;background:{lbg};color:{lbc}">{lbl}</span>
    <div style="font-size:9px;color:#6B7280;line-height:1.7">{approach}</div>
  </div>'''

def registradores_html(reg):
    formal  = reg.get("formal_position", False)
    note    = reg.get("formal_position_note", "")
    vectors = reg.get("vectors", [])
    action  = reg.get("recommended_action", "")

    status_badge = (
        f'<span style="background:#DCFCE7;color:#166534;font-size:7px;font-weight:700;'
        f'padding:2px 8px;border-radius:3px;letter-spacing:1px">POSICIÓN FORMAL ADOPTADA</span>'
        if formal else
        f'<span style="background:#FEF9C3;color:#854D0E;font-size:7px;font-weight:700;'
        f'padding:2px 8px;border-radius:3px;letter-spacing:1px">POSICIÓN FORMAL PENDIENTE</span>'
    )

    vector_rows = "".join(
        f'<div style="margin-bottom:10px">'
        f'<div style="font-size:9px;font-weight:600;color:#1A1A2E;margin-bottom:3px">{v["title"]}</div>'
        f'<div style="font-size:9px;color:#6B7280;line-height:1.7">{v["text"]}</div>'
        f'</div>'
        for v in vectors
    )

    return f'''<div style="padding:14px;background:#fff;border:1px solid rgba(0,0,0,.09);border-radius:8px;font-size:9px;color:#6B7280;line-height:1.75;box-shadow:0 1px 3px rgba(0,0,0,.04)">
    <div style="margin-bottom:10px">{status_badge}</div>
    <div style="font-size:9px;color:#4B5563;margin-bottom:12px">{note}</div>
    {vector_rows}
    <div style="margin-top:10px;padding:10px;background:rgba(154,111,58,.06);border-radius:6px;border-left:3px solid rgba(154,111,58,.4)">
      <div style="font-size:8px;font-weight:600;color:#9A6F3A;margin-bottom:3px;letter-spacing:1px">→ ACCIÓN RECOMENDADA</div>
      <div style="font-size:9px;color:#6B7280;line-height:1.6">{action}</div>
    </div>
  </div>'''


def build_analysis_tab(analysis, pari, risk_label, risk_color, velocity):
    """Genera el HTML completo de la pestaña ANÁLISIS desde el JSON."""
    meta     = analysis.get("_meta", {})
    flags    = analysis.get("risk_flags", [])
    position = analysis.get("position", {})
    timeline = analysis.get("timeline", [])
    reg      = analysis.get("registradores", {})

    vel_color = "#DC2626" if velocity > 0 else "#16A34A" if velocity < 0 else "#9CA3AF"
    vel_text  = f"▲ +{velocity}" if velocity > 0 else f"▼ {velocity}" if velocity < 0 else "→ 0"
    trend_lbl = "TENDENCIA ALCISTA" if velocity > 0 else "TENDENCIA BAJISTA" if velocity < 0 else "ESTABLE"

    section = lambda t: f'<div style="font-size:8px;letter-spacing:3px;color:#6B7280;margin:18px 0 10px">{t}</div>'

    return f'''<div style="margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid rgba(0,0,0,.09)">
    <div style="font-size:8px;letter-spacing:2px;color:#6B7280;margin-bottom:5px">
      ANÁLISIS PARI · CASO ESPAÑA / UE · {meta.get("last_updated", TODAY)}
      <span style="margin-left:8px;font-size:7px;color:#9CA3AF">Actualizado por: {meta.get("updated_by","—")}</span>
    </div>
    <div style="font-family:Lora,Georgia,serif;font-size:19px;font-weight:700;margin-bottom:3px;color:#1A1A2E">{meta.get("issue_name","")}</div>
    <div style="font-size:10px;color:#6B7280">{meta.get("subtitle","")}</div>
    <div style="display:flex;align-items:baseline;gap:10px;margin:10px 0 3px">
      <div id="analysisPariNum" style="font-family:Lora,Georgia,serif;font-size:44px;font-weight:700;color:{risk_color}">{pari}</div>
      <div>
        <div style="font-size:9px;color:#6B7280;letter-spacing:2px">PARI COMPUESTO</div>
        <div id="analysisVel" style="font-size:10px;color:{vel_color}">{vel_text} · RIESGO {risk_label.upper()} · {trend_lbl}</div>
      </div>
    </div>
  </div>

  {section("SEÑALES DE RIESGO — PERSPECTIVA REGISTRAL")}
  {"".join(flag_html(f) for f in flags)}

  {section("POSICIÓN Y PENDIENTES")}
  {position_html(position)}

  {section("CALENDARIO LEGISLATIVO")}
  <div style="background:#fff;border:1px solid rgba(0,0,0,.09);border-radius:8px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,.04)">
    {timeline_html(timeline)}
  </div>

  {section("POSICIÓN DE LOS REGISTRADORES")}
  {registradores_html(reg)}'''


# ── Data loading ──────────────────────────────────────────────────────

def load_scores():
    summary_file = DATA_DIR / "summary.json"
    if not summary_file.exists():
        return get_fallback_scores()
    try:
        summary = json.loads(summary_file.read_text())
        issues  = summary.get("issues", [])
        if not issues:
            return get_fallback_scores()
        cases = []
        for iss in issues:
            h_file = DATA_DIR / f"{iss['id']}_history.json"
            d_file = DATA_DIR / f"{iss['id']}_latest.json"
            history, sub_scores = [], {}
            if h_file.exists():
                try: history = json.loads(h_file.read_text())
                except: pass
            if d_file.exists():
                try:
                    detail = json.loads(d_file.read_text())
                    for pid, pdata in detail.get("pillar_detail", {}).items():
                        if pdata.get("sub"):
                            sub_scores[pid] = pdata["sub"]
                except: pass
            cases.append({
                "name": iss["name"], "scores": iss["scores"],
                "velocity": iss.get("velocity", 0), "date": iss.get("date", TODAY),
                "history": history, "sub_scores": sub_scores,
                "issue_id": iss["id"],
            })
        return cases, TODAY
    except Exception as e:
        print(f"  ⚠ {e}")
        return get_fallback_scores()

def get_fallback_scores():
    return [{
        "issue_id": "vivienda_asequible",
        "name": "Plan Europeo Vivienda Asequible",
        "scores": {"mai":62,"pai":79,"spi":65,"pubai":58,"nsi":71},
        "velocity": 8, "date": TODAY, "history": [],
        "sub_scores": {
            "mai":{"mai_vol":65,"mai_sent":60,"mai_acc":68,"mai_tier":55,"mai_edit":62},
            "pai":{"pai_parl":82,"pai_leg":75,"pai_reg":80,"pai_exec":76,"pai_cont":82},
            "spi":{"spi_ngo":70,"spi_camp":60,"spi_corp":65,"spi_think":68,"spi_lit":62},
            "pubai":{"pub_search":62,"pub_social":55,"pub_viral":50,"pub_polar":58,"pub_geo":65},
            "nsi":{"nsi_kw":75,"nsi_frame":72,"nsi_meta":68,"nsi_coal":70,"nsi_count":69},
        },
    }], TODAY

def load_analysis(issue_id):
    """Carga el JSON de análisis cualitativo para un issue."""
    a_file = DATA_DIR / f"{issue_id}_analysis.json"
    if a_file.exists():
        try:
            return json.loads(a_file.read_text())
        except Exception as e:
            print(f"  ⚠ Error leyendo análisis de {issue_id}: {e}")
    return None

def get_risk(score):
    if score <= 20:  return ("Mínimo",   "#16A34A")
    if score <= 40:  return ("Bajo",     "#65A30D")
    if score <= 60:  return ("Moderado", "#CA8A04")
    if score <= 75:  return ("Elevado",  "#EA580C")
    if score <= 90:  return ("Alto",     "#DC2626")
    return                   ("Crítico",  "#9333EA")

# ── Injection ─────────────────────────────────────────────────────────

def build_cases_js(cases):
    lines = [f"/* ═══ CASOS — generado automáticamente · {TODAY} ═══ */", "const CASES = ["]
    for c in cases:
        h_compact = [{k:v for k,v in h.items() if k in ("date","pari","mai","pai","spi","pubai","nsi","velocity")}
                     for h in c.get("history",[])[-90:]]
        lines.append(
            "  {\n"
            f'    name:{json.dumps(c["name"])},\n'
            f'    scores:{{{",".join(f"{k}:{v}" for k,v in c["scores"].items())}}},\n'
            f'    velocity:{c["velocity"]},\n'
            f'    date:{json.dumps(c["date"])},\n'
            f'    history:{json.dumps(h_compact,ensure_ascii=False)},\n'
            f'    sub_scores:{json.dumps(c.get("sub_scores",{}),ensure_ascii=False)},\n'
            "  },"
        )
    lines.append("];")
    return "\n".join(lines)

def build_header_buttons(cases):
    return "\n".join(
        f'    <button class="demo-btn{" active-case" if i==0 else ""}" onclick="loadCase({i})">'
        f'{c["name"].split("(")[0].strip()[:28]}</button>'
        for i, c in enumerate(cases)
    )

def build_analysis_placeholder():
    """HTML por defecto cuando no hay JSON de análisis."""
    return '''<div style="text-align:center;padding:40px;color:#6B7280;font-size:11px">
    <div style="font-size:24px;margin-bottom:12px">📋</div>
    <div style="font-weight:600;margin-bottom:6px">Análisis cualitativo no disponible</div>
    <div style="font-size:10px">Crea el archivo <code>data/{issue_id}_analysis.json</code><br>
    siguiendo la plantilla incluida en el repositorio.</div>
  </div>'''

def inject(template_html, cases, analyses, generated_date):
    html = template_html

    # 1. CASES JS block
    new_block = build_cases_js(cases)
    pattern = r'/\* ═══ CASOS.*?const CASES = \[.*?\];'
    result = re.sub(pattern, new_block, html, flags=re.DOTALL)
    if result == html:
        occ = [m.start() for m in re.finditer(r'const CASES = \[', html)]
        if len(occ) >= 2:
            start = occ[1]
            close = html.find('\n];', start)
            if close > 0:
                html = html[:start] + new_block + html[close+3:]
                result = html
    html = result

    # 2. Header buttons
    html = re.sub(r'(<div class="header-btns">).*?(</div>)',
                  f'\\1\n{build_header_buttons(cases)}\n  \\2',
                  html, flags=re.DOTALL, count=1)

    # 3. Issue name input
    if cases:
        html = re.sub(r'(id="issueName"\s+value=")[^"]*(")', f'\\g<1>{cases[0]["name"]}\\2', html)

    # 4. Update badge
    html = re.sub(r'(class="case-tag">)[^<]*(</div>)',
                  f'\\1ACTUALIZADO · {generated_date}\\2', html)

    # 5. Title
    html = html.replace(
        "<title>PARI — Plan Europeo de Vivienda Asequible</title>",
        "<title>PARI Spain — Public Affairs Risk Index</title>"
    )

    # 6. ── INJECT ANALYSIS TAB (el más importante) ──
    # Reemplaza el contenido del tab-content id="tab-analysis"
    if cases and analyses:
        main_case     = cases[0]
        main_analysis = analyses.get(main_case.get("issue_id",""), None)
        scores        = main_case["scores"]
        pari          = round(sum(WEIGHTS[k]*v for k,v in scores.items()))
        risk_lbl, risk_color = get_risk(pari)
        velocity      = main_case.get("velocity", 0)

        if main_analysis:
            analysis_content = build_analysis_tab(
                main_analysis, pari, risk_lbl, risk_color, velocity
            )
        else:
            analysis_content = build_analysis_placeholder()

        # Reemplaza el contenido entre las etiquetas del tab de análisis
        # Busca el div del tab-analysis y reemplaza su contenido interno
        tab_pattern = r'(<div class="tab-content" id="tab-analysis">).*?(</div>\s*<!-- ── SCORE)'
        replacement = f'\\1\n  {analysis_content}\n  \\2'
        new_html = re.sub(tab_pattern, replacement, html, flags=re.DOTALL, count=1)

        # Fallback: buscar el bloque de otra forma si el comentario no existe
        if new_html == html:
            tab_pattern2 = r'(<div class="tab-content" id="tab-analysis">)(.*?)(<div class="tab-content active" id="tab-score">|<div class="tab-content" id="tab-score">)'
            replacement2 = f'\\1\n  {analysis_content}\n  \\3'
            new_html = re.sub(tab_pattern2, replacement2, html, flags=re.DOTALL, count=1)

        if new_html != html:
            html = new_html
            print("  ✅ Análisis cualitativo inyectado correctamente.")
        else:
            print("  ⚠  No se pudo inyectar el análisis (el tab no se encontró). Usando contenido original.")

    return html


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"📄 PARI Spain — Generando dashboard v4 · {TODAY}")

    result = load_scores()
    cases, generated_date = result if isinstance(result, tuple) else (result, TODAY)

    # Carga todos los análisis disponibles
    analyses = {}
    for c in cases:
        iid      = c.get("issue_id", "")
        analysis = load_analysis(iid)
        if analysis:
            analyses[iid] = analysis
            print(f"  📋 Análisis cargado: {iid}")
        else:
            print(f"  ⚠  Sin análisis JSON para: {iid} — usando placeholder")

    print(f"  Issues: {len(cases)}")
    for c in cases:
        pari = round(sum(WEIGHTS[k]*v for k,v in c["scores"].items()))
        print(f"    {c['name']}: PARI={pari} vel={c['velocity']:+d}")

    if not TEMPLATE.exists():
        print(f"  ❌ Template no encontrado: {TEMPLATE}")
        raise SystemExit(1)

    template_html = TEMPLATE.read_text(encoding="utf-8")
    final_html    = inject(template_html, cases, analyses, generated_date)
    OUT_FILE.write_text(final_html, encoding="utf-8")
    print(f"  ✅ {OUT_FILE} ({OUT_FILE.stat().st_size//1024}KB)")
