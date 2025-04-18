import requests
import json
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# ─── КОНСТАНТЫ ────────────────────────────────────────────────────────────
TOKEN        = '7829126219:AAFcb5LnMWqBg9PId0F5MGo4-UqUsgZhOW0'
API_URL      = f'https://api.telegram.org/bot{TOKEN}/'
ADMINS       = {8168975341, 6037202333}
FREE_PER_DAY = 5
SUB_DAYS     = 31
PLACEHOLDER  = "🤫 Анонимное сообщение"

MONTHS = {
    1: "января",  2: "февраля",  3: "марта",    4: "апреля",
    5: "мая",      6: "июня",     7: "июля",     8: "августа",
    9: "сентября",10: "октября", 11: "ноября",  12: "декабря"
}

# ─── ПУТИ ────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent
DATA_DIR    = BASE_DIR / 'data'
IMAGES_DIR  = BASE_DIR / 'images'

START_IMG   = IMAGES_DIR / 'start.jpg'
PLUS_IMG    = IMAGES_DIR / 'plus.jpg'
PROMO_IMG   = IMAGES_DIR / 'promocode.jpg'
NO_SUB_IMG  = IMAGES_DIR / 'noob.jpg'
PREM_IMG    = IMAGES_DIR / 'prem.jpg'

USERS_FILE  = DATA_DIR / 'users.json'
SUBS_FILE   = DATA_DIR / 'subs.json'
PROMO_FILE  = DATA_DIR / 'promo.json'

# ─── ЗАГРУЗКА / СОХРАНЕНИЕ JSON ───────────────────────────────────────────
def load(path, default):
    if path.exists():
        raw = path.read_text('utf-8').strip()
        if raw:
            try: return json.loads(raw)
            except: pass
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(default, ensure_ascii=False))
    return default

