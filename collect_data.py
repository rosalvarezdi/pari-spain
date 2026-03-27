"""
PARI Spain — Daily Data Collection Engine - Rosanna Michele Alvarez Diaz (RMAD)
==========================================
Recoge señales reales de fuentes abiertas y calcula los scores
de los 5 pilares del PARI automáticamente cada día.

Fuentes usadas (todas gratuitas / sin API key):
  MAI  — GDELT Project (noticias globales con sentimiento)
  PAI  — EUR-Lex (pipeline legislativo UE) + Congreso.es RSS
  SPI  — RSS de ONGs y sociedad civil española
  PubAI— pytrends (Google Trends)
  NSI  — GDELT tone + keyword emergence

Requiere:
  pip install requests pytrends feedparser beautifulsoup4 pandas
"""

import json
import math
import time
import datetime
import requests
import feedparser
import pandas as pd
from pathlib import Path
from pytrends.request import TrendReq

# ── CONFIG ────────────────────────────────────────────────────────────
TODAY      = datetime.date.today()
DATE_STR   = TODAY.isoformat()
DATA_DIR   = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Issues a monitorear — añade o quita según necesidad
ISSUES = [
    {
        "id":      "vivienda_asequible",
        "name":    "Plan Europeo Vivienda Asequible",
        "geography": "ES",
        # Términos de búsqueda para cada pilar
        "terms": {
            "gdelt":   "vivienda asequible Europa registradores",
            "trends":  ["vivienda asequible", "alquiler turístico registro", "affordable housing act"],
            "eurlex":  "affordable housing",
            "congress": "vivienda",
            "ngo_feeds": [
                "https://provivienda.org/feed/",
                "https://www.habitatespana.org/feed/",
            ],
        },
        # Keywords negativos que indican escalada narrativa
        "risk_keywords": [
            "crisis", "emergencia habitacional", "turistificación", "gentrificación",
            "especulación", "fondos buitre", "derecho fundamental", "vulneración",
            "protesta", "manifestación", "denuncia", "ilegal"
        ],
        # Keywords técnicos (narrativa low-risk)
        "neutral_keywords": [
            "reglamento", "directiva", "subsidiariedad", "consulta",
            "transposición", "informe", "propuesta", "borrador"
        ],
    },
    # Añade más issues aquí con el mismo formato
    # {
    #     "id": "ia_regulacion",
    #     "name": "Regulación IA España",
    #     ...
    # },
]

# ── HELPERS ───────────────────────────────────────────────────────────

def clamp(value, lo=0, hi=100):
    """Mantiene el valor dentro del rango 0-100."""
    return max(lo, min(hi, round(value)))

def minmax_norm(value, v_min, v_max, scale=100):
    """Normalización min-max a escala 0-100."""
    if v_max == v_min:
        return 50
    return clamp((value - v_min) / (v_max - v_min) * scale)

def safe_get(url, timeout=15, retries=2):
    """GET con reintentos y headers de cortesía."""
    headers = {"User-Agent": "PARI-Spain/1.0 (public affairs research; rosalvarezdi@gmail.com)"}
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            if attempt == retries - 1:
                print(f"  ⚠ Error fetching {url[:60]}: {e}")
                return None
            time.sleep(2)

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

# ── PILLAR 1: MEDIA ATTENTION INDEX (MAI) ────────────────────────────

