"""Обычный сценарный бот. Работает без LLM: тексты берутся из knowledge/."""
import logging
from dataclasses import dataclass, field

import db
from agent import tools

log = logging.getLogger("bot_flow")

MAX_TEXT = 1000

MENU = [
    {"label": "Услуги", "action": "services"},
    {"label": "FAQ", "action": "faq"},
    {"label": "Оставить заявку", "action": "lead"},
    {"label": "ИИ-консультант", "action": "ai"},
    {"label": "Обратная связь", "action": "feedback"},
]
BACK = [{"label": "В меню", "action": "menu"}]


@dataclass
class Session:
    id: str
    mode: str = "menu"          # menu | lead | feedback | ai
    step: str = ""              # шаг обычной заявки
    lead: dict = field(default_factory=dict)
    ai_history: list = field(default_factory=list)
    draft: dict | None = None   # черновик заявки от ИИ (в БД не попадает до подтверждения)


SESSIONS: dict[str, Session] = {}


def get_session(session_id: str) -> Session:
    if session_id not in SESSIONS:
        if len(SESSIONS) > 1000:  # простая защита от разрастания памяти
            SESSIONS.clear()
        SESSIONS[session_id] = Session(id=session_id)
    return SESSIONS[session_id]


def reply(text, buttons=None) -> dict:
    return {"messages": [text], "buttons": buttons if buttons is not None else []}


def _knowledge(filename: str):
    return tools.sections((tools.KNOWLEDGE_DIR / filename).read_text(encoding="utf-8"))


def service_names() -> list[str]:
    return [title for title, _ in _knowledge("services.md")]


def reset(s: Session) -> None:
    s.mode, s.step, s.lead, s.draft, s.ai_history = "menu", "", {}, None, []


def main_menu(s: Session) -> dict:
    reset(s)
    return reply("Здравствуйте! Это мастерская «Тихий сервис»: ремонт ноутбуков и компьютеров. "
                 "Что вас интересует?", MENU)


def show_services(s: Session) -> dict:
    s.mode = "menu"
    text = "\n\n".join(f"{title}\n{body}" for title, body in _knowledge("services.md"))
    return reply(text, [{"label": "Оставить заявку", "action": "lead"}] + BACK)


def show_faq(s: Session, category: str | None = None) -> dict:
    s.mode = "menu"
    cats = _knowledge("faq.md")
    if category is None:
        buttons = [{"label": t, "action": f"faq:{i}"} for i, (t, _) in enumerate(cats)]
        return reply("Выберите тему:", buttons + BACK)
    try:
        title, body = cats[int(category)]
    except (ValueError, IndexError):
        return show_faq(s)
    buttons = [{"label": "Другие темы", "action": "faq"}] + BACK
    return reply(f"{title}\n\n{body}", buttons)


def start_lead(s: Session) -> dict:
    reset(s)
    s.mode, s.step = "lead", "service"
    buttons = [{"label": n, "action": f"service:{i}"} for i, n in enumerate(service_names())]
    return reply("Оставим заявку. Выберите услугу:", buttons + [{"label": "Отмена", "action": "menu"}])


def choose_service(s: Session, index: str) -> dict:
    names = service_names()
    if s.mode != "lead" or s.step != "service":
        return start_lead(s)
    try:
        s.lead["service"] = names[int(index)]
    except (ValueError, IndexError):
        return start_lead(s)
    s.step = "problem"
    return reply(f"Услуга: {s.lead['service']}.\nКоротко опишите, что случилось с устройством.",
                 [{"label": "Отмена", "action": "menu"}])


def start_feedback(s: Session) -> dict:
    reset(s)
    s.mode = "feedback"
    return reply("Напишите отзыв или пожелание одним сообщением. Личные данные указывать не нужно.",
                 [{"label": "Отмена", "action": "menu"}])


def confirm_lead(s: Session) -> dict:
    if s.mode != "lead" or s.step != "confirm":
        return main_menu(s)
    lead = s.lead
    db.save_lead(s.id, "bot_flow", lead["service"], lead["contact"], lead["problem"])
    log.info("lead saved source=bot_flow")
    reset(s)
    return reply("Заявка принята. Мы свяжемся с вами по указанному контакту.", BACK)


def handle_action(s: Session, action: str) -> dict | None:
    """Возвращает ответ или None, если действие не относится к bot-flow."""
    if action == "menu":
        return main_menu(s)
    if action == "services":
        return show_services(s)
    if action == "faq":
        return show_faq(s)
    if action.startswith("faq:"):
        return show_faq(s, action[4:])
    if action == "lead":
        return start_lead(s)
    if action.startswith("service:"):
        return choose_service(s, action[8:])
    if action == "lead_send":
        return confirm_lead(s)
    if action == "feedback":
        return start_feedback(s)
    return None


def handle_text(s: Session, text: str) -> dict:
    text = text.strip()[:MAX_TEXT]
    if not text:
        return reply("Напишите сообщение или выберите пункт меню.", MENU)
    if s.mode == "feedback":
        db.save_feedback(s.id, text)
        log.info("feedback saved")
        reset(s)
        return reply("Спасибо за отзыв! Он сохранён.", BACK)
    if s.mode == "lead" and s.step == "problem":
        s.lead["problem"] = text
        s.step = "contact"
        return reply("Как с вами связаться? Напишите телефон, Telegram или email.",
                     [{"label": "Отмена", "action": "menu"}])
    if s.mode == "lead" and s.step == "contact":
        s.lead["contact"] = text
        s.step = "confirm"
        lead = s.lead
        summary = (f"Проверьте заявку:\nУслуга: {lead['service']}\n"
                   f"Задача: {lead['problem']}\nКонтакт: {lead['contact']}")
        return reply(summary, [{"label": "Отправить заявку", "action": "lead_send"},
                               {"label": "Отмена", "action": "menu"}])
    if s.mode == "lead" and s.step == "service":
        return reply("Выберите услугу кнопкой ниже.",
                     [{"label": n, "action": f"service:{i}"} for i, n in enumerate(service_names())])
    return reply("Выберите пункт меню:", MENU)
