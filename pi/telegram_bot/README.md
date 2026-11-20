# Temporary interactive Telegram bot

This is an optional operator tool. It is deliberately isolated from the production inference runtime and is **not installed or enabled by the normal Pi installer**.

Run manually from the repository root:

```bash
./pi/telegram_bot/run.sh
```

On a Pi, setup can instead install the separate systemd unit by selecting the Telegram option together with Pi services, or with `--telegram-bot`. The normal node service does not depend on the bot.

It uses the same repository-root `.env` as the node runtime (`BOT_TOKEN`, `PRIMARY_CHAT_ID`, and `ALLOWED_CHAT_IDS`). The setup wizard writes credentials there with mode `0600`; no Telegram-specific environment file is created.

When an uploaded photo crosses the configured threat confidence threshold, the bot submits a **test incident plus the annotated JPEG** to the backend in one authenticated request. The incident description is marked `TEST — submitted through the Telegram bot; not a live sensor event.` The backend persists the image and incident together, then broadcasts the incident to Android. Photos that do not cross a threat threshold are returned to Telegram only and do not create Android incidents. This path never invokes deterrence. It requires the backend V10 evidence migration.

An optional systemd unit template is provided as `awarespan-bot.service`. To install it, run `scripts/install-telegram-bot.sh`; it renders `%USER%`, `%WORKDIR%`, `%PYTHON%`, and `%ENV_FILE%`, then starts a separate unit which explicitly reads the same `.env` selected during setup (root `.env` by default). The main node installer does not enable this bot automatically.

Removing this directory and its optional service must not affect inference, backend synchronization, MQTT, or the power monitor.
