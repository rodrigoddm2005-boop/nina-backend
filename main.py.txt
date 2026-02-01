import os
import requests
from fastapi import FastAPI, Request
from openai import OpenAI

app = FastAPI()

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Você é Nina, uma assistente virtual acolhedora para pessoas com lúpus.
Seu papel é ouvir, acolher, validar emoções e oferecer informações gerais baseadas em ciência.
Você NÃO faz diagnóstico, NÃO prescreve medicamentos, NÃO sugere doses, NÃO substitui médicos.

Regras:
- Se o usuário pedir diagnóstico, remédio, dose ou conduta clínica: explique que não pode e sugira falar com o médico.
- Se houver sofrimento emocional intenso, desespero ou risco: acolha e sugira buscar apoio humano imediato (familiares, amigos, serviço de saúde).
Estilo:
- linguagem calorosa, simples, sem jargão, sem minimizar a dor.
"""

def send_telegram_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload, timeout=20)

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()

    message = data.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    text = message.get("text", "")

    if not chat_id:
        return {"ok": True}

    # comandos básicos
    if text.startswith("/start"):
        send_telegram_message(
            chat_id,
            "Oi! Eu sou a Nina 💜\n\n"
            "Eu posso te acolher, conversar e te ajudar com informações gerais e seguras sobre lúpus.\n"
            "Eu não faço diagnóstico nem prescrevo medicamentos.\n\n"
            "Se quiser, me conte como você está hoje — ou use /diario."
        )
        return {"ok": True}

    if text.startswith("/diario"):
        send_telegram_message(
            chat_id,
            "Claro. Quer registrar no seu diário?\n\n"
            "Você pode me dizer:\n"
            "1) Como está seu humor hoje (0–10)\n"
            "2) Como está sua fadiga (0–10)\n"
            "3) O que mais pesou no seu dia\n"
            "4) Se teve algo que ajudou um pouco"
        )
        return {"ok": True}

    # mensagem normal → OpenAI
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.6,
        )

        reply = response.choices[0].message.content.strip()
        if not reply:
            reply = "Estou aqui com você 💜 Quer me contar um pouco mais?"

        send_telegram_message(chat_id, reply)

    except Exception:
        send_telegram_message(
            chat_id,
            "Desculpa — tive uma instabilidade técnica aqui. 😕\n"
            "Pode tentar mandar de novo?"
        )

    return {"ok": True}

@app.get("/")
def health():
    return {"status": "ok"}
