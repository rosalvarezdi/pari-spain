"""
PARI Spain — HTML Generator v2
================================
Usa PARI_Standalone.html como template base e inyecta
los datos reales calculados por collect_data.py.
El diseño es siempre el completo; solo cambian los datos.
"""

import json
import re
import datetime
from pathlib import Path

DATA_DIR   = Path(__file__).parent / "data"
DOCS_DIR   = Path(__file__).parent / "docs"
DOCS_DIR.mkdir(exist_ok=True)
OUT_FILE   = DOCS_DIR / "index.html"

# El template base es el standalone con diseño completo
TEMPLATE   = Path(__file__).parent / "PARI_Standalone.html"

TODAY = datetime.date.today().isoformat()


def load_data():
    """Carga los datos reales. Si no existen, devuelve datos hardcodeados."""
    summary_file = DATA_DIR / "summary.json"

    if not summary_file.exists():
        print("  ⚠  No hay datos en /data — usando valores de referencia.")
        return get_fallback_data()

    try:
        summary  = json.loads(summary_file.read_text())
        issues   = summary.get("issues", [])
        if not issues:
            return get_fallback_data()

        cases = []
        for iss in issues:
            h_file = DATA_DIR / f"{iss['id']}_history.json"
            history = []
            if h_file.exists():
                try:
                    history = json.loads(h_file.read_text())
                except:
                    pass

            cases.append({
                "name":     iss["name"],
                "scores":   iss["scores"],
                "velocity": iss.get("velocity", 0),
                "analyst":  "PARI Spain",
                "date":     iss.get("date", TODAY),
                "history":  history,
            })

        return cases, TODAY

    except Exception as e:
        print(f"  ⚠  Error leyendo datos: {e} — usando valores de referencia.")
        return get_fallback_data()


def get_fallback_data():
    """Datos de referencia cuando aún no hay datos calculados."""
    cases = [
        {
            "name":     "Plan Europeo Vivienda Asequible",
            "scores":   {"mai": 62, "pai": 79, "spi": 65, "pubai": 58, "nsi": 71},
            "velocity": 8,
            "analyst":  "PARI Spain",
            "date":     TODAY,
            "history":  [],
        },
        {
            "name":     "AI Regulation (EU)",
            "scores":   {"mai": 72, "pai": 81, "spi": 68, "pubai": 55, "nsi": 79},
            "velocity": 8,
            "analyst":  "PARI Spain",
            "date":     TODAY,
            "history":  [],
        },
        {
            "name":     "Food Dyes (Children's Health)",
            "scores":   {"mai": 62, "pai": 71, "spi": 68, "pubai": 45, "nsi": 74},
            "velocity": 5,
            "analyst":  "PARI Spain",
            "date":     TODAY,
            "history":  [],
        },
        {
            "name":     "Carbon Border Adjustment",
            "scores":   {"mai": 48, "pai": 66, "spi": 52, "pubai": 28, "nsi": 44},
            "velocity": 3,
            "analyst":  "PARI Spain",
            "date":     TODAY,
            "history":  [],
        },
    ]
    return cases, TODAY


def build_cases_js(cases):
    """Construye el bloque JavaScript const CASES = [...] con datos reales."""
    lines = ["/* ═══ CASOS — generado automáticamente por PARI ═══\n"
             "   Actualizado: " + TODAY + " */\n"
             "const CASES = ["]
    for c in cases:
        scores = c["scores"]
        history_compact = [
            {k: v for k, v in h.items()
             if k in ("date","pari","mai","pai","spi","pubai","nsi","velocity")}
            for h in c.get("history", [])[-90:]
        ]
        entry = (
            "  {\n"
            f'    name:"{c["name"]}",\n'
            f'    scores:{{{",".join(f"{k}:{v}" for k,v in scores.items())}}},\n'
            f'    velocity:{c["velocity"]},\n'
            f'    analyst:"{c["analyst"]}",\n'
            f'    date:"{c["date"]}",\n'
            f'    history:{json.dumps(history_compact, ensure_ascii=False)},\n'
            "  },"
        )
        lines.append(entry)
    lines.append("];")
    return "\n".join(lines)