def collect_mai(issue):
    """
    Fuente: GDELT GEO 2.0 Article Search API (gratuito, sin key)
    Mide: volumen, tono y aceleración de cobertura sobre el issue.
    """
    log(f"MAI — Consultando GDELT para '{issue['name']}'...")
    
    results = {}
    
    # Fechas: hoy y hace 30 días (baseline)
    today_fmt  = TODAY.strftime("%Y%m%d%H%M%S")
    week_ago   = (TODAY - datetime.timedelta(days=7)).strftime("%Y%m%d%H%M%S")
    month_ago  = (TODAY - datetime.timedelta(days=30)).strftime("%Y%m%d%H%M%S")
    
    # Términos de búsqueda codificados
    q = requests.utils.quote(issue["terms"]["gdelt"])
    
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
    
    # --- Volume actual (últimos 7 días) ---
    url_recent = (
        f"{base_url}?query={q}%20sourcelang:Spanish"
        f"&mode=artlist&maxrecords=250&startdatetime={week_ago}&enddatetime={today_fmt}"
        f"&sort=DateDesc&format=json"
    )
    r = safe_get(url_recent)
    recent_count = 0
    recent_tone  = 0.0
    articles_recent = []
    if r:
        try:
            data = r.json()
            articles_recent = data.get("articles", [])
            recent_count = len(articles_recent)
            # Tono medio (GDELT: negativo = peor, scale aprox -10 a +10)
            tones = [a.get("tone", 0) for a in articles_recent if "tone" in a]
            recent_tone = sum(tones) / len(tones) if tones else 0
        except Exception as e:
            log(f"  ⚠ GDELT parse error: {e}")
    
    # --- Volume baseline (30 días anteriores, semanas 2-4) ---
    url_baseline = (
        f"{base_url}?query={q}%20sourcelang:Spanish"
        f"&mode=artlist&maxrecords=250&startdatetime={month_ago}&enddatetime={week_ago}"
        f"&sort=DateDesc&format=json"
    )
    r2 = safe_get(url_baseline)
    baseline_count = 0
    if r2:
        try:
            data2 = r2.json()
            baseline_count = len(data2.get("articles", []))
        except:
            pass
    
    # Normaliza el baseline a por-semana (son ~3 semanas vs 1 semana)
    baseline_weekly = baseline_count / 3 if baseline_count > 0 else 1
    
    # --- Sub-indicadores ---
    
    # 1. Coverage Volume (0-100): compara con un máximo esperado de 200 menciones/semana
    vol_score = minmax_norm(recent_count, 0, 200)
    
    # 2. Sentiment Trajectory (0-100): tono muy negativo → score alto
    # GDELT tone: valores negativos = tono negativo
    # Invertimos: -10 → 100, 0 → 50, +10 → 0
    sent_score = clamp(50 - (recent_tone * 5))
    
    # 3. Acceleration Coefficient (0-100)
    if baseline_weekly > 0:
        accel_ratio = (recent_count - baseline_weekly) / baseline_weekly
        accel_score = clamp(50 + accel_ratio * 30)
    else:
        accel_score = 50
    
    # 4. Media Tier Migration: artículos de medios de referencia
    tier1_domains = [
        "elpais.com", "elmundo.es", "abc.es", "larazon.es",
        "expansion.com", "cincodias.elpais.com", "politico.eu",
        "europapress.es", "elconfidencial.com", "eldiario.es"
    ]
    tier1_count = sum(
        1 for a in articles_recent
        if any(d in a.get("url", "").lower() for d in tier1_domains)
    )
    tier1_ratio = tier1_count / max(recent_count, 1)
    tier_score = minmax_norm(tier1_ratio, 0, 0.5)
    
    # 5. Editorial Engagement: estimado por longitud/relevancia (GDELT no distingue ops)
    # Proxy: artículos con tono muy marcado (op-ed suelen tener tono ± extremo)
    editorial_proxy = sum(1 for a in articles_recent if abs(a.get("tone", 0)) > 3)
    edit_score = minmax_norm(editorial_proxy, 0, 30)
    
    # Score MAI compuesto (media ponderada de sub-indicadores)
    mai_score = clamp(
        0.25 * vol_score +
        0.25 * sent_score +
        0.20 * accel_score +
        0.15 * tier_score +
        0.15 * edit_score
    )
    
    results = {
        "score": mai_score,
        "sub": {
            "coverage_volume":      vol_score,
            "sentiment_trajectory": sent_score,
            "acceleration":         accel_score,
            "media_tier":           tier_score,
            "editorial":            edit_score,
        },
        "raw": {
            "recent_articles":   recent_count,
            "baseline_weekly":   round(baseline_weekly, 1),
            "avg_tone":          round(recent_tone, 2),
            "tier1_articles":    tier1_count,
        }
    }
    
    log(f"  MAI = {mai_score} (vol={vol_score}, sent={sent_score}, accel={accel_score})")
    return results

# ── PILLAR 2: POLITICAL ACTIVITY INDEX (PAI) ─────────────────────────

