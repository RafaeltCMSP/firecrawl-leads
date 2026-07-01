"""Dashboard de prospeccao multi-nicho / multi-regiao.

Rodar:  streamlit run app.py
"""
import json

import pandas as pd
import streamlit as st

import config
from src import db
from src.chatwoot_client import ChatwootClient
from src.firecrawl_client import FirecrawlClient
from src.minimax_client import (DEFAULT_OBJECTIVE, PITCH_BLOCKS,
                                 PITCH_OBJECTIVES, MiniMaxClient)
from src.pipeline import (LOCATION_SUGGESTIONS, NICHE_SUGGESTIONS, build_pitch,
                          format_pitch_message, process_candidate,
                          search_candidates)

st.set_page_config(page_title="Prospeccao de Leads", page_icon="🎯", layout="wide")

db.init_db()

# --- Configuracoes de conexao (editaveis em runtime, default = .env / secrets) ---
DEFAULT_SETTINGS = {
    "FIRECRAWL_BASE_URL": config.FIRECRAWL_BASE_URL,
    "FIRECRAWL_API_KEY": config.FIRECRAWL_API_KEY,
    "MINIMAX_API_KEY": config.MINIMAX_API_KEY,
    "MINIMAX_BASE_URL": config.MINIMAX_BASE_URL,
    "MINIMAX_MODEL": config.MINIMAX_MODEL,
    "MINIMAX_GROUP_ID": config.MINIMAX_GROUP_ID,
    "CHATWOOT_BASE_URL": config.CHATWOOT_BASE_URL,
    "CHATWOOT_API_TOKEN": config.CHATWOOT_API_TOKEN,
    "CHATWOOT_ACCOUNT_ID": config.CHATWOOT_ACCOUNT_ID,
    "CHATWOOT_INBOX_ID": config.CHATWOOT_INBOX_ID,
    "AGENCY_OFFER": config.AGENCY_OFFER,
    "DEFAULT_NICHE": config.DEFAULT_NICHE,
}
if "settings" not in st.session_state:
    st.session_state.settings = dict(DEFAULT_SETTINGS)
if "leads" not in st.session_state:
    st.session_state.leads = {l.url: l for l in db.all_leads()}
if "logs" not in st.session_state:
    st.session_state.logs = []


def S():
    return st.session_state.settings


def log(msg):
    st.session_state.logs.append(msg)


def mm_ready():
    k = S()["MINIMAX_API_KEY"]
    return bool(k and "coloque" not in k.lower())


def cw_ready():
    s = S()
    return bool(s["CHATWOOT_BASE_URL"] and s["CHATWOOT_API_TOKEN"] and s["CHATWOOT_ACCOUNT_ID"])


def make_fc():
    s = S()
    return FirecrawlClient(base_url=s["FIRECRAWL_BASE_URL"], api_key=s["FIRECRAWL_API_KEY"])


def make_mm():
    s = S()
    return MiniMaxClient(api_key=s["MINIMAX_API_KEY"], base_url=s["MINIMAX_BASE_URL"],
                         model=s["MINIMAX_MODEL"], group_id=s["MINIMAX_GROUP_ID"],
                         offer=s["AGENCY_OFFER"])


def make_cw():
    s = S()
    return ChatwootClient(base_url=s["CHATWOOT_BASE_URL"], token=s["CHATWOOT_API_TOKEN"],
                          account_id=s["CHATWOOT_ACCOUNT_ID"], inbox_id=s["CHATWOOT_INBOX_ID"])


# Emojis por bloco, para deixar as dicas mais visuais na UI
BLOCK_ICONS = {
    "gancho_inicial": "🎣", "concorrencia": "🏘️", "realidade_dele": "🎯",
    "beneficios": "📈", "dor_principal": "💬", "manter_contato": "🔁",
}


