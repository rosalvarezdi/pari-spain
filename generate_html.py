"""
PARI Spain — Daily Engine v2
==============================
1. Lee issues.json — única fuente de configuración
2. Recoge datos reales (GDELT, Trends, RSS, EUR-Lex)
3. Calcula scores PARI por pilar
4. Llama a Claude API para generar análisis cualitativo
5. Guarda todo en data/ para que generate_html.py lo publique
"""

import json
import time
import datetime
import requests
import feedparser
import os
import re
from pathlib import Path

try:
    from pytrends.request import TrendReq
    HAS_PYTRENDS = True
except ImportError:
    HAS_PYTRENDS = False

# ── CONFIG ────────────────────────────────────────────────────────────
TODAY      = datetime.date.today()
DATE_STR   = TODAY.isoformat()
DATA_DIR   = Path(__file__).parent / "data"
ISSUES_FILE = Path(__file__).parent / "issues.json"
DATA_DIR.mkdir(exist_ok=True)

WEIGHTS = {"mai": 0.20, "pai": 0.30, "spi": 0.20, "pubai": 0.15, "nsi": 0.15}

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ── HELPERS ───────────────────────────────────────────────────────────

def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, round(v)))

def minmax(v, vmin, vmax, scale=100):
    if vmax == vmin: return 50
    return clamp((v - vmin) / (vmax - vmin) * scale)

def safe_get(url, timeout=15, retries=2):
    headers = {"User-Agent": "PARI-Spain/2.0 (public affairs research)"}
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            if i == retries - 1:
                print(f"    ⚠ {url[:55]}: {e}")
            time.sleep(2)
    return None

def log(msg): print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_risk(score):
    if score <= 20:  return "Mínimo",  "#16A34A"
    if score <= 40:  return "Bajo",    "#65A30D"
    if score <= 60:  return "Moderado","#CA8A04"
    if score <= 75:  return "Elevado", "#EA580C"
    if score <= 90:  return "Alto",    "#DC2626"
    return                  "Crítico", "#9333EA"

def today_gdelt(): return TODAY.strftime("%Y%m%d%H%M%S")
def week_gdelt():  return (TODAY - datetime.timedelta(days=7)).strftime("%Y%m%d%H%M%S")
def month_gdelt(): return (TODAY - datetime.timedelta(days=30)).strftime("%Y%m%d%H%M%S")

# ── PILLAR 1: MEDIA ATTENTION (MAI) ──────────────────────────────────

def collect_mai(issue):
    log("  MAI — GDELT...")
    q = requests.utils.quote(issue["search_terms"]["gdelt"])
    base = "https://api.gdeltproject.org/api/v2/doc/doc"

    recent, baseline = [], []
    r1 = safe_get(f"{base}?query={q}%20sourcelang:Spanish&mode=artlist&maxrecords=250"
                  f"&startdatetime={week_gdelt()}&enddatetime={today_gdelt()}&format=json")
    if r1:
        try: recent = r1.json().get("articles", [])
        except: pass

    r2 = safe_get(f"{base}?query={q}%20sourcelang:Spanish&mode=artlist&maxrecords=250"
                  f"&startdatetime={month_gdelt()}&enddatetime={week_gdelt()}&format=json")
    if r2:
        try: baseline = r2.json().get("articles", [])
        except: pass

    rc = len(recent)
    bc_weekly = len(baseline) / 3 if baseline else 1
    tones = [a.get("tone", 0) for a in recent if "tone" in a]
    avg_tone = sum(tones) / len(tones) if tones else 0

    tier1 = ["elpais.com","elmundo.es","abc.es","expansion.com","elconfidencial.com",
             "eldiario.es","europapress.es","politico.eu","cincodias.elpais.com"]
    t1_count = sum(1 for a in recent if any(d in a.get("url","").lower() for d in tier1))

    vol_score   = minmax(rc, 0, 200)
    sent_score  = clamp(50 - avg_tone * 5)
    accel       = (rc - bc_weekly) / bc_weekly if bc_weekly > 0 else 0
    accel_score = clamp(50 + accel * 30)
    tier_score  = minmax(t1_count / max(rc, 1), 0, 0.5)
    edit_score  = minmax(sum(1 for a in recent if abs(a.get("tone",0)) > 3), 0, 30)

    score = clamp(.25*vol_score + .25*sent_score + .20*accel_score + .15*tier_score + .15*edit_score)
    sub   = {"coverage_volume": vol_score, "sentiment_trajectory": sent_score,
             "acceleration": accel_score, "media_tier": tier_score, "editorial": edit_score}
    raw   = {"recent": rc, "baseline_weekly": round(bc_weekly,1), "avg_tone": round(avg_tone,2)}
    log(f"    MAI={score} (vol={vol_score}, sent={sent_score}, accel={accel_score})")
    return {"score": score, "sub": sub, "raw": raw}

