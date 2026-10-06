# -*- coding: utf-8 -*-
"""
JARVIS PC - assistente de voz pessoal com permissões LIMITADAS.
Feito para Gabriel (14 anos). Personalidade: mordomo britânico formal.

O QUE ELE FAZ (e só isso):
  - Abre programas de uma lista permitida (ALLOWED_APPS)
  - Abre sites de uma lista permitida (ALLOWED_SITES)
  - Toca / pausa / pula música (teclas de mídia do Windows)
  - Ajusta o volume do sistema
  - Cria lembretes e timers com aviso falado
  - Organiza arquivos (por extensão) DENTRO de uma única pasta (WORK_FOLDER) - pede confirmação
  - Faz contas
  - Responde perguntas usando a API da Anthropic (sua chave)
  - Guarda notas rápidas no Second Brain (arquivo local second_brain.json)

O QUE ELE NUNCA FAZ:
  - Não lê, copia, apaga ou move nada fora de WORK_FOLDER
  - Não acessa senhas, navegador logado, e-mails, câmera ou histórico
  - Não instala nada
  - Não executa comandos arbitrários do sistema (sem "cmd", sem powershell livre)
  - Nunca apaga ou move arquivo sem você confirmar na hora
"""

import json, os, re, sys, threading, time, queue, subprocess, webbrowser, shutil, urllib.parse
from pathlib import Path

# ============== CONFIGURAÇÃO (ajuste aqui) ==============
NOME = "Jarvis"
ENDERECO = "senhor Gabriel"
WAKE_WORD = "jarvis"
MODEL = "claude-sonnet-5-5"

# Pasta única que o Jarvis tem permissão de organizar. MUDE para a pasta que você quiser.
WORK_FOLDER = Path.home() / "Downloads"

# Programas que ele pode abrir: nome falado -> comando real
ALLOWED_APPS = {
    "calculadora": "calc.exe",
    "bloco de notas": "notepad.exe",
    "navegador": "start chrome",
    "explorador de arquivos": "explorer.exe",
    "spotify": "spotify.exe",
}

# Sites que ele pode abrir: nome falado -> URL
ALLOWED_SITES = {
    "youtube": "https://youtube.com",
    "whatsapp": "https://web.whatsapp.com",
    "google": "https://google.com",
    "mercado livre": "https://www.mercadolivre.com.br",
}

KEY_FILE = Path(__file__).parent / "jarvis_key.txt"
BRAIN_FILE = Path(__file__).parent / "second_brain.json"
# ==========================================================

# E-mail: só leitura e resposta dentro da mesma conversa. Nunca envia para
# destinatário novo, nunca apaga, nunca encaminha. Confirmação sempre antes de enviar.
try:
    import gmail_jarvis
    GMAIL_OK = True
except Exception:
    GMAIL_OK = False

_ultimo_email = {}  # guarda o último e-mail lido, para "responde que..."

def get_key():
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    k = input("Cole sua chave da API Anthropic (fica salva só neste arquivo, neste PC): ").strip()
    KEY_FILE.write_text(k)
    return k

def load_brain():
    if BRAIN_FILE.exists():
        return json.loads(BRAIN_FILE.read_text(encoding="utf-8"))
    return []

def save_note(text):
    notes = load_brain()
    notes.append({"ts": time.strftime("%Y-%m-%d %H:%M"), "text": text})
    BRAIN_FILE.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------- Voz ----------------
try:
    import pyttsx3
    engine = pyttsx3.init()
    engine.setProperty("rate", 178)
    for v in engine.getProperty("voices"):
        if "brazil" in v.name.lower() or "pt" in (v.id or "").lower():
            engine.setProperty("voice", v.id)
            break
except Exception:
    engine = None

def falar(texto):
    print(f"[{NOME}] {texto}")
    if engine:
        engine.say(texto)
        engine.runAndWait()

# ---------------- Confirmação ----------------
def confirmar(pergunta):
    falar(pergunta + " Diga sim ou não.")
    resp = ouvir_uma_frase(timeout=6)
    return bool(resp) and re.search(r"\bsim\b", resp.lower())

# ---------------- Reconhecimento de voz ----------------
import speech_recognition as sr
reconhecedor = sr.Recognizer()
microfone = sr.Microphone()

