# Household Portal

A private landing page for everything to do with the house: recipes, bills,
property info, how-to pages, and the links everyone keeps hunting for.

Built to be self-hosted on your own server. It is a single Python app with a
SQLite database — one file to back up, no external services, no subscriptions.
It works with no internet access at all except for weather.

---

## What is in it

**Home** — a greeting, current conditions at each property, what is due to be
paid, pinned links, essential pages, and what has changed recently.

**Places** — one page per property. NOAA weather and active watches/warnings,
indoor sensor readings, and a table of the things nobody remembers: wifi
password, water shutoff, trash day, gate codes. Anything marked sensitive stays
masked until you click it.

**Money** — the part that replaces a spreadsheet.
- *This month*: every bill with its amount, due date, and a **Pay** button that
  goes straight to that company's payment page. Tick them off as you go.
- *Bills & payments*: the companies you pay, with per-company history so a
  utility that has been creeping up is obvious.
- *Accounts*: savings, TSP, anything owed. Each balance you record is kept with
  its date, so you get change-over-time and a net worth figure.
- *Recurring*: pay, child support, transfers into savings.
- *Forecast*: projects cash and net worth forward, and warns you if more is
  going out than coming in.
- Import an existing spreadsheet, export everything back to `.xlsx` at any time.

**Recipes** — scale any recipe to a different number of servings and the
quantities rewrite themselves as proper fractions (`1½ lb`, not `1.5`). "Salt to
taste" stays as it is. Nutrition fills in for any ingredient linked to the food
table, and tells you honestly what it could not count. Tick ingredients off as
you cook. Build one shopping list from several recipes.

**How-to & info** — wiki-style pages in Markdown, with categories, tags, and full
revision history. Nothing is ever overwritten for good.

**Essentials** — pages marked essential collect into one place and print
cleanly: the set someone would need to keep the house running if you were not
around.

**Appearance** — eight themes, eight font choices, three text sizes. Everyone
can pick their own look, or follow the household default.

---

## Getting it running

### On a server (the real thing)

```bash
git clone <this-repo> /opt/household-portal
cd /opt/household-portal
sudo bash deploy/install.sh
```

That installs dependencies, creates the database and a service account, writes
an `.env` with a fresh secret key, loads starter content, and sets up a systemd
service on port 8000.

Then edit `/opt/household-portal/.env` (see **Sign-in** below) and
`sudo systemctl restart household-portal`.

To put it on a domain with HTTPS, see `deploy/nginx.conf.example`. On a LAN you
can skip nginx — change `--bind` in the service file to `0.0.0.0:8000`.

### On your own machine (to try it out)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then set SECRET_KEY and LOCAL_PASSWORD
.venv/bin/python run.py
```

Open <http://localhost:8000>. Load the starter content with
`.venv/bin/flask --app wsgi seed`.

---

## Sign-in

Two modes, set by `AUTH_MODE` in `.env`.

### Google (what you want in the end)

1. Go to <https://console.cloud.google.com/apis/credentials>.
2. Create an OAuth client ID, type **Web application**.
3. Under *Authorized redirect URIs* add exactly:
   `https://your-domain/auth/callback`
   (or `http://localhost:8000/auth/callback` while testing).
4. Put the client ID and secret in `.env`.
5. List the household's Google addresses in `ALLOWED_EMAILS`.
6. Restart.

The first person to sign in becomes the admin. After that, admins invite people
under **Settings → People** — adding an address there is the invitation, so
nobody needs to be in `ALLOWED_EMAILS`. Keep your own address there anyway; it
is how you get back in if you ever lock yourself out.

Anyone not on the list gets a polite "not on the list" page, and the attempt is
logged.

### Shared password (to get going quickly)

```
AUTH_MODE=local
LOCAL_PASSWORD=something-long
```

One shared login, no Google account needed. Fine on a home network. Set up
Google before exposing the portal to the internet.

---

## Weather

Comes from NOAA's National Weather Service API. It is free, needs no key, and
asks only that you put a contact address in `NWS_USER_AGENT`.

Each place needs a latitude and longitude — an address is not enough. Right-click
the spot in Google Maps and the first line of the menu is the coordinates; paste
them into the place's edit page. Four decimal places is plenty.