# ── PILLAR 2: POLITICAL ACTIVITY (PAI) ───────────────────────────────

def collect_pai(issue):
    log("  PAI — EUR-Lex + Congreso RSS + Euractiv...")
    sub = {}

    # EUR-Lex RSS
    q_el = requests.utils.quote(issue["search_terms"]["eurlex"])
    feed_el = feedparser.parse(
        f"https://eur-lex.europa.eu/search.html?text={q_el}&scope=EURLEX&lang=es&rss=true"
    )
    eurlex_count = len(feed_el.entries) if feed_el.entries else 0
    sub["legislative_pipeline"] = clamp(10 + eurlex_count * 13)

    # Congreso RSS
    q_co = requests.utils.quote(issue["search_terms"]["congress"])
    feed_co = feedparser.parse(
        f"https://www.congreso.es/rss/iniciativasBusqueda?texto={q_co}&legislatura=15&tipo=todos"
    )
    parl_count = len(feed_co.entries) if feed_co.entries else 0
    sub["parliamentary_mentions"] = clamp(minmax(parl_count, 0, 20) * .7 + 30)

    # Euractiv
    reg_hits = 0
    for feed_url in ["https://www.euractiv.com/sections/eu-priorities-2020/feed/",
                     "https://www.europarl.europa.eu/rss/doc/top-stories/es.xml"]:
        feed = feedparser.parse(feed_url)
        kws = issue["search_terms"]["eurlex"].split()[:3]
        for e in feed.entries[:30]:
            if any(k.lower() in (e.get("title","") + e.get("summary","")).lower() for k in kws):
                reg_hits += 1
    sub["regulatory_signals"] = clamp(minmax(reg_hits, 0, 10) * .6 + 30)

    # PE press releases
    ep = feedparser.parse("https://www.europarl.europa.eu/rss/doc/press-releases/es.xml")
    exec_hits = sum(1 for e in ep.entries[:50]
                    if any(k.lower() in (e.get("title","") + e.get("summary","")).lower()
                           for k in issue["search_terms"]["eurlex"].split()))
    sub["executive_statements"] = clamp(minmax(exec_hits, 0, 5) * .7 + 35)

    # Cross-border GDELT
    q_int = requests.utils.quote(issue["search_terms"]["eurlex"] + " Europe regulation")
    r_int = safe_get(
        f"https://api.gdeltproject.org/api/v2/doc/doc?query={q_int}"
        f"&mode=artlist&maxrecords=100&startdatetime={week_gdelt()}&enddatetime={today_gdelt()}&format=json"
    )
    intl = 0
    if r_int:
        try: intl = len(r_int.json().get("articles", []))
        except: pass
    sub["cross_border_contagion"] = clamp(minmax(intl, 0, 100) * .5 + 40)

    score = clamp(.25*sub["parliamentary_mentions"] + .25*sub["legislative_pipeline"] +
                  .20*sub["regulatory_signals"] + .15*sub["executive_statements"] +
                  .15*sub["cross_border_contagion"])
    log(f"    PAI={score}")
    return {"score": score, "sub": sub, "raw": {"eurlex": eurlex_count, "parl": parl_count}}

# ── PILLAR 3: STAKEHOLDER PRESSURE (SPI) ─────────────────────────────