def collect_pai(issue):
    """
    Fuentes:
      - EUR-Lex SPARQL: documentos legislativos sobre el término
      - Congreso.es RSS: menciones parlamentarias
      - Euractiv RSS: señales regulatorias EU
    """
    log(f"PAI — Consultando fuentes legislativas para '{issue['name']}'...")
    
    sub = {}
    
    # --- 1. Pipeline legislativo EU (EUR-Lex) ---
    eurlex_q = requests.utils.quote(issue["terms"]["eurlex"])
    # EUR-Lex REST API (no auth needed)
    eurlex_url = (
        f"https://eur-lex.europa.eu/search.html?qid=1&text={eurlex_q}"
        f"&scope=EURLEX&type=quick&lang=es&andText0=&andText1="
        # Alternativa: EUR-Lex SPARQL endpoint
    )
    # Usamos el search endpoint REST de EUR-Lex
    eurlex_api = f"https://eur-lex.europa.eu/search.html?text={eurlex_q}&scope=EURLEX&lang=es&type=quick"
    r = safe_get(f"https://eur-lex.europa.eu/search.html?text={eurlex_q}&type=quick&lang=es&scope=EURLEX&format=json")
    
    # EUR-Lex no tiene JSON puro; usamos su Atom feed de novedades legislativas
    eurlex_feed_url = (
        f"https://eur-lex.europa.eu/search.html?text={eurlex_q}"
        f"&scope=EURLEX&type=quick&lang=es"
        f"&DD_DATE_FROM={month_str()}&DD_DATE_TO={today_str()}"
        f"&rss=true"
    )
    
    eurlex_count = 0
    feed_data = feedparser.parse(eurlex_feed_url)
    eurlex_count = len(feed_data.entries) if feed_data.entries else 0
    
    # Score: 0 docs → 10, 1-2 → 40, 3-5 → 70, 6+ → 90
    leg_score = min(90, 10 + eurlex_count * 13)
    sub["legislative_pipeline"] = clamp(leg_score)
    
    # --- 2. Menciones parlamentarias (Congreso.es RSS) ---
    congress_term = requests.utils.quote(issue["terms"]["congress"])
    congress_feed_url = f"https://www.congreso.es/web/guest/busqueda-de-iniciativas?p_p_id=iniciativas&_iniciativas_mode=mostrarBuscador&_iniciativas_texto={congress_term}"
    
    # RSS del Congreso (iniciativas)
    congress_rss = f"https://www.congreso.es/rss/iniciativasBusqueda?texto={congress_term}&legislatura=15&tipo=todos"
    feed_congress = feedparser.parse(congress_rss)
    parl_count = len(feed_congress.entries) if feed_congress.entries else 0
    
    # También usamos el RSS de preguntas al gobierno
    parl_score = clamp(minmax_norm(parl_count, 0, 20) * 0.7 + 30)
    sub["parliamentary_mentions"] = parl_score
    
    # --- 3. Señales de agencias reguladoras (Euractiv RSS) ---
    euractiv_feeds = [
        "https://www.euractiv.com/sections/eu-priorities-2020/feed/",
        "https://www.europarl.europa.eu/rss/doc/top-stories/es.xml",
    ]
    reg_hits = 0
    for feed_url in euractiv_feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:30]:
            title_lower = (entry.get("title", "") + entry.get("summary", "")).lower()
            if any(kw in title_lower for kw in ["housing", "vivienda", "alquiler", "rental"]):
                reg_hits += 1
    reg_score = clamp(minmax_norm(reg_hits, 0, 10) * 0.6 + 30)
    sub["regulatory_signals"] = reg_score
    
    # --- 4. Declaraciones ejecutivas (Europarl + Gov España) ---
    ep_feed = feedparser.parse("https://www.europarl.europa.eu/rss/doc/press-releases/es.xml")
    exec_hits = 0
    for entry in ep_feed.entries[:50]:
        text = (entry.get("title", "") + entry.get("summary", "")).lower()
        if any(kw in text for kw in ["housing", "vivienda", "alquiler", "rental", "jørgensen"]):
            exec_hits += 1
    exec_score = clamp(minmax_norm(exec_hits, 0, 5) * 0.7 + 35)
    sub["executive_statements"] = exec_score
    
    # --- 5. Contagio transfronterizo ---
    # Proxy: menciones en medios europeos (GDELT con idioma no-español)
    gdelt_q = requests.utils.quote("affordable housing Europe regulation")
    url_intl = (
        f"https://api.gdeltproject.org/api/v2/doc/doc?query={gdelt_q}"
        f"&mode=artlist&maxrecords=100&startdatetime={week_str()}&enddatetime={today_str()}"
        f"&sort=DateDesc&format=json"
    )
    r_intl = safe_get(url_intl)
    intl_count = 0
    if r_intl:
        try:
            intl_count = len(r_intl.json().get("articles", []))
        except:
            pass
    contagion_score = clamp(minmax_norm(intl_count, 0, 100) * 0.5 + 40)
    sub["cross_border_contagion"] = contagion_score
    
    pai_score = clamp(
        0.25 * sub["parliamentary_mentions"] +
        0.25 * sub["legislative_pipeline"] +
        0.20 * sub["regulatory_signals"] +
        0.15 * sub["executive_statements"] +
        0.15 * sub["cross_border_contagion"]
    )
    
    log(f"  PAI = {pai_score}")
    return {"score": pai_score, "sub": sub, "raw": {"eurlex_docs": eurlex_count, "parl_hits": parl_count, "reg_hits": reg_hits}}

