import os
import requests
from fastapi import FastAPI, Request
from openai import OpenAI
from collections import deque

app = FastAPI()

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Você é Nina, uma assistente virtual acolhedora para pessoas com lúpus.
Seu papel é ouvir, acolher, validar emoções e oferecer informações gerais baseadas em ciência.
Você NÃO faz diagnóstico, NÃO prescreve medicamentos, NÃO sugere doses, NÃO substitui médicos.

Regras de segurança:
- Nunca diagnostique nem prescreva.
- Se o usuário pedir conduta clínica, diga que não pode e oriente conversar com o médico(a).
- Se houver sofrimento emocional intenso ou desesperança, acolha e incentive apoio humano.
- Linguagem calorosa, simples, sem jargão.
- Termine respostas importantes com UMA pergunta curta.
""".strip()

# =========================
# Memória curta (RAM)
# =========================
MEMORY = {}     # chat_id -> deque(maxlen=10)
STATE = {}      # estados de fluxo
CHECKINS = {}
DIARIES = {}

# =========================
# Utilidades
# =========================
def send_telegram_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
    except Exception as e:
        print("TELEGRAM ERROR:", repr(e))


def remember(chat_id: int, role: str, content: str):
    if chat_id not in MEMORY:
        MEMORY[chat_id] = deque(maxlen=10)
    MEMORY[chat_id].append({"role": role, "content": content})


def call_openai(chat_id: int, user_text: str) -> str:
    remember(chat_id, "user", user_text)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(MEMORY.get(chat_id, []))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.6,
    )

    reply = (response.choices[0].message.content or "").strip()
    remember(chat_id, "assistant", reply)
    return reply or "Estou aqui com você 💜 Quer me contar um pouco mais?"


def ensure(store, chat_id):
    if chat_id not in store:
        store[chat_id] = []


def parse_checkin(text):
    parts = text.replace(",", " ").split()
    if len(parts) < 4:
        return None
    try:
        nums = [max(0, min(10, int(p))) for p in parts[:4]]
        return nums
    except:
        return None


# =========================
# Conteúdo educativo seguro
# =========================
EDU = {
    "fadiga": (
        "A fadiga no lúpus é muito comum e nem sempre reflete atividade da doença.\n\n"
        "Ela pode estar ligada a inflamação, sono não reparador, dor, estresse emocional "
        "e até ao impacto psicológico de viver com uma condição crônica.\n\n"
        "Estratégias gerais que costumam ajudar incluem respeitar limites, organizar o dia "
        "em blocos de energia, sono regular e apoio emocional.\n\n"
        "Se a fadiga estiver intensa ou mudando muito, vale conversar com seu médico(a). "
        "Quer me contar como a fadiga tem afetado seu dia a dia?"
    ),
    "sono": (
        "O sono é um pilar importante para quem vive com lúpus.\n\n"
        "Dor, ansiedade, preocupações e alterações do ritmo podem atrapalhar o descanso.\n\n"
        "Em geral, ajuda manter horários regulares, reduzir estímulos antes de dormir "
        "e observar o que piora ou melhora suas noites.\n\n"
        "Se o sono não estiver reparador por muitos dias, vale discutir isso em consulta. "
        "Como têm sido suas noites ultimamente?"
    ),
    "ansiedade": (
        "Ansiedade é muito comum em doenças crônicas e não é sinal de fraqueza.\n\n"
        "Ela pode amplificar dor, fadiga e sofrimento emocional.\n\n"
        "Reconhecer a ansiedade, falar sobre ela e buscar estratégias de enfrentamento "
        "é parte do cuidado integral.\n\n"
        "Se a ansiedade estiver difícil de manejar sozinha, procurar ajuda profissional "
        "pode fazer muita diferença. Quer me contar o que tem te deixado mais ansiosa?"
    ),
    "mitos": (
        "Existem muitos mitos sobre lúpus.\n\n"
        "❌ 'É tudo psicológico'\n"
        "❌ 'Quem tem lúpus não pode ter uma vida ativa'\n"
        "❌ 'Nada ajuda'\n\n"
        "A realidade é que o lúpus é uma condição complexa, com altos e baixos, "
        "e o cuidado envolve corpo, mente e apoio social.\n\n"
        "Você já ouviu algum mito que te incomodou ou te confundiu?"
    ),
}

# =========================
# Webhook
# =========================
@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    message = data.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()

    if not chat_id:
        return {"ok": True}

    # Comandos básicos
    if text.startswith("/start"):
        MEMORY.pop(chat_id, None)
        STATE.pop(chat_id, None)
        send_telegram_message(
            chat_id,
            "Oi! Eu sou a Nina 💜\n\n"
            "Posso te acolher, ajudar com informações seguras e registrar como você está.\n\n"
            "Comandos:\n"
            "/checkin — check-in rápido (0–10)\n"
            "/diario — diário guiado\n"
            "/resumo — resumo para consulta\n"
            "/fadiga | /sono | /ansiedade | /mitos"
        )
        return {"ok": True}

    # Educação
    for cmd in ["fadiga", "sono", "ansiedade", "mitos"]:
        if text.startswith(f"/{cmd}"):
            send_telegram_message(chat_id, EDU[cmd])
            return {"ok": True}

    # Check-in
    if text.startswith("/checkin"):
        STATE[chat_id] = "await_checkin"
        send_telegram_message(
            chat_id,
            "Me mande 4 números (0–10):\n"
            "humor, fadiga, dor, sono\n\n"
            "Exemplo: 5 9 3 6"
        )
        return {"ok": True}

    if STATE.get(chat_id) == "await_checkin":
        nums = parse_checkin(text)
        if not nums:
            send_telegram_message(chat_id, "Pode me mandar 4 números assim: 5 9 3 6")
            return {"ok": True}

        ensure(CHECKINS, chat_id)
        CHECKINS[chat_id].append(
            {"humor": nums[0], "fadiga": nums[1], "dor": nums[2], "sono": nums[3]}
        )
        STATE.pop(chat_id)
        reply = call_openai(
            chat_id,
            f"Usuário fez check-in: humor {nums[0]}, fadiga {nums[1]}, dor {nums[2]}, sono {nums[3]}. "
            "Acolha e faça uma pergunta curta."
        )
        send_telegram_message(chat_id, reply)
        return {"ok": True}

    # Diário
    if text.startswith("/diario"):
        STATE[chat_id] = {"step": 1, "data": {}}
        send_telegram_message(chat_id, "O que mais pesou no seu dia hoje?")
        return {"ok": True}

    if isinstance(STATE.get(chat_id), dict):
        state = STATE[chat_id]
        if state["step"] == 1:
            state["data"]["pesou"] = text
            state["step"] = 2
            send_telegram_message(chat_id, "Teve algo que ajudou um pouco hoje?")
            return {"ok": True}
        elif state["step"] == 2:
            ensure(DIARIES, chat_id)
            DIARIES[chat_id].append(
                {"pesou": state["data"]["pesou"], "ajudou": text}
            )
            STATE.pop(chat_id)
            reply = call_openai(
                chat_id,
                f"O que pesou: {state['data']['pesou']}. "
                f"O que ajudou: {text}. "
                "Acolha e sugira um passo pequeno e seguro."
            )
            send_telegram_message(chat_id, reply)
            return {"ok": True}

    # Resumo
    if text.startswith("/resumo"):
        ensure(CHECKINS, chat_id)
        ensure(DIARIES, chat_id)
        lines = ["📌 Resumo para consulta\n"]
        for c in CHECKINS[chat_id][-5:]:
            lines.append(
                f"- Humor {c['humor']} | Fadiga {c['fadiga']} | Dor {c['dor']} | Sono {c['sono']}"
            )
        for d in DIARIES[chat_id][-5:]:
            lines.append(f"- Pesou: {d['pesou']} | Ajudou: {d['ajudou']}")
        send_telegram_message(chat_id, "\n".join(lines))
        return {"ok": True}

    # Conversa normal (com memória)
    reply = call_openai(chat_id, text)
    send_telegram_message(chat_id, reply)
    return {"ok": True}


@app.get("/")
def health():
    return {"status": "ok"}