def collect_spi(issue):
    log("  SPI — NGOs + News...")
    sub = {}

    ngo_hits = 0
    all_feeds = issue["search_terms"].get("ngo_feeds", []) + [
        "https://www.caritas.es/feed/", "https://www.ccoo.es/rss/Actuaciones_y_noticias.rss",
        "https://afectadosporlahipoteca.com/feed/",
    ]
    kws = issue["risk_keywords"][:5]
    for url in all_feeds:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:20]:
                if any(k in (e.get("title","") + e.get("summary","")).lower() for k in kws):
                    ngo_hits += 1
        except: pass
    sub["ngo_civil_society"] = clamp(minmax(ngo_hits, 0, 15) * .6 + 25)

    q = requests.utils.quote(f"campaña petición {issue['search_terms']['congress']} España {TODAY.year}")
    feed_n = feedparser.parse(f"https://news.google.com/rss/search?q={q}&hl=es&gl=ES&ceid=ES:es")
    camp = sum(1 for e in feed_n.entries[:30]
               if any(k in e.get("title","").lower() for k in ["petición","campaña","manifestación","protesta","plataforma"]))
    sub["advocacy_campaigns"] = clamp(minmax(camp, 0, 10) * .7 + 20)

    corp_kws = ["se compromete","anuncia medidas","nuevo plan","regulación propia"]
    q2 = requests.utils.quote(f"empresa regulación {issue['search_terms']['congress']} España")
    f2  = feedparser.parse(f"https://news.google.com/rss/search?q={q2}&hl=es&gl=ES&ceid=ES:es")
    corp = sum(1 for e in f2.entries[:20]
               if any(k in (e.get("title","") + e.get("summary","")).lower() for k in corp_kws))
    sub["corporate_repositioning"] = clamp(minmax(corp, 0, 8) * .6 + 30)

    tt_hits = 0
    for url in ["https://www.funcas.es/feed/","https://www.elcano.es/rss/","https://www.fedea.net/feed/"]:
        try:
            f = feedparser.parse(url)
            for e in f.entries[:15]:
                if any(k in (e.get("title","") + e.get("summary","")).lower()
                       for k in issue["search_terms"]["congress"].split()):
                    tt_hits += 1
        except: pass
    sub["think_tank_output"] = clamp(minmax(tt_hits, 0, 10) * .7 + 25)

    q3 = requests.utils.quote(f"demanda denuncia recurso {issue['search_terms']['congress']} España tribunal")
    f3  = feedparser.parse(f"https://news.google.com/rss/search?q={q3}&hl=es&gl=ES&ceid=ES:es")
    legal = sum(1 for e in f3.entries[:20]
                if any(k in e.get("title","").lower() for k in ["demanda","denuncia","sentencia","tribunal"]))
    sub["legal_litigation"] = clamp(minmax(legal, 0, 8) * .7 + 20)

    score = clamp(.25*sub["ngo_civil_society"] + .20*sub["advocacy_campaigns"] +
                  .20*sub["corporate_repositioning"] + .20*sub["think_tank_output"] +
                  .15*sub["legal_litigation"])
    log(f"    SPI={score}")
    return {"score": score, "sub": sub, "raw": {"ngo_hits": ngo_hits, "camp": camp}}

# ── PILLAR 4: PUBLIC ATTENTION (PubAI) ───────────────────────────────

def collect_pubai(issue):
    log("  PubAI — Google Trends + News...")
    sub = {}

    search_score = 40
    if HAS_PYTRENDS:
        try:
            pt = TrendReq(hl="es-ES", tz=60, timeout=(10,25), retries=2, backoff_factor=0.5)
            terms = issue["search_terms"]["trends"][:5]
            pt.build_payload(terms, cat=0, timeframe="today 3-m", geo="ES")
            df = pt.interest_over_time()
            if not df.empty:
                last2w = df.iloc[-2:][terms].mean().mean()
                avg    = df[terms].mean().mean()
                ratio  = last2w / max(avg, 1)
                search_score = clamp(minmax(last2w, 0, 100) * .6 + minmax(ratio, 0.5, 2.0) * .4)
        except Exception as e:
            log(f"    ⚠ Trends: {e}")
    sub["search_intensity"] = clamp(search_score)

    q = requests.utils.quote(" ".join(issue["search_terms"]["trends"][:2]))
    f = feedparser.parse(f"https://news.google.com/rss/search?q={q}&hl=es&gl=ES&ceid=ES:es")
    social = len(f.entries)
    sources = len(set(e.get("source",{}).get("title","") for e in f.entries[:20]))
    sub["social_volume"]  = clamp(minmax(social, 0, 30) * .7 + 25)
    sub["virality"]       = clamp(minmax(sources, 1, 15) * .6 + 20)
    sub["public_polarity"] = 40  # default without GDELT tone variance
    sub["geographic_concentration"] = 45

    score = clamp(.30*sub["search_intensity"] + .25*sub["social_volume"] +
                  .20*sub["virality"] + .15*sub["public_polarity"] +
                  .10*sub["geographic_concentration"])
    log(f"    PubAI={score}")
    return {"score": score, "sub": sub, "raw": {"social": social, "sources": sources}}

# ── PILLAR 5: NARRATIVE SHIFT (NSI) ──────────────────────────────────

