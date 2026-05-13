import os

# Tests must never reach OpenAI or HubSpot. Force stub CRM + a dummy key so
# config loading succeeds without a real .env present.
os.environ.setdefault("CRM_PROVIDER", "stub")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("DB_URL", "sqlite+aiosqlite:///:memory:")
