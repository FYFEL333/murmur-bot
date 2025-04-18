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

# Для форматирования месяцев в логах
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

# ─── JSON ─────────────────────────────────────────────────────────────────
def load(path, default):
    if path.exists():
        raw = path.read_text('utf-8').strip()
        if raw:
            try: 
                return json.loads(raw)
            except json.JSONDecodeError:
                print(f"[WARN] сброс {path.name}")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(default, ensure_ascii=False))
    return default

def save(path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

users         = load(USERS_FILE, {})
subs          = load(SUBS_FILE, {})
promo         = load(PROMO_FILE, {})

# храним данные анонимных сообщений и временно inline‐тексты
anon_messages = {}  # mid → {from_id,from_name,from_username,to_id,to_name,to_username,text,timestamp}
temp_storage  = {}  # from_id → текст inline
STATE         = {}  # from_id → 'wait_promo'

# ─── HTTP / API ──────────────────────────────────────────────────────────
def api(method, **p):
    try:
        return requests.post(API_URL + method, data=p, timeout=15).json()
    except Exception as e:
        print(f"[ERROR api {method}]", e)
        return {}

def get_updates(offset=None):
    try:
        return requests.get(API_URL + 'getUpdates',
                            params={'timeout':15, 'offset':offset},
                            timeout=20).json()
    except Exception as e:
        print('[ERROR get_updates]', e)
        return {}

def send_msg(chat, text, kb=None):
    api('sendMessage',
        chat_id=chat,
        text=text,
        reply_markup=json.dumps(kb) if kb else None)

def send_photo(chat, path, caption="", kb=None):
    try:
        with open(path, 'rb') as f:
            r = requests.post(API_URL + 'sendPhoto',
                data={'chat_id':chat, 'caption':caption,
                      'reply_markup':json.dumps(kb) if kb else ''},
                files={'photo':f}, timeout=20)
            if r.status_code != 200:
                print('[PHOTO ERR]', r.status_code, r.text[:200])
    except Exception as e:
        print('[ERROR send_photo]', e)

def answer_cb(qid, text=""):
    api('answerCallbackQuery',
        callback_query_id=qid,
        text=text,
        show_alert=True)

# ─── ПОДПИСКИ / ЛИМИТЫ ───────────────────────────────────────────────────
def is_sub(uid):
    key = str(uid)
    if key in subs:
        till = datetime.fromisoformat(subs[key])
        if till > datetime.utcnow():
            return till
        subs.pop(key, None)
        save(SUBS_FILE, subs)
    return None

def left_today(uid):
    today = datetime.utcnow().date().isoformat()
    rec = users.get(str(uid))
    if not rec or rec.get("last") != today:
        return FREE_PER_DAY
    return max(0, FREE_PER_DAY - rec.get("today", 0))

def inc_today(uid):
    key = str(uid)
    today = datetime.utcnow().date().isoformat()
    rec = users.setdefault(key, {"today":0, "last":today})
    if rec["last"] != today:
        rec["today"], rec["last"] = 0, today
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

def menu_photo(uid):
    return PREM_IMG if is_sub(uid) else NO_SUB_IMG

# ─── BOT LOOP ────────────────────────────────────────────────────────────
OFFSET = None
print(">>> BOT STARTED <<<")

while True:
    updates = get_updates(OFFSET).get('result', [])
    for upd in updates:
        OFFSET = upd['update_id'] + 1

        # 1) INLINE QUERY
        if 'inline_query' in upd:
            iq    = upd['inline_query']
            qid   = iq['id']
            uid   = iq['from']['id']
            query = iq.get('query','').strip()
            if not query:
                api('answerInlineQuery',
                    inline_query_id=qid,
                    results=json.dumps([]))
                continue
            temp_storage[uid] = query
            result = {
                "type":"article",
                "id":str(uuid.uuid4()),
                "title":"🤫 Анонимное сообщение",
                "description":query,
                "input_message_content":{"message_text":PLACEHOLDER}
            }
            api('answerInlineQuery',
                inline_query_id=qid,
                results=json.dumps([result]),
                cache_time=0)
            continue

        # 2) MESSAGE
        if 'message' in upd:
            m    = upd['message']
            uid  = m['from']['id']
            chat = m['chat']['id']
            txt  = m.get('text','')

            # /start
            if txt == '/start':
                st = is_sub(uid)
                if st:
                    delta = st - datetime.utcnow()
                    caption = f"👑 Подписка ещё {delta.days}д {delta.seconds//3600}ч"
                else:
                    caption = f"Осталось {left_today(uid)}/{FREE_PER_DAY} сообщений"
                send_photo(chat, START_IMG, caption, main_kb(uid))
                continue

            # /admin в личке
            if txt == '/admin' and uid in ADMINS and m['chat']['type']=='private':
                kb = {"inline_keyboard":[
                    [{"text":"ПОЛЬЗОВАТЕЛИ","callback_data":"list_sub"}],
                    [{"text":"КЛЮЧИ","callback_data":"gen_key"}],
                    [{"text":"ЛОГИ","callback_data":"logs"}]
                ]}
                send_msg(chat, "👑 Админ‐панель", kb)
                continue

            # ввод промокода
            if STATE.get(uid) == 'wait_promo':
                code = txt.strip()
                if promo.pop(code, None):
                    till = datetime.utcnow() + timedelta(days=SUB_DAYS)
                    subs[str(uid)] = till.isoformat()
                    save(PROMO_FILE, promo)
                    save(SUBS_FILE, subs)
                    send_msg(chat, "💎 Теперь ты M.U.R.M.U.R + 💎")
                    STATE.pop(uid, None)
                else:
                    send_msg(chat, "❌ Ключ неверен или уже использован.")
                continue

            # inline‐placeholder (reply)
            if txt == PLACEHOLDER and m.get('reply_to_message'):
                if uid not in temp_storage:
                    continue
                payload = temp_storage.pop(uid)
                if not is_sub(uid) and left_today(uid) <= 0:
                    send_msg(chat, "🕐 Лимит исчерпан. Купи подписку.")
                    continue

                src = m['from']
                tgt = m['reply_to_message']['from']
                mid = str(uuid.uuid4())[:8]
                anon_messages[mid] = {
                    'from_id'      : uid,
                    'from_name'    : src.get('first_name',''),
                    'from_username': src.get('username'),
                    'to_id'        : tgt['id'],
                    'to_name'      : tgt.get('first_name',''),
                    'to_username'  : tgt.get('username'),
                    'text'         : payload,
                    'timestamp'    : datetime.utcnow().isoformat()
                }
                if not is_sub(uid):
                    inc_today(uid)

                kb = {"inline_keyboard":[[
                    {"text":"🔓 Посмотреть","callback_data":f"view_{mid}"}
                ]]}
                send_msg(chat,
                    f"🤫 АНОНИМНОЕ СООБЩЕНИЕ ДЛЯ {anon_messages[mid]['to_name']}", kb)
                continue

        # 3) CALLBACK QUERY
        if 'callback_query' in upd:
            cb   = upd['callback_query']
            data = cb['data']
            cid  = cb['id']
            uid  = cb['from']['id']
            chat = cb['message']['chat']['id']

            # просмотр анонимки
            if data.startswith('view_'):
                mid  = data.split('_',1)[1]
                info = anon_messages.get(mid)
                if not info:
                    answer_cb(cid, "❗ Сообщение не найдено.")
                elif uid != info['to_id']:
                    answer_cb(cid, "❗ Это сообщение не для тебя.")
                else:
                    answer_cb(cid, f"✅ Только для тебя ✅\n\n{info['text']}")
                continue

            # подписка
            if data == 'buy':
                send_photo(chat, PLUS_IMG,
                    "Открой весь потенциал анонимности с M.U.R.M.U.R +\n\n"
                    "♾ Безлимит • ⚡ Моментальная отправка • 🚀 Полный доступ\n\n"
                    "💬 Контакт: @CERBERUS_IS",
                    {"inline_keyboard":[[{"text":"Меню","callback_data":"menu"}]]})
                answer_cb(cid)
                continue

            # промокод
            if data == 'promo':
                send_photo(chat, PROMO_IMG,
                    "💬 Введи ключ, купленный у владельца 💬",
                    {"inline_keyboard":[[{"text":"Меню","callback_data":"menu"}]]})
                STATE[uid] = 'wait_promo'
                answer_cb(cid)
                continue

            # профиль
            if data == 'profile':
                st = is_sub(uid)
                if st:
                    days = (st - datetime.utcnow()).days
                    hrs  = ((st - datetime.utcnow()).seconds)//3600
                    txt  = (f"👑 Подписка: M.U.R.M.U.R. + — ДА ✅\n"
                            f"⌛ Истекает через {days}д {hrs}ч")
                    img  = PREM_IMG
                else:
                    txt = "👑 Подписка: M.U.R.M.U.R. + — НЕТ ❌"
                    img = NO_SUB_IMG
                send_photo(chat, img, txt, profile_kb())
                answer_cb(cid)
                continue

            # меню
            if data == 'menu':
                send_photo(chat, menu_photo(uid), "Меню", main_kb(uid))
                answer_cb(cid)
                continue

            # админ: пользователи
            if data == 'list_sub' and uid in ADMINS:
                now  = datetime.utcnow()
                rows = []
                for uid_str, exp_iso in subs.items():
                    exp = datetime.fromisoformat(exp_iso)
                    if exp <= now: continue
                    # получаем профиль через getChat
                    info = api('getChat', chat_id=int(uid_str)).get('result', {})
                    fn = info.get('first_name','')
                    ln = info.get('last_name','')
                    un = info.get('username')
                    name = fn + (' '+ln if ln else '')
                    if un: name += f' (@{un})'
                    days_left = (exp-now).days
                    rows.append(f"{name} — {days_left}д")
                send_msg(uid, "\n".join(rows) or "Нет подписок", list_users_kb())
                answer_cb(cid)
                continue

            # админ: генерация ключей
            if data == 'gen_key' and uid in ADMINS:
                key = f"{uuid.uuid4().hex[:5]}$&&murmur{uuid.uuid4().hex}"
                promo[key] = True; save(PROMO_FILE, promo)
                send_msg(uid,
                    f"Сгенерирован ключ:\n`{key}`",
                    {"inline_keyboard":[[{"text":"Еще","callback_data":"gen_key"}]]})
                answer_cb(cid)
                continue

            # админ: логи с датой и временем
            if data == 'logs' and uid in ADMINS:
                now    = datetime.utcnow()
                cutoff = now - timedelta(days=1)
                records = []
                for mid, info in list(anon_messages.items()):
                    ts = datetime.fromisoformat(info['timestamp'])
                    if ts < cutoff:
                        anon_messages.pop(mid)
                        continue
                    day   = ts.day
                    month = MONTHS[ts.month]
                    time_str = ts.strftime("%H:%M")
                    timestamp_str = f"{day} {month} {time_str}"
                    # отправитель
                    sender = info['from_name']
                    if info.get('from_username'):
                        sender += f" (@{info['from_username']})"
                    # получатель
                    receiver = info['to_name']
                    if info.get('to_username'):
                        receiver += f" (@{info['to_username']})"
                    records.append(
                        f"{timestamp_str} | {sender} → {receiver} | {info['text']}"
                    )
                msg = "\n".join(records) if records else "Нет анонимок за 24 ч"
                for chunk in [msg[i:i+4000] for i in range(0,len(msg),4000)]:
                    send_msg(uid, chunk)
                answer_cb(cid)
                continue

    time.sleep(1)