def collect_nsi(issue):
    log("  NSI — GDELT keyword analysis...")
    sub = {}

    q = requests.utils.quote(issue["search_terms"]["gdelt"])
    r = safe_get(
        f"https://api.gdeltproject.org/api/v2/doc/doc?query={q}%20sourcelang:Spanish"
        f"&mode=artlist&maxrecords=250&startdatetime={week_gdelt()}&enddatetime={today_gdelt()}&format=json"
    )
    articles = []
    if r:
        try: articles = r.json().get("articles", [])
        except: pass

    all_text = " ".join(
        a.get("title","") + " " + a.get("url","") for a in articles
    ).lower()

    risk_kws    = issue.get("risk_keywords", [])
    neutral_kws = issue.get("neutral_keywords", [])
    rc = sum(all_text.count(k) for k in risk_kws)
    nc = sum(all_text.count(k) for k in neutral_kws)
    ratio = rc / (rc + nc) if (rc + nc) > 0 else 0.4
    sub["keyword_emergence"] = clamp(minmax(ratio, 0, 0.8) * .7 + 20)

    moral   = ["derecho fundamental","derecho humano","emergencia","crisis","dignidad","exclusión","víctima"]
    tech    = ["reglamento","directiva","transposición","propuesta","consulta","borrador"]
    mc = sum(all_text.count(k) for k in moral)
    tc = sum(all_text.count(k) for k in tech)
    mr = mc / (mc + tc) if (mc + tc) > 0 else 0.4
    sub["framing_migration"] = clamp(minmax(mr, 0, 0.8) * .7 + 20)

    analogy = ["escándalo","burbuja","colapso","especulación","expulsión","gentrificación","turistificación"]
    ac = sum(all_text.count(k) for k in analogy)
    sub["metaphor_tracking"] = clamp(minmax(ac, 0, 20) * .7 + 20)

    risk_domains = set()
    for a in articles:
        if any(k in a.get("title","").lower() for k in risk_kws[:5]):
            try: risk_domains.add(a.get("url","").split("/")[2])
            except: pass
    sub["narrative_coalition"] = clamp(minmax(len(risk_domains), 0, 20) * .7 + 20)

    pos_kws = ["seguridad jurídica","inversión","oferta","simplificación","datos positivos","acuerdo"]
    pc = sum(all_text.count(k) for k in pos_kws)
    sub["counter_narrative"] = clamp(100 - minmax(pc, 0, 30) * .5)

    score = clamp(.25*sub["keyword_emergence"] + .25*sub["framing_migration"] +
                  .20*sub["metaphor_tracking"] + .20*sub["narrative_coalition"] +
                  .10*sub["counter_narrative"])
    log(f"    NSI={score}")
    return {"score": score, "sub": sub, "raw": {"risk_kw": rc, "moral": mc, "domains": len(risk_domains)}}

# ── GEMINI AI ANALYSIS ───────────────────────────────────────────────

