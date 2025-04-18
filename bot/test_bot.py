# test_bot.py  ───────────────────────────────
import requests, json, time
TOKEN = '7662219387:AAGu2fAicy4IliDLTw81ThfCVFY8BEQ45Cg'
URL   = f'https://api.telegram.org/bot{TOKEN}/'

def tg(method, **p):
    try:
        r = requests.post(URL+method, data=p, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print('[ERROR]', e)
        return {}

print('1) Проверяем токен...')
print(json.dumps(tg('getMe'), indent=2, ensure_ascii=False))

print('\n2) Пробуем получить обновления (30 сек)...')
offset = None
t0 = time.time()
while time.time() - t0 < 30:
    upd = tg('getUpdates', offset=offset, timeout=5)
    print('→', upd)
    for u in upd.get('result', []):
        offset = u['update_id'] + 1
    time.sleep(2)
print('Тест завершён')
# ────────────────────────────────────────────