def render_tips(l):
    """Renderiza as dicas de abordagem de um lead + controles de (re)geracao."""
    st.markdown("**🧠 Dicas de abordagem (MiniMax)**")
    tips = l.tips_dict
    if not mm_ready():
        st.caption("Ative o MiniMax em Configuracoes para gerar dicas.")
        return
    if tips:
        for key, label in PITCH_BLOCKS:
            val = (tips.get(key) or "").strip()
            if val:
                st.markdown(f"{BLOCK_ICONS.get(key, '•')} **{label}:** {val}")
        if l.pitch_objetivo:
            st.caption(f"Objetivo: {l.pitch_objetivo}")
        st.text_area("Mensagem pronta (copiar)", format_pitch_message(tips),
                     key=f"tipmsg_{l.url}", height=140)
    else:
        st.caption("Nenhuma dica gerada ainda. Escolha um objetivo e gere abaixo.")

    with st.form(f"tipform_{l.url}"):
        obj_default = l.pitch_objetivo if l.pitch_objetivo in PITCH_OBJECTIVES else DEFAULT_OBJECTIVE
        obj = st.selectbox("Objetivo", PITCH_OBJECTIVES,
                           index=PITCH_OBJECTIVES.index(obj_default), key=f"tipobj_{l.url}")
        ctx = st.text_area(
            "Contexto (opcional)", l.pitch_contexto, key=f"tipctx_{l.url}", height=70,
            help="Ex.: 'ele comentou que o orcamento esta apertado', 'tem sauna e "
                 "area gourmet', 'ja falei com ele mes passado'...")
        gerar = st.form_submit_button(
            "✨ Gerar novas dicas" if tips else "✨ Gerar dicas", type="primary")
    if gerar:
        with st.spinner("Gerando dicas..."):
            try:
                data = build_pitch(l, make_mm(), objetivo=obj, contexto=ctx)
                if data:
                    db.upsert(l)
                    st.session_state.leads[l.url] = l
                    st.success("Dicas geradas!")
                    st.rerun()
                else:
                    st.error("O MiniMax nao retornou dicas. Tente novamente.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Falha ao gerar dicas: {e}")


# ----------------------------- Sidebar -----------------------------
with st.sidebar:
    st.header("⚙️ Conexoes")
    st.write(f"**Firecrawl:** {'🟢' if S()['FIRECRAWL_BASE_URL'] else '🔴'}")
    st.caption(S()["FIRECRAWL_BASE_URL"] or "-")
    st.write(f"**MiniMax:** {'🟢 ativo' if mm_ready() else '🟡 desativado'}")
    st.write(f"**Chatwoot:** {'🟢' if cw_ready() else '🟡 desativado'}")
    if st.button("Testar conexoes"):
        ok, msg = make_fc().ping()
        st.write(f"Firecrawl: {'🟢' if ok else '🔴'} {msg}")
        if cw_ready():
            ok2, msg2 = make_cw().ping()
            st.write(f"Chatwoot: {'🟢' if ok2 else '🔴'} {msg2}")

    st.divider()
    st.header("🎯 Prospeccao")
    niche = st.text_input("Nicho", value=S()["DEFAULT_NICHE"],
                          help="Qualquer segmento. Ex: clinica odontologica, academia, restaurante...")
    with st.expander("Sugestoes de nicho"):
        st.caption(" · ".join(NICHE_SUGGESTIONS))
    st.markdown("**Localidades** (uma por linha)")
    locations_text = st.text_area(
        "locais", value="Sao Paulo SP", label_visibility="collapsed",
        help="Cidade, bairro+cidade, estado... Ex: Tatuape Sao Paulo / Campinas SP / Rio de Janeiro RJ")
    add_loc = st.multiselect("Adicionar cidades comuns", LOCATION_SUGGESTIONS, default=[])
    locations = [l.strip() for l in locations_text.splitlines() if l.strip()] + add_loc
    locations = list(dict.fromkeys(locations))

    limit = st.slider("Resultados por busca", 3, 20, 8)
    variations = st.checkbox("Variacoes de busca (mais alcance)", value=True)
    skip_portals = st.checkbox("Ignorar portais/agregadores", value=True)
    deep_enrich = st.checkbox("Enriquecer (buscar redes/Google)", value=True)
    use_mm = st.checkbox("Analise MiniMax", value=mm_ready(), disabled=not mm_ready())
    gen_tips = st.checkbox(
        "Gerar dicas de abordagem", value=mm_ready(), disabled=not mm_ready(),
        help="Cria automaticamente as dicas estruturadas (gancho, concorrencia, "
             "beneficios...) para cada bom lead ja na captura. Usa o MiniMax.")
    tips_objetivo = st.selectbox(
        "Objetivo das dicas (captura)", PITCH_OBJECTIVES, index=0,
        disabled=not (mm_ready() and gen_tips),
        help="Rumo padrao das dicas geradas na prospeccao. Voce pode regerar por "
             "lead depois, com outro objetivo e contexto.")
    skip_existing = st.checkbox("Pular URLs ja processadas", value=True)
    run = st.button("🚀 Rodar prospeccao", type="primary", use_container_width=True)