def generate_ai_analysis(issue, pillar_scores, pari, risk_label, velocity, history):
    """
    Llama a Google Gemini API (gratuita) para generar el análisis cualitativo.
    Modelo: gemini-2.0-flash  — gratuito, 1500 req/día, muy rápido.
    Obtén tu key gratis en: https://aistudio.google.com/app/apikey
    """
    if not GEMINI_API_KEY:
        log("  ⚠ GEMINI_API_KEY no configurada — análisis IA omitido")
        return None

    # Historial reciente para dar contexto de tendencia
    hist_text = ""
    if len(history) > 1:
        last_7 = history[-7:]
        hist_text = f"\nHistórico reciente (últimos {len(last_7)} días):\n"
        for h in last_7:
            hist_text += f"  {h['date']}: PARI={h['pari']} ({h.get('risk','')})\n"

    scores_text = "\n".join(
        f"  - {k.upper()} ({int(WEIGHTS[k]*100)}% peso): {v}/100"
        for k, v in pillar_scores.items()
    )

    velocity_text = (
        f"▲ +{velocity} puntos (ESCALANDO)" if velocity > 5
        else f"▲ +{velocity} (subiendo)" if velocity > 0
        else f"→ {velocity} (estable)" if velocity == 0
        else f"▼ {velocity} (descendiendo)"
    )

    prompt = f"""Eres un analista senior de public affairs especializado en regulación europea y riesgo político.
Analiza este caso y genera un análisis estratégico en JSON.

ISSUE: {issue['name']}
GEOGRAFÍA: {issue['geography']}
SECTOR: {issue['sector']}
CONTEXTO: {issue['context']}
STAKEHOLDERS CLAVE: {issue['stakeholders']}

PARI SCORE HOY: {pari}/100 — RIESGO {risk_label.upper()}
VELOCITY: {velocity_text}
{hist_text}
SCORES POR PILAR:
{scores_text}

Interpreta los scores así:
- MAI alto → cobertura mediática intensa y/o negativa
- PAI alto → actividad parlamentaria/regulatoria elevada
- SPI alto → presión activa de stakeholders (ONGs, empresas, academia)
- PubAI alto → alta atención pública (búsquedas, redes sociales)
- NSI alto → cambio de narrativa hacia framing de riesgo/crisis

Genera SOLO el siguiente JSON sin texto adicional, sin bloques markdown, sin explicaciones:

{{
  "risk_flags": [
    {{
      "level": "high",
      "title": "Título conciso del riesgo principal (máx 80 caracteres)",
      "text": "Descripción del riesgo, su origen y consecuencias prácticas para public affairs (2-3 frases)."
    }},
    {{
      "level": "medium",
      "title": "Segundo riesgo",
      "text": "Descripción (2-3 frases)."
    }},
    {{
      "level": "low",
      "title": "Oportunidad o riesgo menor",
      "text": "Descripción (2-3 frases)."
    }}
  ],
  "position": {{
    "adopted": [
      "Primera acción o posición ya adoptada",
      "Segunda acción o posición ya adoptada"
    ],
    "pending": [
      "Primera acción pendiente de definir o ejecutar",
      "Segunda acción pendiente",
      "Tercera acción pendiente"
    ],
    "strategic_approach": "Descripción del enfoque estratégico recomendado basado en el score actual (2-3 frases).",
    "strategic_level": "preventive"
  }},
  "timeline": [
    {{
      "status": "done",
      "date": "MES AÑO",
      "text": "Hito legislativo o político ya ocurrido",
      "badge": "COMPLETADO"
    }},
    {{
      "status": "active",
      "date": "MES AÑO",
      "text": "Hito en curso ahora mismo",
      "badge": "EN CURSO"
    }},
    {{
      "status": "pending",
      "date": "AÑO (tf)",
      "text": "Hito futuro relevante para el issue",
      "badge": "PENDIENTE"
    }}
  ],
  "registradores": {{
    "formal_position": false,
    "formal_position_note": "Estado actual de la posición formal del actor institucional principal.",
    "vectors": [
      {{
        "title": "Vector 1 — nombre descriptivo",
        "text": "Análisis del primer vector de riesgo o impacto (2-3 frases)."
      }},
      {{
        "title": "Vector 2 — nombre descriptivo",
        "text": "Análisis del segundo vector (2-3 frases)."
      }}
    ],
    "recommended_action": "Acción concreta recomendada para el profesional de public affairs (1-2 frases)."
  }},
  "strategic_summary": "Síntesis ejecutiva de 3-4 frases para un director de public affairs: qué está pasando, por qué importa ahora, y qué hacer.",
  "watch_next": [
    "Primera señal concreta a vigilar en los próximos 30 días",
    "Segunda señal a vigilar",
    "Tercera señal a vigilar"
  ]
}}"""

    log("  🤖 Generando análisis con Gemini API...")
    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,        # más determinista = más consistente
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",  # fuerza JSON puro
            }
        }
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()

        raw = resp.json()
        content = raw["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Limpia bloques markdown por si acaso
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'\s*```$', '', content)

        analysis = json.loads(content)
        analysis["_meta"] = {
            "issue_id":            issue["id"],
            "issue_name":          issue["name"],
            "last_updated":        DATE_STR,
            "generated_by":        "gemini-2.0-flash",
            "pari_at_generation":  pari,
            "subtitle": f"Análisis de public affairs · {issue['geography']} · {DATE_STR}"
        }
        n_flags    = len(analysis.get("risk_flags", []))
        n_timeline = len(analysis.get("timeline", []))
        log(f"  ✅ Análisis Gemini: {n_flags} flags, {n_timeline} hitos en timeline")
        return analysis

    except json.JSONDecodeError as e:
        log(f"  ⚠ JSON inválido de Gemini: {e}")
        log(f"     Respuesta: {content[:200] if 'content' in dir() else 'N/A'}")
        return None
    except Exception as e:
        log(f"  ⚠ Error Gemini API: {e}")
        return None

# ── VELOCITY ──────────────────────────────────────────────────────────