def save(path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

users        = load(USERS_FILE, {})
subs         = load(SUBS_FILE, {})
promo        = load(PROMO_FILE, {})

anon_messages = {}
temp_storage  = {}
STATE         = {}

# ─── HTTP / API ──────────────────────────────────────────────────────────
def api(method, **p):
    try:    return requests.post(API_URL + method, data=p, timeout=15).json()
    except: return {}

def get_updates(offset=None):
    try:
        return requests.get(API_URL + 'getUpdates',
                            params={'timeout':15, 'offset':offset},
                            timeout=20).json()
    except:
        return {}

def send_msg(chat, text, kb=None):
    api('sendMessage',
        chat_id=chat,
        text=text,
        reply_markup=json.dumps(kb) if kb else None)

def send_photo(chat, path, caption="", kb=None):
    try:
        with open(path, 'rb') as f:
            requests.post(API_URL + 'sendPhoto',
                data={'chat_id':chat,'caption':caption,
                      'reply_markup':json.dumps(kb) if kb else ''},
                files={'photo':f}, timeout=20)
    except: pass

def answer_cb(qid, text="", show_alert=True):
    api('answerCallbackQuery',
        callback_query_id=qid,
        text=text,
        show_alert=show_alert)

# ─── ПОДПИСКИ / ЛИМИТЫ ───────────────────────────────────────────────────
def is_sub(uid):
    k = str(uid)
    if k in subs:
        t = datetime.fromisoformat(subs[k])
        if t > datetime.utcnow(): return t
        subs.pop(k); save(SUBS_FILE, subs)
    return None

def left_today(uid):
    today = datetime.utcnow().date().isoformat()
    rec = users.get(str(uid), {})
    if rec.get("last") != today:
        return FREE_PER_DAY
    return max(0, FREE_PER_DAY - rec.get("today", 0))

def inc_today(uid):
    k = str(uid); d = datetime.utcnow().date().isoformat()
    rec = users.setdefault(k, {"today":0, "last":d})
    if rec["last"] != d:
        rec["today"], rec["last"] = 0, d
    rec["today"] += 1
    save(USERS_FILE, users)

# ─── КНОПКИ ──────────────────────────────────────────────────────────────
def main_kb(uid):
    return {"inline_keyboard":[
        [{"text":"💎 ПОДПИСКА 💎","callback_data":"buy"}],
        [{"text":"✅ ПРОМОКОД ✅","callback_data":"promo"}],
        [{"text":"👤 Профиль","callback_data":"profile"}]
    ]}

def profile_kb():
    return {"inline_keyboard":[
        [{"text":"Меню","callback_data":"menu"}]
    ]}

def list_users_kb():
    return {"inline_keyboard":[
        [{"text":"Меню","callback_data":"menu"}]
    ]}

def message_kb(msg_id):
    return {"inline_keyboard":[
        [{"text":"🔓 Посмотреть","callback_data":f"view_{msg_id}"}]
    ]}

# ─── BOT LOOP ────────────────────────────────────────────────────────────
OFFSET = None
print(">>> BOT STARTED <<<")

while True:
    for upd in get_updates(OFFSET).get('result', []):
        OFFSET = upd['update_id'] + 1

        # 1) INLINE QUERY ───────────────────────────────────────────────
        if 'inline_query' in upd:
            iq    = upd['inline_query']
            qid   = iq['id']
            uid   = iq['from']['id']
            txt   = iq.get('query','').strip()
            if not txt:
                api('answerInlineQuery', inline_query_id=qid,
                    results="[]", cache_time=0)
                continue
            temp_storage[uid] = txt
            art = {
                "type":"article","id":str(uuid.uuid4()),
                "title":PLACEHOLDER,
                "description":txt,
                "input_message_content":{"message_text":PLACEHOLDER}
            }
            api('answerInlineQuery', inline_query_id=qid,
                results=json.dumps([art]), cache_time=0)
            continue

        # 2) MESSAGE ────────────────────────────────────────────────────
        if 'message' in upd:
            m    = upd['message']
            uid  = m['from']['id']
            chat = m['chat']['id']
            txt  = m.get('text','')

            # /start
            if txt == '/start':
                sub = is_sub(uid)
                if sub:
                    d = sub - datetime.utcnow()
                    cap = f"👑 Подписка ещё {d.days}д {d.seconds//3600}ч"
                else:
                    cap = f"Осталось {left_today(uid)}/{FREE_PER_DAY} сообщений"
                send_photo(chat, START_IMG, cap, main_kb(uid))
                continue

            # /admin (только в ЛС)
            if txt == '/admin' and uid in ADMINS and m['chat']['type']=='private':
                kb = {"inline_keyboard":[
                    [{"text":"ПОЛЬЗОВАТЕЛИ","callback_data":"list_sub"}],
                    [{"text":"КЛЮЧИ","callback_data":"gen_key"}],
                    [{"text":"ЛОГИ","callback_data":"logs"}],
                    [{"text":"Меню","callback_data":"menu"}]
                ]}
                send_msg(chat, "👑 Админ‑панель", kb)
                continue

            # ввод промокода (только в ЛС, STATE сохраняется при ошибке)
            if STATE.get(uid)=='wait_promo' and m['chat']['type']=='private':
                code = txt.strip()
                if promo.pop(code, None):
                    exp = datetime.utcnow() + timedelta(days=SUB_DAYS)
                    subs[str(uid)] = exp.isoformat()
                    save(PROMO_FILE, promo); save(SUBS_FILE, subs)
                    send_msg(chat, "💎 Теперь ты M.U.R.M.U.R + 💎")
                    STATE.pop(uid, None)
                else:
                    send_msg(chat, "❌ Ключ неверен или уже использован.")
                continue

            # плацехолдер из inline (reply → основная анонимка)
            if txt == PLACEHOLDER and m.get('reply_to_message'):
                if uid not in temp_storage:
                    continue
                if not is_sub(uid) and left_today(uid)<=0:
                    send_msg(chat, "🕐 Лимит исчерпан. Купи подписку.")
                    continue
                payload = temp_storage.pop(uid)
                src,tgt = m['from'], m['reply_to_message']['from']
                mid     = str(uuid.uuid4())[:8]
                anon_messages[mid] = {
                    'from_id':uid, 'from_name':src.get('first_name',''),
                    'to_id':tgt['id'], 'to_name':tgt.get('first_name',''),
                    'text':payload, 'timestamp':datetime.utcnow().isoformat()
                }
                if not is_sub(uid): inc_today(uid)
                send_msg(chat,
                    f"🤫 АНОНИМНОЕ СООБЩЕНИЕ ДЛЯ {anon_messages[mid]['to_name']}",
                    message_kb(mid))
                continue

        # 3) CALLBACK QUERY ───────────────────────────────────────────────
        if 'callback_query' in upd:
            cb    = upd['callback_query']
            data  = cb['data']
            cid   = cb['id']
            uid   = cb['from']['id']
            ctype = cb['message']['chat']['type']
            chat  = cb['message']['chat']['id']

            # «Посмотреть» – работает и в группе, и в ЛС
            if data.startswith('view_'):
                mid  = data.split('_',1)[1]
                info = anon_messages.get(mid)
                if not info:
                    answer_cb(cid, "❗ Сообщение не найдено.")
                elif uid != info['to_id']:
                    answer_cb(cid, "❗ Это сообщение не для тебя.")
                else:
                    answer_cb(cid, f"✅ Только для тебя ✅\n\n{info['text']}")
                continue

            # остальные кнопки – только в личке
            if ctype != 'private':
                answer_cb(cid)  # просто закрыть popup
                continue

            # «💎 ПОДПИСКА 💎»
            if data=='buy':
                send_photo(chat, PLUS_IMG,
                    "Открой весь потенциал aнонимности с M.U.R.M.U.R +\n\n"
                    "♾ Безлимит • ⚡ Моментальная отправка • 🚀 Полный доступ\n\n"
                    "💬 Контакт: @CERBERUS_IS",
                    {"inline_keyboard":[[{"text":"Меню","callback_data":"menu"}]]})
                answer_cb(cid); continue

            # «✅ ПРОМОКОД ✅»
            if data=='promo':
                send_photo(chat, PROMO_IMG,
                    "💬 Введи ключ, купленный у владельца 💬",
                    {"inline_keyboard":[[{"text":"Меню","callback_data":"menu"}]]})
                STATE[uid] = 'wait_promo'
                answer_cb(cid); continue

            # «👤 Профиль»
            if data=='profile':
                sub = is_sub(uid)
                if sub:
                    d = sub - datetime.utcnow()
                    txt = f"👑 Подписка: ДА ✅\n⌛ Осталось {d.days}д {d.seconds//3600}ч"
                    img = PREM_IMG
                else:
                    txt = "👑 Подписка: НЕТ ❌"
                    img = NO_SUB_IMG
                send_photo(chat, img, txt, profile_kb())
                answer_cb(cid); continue

            # «Меню»
            if data=='menu':
                send_photo(chat,
                    PREM_IMG if is_sub(uid) else NO_SUB_IMG,
                    "Меню", main_kb(uid))
                answer_cb(cid); continue

            # — АДМИНКА —
            if data=='list_sub' and uid in ADMINS:
                now  = datetime.utcnow(); rows=[]
                for u,iso in subs.items():
                    exp = datetime.fromisoformat(iso)
                    if exp<=now: continue
                    info = api('getChat', chat_id=int(u)).get('result',{})
                    name = info.get('first_name','')
                    if info.get('username'):
                        name += f" (@{info['username']})"
                    rows.append(f"{name} — {(exp-now).days}д")
                send_msg(chat, "\n".join(rows) or "Нет подписок", list_users_kb())
                answer_cb(cid); continue

            if data=='gen_key' and uid in ADMINS:
                key = f"{uuid.uuid4().hex[:5]}$&&murmur{uuid.uuid4().hex}"
                promo[key] = True; save(PROMO_FILE, promo)
                send_msg(chat,
                    f"Сгенерирован ключ:\n`{key}`",
                    {"inline_keyboard":[[{"text":"Ещё","callback_data":"gen_key"}]]})
                answer_cb(cid); continue

            if data=='logs' and uid in ADMINS:
                now    = datetime.utcnow(); cutoff=now-timedelta(days=1)
                recs   = []
                for mid,inf in list(anon_messages.items()):
                    ts = datetime.fromisoformat(inf['timestamp'])
                    if ts<cutoff:
                        anon_messages.pop(mid); continue
                    d,mn = ts.day, MONTHS[ts.month]
                    t     = ts.strftime("%H:%M")
                    snd   = inf['from_name']; rcv = inf['to_name']
                    recs.append(f"{d} {mn} {t} | {snd} → {rcv} | {inf['text']}")
                text = "\n".join(recs) if recs else "Нет анонимок за 24 ч"
                for i in range(0,len(text),3800):
                    send_msg(chat, text[i:i+3800])
                answer_cb(cid); continue

    time.sleep(1)