# ----------------------------- Header + Configuracoes -----------------------------
st.title("🎯 Prospeccao de Leads")
st.caption("Multi-nicho e multi-regiao · Firecrawl + MiniMax · analise de site, redes, Google e anuncios.")

with st.expander("⚙️ Configuracoes de conexao (Firecrawl · MiniMax · Chatwoot)", expanded=not mm_ready()):
    st.caption("Os valores valem para esta sessao e tem prioridade sobre o .env/Secrets. "
               "As chaves nao sao salvas em disco.")
    with st.form("cfg_form"):
        st.markdown("**Firecrawl**")
        fb = st.text_input("Base URL", S()["FIRECRAWL_BASE_URL"])
        fk = st.text_input("API Key (opcional)", S()["FIRECRAWL_API_KEY"], type="password")

        st.markdown("**MiniMax**")
        mk = st.text_input("API Key", S()["MINIMAX_API_KEY"], type="password")
        m1, m2, m3 = st.columns(3)
        mb = m1.text_input("Base URL", S()["MINIMAX_BASE_URL"])
        mdl = m2.text_input("Model", S()["MINIMAX_MODEL"])
        mg = m3.text_input("Group ID (opcional)", S()["MINIMAX_GROUP_ID"])
        offer = st.text_input("O que sua agencia vende (personaliza a abordagem)", S()["AGENCY_OFFER"])

        st.markdown("**Chatwoot (opcional)**")
        w1, w2 = st.columns(2)
        cb = w1.text_input("Base URL", S()["CHATWOOT_BASE_URL"])
        ct = w2.text_input("API Token", S()["CHATWOOT_API_TOKEN"], type="password")
        w3, w4 = st.columns(2)
        ca = w3.text_input("Account ID", S()["CHATWOOT_ACCOUNT_ID"])
        ci = w4.text_input("Inbox ID", S()["CHATWOOT_INBOX_ID"])

        if st.form_submit_button("💾 Salvar configuracoes", type="primary"):
            S().update({
                "FIRECRAWL_BASE_URL": fb.strip().rstrip("/"), "FIRECRAWL_API_KEY": fk.strip(),
                "MINIMAX_API_KEY": mk.strip(), "MINIMAX_BASE_URL": mb.strip().rstrip("/"),
                "MINIMAX_MODEL": mdl.strip(), "MINIMAX_GROUP_ID": mg.strip(),
                "AGENCY_OFFER": offer.strip(),
                "CHATWOOT_BASE_URL": cb.strip().rstrip("/"), "CHATWOOT_API_TOKEN": ct.strip(),
                "CHATWOOT_ACCOUNT_ID": ca.strip(), "CHATWOOT_INBOX_ID": ci.strip(),
            })
            st.success("Configuracoes atualizadas para esta sessao.")
            st.rerun()

