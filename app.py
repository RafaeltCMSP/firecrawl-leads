"""Dashboard de prospeccao multi-nicho / multi-regiao.

Rodar:  streamlit run app.py
"""
import pandas as pd
import streamlit as st

import config
from src import db
from src.chatwoot_client import ChatwootClient
from src.firecrawl_client import FirecrawlClient
from src.minimax_client import MiniMaxClient
from src.pipeline import (LOCATION_SUGGESTIONS, NICHE_SUGGESTIONS,
                          process_candidate, search_candidates)

st.set_page_config(page_title="Prospeccao de Leads", page_icon="🎯", layout="wide")

db.init_db()
if "leads" not in st.session_state:
    st.session_state.leads = {l.url: l for l in db.all_leads()}
if "logs" not in st.session_state:
    st.session_state.logs = []


def log(msg):
    st.session_state.logs.append(msg)


# ----------------------------- Sidebar -----------------------------
with st.sidebar:
    st.header("⚙️ Conexoes")
    st.write(f"**Firecrawl:** {'🟢' if config.FIRECRAWL_BASE_URL else '🔴'}")
    st.caption(config.FIRECRAWL_BASE_URL or "-")
    mm_ok = config.minimax_enabled()
    st.write(f"**MiniMax:** {'🟢 ativo' if mm_ok else '🟡 desativado'}")
    cw_ok = config.chatwoot_enabled()
    st.write(f"**Chatwoot:** {'🟢' if cw_ok else '🟡 desativado'}")
    if st.button("Testar conexoes"):
        ok, msg = FirecrawlClient().ping()
        st.write(f"Firecrawl: {'🟢' if ok else '🔴'} {msg}")
        if cw_ok:
            ok2, msg2 = ChatwootClient().ping()
            st.write(f"Chatwoot: {'🟢' if ok2 else '🔴'} {msg2}")

    st.divider()
    st.header("🎯 Prospeccao")

    niche = st.text_input("Nicho", value=config.DEFAULT_NICHE,
                          help="Qualquer segmento. Ex: clinica odontologica, academia, restaurante...")
    with st.expander("Sugestoes de nicho"):
        st.caption(" · ".join(NICHE_SUGGESTIONS))

    st.markdown("**Localidades** (uma por linha)")
    locations_text = st.text_area(
        "locais", value="Sao Paulo SP", label_visibility="collapsed",
        help="Cidade, bairro+cidade, estado... Ex: Tatuape Sao Paulo / Campinas SP / Rio de Janeiro RJ")
    add_loc = st.multiselect("Adicionar cidades comuns", LOCATION_SUGGESTIONS, default=[])
    locations = [l.strip() for l in locations_text.splitlines() if l.strip()] + add_loc
    locations = list(dict.fromkeys(locations))  # dedup preservando ordem

    limit = st.slider("Resultados por busca", 3, 20, 8)
    variations = st.checkbox("Variacoes de busca (mais alcance)", value=True)
    skip_portals = st.checkbox("Ignorar portais/agregadores", value=True)
    deep_enrich = st.checkbox("Enriquecer (buscar redes/Google)", value=True)
    use_mm = st.checkbox("Analise MiniMax", value=mm_ok, disabled=not mm_ok)
    skip_existing = st.checkbox("Pular URLs ja processadas", value=True)

    run = st.button("🚀 Rodar prospeccao", type="primary", use_container_width=True)
    st.caption(f"Oferta da agencia: _{config.AGENCY_OFFER}_")


# ----------------------------- Execucao -----------------------------
st.title("🎯 Prospeccao de Leads")
st.caption("Multi-nicho e multi-regiao · Firecrawl + MiniMax · analise de site, redes, Google e anuncios.")

if run:
    if not niche.strip():
        st.warning("Informe um nicho.")
    elif not locations:
        st.warning("Informe ao menos uma localidade.")
    else:
        st.session_state.logs = []
        fc = FirecrawlClient()
        mm = MiniMaxClient() if (use_mm and config.minimax_enabled()) else None
        with st.status("Buscando candidatos...", expanded=True) as status:
            cands = search_candidates(niche, locations, limit, variations, fc,
                                      skip_portals=skip_portals, on_log=log)
            st.write(f"Encontrados {len(cands)} sites unicos.")
            if skip_existing:
                cands = [c for c in cands if c["url"] not in st.session_state.leads]
                st.write(f"{len(cands)} novos para processar.")
            total = len(cands)
            bar = st.progress(0.0)
            for i, c in enumerate(cands, start=1):
                st.write(f"[{i}/{total}] {c['url']}")
                lead = process_candidate(c, fc, mm, use_minimax=(mm is not None),
                                         deep_enrich=deep_enrich, on_log=log)
                st.session_state.leads[lead.url] = lead
                bar.progress(i / total if total else 1.0)
            status.update(label=f"Concluido: {total} sites processados.", state="complete")


# ----------------------------- Resultados -----------------------------
leads = list(st.session_state.leads.values())