You get current conditions from the nearest station, a multi-day forecast, and
any active watches or warnings, which is the point of using NOAA rather than a
generic weather API — a hurricane warning for Palacios shows at the top of the
page.

Responses are cached for 20 minutes. If weather.gov is unreachable the portal
keeps showing the last good reading with a note, rather than breaking.

To warm the cache so the dashboard is instant:

```bash
flask --app wsgi refresh-weather
```

---

## Indoor sensors

Add sensors on a place's page. Four kinds:

- **Manual** — type the number in. Always works.
- **Home Assistant** — reads an entity from your Home Assistant instance. If
  your thermostat is already in Home Assistant, this is the easiest route.
- **Any JSON URL** — give it a URL and a dotted path to the value.
- **Ecobee** — not wired up yet. See `docs/integrations.md`.

To keep them updating, run this from cron every 15 minutes:

```bash
*/15 * * * * cd /opt/household-portal && .venv/bin/flask --app wsgi refresh-sensors
```

A sensor that fails records the error against itself and leaves the last good
reading in place. One dead sensor never takes the dashboard down.

---

## Bringing in your spreadsheet

**Money → Import**. Upload the `.xlsx` or `.csv`. It finds the header row even
if the sheet starts with a title, guesses which column is the company name, the
amount, the due day, and so on, and shows you the guess before saving anything.
Correct anything wrong, choose whether the rows are bills, accounts, or
recurring items, and import.

It handles the things real sheets contain: `$1,842.00`, `(650.00)` for a
negative, `5th` for a day. Rows are matched by name, so importing an updated
copy of the same sheet updates what is there rather than duplicating it.

Going the other way, **Money → Export** produces a workbook with bills,
accounts, recurring items, and full payment history on separate sheets. Your
data is never trapped in here.

---

## Looking after it

Everything lives in one file: `instance/portal.db`.

```bash
sudo cp deploy/backup.sh /usr/local/bin/household-portal-backup
sudo chmod +x /usr/local/bin/household-portal-backup
# then: 15 3 * * *  /usr/local/bin/household-portal-backup
```

It uses SQLite's own backup command, which is safe to run while the portal is
being used — copying a live database file can give you a corrupt copy.

Handy commands:

```bash
systemctl status household-portal      # is it running
journalctl -u household-portal -f      # what is it doing
flask --app wsgi seed                  # (re)load starter content
flask --app wsgi refresh-sensors       # pull every sensor now
flask --app wsgi refresh-weather       # warm the weather cache
```

---

## A note on what to store here

Sensitive facts (gate codes, wifi passwords) are masked on screen until clicked,
which stops someone reading them off a wall tablet over your shoulder. They are
**not encrypted in the database**, and the portal is not a password manager.

Keep account passwords in a real password manager. What belongs here is the
pointer: which bank, roughly which account, where the password manager is, and
how someone would get into it. That is the thing that is actually missing when
somebody needs to take over.

---

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

137 tests, no network needed — the NOAA client is tested against recorded
responses so the suite passes on a machine with no internet.

---

## How it is put together

```
portal/
  models.py            all the tables
  auth.py              Google OAuth, the allowlist, the local fallback
  themes.py            themes and fonts (add one here, it appears in the picker)
  security.py          CSRF for plain HTML forms
  util.py              template filters - fractions, money, dates, Markdown
  services/
    weather.py         NOAA client, caching, graceful failure
    nutrition.py       scaling, unit-to-grams, nutrition totals
    money.py           the month view and the forecast
    sensors.py         Home Assistant / JSON / manual readings
    importers.py       spreadsheet in, .xlsx out
  views/               one blueprint per section
  templates/
  static/
deploy/                systemd unit, nginx config, install and backup scripts
tests/
```

Flask, SQLAlchemy, and SQLite. Server-rendered HTML with a small amount of
plain JavaScript — no build step, no framework, nothing to `npm install`. The
pages work with JavaScript switched off; it just gets less lively.

Nothing is loaded from a CDN, so the whole thing runs on a network with no
internet access (weather being the obvious exception).