with st.expander("💾 Backup / Restaurar dados (JSON)"):
    st.caption("Exporte todos os leads num arquivo JSON e reimporte depois (apos atualizar "
               "a ferramenta ou se a base for resetada). As URLs restauradas voltam a ser "
               "puladas nas proximas prospeccoes com 'Pular URLs ja processadas' ativo.")
    bcol1, bcol2 = st.columns(2)
    with bcol1:
        st.markdown("**Exportar**")
        total_leads = len(st.session_state.leads)
        st.download_button(
            f"⬇️ Baixar backup ({total_leads} leads)",
            data=db.export_json().encode("utf-8"),
            file_name="leads_backup.json",
            mime="application/json",
            use_container_width=True,
            disabled=total_leads == 0,
        )
    with bcol2:
        st.markdown("**Importar**")
        overwrite = st.radio(
            "Se a URL ja existir na base:",
            ["Manter o existente", "Substituir pelo importado"],
            index=0,
        ) == "Substituir pelo importado"
        up = st.file_uploader("Arquivo JSON de backup", type=["json"], key="import_json")
        if up is not None and st.button("📥 Importar agora", use_container_width=True):
            try:
                data = json.loads(up.getvalue().decode("utf-8"))
                res = db.import_leads(data, overwrite=overwrite)
                st.session_state.leads = {l.url: l for l in db.all_leads()}
                msg = (f"Importado: {res['added']} novos · {res['updated']} atualizados · "
                       f"{res['skipped']} mantidos. Total na base: {len(st.session_state.leads)}.")
                if res["invalid"]:
                    msg += f" ({res['invalid']} registros ignorados por estarem invalidos.)"
                st.success(msg)
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Falha ao importar: {e}")


# ----------------------------- Execucao -----------------------------
if run:
    if not niche.strip():
        st.warning("Informe um nicho.")
    elif not locations:
        st.warning("Informe ao menos uma localidade.")
    elif not S()["FIRECRAWL_BASE_URL"]:
        st.error("Configure a URL do Firecrawl em Configuracoes de conexao.")
    else:
        st.session_state.logs = []
        fc = make_fc()
        mm = make_mm() if (use_mm and mm_ready()) else None
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
                                         deep_enrich=deep_enrich,
                                         generate_tips=(gen_tips and mm is not None),
                                         tips_objetivo=tips_objetivo, on_log=log)
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
    fa, fb2, fc2, fd = st.columns([1, 1, 1, 1])
    only_good = fa.checkbox("So bons leads", value=True, help="Nao rodam anuncio e da pra contatar")
    only_hot = fb2.checkbox("So quentes", value=False)
    min_opp = fc2.slider("Opp-score min", 0, 100, 0)
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
        "Nome": l.name or l.domain, "Nicho": l.niche, "Local": l.location,
        "Opp": l.opportunity_score, "Temp": l.lead_temp,
        "Anuncios": l.ad_pixels or "nao", "Redes": l.social_count,
        "Google": "sim" if l.has_maps else "nao", "Mobile": "sim" if l.is_mobile else "nao",
        "WhatsApp": l.whatsapp, "Telefone": l.phone, "Email": l.email,
        "Status": l.status, "URL": l.url,
    } for l in view])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Exportar CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="leads.csv", mime="text/csv")

    st.divider()
    st.subheader("📇 Detalhe e acoes por lead")
    cw_enabled = cw_ready()
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
                st.divider()
                render_tips(l)
            with right:
                st.metric("Opp-score", l.opportunity_score)
                st.metric("Qualidade (MiniMax)", l.quality_score)
                st.write(f"Status: **{l.status}**")
                if l.chatwoot_id:
                    st.success(f"Chatwoot #{l.chatwoot_id}")
                if cw_enabled and st.button("➡️ Enviar pro Chatwoot", key=f"cw_{l.url}"):
                    try:
                        l.outreach = msg
                        payload = make_cw().create_contact(l)
                        cid = ChatwootClient.extract_id(payload)
                        l.chatwoot_id = cid
                        l.status = "enviado_chatwoot"
                        db.upsert(l)
                        st.session_state.leads[l.url] = l
                        st.success(f"Enviado! Contato #{cid}")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Falha no Chatwoot: {e}")
                elif not cw_enabled:
                    st.caption("Configure o Chatwoot em Configuracoes.")

if st.session_state.logs:
    with st.expander("📝 Logs da ultima execucao"):
        st.code("\n".join(st.session_state.logs[-200:]))
