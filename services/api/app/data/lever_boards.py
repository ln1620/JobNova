"""Curated Lever company slugs with public postings API enabled.

Not all of these will have active postings at any given time, but
_fetch_lever_jobs() in lever_discovery.py silently returns [] for any slug
that 404s or errors, so listing more candidates than are currently active
is harmless and increases the chance of matches across different job
titles/locations.
"""

LEVER_BOARDS: list[dict[str, str]] = [
    {"slug": "palantir", "company": "Palantir"},
    {"slug": "plaid", "company": "Plaid"},
    {"slug": "netflix", "company": "Netflix"},
    {"slug": "affirm", "company": "Affirm"},
    {"slug": "lever", "company": "Lever"},
    {"slug": "box", "company": "Box"},
    {"slug": "brex", "company": "Brex"},
    {"slug": "carta", "company": "Carta"},
    {"slug": "clari", "company": "Clari"},
    {"slug": "coursera", "company": "Coursera"},
    {"slug": "eventbrite", "company": "Eventbrite"},
    {"slug": "figma", "company": "Figma"},
    {"slug": "iterable", "company": "Iterable"},
    {"slug": "klaviyo", "company": "Klaviyo"},
    {"slug": "lattice", "company": "Lattice"},
    {"slug": "mixpanel", "company": "Mixpanel"},
    {"slug": "newrelic", "company": "New Relic"},
    {"slug": "nuro", "company": "Nuro"},
    {"slug": "opendoor", "company": "Opendoor"},
    {"slug": "outreach", "company": "Outreach"},
    {"slug": "ramp", "company": "Ramp"},
    {"slug": "remote", "company": "Remote"},
    {"slug": "scaleai", "company": "Scale AI"},
    {"slug": "sofi", "company": "SoFi"},
    {"slug": "spotinst", "company": "Spot"},
    {"slug": "squarespace", "company": "Squarespace"},
    {"slug": "stripe", "company": "Stripe"},
    {"slug": "tanium", "company": "Tanium"},
    {"slug": "thumbtack", "company": "Thumbtack"},
    {"slug": "twitch", "company": "Twitch"},
    {"slug": "vercel", "company": "Vercel"},
    {"slug": "webflow", "company": "Webflow"},
    {"slug": "wish", "company": "Wish"},
    {"slug": "zapier", "company": "Zapier"},
    {"slug": "zendesk", "company": "Zendesk"},
    {"slug": "zscaler", "company": "Zscaler"},
]

LEVER_JOBS_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"