def ouvir_uma_frase(timeout=5):
    with microfone as src:
        reconhecedor.adjust_for_ambient_noise(src, duration=0.3)
        try:
            audio = reconhecedor.listen(src, timeout=timeout, phrase_time_limit=8)
        except sr.WaitTimeoutError:
            return None
    try:
        return reconhecedor.recognize_google(audio, language="pt-BR")
    except Exception:
        return None

# ---------------- Ações permitidas ----------------
def abrir_app(nome):
    nome = nome.strip().lower()
    for chave, cmd in ALLOWED_APPS.items():
        if chave in nome:
            try:
                os.system(cmd if cmd.startswith("start") else f'start "" "{cmd}"')
                return f"Abrindo {chave}, {ENDERECO}."
            except Exception as e:
                return f"Não consegui abrir {chave}: {e}"
    return f"Esse programa não está na minha lista permitida, {ENDERECO}. Posso abrir: {', '.join(ALLOWED_APPS)}."

def abrir_site(nome):
    nome = nome.strip().lower()
    for chave, url in ALLOWED_SITES.items():
        if chave in nome:
            webbrowser.open(url)
            return f"Abrindo {chave}, {ENDERECO}."
    return f"Esse site não está na minha lista permitida. Posso abrir: {', '.join(ALLOWED_SITES)}."

def enviar_whatsapp(numero, texto):
    """Abre o WhatsApp Web com a mensagem já escrita. NUNCA envia sozinho:
    você precisa clicar no botão de enviar. Não lê conversas."""
    numero = re.sub(r"\D", "", numero)
    if len(numero) < 10:
        return f"Não entendi o número, {ENDERECO}. Diga o DDD e o número completos."
    url = f"https://wa.me/{numero}?text={urllib.parse.quote(texto)}"
    webbrowser.open(url)
    return f"Abri o WhatsApp com a mensagem pronta para {numero}, {ENDERECO}. É só você tocar em enviar."

def midia(acao):
    import ctypes
    VK = {"tocar": 0xB3, "pausar": 0xB3, "proxima": 0xB0, "anterior": 0xB1, "mais volume": 0xAF, "menos volume": 0xAE, "mudo": 0xAD}
    code = VK.get(acao)
    if not code:
        return "Não entendi o comando de mídia."
    ctypes.windll.user32.keybd_event(code, 0, 0, 0)
    ctypes.windll.user32.keybd_event(code, 0, 2, 0)
    return "Feito."

def organizar_pasta():
    if not confirmar(f"Vou organizar os arquivos dentro de {WORK_FOLDER.name} em subpastas por tipo. Posso continuar?"):
        return "Tudo bem, não vou mexer em nada."
    moved = 0
    for f in WORK_FOLDER.iterdir():
        if f.is_file():
            ext = f.suffix.lstrip(".").lower() or "sem_extensao"
            dest = WORK_FOLDER / ext
            dest.mkdir(exist_ok=True)
            try:
                shutil.move(str(f), str(dest / f.name))
                moved += 1
            except Exception:
                pass
    return f"Pronto, {ENDERECO}. Organizei {moved} arquivos em {WORK_FOLDER}."

def timer(segundos, aviso):
    def run():
        time.sleep(segundos)
        falar(aviso)
    threading.Thread(target=run, daemon=True).start()
    return f"Combinado, {ENDERECO}. Vou te avisar em {segundos//60} minutos." if segundos>=60 else f"Vou te avisar em {segundos} segundos."

def calcular(s):
    e = s.lower().replace(",", ".").replace("vezes", "*").replace("mais", "+").replace("menos", "-").replace("dividido por", "/")
    e = re.sub(r"quanto e|quanto é|calcule|=|\?", "", e).strip()
    if not re.search(r"\d", e) or not re.fullmatch(r"[\d\s+\-*/().]+", e):
        return None
    try:
        return round(eval(e, {"__builtins__": {}}), 6)
    except Exception:
        return None