# ── PILLAR 3: STAKEHOLDER PRESSURE INDEX (SPI) ───────────────────────

def collect_spi(issue):
    """
    Fuentes:
      - RSS de ONGs y plataformas civiles relevantes
      - Change.org (sin API: scrape de contador público)
      - Google News RSS (peticiones, campañas)
    """
    log(f"SPI — Monitorizando stakeholders para '{issue['name']}'...")
    
    sub = {}
    
    # --- 1. Actividad ONG / Sociedad civil ---
    ngo_hits = 0
    ngo_recent = []
    
    # Feeds directos de ONGs clave
    ngo_feeds = issue["terms"].get("ngo_feeds", [])
    # Añadimos feeds genéricos de sociedad civil española
    ngo_feeds += [
        "https://www.caritas.es/feed/",
        "https://www.ccoo.es/rss/Actuaciones_y_noticias.rss",
        "https://www.ugt.es/rss.xml",
        "https://afectadosporlahipoteca.com/feed/",
    ]
    
    for feed_url in ngo_feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                text = (entry.get("title", "") + entry.get("summary", "")).lower()
                if any(kw in text for kw in ["vivienda", "alquiler", "housing", "registro", "turistico"]):
                    ngo_hits += 1
                    ngo_recent.append(entry.get("title", ""))
        except:
            pass
    
    ngo_score = clamp(minmax_norm(ngo_hits, 0, 15) * 0.6 + 25)
    sub["ngo_civil_society"] = ngo_score
    
    # --- 2. Campañas de advocacy (Google News RSS como proxy) ---
    gnews_q = requests.utils.quote(f"campaña petición vivienda alquiler España {TODAY.year}")
    gnews_url = f"https://news.google.com/rss/search?q={gnews_q}&hl=es&gl=ES&ceid=ES:es"
    feed_news = feedparser.parse(gnews_url)
    campaign_hits = len([e for e in feed_news.entries[:30]
                         if any(kw in e.get("title","").lower()
                                for kw in ["petición","campaña","manifestación","protesta","plataforma"])])
    campaign_score = clamp(minmax_norm(campaign_hits, 0, 10) * 0.7 + 20)
    sub["advocacy_campaigns"] = campaign_score
    
    # --- 3. Reposicionamiento corporativo ---
    # Proxy: menciones de empresas inmobiliarias + vocabulario de distanciamiento
    gnews_corp = requests.utils.quote("inmobiliaria compromisos regulación alquiler España 2025 2026")
    feed_corp = feedparser.parse(f"https://news.google.com/rss/search?q={gnews_corp}&hl=es&gl=ES&ceid=ES:es")
    corp_keywords = ["se compromete", "anuncia medidas", "nuevo plan", "regulación propia", "autorregulación"]
    corp_hits = sum(1 for e in feed_corp.entries[:20]
                    if any(kw in e.get("title","").lower() + e.get("summary","").lower()
                           for kw in corp_keywords))
    corp_score = clamp(minmax_norm(corp_hits, 0, 8) * 0.6 + 30)
    sub["corporate_repositioning"] = corp_score
    
    # --- 4. Think tanks y academia ---
    thinktank_feeds = [
        "https://www.funcas.es/feed/",
        "https://www.elcano.es/rss/",
        "https://www.cidob.org/rss/",
        "https://www.fedea.net/feed/",
    ]
    tt_hits = 0
    for feed_url in thinktank_feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                text = (entry.get("title","") + entry.get("summary","")).lower()
                if any(kw in text for kw in ["vivienda","alquiler","housing","inmobiliario","registro"]):
                    tt_hits += 1
        except:
            pass
    tt_score = clamp(minmax_norm(tt_hits, 0, 10) * 0.7 + 25)
    sub["think_tank_output"] = tt_score
    
    # --- 5. Actividad legal / litigación ---
    gnews_legal = requests.utils.quote("demanda denuncia recurso vivienda alquiler registro propiedad España")
    feed_legal = feedparser.parse(f"https://news.google.com/rss/search?q={gnews_legal}&hl=es&gl=ES&ceid=ES:es")
    legal_hits = len([e for e in feed_legal.entries[:20]
                      if any(kw in e.get("title","").lower()
                             for kw in ["demanda","denuncia","recurso","sentencia","tribunal","ilegal"])])
    legal_score = clamp(minmax_norm(legal_hits, 0, 8) * 0.7 + 20)
    sub["legal_litigation"] = legal_score
    
    spi_score = clamp(
        0.25 * sub["ngo_civil_society"] +
        0.20 * sub["advocacy_campaigns"] +
        0.20 * sub["corporate_repositioning"] +
        0.20 * sub["think_tank_output"] +
        0.15 * sub["legal_litigation"]
    )
    
    log(f"  SPI = {spi_score}")
    return {"score": spi_score, "sub": sub, "raw": {"ngo_hits": ngo_hits, "campaign_hits": campaign_hits, "legal_hits": legal_hits}}

