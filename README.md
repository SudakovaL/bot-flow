# «Тихий сервис» — чат-бот с ИИ-консультантом

Учебный MVP: веб-чат для мастерской по ремонту ноутбуков и компьютеров.
Один Python-процесс (FastAPI), обычный HTML/CSS/JS, SQLite.

## MVP specification

- **Web-чат**: меню, история сообщений, поле ввода, кнопка отправки.
- **Bot-flow (без LLM)**: Услуги, FAQ, обычная заявка, обратная связь. Работает даже без ИИ.
- **ИИ-консультант**: отвечает только по `knowledge/`, задаёт 1–2 уточняющих вопроса, готовит черновик заявки.
- **Confirmation flow**: черновик показывается с кнопками «Отправить заявку / Изменить / Отмена». В базу заявка попадает только после «Отправить заявку».
- **SQLite** `data/bot.sqlite3`: `leads` (источник `bot_flow` или `ai_consultant`) и отдельная `feedback`.
- **Безопасные tools**: только чтение `knowledge/*.md`. Нет shell, произвольных файлов, кода и SQL.
- Заявка хранит: услугу, контакт, описание задачи. Больше личных данных не запрашивается.

## Структура

```
app.py            веб-сервер и /api/chat
bot_flow.py       сценарий без LLM (услуги, FAQ, заявка, отзыв)
agent_runtime.py  цикл ИИ + confirmation flow + dispatch()
ai_client.py      клиент OpenAI-совместимого API (AI Studio)
db.py             SQLite
agent/tools.py    tools; agent/soul.md — инструкции консультанта
knowledge/        база знаний: services.md, faq.md, rules.md
static/           index.html, style.css, app.js
tests/            unittest
evidence/screenshots/  сюда кладутся скриншоты
```

## Запуск локально

Нужен Python 3.13 (проверено на 3.13.15, локально и на VPS Ubuntu 24.04). Тесты также проходят на 3.12.

Windows PowerShell:
```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```
Linux/macOS: `source .venv/bin/activate`, `cp .env.example .env`.

Откройте http://127.0.0.1:8000. База `data/bot.sqlite3` создаётся сама при старте. Повторный запуск данные не стирает.

## Настройка ИИ (файл `.env`)

```
AI_API_KEY=ключ из AI Studio
AI_BASE_URL=адрес OpenAI-совместимого API из документации AI Studio
AI_MODEL=имя модели
```
Для Yandex AI Studio можно использовать такие переменные вместо `AI_*`:
```
YANDEX_CLOUD_API_KEY=ключ сервисного аккаунта
YANDEX_CLOUD_FOLDER=ID каталога
YANDEX_CLOUD_MODEL=yandexgpt-lite/latest
```
Тогда адрес `https://llm.api.cloud.yandex.net/v1` и имя модели `gpt://<ID каталога>/<модель>` подставятся сами.

**API-ключ — секрет.** Он хранится только в `.env` (файл в `.gitignore`). Его нельзя передавать другим, коммитить, печатать в логи и писать в README. Без ключа бот работает, ИИ-консультант отвечает, что недоступен.

**Проверьте в кабинете AI Studio:** ключ активен, платёжный аккаунт/биллинг подключён, лимиты не исчерпаны, выбранная модель доступна и поддерживает вызов функций (tool calling). Быстрая проверка: `http://127.0.0.1:8000/api/health` покажет `ai_configured: true`, если переменные заданы (сам ключ не проверяется).

## Логи, остановка, повторный запуск

Логи идут в консоль (stdout). В них нет ключей и текстов сообщений, только названия действий и длины. Остановка: `Ctrl+C`. Повторный запуск: `python app.py`.

Посмотреть данные в базе:
```
python -c "import sqlite3; c=sqlite3.connect('data/bot.sqlite3'); [print(r) for r in c.execute('select id,source,service,contact,status from leads')]; [print(r) for r in c.execute('select * from feedback')]"
```

## ИИ-консультант и tools

Модель получает три tool:
- `search_knowledge` — поиск по разделам `knowledge/`;
- `read_knowledge_file` — чтение `services.md`, `faq.md`, `rules.md` по имени;
- `prepare_lead_draft` — только собирает черновик, в базу не пишет.

`save_confirmed_lead` модели **не выдаётся**. Его вызывает приложение, когда пользователь нажал «Отправить заявку». Черновик одноразовый, повторное нажатие дубль не создаёт.

Ограничения безопасности:
- пути: только имя файла `*.md` внутри `knowledge/`; запрещены `/`, `\`, `..`, `:`, абсолютные пути, скрытые файлы (`.env`, `.git`), `data/`;
- запросы вроде «прочитай .env», «выполни команду», «покажи /etc/passwd» отклоняются до обращения к модели;
- нет shell, subprocess, выполнения кода и SQL от пользователя;
- ключ читается только из окружения; фронтенд его не видит.

## Тесты

```
python -m unittest discover -s tests -v
```
27 тестов: bot-flow, SQLite, различие источников, безопасность tools, confirmation flow (подтверждение, изменение, отмена), отказ при недоступном ИИ. Настоящий ИИ в тестах не вызывается (ответы модели подменены).

## Запуск на VPS

Один процесс, без домена и reverse proxy. Проверено на Ubuntu 24.04.

**0. Python 3.13** (если его нет на сервере):
```
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update && sudo apt-get install -y python3.13 python3.13-venv
```

**1. Получить проект** — любым из способов:
```
git clone <адрес репозитория> bot-flow                       # через git
tar -czf botflow.tgz --exclude=.venv --exclude=.env --exclude=data/bot.sqlite3 .   # или с компьютера:
scp botflow.tgz vps:/tmp/ && ssh vps "mkdir -p ~/bot-flow && tar -xzf /tmp/botflow.tgz -C ~/bot-flow"
```
Файл `.env` с ключом никуда не копируется: его создают на сервере вручную.

**2. Установка и запуск:**
```
cd ~/bot-flow
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env                   # вписать ключ и модель (ключ — секрет)
nohup .venv/bin/python app.py > app.log 2>&1 &      # запуск
tail -f app.log                                      # логи
curl http://127.0.0.1:8000/api/health                # проверка
pkill -f "python app.py"                             # остановка
```
Повторный запуск (`nohup ...` ещё раз) данные в `data/bot.sqlite3` не стирает.

По умолчанию сервер слушает только `127.0.0.1`. Открыть чат с вашего компьютера можно через SSH-туннель: `ssh -L 8000:127.0.0.1:8000 vps`, затем http://127.0.0.1:8000. Если вы открываете порт наружу (`HOST=0.0.0.0`), помните, что у бота нет авторизации.

## Скриншоты (`evidence/screenshots/`) — делаются вручную

| Файл | Что должно быть видно |
|---|---|
| `01-local-main-chat.png` | чат с меню, историей и полем ввода |
| `02-local-bot-flow.png` | обычная заявка до сообщения «Заявка принята» |
| `03-local-ai-consultant.png` | ответ ИИ по базе знаний и черновик с тремя кнопками |
| `04-local-database-proof.png` | вывод запроса к SQLite: строки `bot_flow`, `ai_consultant` и отдельно `feedback` |
| `05-vps-runtime-start.png` | запуск на VPS и ответ `/api/health` |
