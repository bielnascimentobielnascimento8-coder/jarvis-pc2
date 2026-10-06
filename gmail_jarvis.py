# -*- coding: utf-8 -*-
"""
Acesso ao Gmail do Jarvis - SOMENTE para ler e-mails e responder dentro da
mesma conversa (reply). Nunca escreve para um destinatário novo, nunca apaga,
nunca arquiva, nunca encaminha. Pede confirmação por voz antes de enviar.

Para funcionar, siga o LEIA-ME.txt (seção Gmail) para gerar o arquivo
credentials.json. Na primeira execução, uma janela do navegador vai pedir
para você fazer login e autorizar.
"""
import base64, os
from email.mime.text import MIMEText
from pathlib import Path

HERE = Path(__file__).parent
CREDS_FILE = HERE / "credentials.json"
TOKEN_FILE = HERE / "gmail_token.json"
# Escopo mínimo: ler e enviar/responder. NÃO inclui apagar, nem gerenciar contatos.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                raise RuntimeError(
                    "Falta o arquivo credentials.json. Siga o LEIA-ME.txt, seção Gmail.")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)

def listar_novos(max_results=5):
    """Retorna as últimas mensagens não lidas: [{id, threadId, de, assunto, trecho}]."""
    svc = _service()
    res = svc.users().messages().list(userId="me", labelIds=["INBOX", "UNREAD"],
                                       maxResults=max_results).execute()
    out = []
    for m in res.get("messages", []):
        msg = svc.users().messages().get(userId="me", id=m["id"], format="metadata",
                                          metadataHeaders=["From", "Subject"]).execute()
        heads = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        out.append({
            "id": m["id"], "threadId": msg["threadId"],
            "de": heads.get("From", "desconhecido"),
            "assunto": heads.get("Subject", "(sem assunto)"),
            "trecho": msg.get("snippet", ""),
        })
    return out

def corpo_completo(msg_id):
    """Texto puro do e-mail, para o Jarvis ler em voz alta ou mandar ao Claude."""
    svc = _service()
    msg = svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
    def walk(part):
        if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "ignore")
        for p in part.get("parts", []) or []:
            t = walk(p)
            if t:
                return t
        return ""
    return walk(msg["payload"]) or msg.get("snippet", "")

def responder(thread_id, to_addr, assunto, texto):
    """Envia uma resposta DENTRO da mesma thread. Só é chamada depois de
    confirmação explícita do usuário em jarvis.py."""
    svc = _service()
    mime = MIMEText(texto)
    mime["to"] = to_addr
    mime["subject"] = "Re: " + assunto if not assunto.lower().startswith("re:") else assunto
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    svc.users().messages().send(userId="me", body={"raw": raw, "threadId": thread_id}).execute()

def marcar_lido(msg_id):
    svc = _service()
    svc.users().messages().modify(userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}).execute()
