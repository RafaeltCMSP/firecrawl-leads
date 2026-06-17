"""Cliente MiniMax. UMA chamada por lead -> JSON com analise completa:
parecer do site, pontos fracos, canais faltando, score, temperatura, gancho
de venda e mensagens de abordagem (WhatsApp + e-mail). Generico por nicho.
"""
import json
import re

import requests

import config


def _system_prompt(offer: str) -> str:
    return (
        "Voce acumula duas funcoes: (1) analista senior de prospeccao B2B e "
        f"(2) copywriter de outbound, de uma agencia que vende {offer}. "
        "Analise o site de um negocio (qualquer nicho) e avalie o quao boa "
        "oportunidade ele e como CLIENTE. Negocios com presenca digital fraca e que "
        "NAO investem em anuncios sao as MELHORES oportunidades. "
        "As mensagens de abordagem devem soar HUMANAS, especificas e consultivas - "
        "nunca spam de agencia. Responda SOMENTE com JSON valido, sem markdown."
    )


JSON_SCHEMA_HINT = """
Formato EXATO da resposta:
{
  "nome": "nome do negocio",
  "segmento": "segmento/nicho confirmado pelo site",
  "regiao": "cidade/regiao de atuacao se identificar",
  "telefone": "", "whatsapp": "", "email": "",
  "qualidade_site": "parecer curto (1-2 frases): o que o site tem de fraco e a oportunidade",
  "pontos_fracos": ["item", "item"],
  "canais_faltando": ["ex: sem Instagram", "ex: nao roda anuncios", "ex: sem Google Meu Negocio"],
  "quality_score": 0,
  "lead_temp": "quente|morno|frio",
  "gancho_venda": "1 frase: o angulo mais forte para abordar este lead",
  "mensagem_whatsapp": "mensagem de WhatsApp (ver regras de copy)",
  "assunto_email": "assunto de e-mail (ver regras)",
  "mensagem_email": "corpo de e-mail (ver regras)"
}

Regras de classificacao:
- quality_score 0-100: MENOR = site/presenca pior = MELHOR oportunidade.
- lead_temp = "quente" quando a presenca e fraca e o negocio NAO investe em anuncios.

REGRAS DE COPYWRITING (valem para WhatsApp e e-mail):
1. Abra citando algo ESPECIFICO e verdadeiro do negocio (nome, bairro/cidade, um
   servico real, ou um detalhe que aparece no site). Nada de saudacao vazia.
2. Aponte UMA oportunidade concreta observada nos sinais (ex.: "nao achei o
   Instagram de voces", "o site demora/nao abre bem no celular", "voces ainda nao
   aparecem no Google Maps", "nao vi anuncios rodando"). Use so o que for real.
3. Ligue a oportunidade a um RESULTADO do negocio (mais clientes/pacientes/
   agendamentos/orcamentos), nao a um servico tecnico.
4. CTA leve, sem pressao, em forma de pergunta (ex.: "Faz sentido eu te mandar
   2 ideias rapidas?" / "Posso te mostrar como ficaria?").
5. Primeira pessoa, tom de quem conhece o negocio, portugues do Brasil natural.
6. PROIBIDO clichês: "identificamos que sua empresa tem potencial", "somos uma
   agencia que", "oferecemos servicos de", "venho por meio desta", "prezado(a)".
7. WhatsApp: ate 4 frases curtas, no maximo 1 emoji (pode ser nenhum).
8. E-mail: assunto curto e especifico (NUNCA "Proposta comercial"); corpo de ate
   6 frases, profissional e direto, terminando com a pergunta-CTA. Sem assinatura.

Exemplo de bom WhatsApp (apenas referencia de tom, NAO copie):
"Oi! Vi o site da [Nome] aqui no [bairro]. Reparei que voces ainda nao tem perfil
no Google Maps - e ali que a maioria procura [servico] hoje. Da pra capturar bem
mais agendamento com isso ajustado. Posso te mandar 2 ideias rapidas?"
"""


class MiniMaxClient:
    def __init__(self, api_key=None, base_url=None, model=None, timeout=None,
                 group_id=None, offer=None):
        self.api_key = api_key or config.MINIMAX_API_KEY
        self.base_url = (base_url or config.MINIMAX_BASE_URL).rstrip("/")
        self.model = model or config.MINIMAX_MODEL
        self.group_id = group_id if group_id is not None else config.MINIMAX_GROUP_ID
        self.timeout = timeout or config.REQUEST_TIMEOUT
        self.offer = offer or config.AGENCY_OFFER

    def _endpoint(self):
        url = f"{self.base_url}/text/chatcompletion_v2"
        if self.group_id:
            url += f"?GroupId={self.group_id}"
        return url

    def _chat(self, messages):
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages, "temperature": 0.6}
        r = requests.post(self._endpoint(), json=payload, headers=headers, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        base = data.get("base_resp") or {}
        if base.get("status_code") not in (0, None):
            raise RuntimeError(f"MiniMax erro {base.get('status_code')}: {base.get('status_msg')}")
        choices = data.get("choices") or []
        if choices:
            return choices[0].get("message", {}).get("content", "") or ""
        return data.get("reply", "") or ""

    @staticmethod
    def _parse_json(text: str) -> dict:
        if not text:
            return {}
        text = re.sub(r"^```(?:json)?", "", text.strip()).strip()
        text = re.sub(r"```$", "", text).strip()
        try:
            return json.loads(text)
        except Exception:  # noqa: BLE001
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:  # noqa: BLE001
                    return {}
        return {}

    def analyze(self, *, niche, name_hint, url, location, tech, markdown) -> dict:
        present = [n for n in ("instagram", "facebook", "linkedin", "youtube", "tiktok", "twitter")
                   if tech.get(n)]
        contexto = (
            f"Nicho buscado: {niche}\n"
            f"URL: {url}\n"
            f"Localidade alvo: {location}\n"
            f"Titulo/dica do buscador: {name_hint}\n"
            f"--- Sinais detectados ---\n"
            f"Anuncios pagos: {tech.get('ad_pixels') or 'NENHUM'}\n"
            f"Analytics: {tech.get('analytics') or 'nenhum'}\n"
            f"Plataforma/CMS: {tech.get('cms')}\n"
            f"Mobile: {tech.get('is_mobile')} | HTTPS: {tech.get('is_https')} | "
            f"Google Maps/Meu Negocio: {tech.get('has_maps')}\n"
            f"Redes sociais presentes: {', '.join(present) or 'NENHUMA'}\n"
            f"Contato: whats={tech.get('whatsapp')} tel={tech.get('phone')} email={tech.get('email')}\n\n"
            f"--- Conteudo do site (resumo) ---\n{(markdown or '')[:4000]}"
        )
        messages = [
            {"role": "system", "content": _system_prompt(self.offer) + "\n" + JSON_SCHEMA_HINT},
            {"role": "user", "content": contexto},
        ]
        return self._parse_json(self._chat(messages))
