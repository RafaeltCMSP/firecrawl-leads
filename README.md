# 🎯 Prospeccao de Leads — Firecrawl + MiniMax

Ferramenta de **geracao e qualificacao de leads B2B** para agencias que vendem
gestao de trafego, anuncios e presenca digital. Ela busca negocios na web (de
**qualquer nicho** e **qualquer regiao**), analisa o site de cada um e identifica
quem tem **presenca digital fraca** e **nao investe em anuncios** — ou seja, os
melhores prospects para abordar. Para cada lead, gera um **parecer**, um **score
de oportunidade** e **mensagens de abordagem prontas** (WhatsApp + e-mail).

> Stack: **Streamlit** (UI) · **Firecrawl** self-hosted (busca + scraping) ·
> **MiniMax** (analise e copywriting) · **SQLite** (persistencia) ·
> **Chatwoot** (CRM, opcional).

---

## 📑 Indice

- [Como funciona](#-como-funciona)
- [Recursos](#-recursos)
- [O que e analisado em cada site](#-o-que-e-analisado-em-cada-site)
- [Score de oportunidade](#-score-de-oportunidade)
- [Instalacao local](#-instalacao-local-windows--powershell)
- [Configuracao (.env)](#-configuracao-env)
- [Uso](#-uso)
- [Deploy no Streamlit Cloud](#-deploy-no-streamlit-cloud)
- [Integracao com Chatwoot](#-integracao-com-chatwoot-opcional)
- [Estrutura do projeto](#-estrutura-do-projeto)
- [Solucao de problemas](#-solucao-de-problemas)
- [Roadmap](#-roadmap)

---

## 🔁 Como funciona

```
1. BUSCAR     Firecrawl /search  "<nicho> <localidade>" (+ variacoes)   -> URLs
2. FILTRAR    descarta portais/diretorios/listas (zap, OLX, guias...)
3. RASPAR     Firecrawl /scrape  (rawHtml + markdown)                    -> conteudo
4. DETECTAR   regex: anuncios, analytics, CMS, mobile, https, redes,     -> sinais
              Google Meu Negocio, contatos                               -> opp-score
5. ENRIQUECER (opcional) busca extra pelo nome para achar redes/Google
6. ANALISAR   MiniMax: parecer, pontos fracos, canais faltando, temp,    -> analise +
              gancho de venda, copy de WhatsApp e e-mail                    abordagens
7. SALVAR     SQLite (dedup por URL) + Chatwoot (opcional)
```

**Regra de ouro:** quem **tem** pixel de anuncio (Google Ads / Meta Pixel) ja
investe em midia → prospect fraco. Quem **nao tem** e ainda tem site/presenca
fraca → prospect quente.

---

## ✨ Recursos

- **Multi-nicho**: campo livre (imobiliaria, clinica, academia, restaurante,
  advocacia, pet shop, estetica...). Nada e fixo.
- **Multi-regiao**: uma ou varias localidades por execucao (bairro, cidade, estado).
- **Variacoes de busca** para ampliar o alcance dos resultados.
- **Filtro inteligente** de portais, agregadores e paginas de "lista/ranking".
- **Deteccao tecnica ampla** (ver secao abaixo).
- **Enriquecimento opcional**: quando o site nao linka redes/Google, faz uma busca
  extra para encontrar.
- **MiniMax** gera parecer, pontos fracos, canais faltando, gancho de venda e
  **copy de abordagem humanizada** (WhatsApp + e-mail), seguindo regras de
  copywriting (cita algo concreto do negocio, sem cliche de agencia).
- **Score de oportunidade (0-100)** + classificacao quente/morno/frio.
- **Persistencia + dedup**: nao reprocessa a mesma URL.
- **Filtros e tabela** interativos, **export CSV** e **envio para Chatwoot**.

---

## 🔬 O que e analisado em cada site

| Categoria | Sinais detectados |
|---|---|
| **Anuncios pagos** | Google Ads, Meta Pixel, TikTok Ads, LinkedIn Ads |
| **Analytics/mensuracao** | Google Analytics, Google Tag Manager, Hotjar, MS Clarity |
| **Plataforma / CMS** | WordPress, Wix, Squarespace, Webflow, Shopify, Joomla, Elementor |
| **Qualidade tecnica** | responsivo (mobile), HTTPS |
| **Presenca social** | Instagram, Facebook, LinkedIn, YouTube, TikTok, Twitter/X |
| **Google Meu Negocio** | embed/link de Google Maps |
| **Contatos** | WhatsApp, telefone, e-mail |

---

## 📊 Score de oportunidade

Calculado por regras (em `src/detector.py`), de **0 a 100** — quanto **maior**,
melhor o prospect:

| Sinal | Pontos |
|---|---|
| Nao roda anuncio pago | +35 |
| Site nao responsivo (sem mobile) | +15 |
| Sem HTTPS | +10 |
| Sem nenhuma rede social | +20 (1 rede: +10) |
| Sem Google Maps/Meu Negocio | +10 |
| Tem contato (da pra abordar) | +10 |

O **MiniMax** complementa com um `quality_score` proprio (menor = pior presenca =
melhor oportunidade) e a temperatura (`quente`/`morno`/`frio`).

---

## 💻 Instalacao local (Windows / PowerShell)

```powershell
git clone https://github.com/<seu-usuario>/<seu-repo>.git
cd <seu-repo>

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env   # depois edite o .env com suas chaves
streamlit run app.py
```

A interface abre em `http://localhost:8501`.

---

## ⚙️ Configuracao (.env)

| Variavel | Obrigatorio | Descricao |
|---|---|---|
| `FIRECRAWL_BASE_URL` | sim | URL da sua instancia Firecrawl |
| `FIRECRAWL_API_KEY` | nao | so se a instancia exigir |
| `MINIMAX_API_KEY` | recomendado | chave MiniMax (sem ela, roda so a deteccao por regex) |
| `MINIMAX_BASE_URL` | nao | padrao `https://api.minimax.io/v1` |
| `MINIMAX_MODEL` | nao | padrao `MiniMax-Text-01` |
| `MINIMAX_GROUP_ID` | nao | so se sua conta exigir |
| `AGENCY_OFFER` | nao | o que sua agencia vende (personaliza a abordagem) |
| `DEFAULT_NICHE` | nao | nicho que ja vem preenchido na UI |
| `CHATWOOT_*` | nao | integracao com Chatwoot (ver secao) |
| `REQUEST_TIMEOUT` | nao | timeout das chamadas HTTP (s) |
| `RATE_LIMIT_SECONDS` | nao | intervalo entre chamadas (protege a VPS) |

Sem `MINIMAX_API_KEY` a ferramenta ainda funciona: faz busca, scraping, deteccao
tecnica e score — apenas nao gera parecer nem copy.

---

## ▶️ Uso

> **Configuracao na propria interface:** alem do `.env`/Secrets, o app tem um painel
> **⚙️ Configuracoes de conexao** (no topo) onde da para colar, em runtime, a URL/chave
> do Firecrawl, a chave/modelo do MiniMax e os dados do Chatwoot. Os valores valem para
> a sessao, tem prioridade sobre o `.env` e nao sao salvos em disco. Ideal no Streamlit
> Cloud para ajustar sem mexer nos Secrets.

1. Na barra lateral, defina o **nicho** e uma ou mais **localidades** (uma por linha).
2. Ajuste **resultados por busca**, **variacoes**, **enriquecimento** e **MiniMax**.
3. Clique em **🚀 Rodar prospeccao** e acompanhe o progresso.
4. Use os filtros (so bons leads / so quentes / opp-score minimo / nicho) e a tabela.
5. Em cada lead: leia o parecer, ajuste a mensagem e **exporte CSV** ou **envie ao
   Chatwoot**.

> Dica: comece com poucas localidades e ~5-8 resultados por busca para validar o
> fluxo sem sobrecarregar a VPS nem gastar tokens a toa.

---

## ☁️ Deploy no Streamlit Cloud

> **Por que nao Netlify?** Netlify hospeda sites estaticos/funcoes serverless.
> Streamlit e um servidor persistente, entao nao roda la. Use Streamlit Cloud
> (gratis), a sua VPS (EasyPanel/Docker), Render ou Hugging Face Spaces.

Passo a passo no **Streamlit Community Cloud**:

1. Garanta que o repositorio esta no GitHub (este projeto ja inclui
   `requirements.txt`, `.streamlit/config.toml` e `.gitignore`).
2. Acesse <https://share.streamlit.io>, faca login com o GitHub.
3. **New app** → selecione o repositorio, o branch e o arquivo `app.py`.
4. Em **Advanced settings → Secrets**, cole o conteudo no formato TOML (use
   `.streamlit/secrets.toml.example` como modelo):

   ```toml
   FIRECRAWL_BASE_URL = "https://automate-firecrawl.hr91bv.easypanel.host"
   MINIMAX_API_KEY = "sua_chave"
   MINIMAX_BASE_URL = "https://api.minimax.io/v1"
   MINIMAX_MODEL = "MiniMax-Text-01"
   AGENCY_OFFER = "gestao de trafego pago, anuncios online (Google e Meta) e presenca digital"
   ```

5. **Deploy**. O `config.py` le esses secrets automaticamente (nao precisa de `.env`
   na nuvem).

> ⚠️ O SQLite (`data/leads.db`) no Streamlit Cloud e **efemero** (some a cada
> redeploy/reboot). Para a nuvem, use o **export CSV** ou o **envio ao Chatwoot**
> para nao perder os leads. Para persistencia real, migrar para um Postgres
> gerenciado (ver Roadmap).

---

## 💬 Integracao com Chatwoot (opcional)

Preencha no `.env` (ou nos Secrets):

| Variavel | Onde achar no Chatwoot |
|---|---|
| `CHATWOOT_BASE_URL` | URL da sua instancia (ex.: `https://app.chatwoot.com`) |
| `CHATWOOT_API_TOKEN` | Perfil → Access Token |
| `CHATWOOT_ACCOUNT_ID` | numero da conta na URL (`/accounts/<id>`) |
| `CHATWOOT_INBOX_ID` | id da inbox de destino |

Com isso habilitado, cada lead pode ser enviado como **contato** com atributos
customizados (nicho, opportunity_score, temperatura, anuncios, redes, parecer,
gancho e a mensagem de abordagem).

---

## 🗂 Estrutura do projeto

```
app.py                      UI Streamlit (dashboard)
config.py                   carrega .env / st.secrets
requirements.txt            dependencias
.env.example                modelo de configuracao local
.streamlit/
  config.toml               tema + ajustes do Streamlit
  secrets.toml.example      modelo de secrets para o Streamlit Cloud
src/
  firecrawl_client.py       search + scrape (retry/timeout)
  detector.py               deteccao tecnica por regex + score
  minimax_client.py         analise + copywriting (1 chamada/lead -> JSON)
  chatwoot_client.py        cria contatos no Chatwoot
  db.py                     SQLite (dedup, migracao automatica de colunas)
  pipeline.py               orquestra o funil + filtros + enriquecimento
  models.py                 dataclass Lead
data/                       leads.db gerado em runtime (ignorado no git)
```

---

## 🛠 Solucao de problemas

- **MiniMax aparece "desativado"**: faltou `MINIMAX_API_KEY` no `.env`/Secrets.
- **Erro 401/403 no MiniMax**: chave invalida ou `MINIMAX_BASE_URL`/`MINIMAX_GROUP_ID`
  incompativeis com sua conta.
- **Busca nao retorna nada**: confira `FIRECRAWL_BASE_URL` e use o botao
  **Testar conexoes** na barra lateral.
- **Muitos portais nos resultados**: mantenha **Ignorar portais/agregadores** ligado;
  novos dominios podem ser adicionados em `PORTALS`/`LISTICLE_HINTS` (`src/pipeline.py`).
- **Leads sumiram apos redeploy na nuvem**: SQLite e efemero no Streamlit Cloud
  (ver aviso no deploy). Exporte CSV ou use Chatwoot.

---

## 🗺 Roadmap

- [ ] Persistencia em Postgres (para deploy em nuvem sem perder dados).
- [ ] Deploy via Docker na VPS (EasyPanel), no mesmo painel do Firecrawl.
- [ ] Criacao automatica de conversa/nota no Chatwoot junto do contato.
- [ ] Exportacao para Google Sheets.
- [ ] Agendamento de prospeccoes recorrentes.

---

> Projeto de uso interno para prospeccao. Respeite os termos de uso dos sites
> raspados e a LGPD ao tratar dados de contato.