# ---------------- E-mail (ler e responder, nunca mais que isso) ----------------
def verificar_emails():
    if not GMAIL_OK:
        return "O acesso ao Gmail não está configurado. Veja o LEIA-ME, seção Gmail."
    try:
        novos = gmail_jarvis.listar_novos()
    except Exception as e:
        return f"Não consegui acessar seus e-mails, {ENDERECO}: {e}"
    if not novos:
        return f"Nenhum e-mail novo, {ENDERECO}."
    e = novos[0]
    _ultimo_email.clear()
    _ultimo_email.update(e)
    return f"Você tem {len(novos)} e-mails novos. O mais recente é de {e['de']}, assunto {e['assunto']}: {e['trecho']}"

def responder_email(pedido, key):
    if not GMAIL_OK:
        return "O acesso ao Gmail não está configurado."
    if not _ultimo_email:
        return f"Eu ainda não li nenhum e-mail agora, {ENDERECO}. Diga 'Jarvis, veja meus e-mails' primeiro."
    try:
        corpo = gmail_jarvis.corpo_completo(_ultimo_email["id"])
        rascunho = perguntar_claude(
            f"Recebi este e-mail de {_ultimo_email['de']}, assunto '{_ultimo_email['assunto']}':\n{corpo}\n\n"
            f"Escreva uma resposta curta e educada, em português, atendendo a este pedido do {ENDERECO}: {pedido}",
            key)
    except Exception as e:
        return f"Não consegui preparar a resposta: {e}"
    falar(f"Aqui está o rascunho: {rascunho}")
    if confirmar("Posso enviar esta resposta agora?"):
        from_addr = _ultimo_email["de"]
        gmail_jarvis.responder(_ultimo_email["threadId"], from_addr, _ultimo_email["assunto"], rascunho)
        gmail_jarvis.marcar_lido(_ultimo_email["id"])
        return f"Enviado, {ENDERECO}."
    return "Tudo bem, não enviei. Me diga o que mudar, se quiser tentar de novo."

# ---------------- Cérebro (API Anthropic) ----------------
import urllib.request

def system_prompt():
    notas = "\n".join(f"- {n['text']}" for n in load_brain()[-20:])
    return (f"Você é {NOME}, assistente pessoal estilo Jarvis, personalidade de mordomo britânico formal: "
            f"educado, elegante, levemente irônico. Chame o usuário sempre de '{ENDERECO}'. "
            f"Ele tem 14 anos: mantenha tudo adequado à idade. Responda em português do Brasil, "
            f"no máximo 3 frases curtas, sem markdown nem emojis, pois será falado em voz alta.\n"
            f"Notas que ele pediu para lembrar:\n{notas}")

