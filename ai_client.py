"""Тонкий слой над OpenAI-совместимым API (AI Studio). Ключ берётся только из окружения.

Основные переменные: AI_API_KEY, AI_BASE_URL, AI_MODEL.
Для Yandex AI Studio также понимаются YANDEX_CLOUD_API_KEY, YANDEX_CLOUD_FOLDER,
YANDEX_CLOUD_MODEL (например «yandexgpt-lite/latest»).
"""
import logging
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # .env тогда читается самим окружением
    pass
log = logging.getLogger("ai_client")

YANDEX_BASE_URL = "https://llm.api.cloud.yandex.net/v1"
YANDEX_KEY_VARS = ("YANDEX_CLOUD_API_KEY", "YANDEX_AI_API_KEY")


class AIUnavailable(Exception):
    """ИИ не настроен или временно недоступен. Обычный bot-flow от этого не зависит."""


def _env(name: str) -> str:
    value = os.getenv(name, "").strip().strip('"').strip("'")
    # значения вида <ваш ключ> — это незаполненный шаблон
    return "" if value.startswith("<") else value


def _yandex_key() -> str:
    return next((v for v in map(_env, YANDEX_KEY_VARS) if v), "")


def api_key() -> str:
    return _env("AI_API_KEY") or _yandex_key()


def base_url() -> str:
    if _env("AI_BASE_URL"):
        return _env("AI_BASE_URL")
    return YANDEX_BASE_URL if not _env("AI_API_KEY") and _yandex_key() else ""


def model_name() -> str:
    model = _env("AI_MODEL") or _env("YANDEX_CLOUD_MODEL")
    folder = _env("YANDEX_CLOUD_FOLDER")
    if model and "://" not in model and folder and base_url() == YANDEX_BASE_URL:
        return f"gpt://{folder}/{model}"
    return model


def is_configured() -> bool:
    return bool(api_key() and model_name())


def chat(messages: list, tools: list | None = None):
    """Один запрос к модели. Возвращает message (с .content и .tool_calls)."""
    if not is_configured():
        raise AIUnavailable("ключ или модель ИИ не заданы")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key(), base_url=base_url() or None, timeout=30, max_retries=1)
        kwargs = {"model": model_name(), "messages": messages, "temperature": 0.2}
        if tools:
            kwargs["tools"] = tools
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message
    except Exception as exc:  # ключ и тексты запроса не логируем
        log.warning("AI request failed: %s", type(exc).__name__)
        raise AIUnavailable(type(exc).__name__) from exc
