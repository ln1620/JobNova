"""Curated Greenhouse public board tokens for demo job discovery."""

GREENHOUSE_BOARDS: list[dict[str, str]] = [
    {"token": "stripe", "company": "Stripe"},
    {"token": "figma", "company": "Figma"},
    {"token": "notion", "company": "Notion"},
    {"token": "discord", "company": "Discord"},
    {"token": "databricks", "company": "Databricks"},
    {"token": "robinhood", "company": "Robinhood"},
    {"token": "coinbase", "company": "Coinbase"},
    {"token": "plaid", "company": "Plaid"},
    {"token": "brex", "company": "Brex"},
    {"token": "airbnb", "company": "Airbnb"},
    {"token": "dropbox", "company": "Dropbox"},
    {"token": "gitlab", "company": "GitLab"},
    {"token": "hashicorp", "company": "HashiCorp"},
    {"token": "mongodb", "company": "MongoDB"},
    {"token": "cloudflare", "company": "Cloudflare"},
]

GREENHOUSE_JOBS_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