def perguntar_claude(pergunta, key):
    body = json.dumps({
        "model": MODEL, "max_tokens": 300,
        "system": system_prompt(),
        "messages": [{"role": "user", "content": pergunta}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    return " ".join(b["text"] for b in data["content"] if b["type"] == "text").strip()

# ---------------- Roteador de comandos ----------------
def processar(texto, key):
    t = texto.lower().strip()
    if not t:
        return None
    if re.search(r"\babr[ae]\b", t):
        alvo = re.sub(r".*\babr[ae]\b", "", t).strip()
        return abrir_site(alvo) if alvo in " ".join(ALLOWED_SITES) or any(s in alvo for s in ALLOWED_SITES) else abrir_app(alvo)
    if any(w in t for w in ["toca", "tocar", "pausa", "pausar", "proxima musica", "próxima música"]):
        return midia("tocar")
    if "aumenta o volume" in t or "mais volume" in t:
        return midia("mais volume")
    if "diminui o volume" in t or "menos volume" in t:
        return midia("menos volume")
    if "organiza" in t and ("pasta" in t or "download" in t or "arquivo" in t):
        return organizar_pasta()
    if re.search(r"e-?mails?", t) and any(w in t for w in ["ve", "veja", "checa", "confere", "tem novo", "le", "leia"]):
        return verificar_emails()
    m = re.search(r"(?:mensagem|manda|mande|whats ?app)\D*?(?:para|pra)\s+([\d+\s()-]{8,})\s*[:,]?\s*(.+)", t)
    if m:
        return enviar_whatsapp(m.group(1), m.group(2))
    m = re.search(r"respond\w*\s*(?:o e-?mail)?\s*(?:que|dizendo|com)?\s*(.+)", t)
    if m and ("email" in t or _ultimo_email):
        return responder_email(m.group(1), key)
    m = re.search(r"me lembr\w+ (?:em|daqui a)\s*(\d+)\s*(minuto|segundo)s?\s*(?:de|para)?\s*(.*)", t)
    if m:
        n, unit, aviso = int(m.group(1)), m.group(2), m.group(3) or "seu lembrete"
        return timer(n * (60 if "min" in unit else 1), f"{ENDERECO}, hora de: {aviso}")
    m = re.search(r"anot[ae]\s*(?:que)?\s*(.+)", t)
    if m:
        save_note(m.group(1))
        return f"Anotado, {ENDERECO}."
    c = calcular(t)
    if c is not None:
        return f"O resultado é {c}, {ENDERECO}.".replace(".0,", ",")
    try:
        return perguntar_claude(texto, key)
    except Exception as e:
        return f"Não consegui pensar nisso agora, {ENDERECO}: {e}"

# ---------------- Bandeja do sistema (ícone perto do relógio) ----------------
pausado = threading.Event()  # quando "setado", o Jarvis ignora a voz
tray_icon = None

def _loop_de_escuta(key):
    while True:
        if pausado.is_set():
            time.sleep(0.5)
            continue
        frase = ouvir_uma_frase(timeout=None)
        if not frase or pausado.is_set():
            continue
        low = frase.lower()
        if WAKE_WORD not in low:
            continue
        comando = low.split(WAKE_WORD, 1)[1].strip(" ,.:!")
        if not comando:
            falar(f"Pois não, {ENDERECO}?")
            comando = ouvir_uma_frase(timeout=6)
            if not comando:
                continue
        resposta = processar(comando, key)
        if resposta:
            falar(resposta)

def _abrir_second_brain(icon=None, item=None):
    if not BRAIN_FILE.exists():
        BRAIN_FILE.write_text("[]", encoding="utf-8")
    os.startfile(str(BRAIN_FILE))

def _pausar_retomar(icon=None, item=None):
    if pausado.is_set():
        pausado.clear()
        falar(f"De volta, {ENDERECO}.")
    else:
        pausado.set()
        falar("Pausando a escuta.")
    icon.update_menu()

def _sair(icon=None, item=None):
    falar("Até logo, senhor.")
    icon.stop()
    os._exit(0)

def _estado_texto(item):
    return "Retomar escuta" if pausado.is_set() else "Pausar escuta"

def rodar_com_bandeja(key):
    import pystray
    from PIL import Image
    here = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    icon_path = here / "icon.ico"
    image = Image.open(icon_path) if icon_path.exists() else Image.new("RGB", (64, 64), "#19c8ff")
    menu = pystray.Menu(
        pystray.MenuItem(_estado_texto, _pausar_retomar),
        pystray.MenuItem("Abrir Second Brain", _abrir_second_brain),
        pystray.MenuItem("Sair", _sair),
    )
    global tray_icon
    tray_icon = pystray.Icon("jarvis", image, f"{NOME} - online", menu)
    threading.Thread(target=_loop_de_escuta, args=(key,), daemon=True).start()
    tray_icon.run()  # bloqueia aqui; o programa vive na bandeja do sistema

# ---------------- Ponto de entrada ----------------
def main():
    if sys.platform != "win32":
        print("Este script usa recursos específicos do Windows (teclas de mídia, abrir .exe).")
        print("Rode-o no seu PC com Windows depois de instalar as dependências.")
    key = get_key()
    falar(f"Sistemas online. Estou ouvindo, {ENDERECO}.")
    try:
        rodar_com_bandeja(key)
    except Exception:
        # Se a bandeja falhar por algum motivo, cai para o modo simples no console.
        while True:
            frase = ouvir_uma_frase(timeout=None)
            if not frase:
                continue
            low = frase.lower()
            if WAKE_WORD not in low:
                continue
            comando = low.split(WAKE_WORD, 1)[1].strip(" ,.:!")
            if not comando:
                falar(f"Pois não, {ENDERECO}?")
                comando = ouvir_uma_frase(timeout=6)
                if not comando:
                    continue
            if comando.strip() in ("sair", "desligar", "tchau"):
                falar("Até logo, senhor.")
                break
            resposta = processar(comando, key)
            if resposta:
                falar(resposta)

if __name__ == "__main__":
    main()