if not leads:
    st.info("Nenhum lead ainda. Configure nicho e localidades na barra lateral e clique em **Rodar prospeccao**.")
else:
    bons = [l for l in leads if l.is_good_lead]
    quentes = [l for l in leads if l.lead_temp == "quente"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", len(leads))
    c2.metric("Bons leads", len(bons))
    c3.metric("Quentes", len(quentes))
    c4.metric("Descartados", len([l for l in leads if l.status == "descartado"]))

    st.divider()
    fa, fb, fc_, fd = st.columns([1, 1, 1, 1])
    only_good = fa.checkbox("So bons leads", value=True, help="Nao rodam anuncio e da pra contatar")
    only_hot = fb.checkbox("So quentes", value=False)
    min_opp = fc_.slider("Opp-score min", 0, 100, 0)
    niche_filter = fd.text_input("Filtrar nicho", "")

    view = leads
    if only_good:
        view = [l for l in view if l.is_good_lead]
    if only_hot:
        view = [l for l in view if l.lead_temp == "quente"]
    view = [l for l in view if l.opportunity_score >= min_opp]
    if niche_filter.strip():
        nf = niche_filter.lower()
        view = [l for l in view if nf in (l.niche or "").lower()]
    view.sort(key=lambda l: (l.opportunity_score, -l.quality_score), reverse=True)

    df = pd.DataFrame([{
        "Nome": l.name or l.domain,
        "Nicho": l.niche,
        "Local": l.location,
        "Opp": l.opportunity_score,
        "Temp": l.lead_temp,
        "Anuncios": l.ad_pixels or "nao",
        "Redes": l.social_count,
        "Google": "sim" if l.has_maps else "nao",
        "Mobile": "sim" if l.is_mobile else "nao",
        "WhatsApp": l.whatsapp,
        "Telefone": l.phone,
        "Email": l.email,
        "Status": l.status,
        "URL": l.url,
    } for l in view])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Exportar CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="leads.csv", mime="text/csv")

    st.divider()
    st.subheader("📇 Detalhe e acoes por lead")
    cw_enabled = config.chatwoot_enabled()
    for l in view:
        header = f"{'🔥' if l.lead_temp == 'quente' else '•'} {l.name or l.domain} — opp {l.opportunity_score} · {l.niche} · {l.location}"
        with st.expander(header):
            left, right = st.columns([2, 1])
            with left:
                st.markdown(f"**Site:** [{l.url}]({l.url})")
                if l.site_quality:
                    st.markdown(f"**Parecer:** {l.site_quality}")
                if l.weaknesses:
                    st.markdown(f"**Pontos fracos:** {l.weaknesses}")
                if l.missing_channels:
                    st.markdown(f"**Canais faltando:** {l.missing_channels}")
                if l.pitch_angle:
                    st.info(f"💡 Gancho: {l.pitch_angle}")
                st.markdown(
                    f"**Anuncios:** {l.ad_pixels or 'nenhum'} | **Analytics:** {l.analytics or 'nenhum'} | "
                    f"**CMS:** {l.cms} | **Mobile:** {'sim' if l.is_mobile else 'nao'} | "
                    f"**HTTPS:** {'sim' if l.is_https else 'nao'}"
                )
                socials = l.socials_list
                if socials:
                    st.markdown("**Redes:** " + " · ".join(f"[{n}]({u})" for n, u in socials))
                else:
                    st.markdown("**Redes:** _nenhuma encontrada_")
                if l.google_business:
                    st.markdown(f"**Google/Maps:** [{l.google_business}]({l.google_business})")
                st.markdown(f"**Contato:** {l.whatsapp or '-'} / {l.phone or '-'} / {l.email or '-'}")
                msg = st.text_area("Abordagem WhatsApp", l.outreach, key=f"wa_{l.url}", height=110)
                if l.outreach_email:
                    st.text_area("Abordagem E-mail", l.outreach_email, key=f"em_{l.url}", height=140)
            with right:
                st.metric("Opp-score", l.opportunity_score)
                st.metric("Qualidade (MiniMax)", l.quality_score)
                st.write(f"Status: **{l.status}**")
                if l.chatwoot_id:
                    st.success(f"Chatwoot #{l.chatwoot_id}")
                if cw_enabled and st.button("➡️ Enviar pro Chatwoot", key=f"cw_{l.url}"):
                    try:
                        l.outreach = msg
                        payload = ChatwootClient().create_contact(l)
                        cid = ChatwootClient.extract_id(payload)
                        l.chatwoot_id = cid
                        l.status = "enviado_chatwoot"
                        db.upsert(l)
                        st.session_state.leads[l.url] = l
                        st.success(f"Enviado! Contato #{cid}")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Falha no Chatwoot: {e}")
                elif not cw_enabled:
                    st.caption("Configure o Chatwoot no .env.")

if st.session_state.logs:
    with st.expander("📝 Logs da ultima execucao"):
        st.code("\n".join(st.session_state.logs[-200:]))