def compute_velocity(issue_id, current_pari):
    h_file = DATA_DIR / f"{issue_id}_history.json"
    if h_file.exists():
        try:
            history = json.loads(h_file.read_text())
            if history:
                return current_pari - history[-1]["pari"]
        except: pass
    return 0

def save_history(issue_id, pari, risk_label, velocity, pillar_scores):
    h_file = DATA_DIR / f"{issue_id}_history.json"
    history = []
    if h_file.exists():
        try: history = json.loads(h_file.read_text())
        except: pass
    history = [h for h in history if h["date"] != DATE_STR]
    history.append({
        "date": DATE_STR, "pari": pari, "risk": risk_label, "velocity": velocity,
        **{k: pillar_scores[k] for k in WEIGHTS}
    })
    history = sorted(history, key=lambda x: x["date"])[-90:]
    h_file.write_text(json.dumps(history, indent=2, ensure_ascii=False))
    return history

# ── MAIN ──────────────────────────────────────────────────────────────

def run_issue(issue):
    log(f"\n{'='*55}")
    log(f"  {issue['name']} [{issue['geography']}]")
    log(f"{'='*55}")

    mai   = collect_mai(issue)
    pai   = collect_pai(issue)
    spi   = collect_spi(issue)
    pubai = collect_pubai(issue)
    nsi   = collect_nsi(issue)

    pillar_scores = {
        "mai": mai["score"], "pai": pai["score"], "spi": spi["score"],
        "pubai": pubai["score"], "nsi": nsi["score"]
    }
    pari = round(sum(WEIGHTS[k] * v for k, v in pillar_scores.items()))
    risk_label, risk_color = get_risk(pari)
    velocity = compute_velocity(issue["id"], pari)
    history  = save_history(issue["id"], pari, risk_label, velocity, pillar_scores)

    # Genera análisis con IA
    analysis = generate_ai_analysis(
        issue, pillar_scores, pari, risk_label, velocity, history
    )

    # Si Claude falla, carga el último análisis guardado
    if analysis is None:
        a_file = DATA_DIR / f"{issue['id']}_analysis.json"
        if a_file.exists():
            try:
                analysis = json.loads(a_file.read_text())
                analysis["_meta"]["last_updated"] = DATE_STR
                log("  ↩ Usando análisis anterior guardado")
            except: pass

    # Guarda análisis
    if analysis:
        a_file = DATA_DIR / f"{issue['id']}_analysis.json"
        a_file.write_text(json.dumps(analysis, indent=2, ensure_ascii=False))

    result = {
        "issue_id": issue["id"], "issue_name": issue["name"],
        "geography": issue.get("geography",""), "sector": issue.get("sector",""),
        "date": DATE_STR, "pari": pari, "risk_level": risk_label,
        "risk_color": risk_color, "velocity": velocity,
        "pillar_scores": pillar_scores,
        "pillar_detail": {
            "mai": mai, "pai": pai, "spi": spi, "pubai": pubai, "nsi": nsi
        },
        "weights": WEIGHTS,
        "contributions": {k: round(WEIGHTS[k]*v, 1) for k, v in pillar_scores.items()},
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z"
    }

    # Guarda latest y today
    (DATA_DIR / f"{issue['id']}_latest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    (DATA_DIR / f"{issue['id']}_{DATE_STR}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

    log(f"\n  ✅ PARI={pari} [{risk_label}]  Velocity={velocity:+d}  Analysis={'✅' if analysis else '❌'}")
    return result

def generate_summary(results):
    summary = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "date": DATE_STR,
        "issues": [{
            "id": r["issue_id"], "name": r["issue_name"],
            "geography": r.get("geography",""), "sector": r.get("sector",""),
            "date": r["date"], "pari": r["pari"],
            "risk_level": r["risk_level"], "risk_color": r["risk_color"],
            "velocity": r["velocity"], "scores": r["pillar_scores"]
        } for r in results]
    }
    (DATA_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    log("🚀 PARI Spain Engine v2")
    log(f"   Fecha: {DATE_STR}")

    if not ISSUES_FILE.exists():
        log("❌ issues.json no encontrado")
        raise SystemExit(1)

    issues = json.loads(ISSUES_FILE.read_text())
    active = [i for i in issues if i.get("active", True)]
    log(f"   Issues activos: {[i['id'] for i in active]}")

    results = []
    for issue in active:
        try:
            r = run_issue(issue)
            results.append(r)
        except Exception as e:
            log(f"❌ Error en {issue['id']}: {e}")
            import traceback; traceback.print_exc()

    generate_summary(results)
    log(f"\n✅ Completado — {len(results)} issues procesados")