# ── PILLAR 4: PUBLIC ATTENTION INDEX (PubAI) ─────────────────────────

def collect_pubai(issue):
    """
    Fuente principal: pytrends (Google Trends, sin API key)
    Complemento: Google News RSS como proxy de volumen social
    """
    log(f"PubAI — Consultando Google Trends para '{issue['name']}'...")
    
    sub = {}
    
    # --- 1. Google Trends (pytrends) ---
    try:
        pytrends = TrendReq(hl="es-ES", tz=60, timeout=(10, 25), retries=2, backoff_factor=0.5)
        terms = issue["terms"]["trends"][:5]  # máximo 5 por petición
        pytrends.build_payload(terms, cat=0, timeframe="today 3-m", geo="ES")
        interest = pytrends.interest_over_time()
        
        if not interest.empty:
            # Score = media de las últimas 2 semanas vs media de las 12 semanas
            last_2w = interest.iloc[-2:][terms].mean().mean()
            full_avg = interest[terms].mean().mean()
            # Trend score: si la media reciente es mayor → más riesgo
            trend_ratio = last_2w / max(full_avg, 1)
            search_score = clamp(minmax_norm(last_2w, 0, 100) * 0.6 + minmax_norm(trend_ratio, 0.5, 2.0) * 0.4)
        else:
            search_score = 40
    except Exception as e:
        log(f"  ⚠ pytrends error: {e}")
        search_score = 40
    
    sub["search_intensity"] = clamp(search_score)
    
    # --- 2. Volumen social (proxy: Google News reciente) ---
    gnews_q = requests.utils.quote(" ".join(issue["terms"]["trends"][:2]))
    feed_social = feedparser.parse(
        f"https://news.google.com/rss/search?q={gnews_q}&hl=es&gl=ES&ceid=ES:es"
    )
    social_count = len(feed_social.entries)
    social_score = clamp(minmax_norm(social_count, 0, 30) * 0.7 + 25)
    sub["social_volume"] = social_score
    
    # --- 3. Viralidad / amplificación ---
    # Proxy: artículos repetidos en múltiples fuentes = señal de amplificación
    titles = [e.get("title", "").lower() for e in feed_social.entries[:20]]
    unique_sources = len(set(e.get("source", {}).get("title", "") for e in feed_social.entries[:20]))
    viral_score = clamp(minmax_norm(unique_sources, 1, 15) * 0.6 + 20)
    sub["virality"] = viral_score
    
    # --- 4. Polaridad del discurso ---
    # GDELT tiene un campo de "tone variance" — la usamos como proxy de polaridad
    # Alternativa: comparar volumen de artículos muy positivos vs muy negativos en GDELT
    gdelt_q = requests.utils.quote(issue["terms"]["gdelt"])
    url_tone = (
        f"https://api.gdeltproject.org/api/v2/doc/doc?query={gdelt_q}%20sourcelang:Spanish"
        f"&mode=artlist&maxrecords=100&startdatetime={week_str()}&enddatetime={today_str()}"
        f"&format=json"
    )
    r_tone = safe_get(url_tone)
    polarity_score = 40
    if r_tone:
        try:
            arts = r_tone.json().get("articles", [])
            tones = [a.get("tone", 0) for a in arts if "tone" in a]
            if len(tones) > 3:
                pos = sum(1 for t in tones if t > 2)
                neg = sum(1 for t in tones if t < -2)
                total = len(tones)
                # Alta polaridad = muchos en cada extremo
                polarity_ratio = (pos + neg) / total
                polarity_score = clamp(minmax_norm(polarity_ratio, 0, 0.8) * 0.6 + 25)
        except:
            pass
    sub["public_polarity"] = polarity_score
    
    # --- 5. Concentración geográfica ---
    # Proxy: Google Trends por regiones españolas (Madrid, Barcelona, Valencia = más político)
    geo_score = 45  # default
    try:
        pytrends2 = TrendReq(hl="es-ES", tz=60, timeout=(10, 25), retries=1)
        pytrends2.build_payload([issue["terms"]["trends"][0]], timeframe="today 1-m", geo="ES")
        by_region = pytrends2.interest_by_region(resolution="REGION", inc_low_vol=True)
        if not by_region.empty:
            col = by_region.columns[0]
            political_regions = ["Community of Madrid", "Catalonia", "Valencian Community", "Basque Country"]
            high_attention = by_region[by_region.index.isin(political_regions)][col].mean()
            geo_score = clamp(minmax_norm(high_attention, 0, 100) * 0.6 + 25)
    except Exception as e:
        log(f"  ⚠ geo trends error: {e}")
    sub["geographic_concentration"] = clamp(geo_score)
    
    pubai_score = clamp(
        0.30 * sub["search_intensity"] +
        0.25 * sub["social_volume"] +
        0.20 * sub["virality"] +
        0.15 * sub["public_polarity"] +
        0.10 * sub["geographic_concentration"]
    )
    
    log(f"  PubAI = {pubai_score}")
    return {"score": pubai_score, "sub": sub, "raw": {"search_score": search_score, "social_count": social_count}}

