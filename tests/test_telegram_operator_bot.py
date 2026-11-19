"""Access-control contract tests for the optional Telegram operator bot."""
from pi.telegram_bot.bot import TelegramOperatorBot


VALID_TEST_TOKEN = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_1234567890"


def _bot(token=VALID_TEST_TOKEN, allowed=None):
    bot = TelegramOperatorBot.__new__(TelegramOperatorBot)
    bot.bot_token = token
    bot.allowed_chats = set(allowed or [])
    return bot


def test_bot_accepts_valid_token_and_explicit_numeric_allowlist():
    bot = _bot(allowed={"123456789", "-1001234567890"})
    assert bot.validate_configuration() is True


def test_bot_refuses_missing_or_malformed_token():
    assert _bot(token="").validate_configuration() is False
    assert _bot(token="not-a-telegram-token", allowed={"123456789"}).validate_configuration() is False


def test_bot_refuses_empty_allowlist():
    assert _bot(allowed=set()).validate_configuration() is False


def test_bot_refuses_non_numeric_allowlist_entries():
    assert _bot(allowed={"123456789", "not-a-chat-id"}).validate_configuration() is False
