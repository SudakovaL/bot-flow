"""Безопасные tools ИИ-консультанта.

Нет shell, subprocess, произвольного доступа к файлам, выполнения кода и SQL.
Читать можно только *.md внутри knowledge/.
"""
import re
from pathlib import Path

import db

KNOWLEDGE_DIR = (Path(__file__).resolve().parent.parent / "knowledge").resolve()
ALLOWED_SUFFIX = ".md"
MAX_FILE_CHARS = 8000


class ToolError(Exception):
    pass


def _safe_knowledge_path(filename: str) -> Path:
    """Проверяет имя файла и возвращает путь строго внутри knowledge/."""
    if not isinstance(filename, str) or not filename.strip():
        raise ToolError("нужно имя файла из knowledge/, например services.md")
    name = filename.strip()
    if ("/" in name or "\\" in name or ".." in name or ":" in name
            or "\x00" in name or name.startswith(".")):
        raise ToolError("доступ запрещён, можно читать только файлы базы знаний по имени")
    path = (KNOWLEDGE_DIR / name).resolve()
    if path.parent != KNOWLEDGE_DIR or path.suffix != ALLOWED_SUFFIX or not path.is_file():
        raise ToolError("такого файла в базе знаний нет")
    return path


def list_knowledge_files() -> list[str]:
    return sorted(p.name for p in KNOWLEDGE_DIR.glob(f"*{ALLOWED_SUFFIX}"))


def sections(text: str) -> list[tuple[str, str]]:
    """Делит markdown на разделы «## Заголовок»."""
    out = []
    for part in re.split(r"(?m)^## ", text)[1:]:
        title, _, body = part.partition("\n")
        out.append((title.strip(), body.strip()))
    return out


def _stem(word: str) -> str:
    return word[:5]


# Слова пользователя -> слова, которые реально встречаются в базе знаний.
_TIME = {"срок", "сроки", "сроко", "срока"}
_PRICE = {"цена", "цены", "цену", "стоим", "стоит"}
SYNONYMS = {
    **{k: _TIME for k in ("време", "долго", "быстр", "длитс", "длить", "когда", "выпол", "готов")},
    **{k: _PRICE for k in ("дорог", "дешев", "оплат", "цены", "цену", "рубле", "рубли", "денег", "прайс", "сумма", "суммы", "сумму", "тариф", "плати", "минис", "миним")},
}


def _expand(words: set[str]) -> set[str]:
    out = set(words)
    for w in words:
        out |= SYNONYMS.get(w, set())
    return out


def services_summary() -> str:
    """Сводка «услуга: цена; срок» по всем услугам из services.md."""
    text = (KNOWLEDGE_DIR / "services.md").read_text(encoding="utf-8")
    lines = []
    for title, body in sections(text):
        facts = [ln.lstrip("- ").strip() for ln in body.splitlines()
                 if ln.lstrip("- ").startswith(("Цена", "Срок"))]
        lines.append(f"- {title}: " + "; ".join(facts))
    return "\n".join(lines)


def search_knowledge(query: str) -> str:
    """Ищет разделы в knowledge/ по словам запроса."""
    raw = {_stem(w) for w in re.findall(r"\w{3,}", str(query).lower())}
    words = _expand(raw)
    asks_price_or_time = bool(raw & (_PRICE | _TIME)) or words != raw
    summary = ("Сводка цен и сроков по всем услугам (из services.md):\n" + services_summary()
               + "\n\n") if asks_price_or_time else ""
    if not words:
        return "Пустой запрос. Файлы базы знаний: " + ", ".join(list_knowledge_files())
    scored = []
    for name in list_knowledge_files():
        text = (KNOWLEDGE_DIR / name).read_text(encoding="utf-8")
        for title, body in sections(text):
            hay = {_stem(w) for w in re.findall(r"\w{3,}", (title + " " + body).lower())}
            score = len(words & hay)
            if score:
                scored.append((score, name, title, body))
    if not scored:
        return summary or "Ничего не найдено в базе знаний."
    scored.sort(key=lambda x: -x[0])
    return summary + "\n\n".join(f"[{n}] {t}\n{b}" for _, n, t, b in scored[:4])