# ── PILLAR 5: NARRATIVE SHIFT INDEX (NSI) ────────────────────────────

def collect_nsi(issue):
    """
    Mide la migración de framing usando GDELT tone + keyword analysis
    sobre los artículos recientes vs. baseline.
    """
    log(f"NSI — Analizando narrativa para '{issue['name']}'...")
    
    sub = {}
    risk_kws   = issue["risk_keywords"]
    neutral_kws = issue["neutral_keywords"]
    
    # --- Recoger artículos recientes ---
    gdelt_q = requests.utils.quote(issue["terms"]["gdelt"])
    url_art = (
        f"https://api.gdeltproject.org/api/v2/doc/doc?query={gdelt_q}%20sourcelang:Spanish"
        f"&mode=artlist&maxrecords=250&startdatetime={week_str()}&enddatetime={today_str()}"
        f"&sort=DateDesc&format=json"
    )
    r = safe_get(url_art)
    articles = []
    if r:
        try:
            articles = r.json().get("articles", [])
        except:
            pass
    
    all_text = " ".join([
        a.get("title", "") + " " + a.get("url", "")
        for a in articles
    ]).lower()
    
    # --- 1. Keyword Emergence Score ---
    risk_count    = sum(all_text.count(kw) for kw in risk_kws)
    neutral_count = sum(all_text.count(kw) for kw in neutral_kws)
    total_kw = risk_count + neutral_count
    if total_kw > 0:
        risk_ratio = risk_count / total_kw
        kw_score = clamp(minmax_norm(risk_ratio, 0, 0.8) * 0.7 + 20)
    else:
        kw_score = 40
    sub["keyword_emergence"] = kw_score
    
    # --- 2. Framing Migration Index ---
    # Vocabulario moral/crisis vs. técnico
    moral_frames   = ["derecho fundamental","derecho humano","emergencia","crisis","dignidad","exclusión","víctima","injusticia","desahucio"]
    technical_frames = ["reglamento","directiva","transposición","propuesta","consulta","borrador","subsidiariedad","informe técnico"]
    
    moral_count = sum(all_text.count(kw) for kw in moral_frames)
    tech_count  = sum(all_text.count(kw) for kw in technical_frames)
    
    if moral_count + tech_count > 0:
        moral_ratio = moral_count / (moral_count + tech_count)
        frame_score = clamp(minmax_norm(moral_ratio, 0, 0.8) * 0.7 + 20)
    else:
        frame_score = 40
    sub["framing_migration"] = frame_score
    
    # --- 3. Metáforas y analogías ---
    analogy_kws = [
        "escándalo","burbuja","colapso","tipping point","punto de inflexión",
        "como en 2008","speculación","expulsión","gentrificación","turistificación"
    ]
    analogy_count = sum(all_text.count(kw) for kw in analogy_kws)
    analogy_score = clamp(minmax_norm(analogy_count, 0, 20) * 0.7 + 20)
    sub["metaphor_tracking"] = analogy_score
    
    # --- 4. Coalición narrativa (convergencia de fuentes) ---
    # Si ONGs, sindicatos Y medios mainstream usan el mismo lenguaje → coalición
    # Proxy: diversidad de dominios con keywords de riesgo
    risk_domains = set()
    for a in articles:
        url = a.get("url", "")
        title = a.get("title", "").lower()
        if any(kw in title for kw in risk_kws[:5]):
            try:
                domain = url.split("/")[2]
                risk_domains.add(domain)
            except:
                pass
    coalition_score = clamp(minmax_norm(len(risk_domains), 0, 20) * 0.7 + 20)
    sub["narrative_coalition"] = coalition_score
    
    # --- 5. Resiliencia del contra-relato ---
    # Keywords positivos o defensivos de los actores protagonistas
    positive_frames = [
        "seguridad jurídica","inversión","oferta","construcción","simplificación",
        "datos positivos","mejora","solución","acuerdo","diálogo","consenso"
    ]
    positive_count = sum(all_text.count(kw) for kw in positive_frames)
    # Alto número de keywords positivos → contra-narrativa fuerte → menor riesgo NSI
    # Invertimos: más positivos = menor score NSI (50 - ratio)
    counter_strength = minmax_norm(positive_count, 0, 30)
    counter_score = clamp(100 - counter_strength * 0.5)
    sub["counter_narrative"] = clamp(counter_score)
    
    nsi_score = clamp(
        0.25 * sub["keyword_emergence"] +
        0.25 * sub["framing_migration"] +
        0.20 * sub["metaphor_tracking"] +
        0.20 * sub["narrative_coalition"] +
        0.10 * sub["counter_narrative"]
    )
    
    log(f"  NSI = {nsi_score}")
    return {"score": nsi_score, "sub": sub, "raw": {"risk_kw_count": risk_count, "moral_count": moral_count, "coalition_domains": len(risk_domains)}}

