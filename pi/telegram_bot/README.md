# Temporary interactive Telegram bot

This is an optional operator tool. It is deliberately isolated from the production inference runtime and is **not installed or enabled by the normal Pi installer**.

Run manually from the repository root:

```bash
./pi/telegram_bot/run.sh
```

It uses the existing Telegram environment settings (`BOT_TOKEN`, `PRIMARY_CHAT_ID`, and any allowed-chat configuration). Keep credentials in the external node environment file; never put them in this directory or commit them.

An optional systemd unit template is provided as `awarespan-bot.service`. To install it manually, render `%USER%`, `%WORKDIR%`, and `%PYTHON%` for the target machine, copy it to `/etc/systemd/system/`, then explicitly enable it. The production installer does not do this.

Removing this directory and its optional service must not affect inference, backend synchronization, MQTT, or the power monitor.