def read_knowledge_file(filename: str) -> str:
    try:
        return _safe_knowledge_path(filename).read_text(encoding="utf-8")[:MAX_FILE_CHARS]
    except ToolError as exc:
        return f"Отказ: {exc}"


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_TG = re.compile(r"(?<![\w@])@[A-Za-z][A-Za-z0-9_]{3,31}\b|t\.me/[A-Za-z][A-Za-z0-9_]{3,31}")
_PHONE = re.compile(r"(?<![\w.])\+?\d[\d\s\-()]{8,}\d(?!\d)")


def extract_contact(text: str) -> str:
    """Находит в тексте телефон, Telegram (@имя) или email. Нет контакта — пустая строка."""
    text = str(text or "")
    m = _EMAIL.search(text)
    if m:
        return m.group(0)
    m = _TG.search(text)
    if m:
        return m.group(0)
    for m in _PHONE.finditer(text):
        if 10 <= len(re.sub(r"\D", "", m.group(0))) <= 15:
            return m.group(0).strip()
    return ""


def prepare_lead_draft(service: str = "", contact: str = "", problem_text: str = "",
                       known_info: str = "", missing_info: str = "") -> dict:
    """Только формирует черновик. В базу ничего не пишет."""
    draft = {
        "service": str(service or "").strip()[:200],
        "contact": extract_contact(contact),
        "problem_text": str(problem_text or "").strip()[:1000],
        "known_info": str(known_info or "").strip()[:500],
        "missing_info": str(missing_info or "").strip()[:500],
    }
    if str(contact or "").strip() and not draft["contact"]:
        draft["missing_info"] = ", ".join(filter(None, [
            draft["missing_info"], "контакт указан неверно (нужен телефон, @telegram или email с @)"]))
    lacking = [label for key, label in
               (("service", "услуга"), ("contact", "контакт"), ("problem_text", "описание задачи"))
               if not draft[key]]
    if lacking:
        have = draft["missing_info"].lower()
        draft["missing_info"] = ", ".join(filter(None, [
            draft["missing_info"], *[x for x in lacking if x.split()[0] not in have]]))
    draft["complete"] = not lacking
    return draft


def save_confirmed_lead(session_id: str, draft: dict, user_confirmed: bool) -> int:
    """Сохраняет заявку от ИИ. Работает только при явном подтверждении пользователя."""
    if user_confirmed is not True:
        raise PermissionError("Заявка не подтверждена пользователем")
    if not draft or not draft.get("complete"):
        raise ValueError("В черновике не хватает данных")
    return db.save_lead(
        session_id=session_id, source="ai_consultant",
        service=draft["service"], contact=draft["contact"],
        problem_text=draft["problem_text"],
        agent_summary=draft.get("known_info") or None,
        missing_info=draft.get("missing_info") or None,
    )


# Эти три tool видит модель. save_confirmed_lead модели НЕ выдаётся:
# его вызывает только приложение после нажатия кнопки «Отправить заявку».
TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "search_knowledge",
        "description": "Поиск по базе знаний мастерской (услуги, FAQ, правила).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "read_knowledge_file",
        "description": "Прочитать файл базы знаний целиком: services.md, faq.md или rules.md.",
        "parameters": {"type": "object", "properties": {"filename": {"type": "string"}},
                       "required": ["filename"]}}},
    {"type": "function", "function": {
        "name": "prepare_lead_draft",
        "description": "Подготовить черновик заявки. Ничего не сохраняет.",
        "parameters": {"type": "object", "properties": {
            "service": {"type": "string"}, "contact": {"type": "string"},
            "problem_text": {"type": "string"}, "known_info": {"type": "string"},
            "missing_info": {"type": "string"}}, "required": []}}},
]

LLM_TOOLS = {
    "search_knowledge": search_knowledge,
    "read_knowledge_file": read_knowledge_file,
    "prepare_lead_draft": prepare_lead_draft,
}