# ── COMPUTE COMPOSITE PARI ────────────────────────────────────────────

WEIGHTS = {"mai": 0.20, "pai": 0.30, "spi": 0.20, "pubai": 0.15, "nsi": 0.15}

def compute_pari(pillar_scores):
    return clamp(sum(WEIGHTS[k] * v for k, v in pillar_scores.items()))

def get_risk_level(score):
    if score <= 20:  return ("Mínimo",   "#16A34A")
    if score <= 40:  return ("Bajo",     "#65A30D")
    if score <= 60:  return ("Moderado", "#CA8A04")
    if score <= 75:  return ("Elevado",  "#EA580C")
    if score <= 90:  return ("Alto",     "#DC2626")
    return            ("Crítico",  "#9333EA")

# ── DATE HELPERS ──────────────────────────────────────────────────────

def today_str():
    return TODAY.strftime("%Y%m%d%H%M%S")

def week_str():
    return (TODAY - datetime.timedelta(days=7)).strftime("%Y%m%d%H%M%S")

def month_str():
    return (TODAY - datetime.timedelta(days=30)).strftime("%Y%m%d")

# ── MAIN RUN ─────────────────────────────────────────────────────────

def run_issue(issue):
    log(f"\n{'='*55}")
    log(f"Procesando: {issue['name']}")
    log(f"{'='*55}")
    
    mai   = collect_mai(issue)
    pai   = collect_pai(issue)
    spi   = collect_spi(issue)
    pubai = collect_pubai(issue)
    nsi   = collect_nsi(issue)
    
    pillar_scores = {
        "mai":   mai["score"],
        "pai":   pai["score"],
        "spi":   spi["score"],
        "pubai": pubai["score"],
        "nsi":   nsi["score"],
    }
    pari = compute_pari(pillar_scores)
    risk_label, risk_color = get_risk_level(pari)
    
    # Velocity: diferencia vs. día anterior (si existe)
    velocity = compute_velocity(issue["id"], pari)
    
    result = {
        "issue_id":     issue["id"],
        "issue_name":   issue["name"],
        "date":         DATE_STR,
        "pari":         pari,
        "risk_level":   risk_label,
        "risk_color":   risk_color,
        "velocity":     velocity,
        "pillar_scores": pillar_scores,
        "pillar_detail": {
            "mai":   mai,
            "pai":   pai,
            "spi":   spi,
            "pubai": pubai,
            "nsi":   nsi,
        },
        "weights": WEIGHTS,
        "contributions": {k: round(WEIGHTS[k] * v, 1) for k, v in pillar_scores.items()},
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    
    log(f"\n✅ PARI = {pari} [{risk_label}]  Velocity: {velocity:+d}")
    return result

def compute_velocity(issue_id, current_pari):
    """Calcula Δ respecto al último score guardado."""
    history_file = DATA_DIR / f"{issue_id}_history.json"
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text())
            if history:
                last = history[-1]["pari"]
                return current_pari - last
        except:
            pass
    return 0