def build_header_buttons(cases):
    """Genera los botones del header para cada issue."""
    btns = []
    for i, c in enumerate(cases):
        short = c["name"].split("(")[0].strip()[:28]
        active = ' active-case' if i == 0 else ''
        btns.append(
            f'    <button class="demo-btn{active}" onclick="loadCase({i})">{short}</button>'
        )
    return "\n".join(btns)


def inject_data(template_html, cases, generated_date):
    """
    Reemplaza en el template:
      1. El bloque const CASES = [...] con los datos reales
      2. Los botones del header con los issues reales
      3. El valor del issue-input inicial
      4. El badge de fecha de actualización
    """
    html = template_html

    # ── 1. Reemplazar bloque CASES ──────────────────────────────────
    # Marcador de inicio: línea que dice /* ═══ CASOS...  o  const CASES = [
    # Marcador de fin:    el ]; que cierra el array
    # Buscamos el bloque completo con regex
    pattern = r'/\* ═══ CASOS.*?const CASES = \[.*?\];'
    new_cases_block = build_cases_js(cases)

    result = re.sub(pattern, new_cases_block, html, flags=re.DOTALL)
    if result == html:
        # fallback: reemplazar solo const CASES = [...]; sin el comentario
        pattern2 = r'const CASES = \[.*?\];'
        result = re.sub(pattern2, new_cases_block, html, flags=re.DOTALL, count=1)

    html = result

    # ── 2. Reemplazar botones del header ────────────────────────────
    old_btns_pattern = r'(<div class="header-btns">).*?(</div>)'
    new_btns = f'\\1\n{build_header_buttons(cases)}\n  \\2'
    html = re.sub(old_btns_pattern, new_btns, html, flags=re.DOTALL, count=1)

    # ── 3. Actualizar el input del issue activo ──────────────────────
    first_name = cases[0]["name"] if cases else "PARI Spain"
    html = re.sub(
        r'(id="issueName"\s+value=")[^"]*(")',
        f'\\g<1>{first_name}\\2',
        html
    )

    # ── 4. Actualizar badge de fecha ─────────────────────────────────
    html = re.sub(
        r'(class="case-tag">)[^<]*(</div>)',
        f'\\1ACTUALIZADO · {generated_date}\\2',
        html
    )

    # ── 5. Actualizar title ──────────────────────────────────────────
    html = html.replace(
        "<title>PARI — Plan Europeo de Vivienda Asequible</title>",
        "<title>PARI Spain — Public Affairs Risk Index</title>"
    )

    return html


if __name__ == "__main__":
    print("📄 PARI Spain — Generando dashboard...")

    # Cargar datos
    result = load_data()
    if isinstance(result, tuple):
        cases, generated_date = result
    else:
        cases, generated_date = result, TODAY

    print(f"  Issues cargados: {len(cases)}")
    for c in cases:
        pari = round(sum({
            "mai":0.20,"pai":0.30,"spi":0.20,"pubai":0.15,"nsi":0.15
        }[k]*v for k,v in c["scores"].items()))
        print(f"    {c['name']}: PARI={pari}, velocity={c['velocity']:+d}")

    # Leer template
    if not TEMPLATE.exists():
        print(f"  ❌ No se encuentra PARI_Standalone.html en {TEMPLATE}")
        print("     Asegúrate de que el archivo está en el repositorio.")
        raise SystemExit(1)

    template_html = TEMPLATE.read_text(encoding="utf-8")
    print(f"  Template: {TEMPLATE.name} ({len(template_html)//1024}KB)")

    # Inyectar datos
    final_html = inject_data(template_html, cases, generated_date)

    # Escribir output
    OUT_FILE.write_text(final_html, encoding="utf-8")
    print(f"  ✅ Dashboard generado: {OUT_FILE}")
    print(f"     Tamaño: {OUT_FILE.stat().st_size // 1024}KB")
    print(f"     Fecha:  {generated_date}")