def save_result(result):
    issue_id = result["issue_id"]
    
    # Guarda el resultado de hoy
    today_file = DATA_DIR / f"{issue_id}_{DATE_STR}.json"
    today_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Actualiza el archivo "latest" (lo lee el HTML)
    latest_file = DATA_DIR / f"{issue_id}_latest.json"
    latest_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Actualiza el historial (últimos 90 días)
    history_file = DATA_DIR / f"{issue_id}_history.json"
    history = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text())
        except:
            history = []
    
    # Añade entrada compacta al historial
    history_entry = {
        "date":      DATE_STR,
        "pari":      result["pari"],
        "risk":      result["risk_level"],
        "velocity":  result["velocity"],
        "mai":       result["pillar_scores"]["mai"],
        "pai":       result["pillar_scores"]["pai"],
        "spi":       result["pillar_scores"]["spi"],
        "pubai":     result["pillar_scores"]["pubai"],
        "nsi":       result["pillar_scores"]["nsi"],
    }
    # Evita duplicados del mismo día
    history = [h for h in history if h["date"] != DATE_STR]
    history.append(history_entry)
    # Mantiene solo 90 días
    history = sorted(history, key=lambda x: x["date"])[-90:]
    history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False))
    
    log(f"  💾 Guardado: {today_file.name}")

def generate_summary():
    """Genera un resumen JSON con todos los issues (para el dashboard)."""
    summary = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "date": DATE_STR,
        "issues": []
    }
    for issue in ISSUES:
        latest_file = DATA_DIR / f"{issue['id']}_latest.json"
        if latest_file.exists():
            try:
                data = json.loads(latest_file.read_text())
                summary["issues"].append({
                    "id":          data["issue_id"],
                    "name":        data["issue_name"],
                    "date":        data["date"],
                    "pari":        data["pari"],
                    "risk_level":  data["risk_level"],
                    "risk_color":  data["risk_color"],
                    "velocity":    data["velocity"],
                    "scores":      data["pillar_scores"],
                })
            except:
                pass
    
    summary_file = DATA_DIR / "summary.json"
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    log(f"\n📊 Summary guardado con {len(summary['issues'])} issues.")

if __name__ == "__main__":
    log("🚀 PARI Spain — Iniciando recolección de datos")
    log(f"   Fecha: {DATE_STR}")
    log(f"   Issues: {[i['id'] for i in ISSUES]}\n")
    
    for issue in ISSUES:
        try:
            result = run_issue(issue)
            save_result(result)
        except Exception as e:
            log(f"❌ Error en issue {issue['id']}: {e}")
            import traceback
            traceback.print_exc()
    
    generate_summary()
    log("\n✅ Recolección completada")
