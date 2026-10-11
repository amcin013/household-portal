# Household Portal

A private landing page for everything to do with the house: recipes, bills,
property info, how-to pages, and the links everyone keeps hunting for.

Built to be self-hosted on your own server. It is a single Python app with a
SQLite database — one file to back up, no external services, no subscriptions.
It works with no internet access at all except for weather.

---

## What is in it

**Home** — a grid of panels you choose. Weather, NOAA radar, bills due,
obligations, accounts, pinned links, essentials, recipes, storage, recent
activity. Tick what you want and drag to reorder under Settings → Home page;
the layout is per person, so what you arrange is yours. A panel with nothing to
show hides itself rather than sitting empty.

**Places** — one page per property. NOAA weather and active watches/warnings,
indoor sensor readings, and a table of the things nobody remembers: wifi
password, water shutoff, trash day, gate codes. Anything marked sensitive stays
masked until you click it.

**Money** — the part that replaces a spreadsheet.
- *This month*: every bill as a sortable, filterable table. Search by company,
  category or account; filter to unpaid or past due; group by category. Tick a
  bill off or correct an amount straight in the row — no page reload, and the
  month totals repaint as you go. Sorting and filtering are query parameters, so
  every view is a URL you can bookmark, and it all works with JavaScript off.
- *Bills & payments*: the companies you pay, with per-company history so a
  utility that has been creeping up is obvious.
- *Accounts*: savings, TSP, anything owed. Each balance you record is kept with
  its date, so you get change-over-time and a net worth figure.
- *Recurring*: pay, child support, transfers into savings.
- *Obligations*: a balance being paid down rather than billed forever — child
  support, a share of the kids' medical bills. Tracks each cheque by number
  through written → sent → cleared, and works the remaining balance out from
  what you actually recorded rather than extrapolating. A new bill goes on as a
  charge, so the balance can go up as well as down.
- *Trends & forecast*: what the house has actually cost, month by month and by
  category, with the forward projection underneath it on the same page — a
  projection is only worth reading next to the record it comes from.
- Import an existing spreadsheet — including the wide kind, with the companies
  down the side and years of months across the top. Export everything back to
  `.xlsx` at any time.

**Usage** — record what a utility metered, not just what it charged. Then a
bill going up $50 can be split into the part caused by the rate and the part
caused by using more, which are completely different problems. Readings load
from Green Button XML, a Smart Meter Texas CSV, or anything with a date and a
number in it.

**Recipes** — a cookbook rather than a list: chapters by course, a contents
page when there is more than one chapter, and an alphabetical index at the back.
Scale any recipe to a different number of servings and the
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

## How it is laid out

The sidebar groups sections by what you are doing rather than by where the data
lives:

- **Money** — This month, Bills & companies, Usage & meters, Accounts,
  Obligations, Trends & forecast, Import & export
- **House** — Places, Storage, Links
- **Kitchen** — Recipes, Shopping list
- **Reference** — How-to & info, Essentials

Money comes first because it is the heaviest-used part, and Usage sits inside it
because a meter reading only means something next to the bill it explains. Each
group is a plain `<details>`, so the rail works with no JavaScript; the group
holding the page you are on is the one that opens.

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

**Money → Import**. Upload the `.xlsx` or `.csv`; it works out the shape for
itself.

**A sheet with months across the top** — companies down the side, one column
per month, a few summary columns wedged in front — is imported as history: each
row becomes a company and each month becomes a bill on it. Summary columns
(Total, Estimated, AVG, % of Total) are recognised and skipped, unlabelled
totals rows are ignored, and the year is carried across the columns and rolled
over at January when the sheet stops labelling it. Totals and averages are then
computed rather than stored, so they cannot drift out of date the way a
spreadsheet formula does when the data outgrows its range.

**A simple list** — one row per bill — goes through column mapping instead: it
finds the header row even if the sheet starts with a title, guesses which column
is the company name, the amount, the due day, and so on, and shows you the guess
before saving anything. Correct anything wrong, choose whether the rows are
bills, accounts, or recurring items, and import.

It handles the things real sheets contain: `$1,842.00`, `(650.00)` for a
negative, `5th` for a day. Rows are matched by name, so importing an updated
copy of the same sheet updates what is there rather than duplicating it.

Going the other way, **Money → Export** produces a workbook with bills,
accounts, recurring items, and full payment history on separate sheets. Your
data is never trapped in here.

---

## Meter readings

**Money → Usage**. Three ways in:

- **Green Button XML** — the national standard. Any utility with a "Download My
  Data" button produces it.
- **Smart Meter Texas CSV** — for electricity in deregulated Texas the meter
  belongs to the wires company, not whoever you buy power from, so readings come
  from [smartmetertexas.com](https://www.smartmetertexas.com) rather than your
  retailer. Register once with your ESIID and export; it holds 13 months of
  15-minute interval data, and the history survives switching retailer.
- **Any CSV** with a date column and a usage column.

Interval data is totalled to months, because that is the grain bills are at.
Readings only attach to months that have a bill — usage with no cost cannot say
anything about a rate — and part-months at either end of an export are dropped
by default, since half a month of readings against a whole month's bill gives a
badly wrong figure.

Set what a company is metered in on its page (kWh, ccf, therms, gallons) and
each bill can then carry a reading, giving you rate over time, usage over time,
usage per day, and the rate-versus-volume split on any change.

---

## When you cannot reach it from another machine

The portal answers on the server itself but every other machine times out.
Nine times in ten the service is bound to loopback. On the server:

```bash
ss -tlnp | grep 8000
```

- `127.0.0.1:8000` — loopback only. That is the problem.
- `0.0.0.0:8000` — bound correctly; keep reading below.

To open it to the house network:

```bash
sudo systemctl edit household-portal
```

and put this in the override, blank `ExecStart=` line included — systemd needs
the empty one to replace the original rather than add a second:

```
[Service]
ExecStart=
ExecStart=/opt/household-portal/.venv/bin/gunicorn --workers 3 \
    --bind 0.0.0.0:8000 --timeout 60 \
    --access-logfile - --error-logfile - wsgi:app
```

Then `sudo systemctl daemon-reload && sudo systemctl restart household-portal`.

If it is already on `0.0.0.0` and still unreachable, work down this list:

1. **Firewall** — `sudo ufw status`. If active, `sudo ufw allow 8000/tcp`.
2. **Wrong IP.** In a VM or container the guest has its own address, which is
   not the host's. Run `hostname -I` *on the guest* and use what it prints. If
   the guest is NAT'd rather than bridged, no amount of binding helps — the
   hypervisor needs a port forward, or the guest needs a bridged adapter so it
   gets its own address on the LAN.
3. **Check from the server first** — `curl -I http://localhost:8000/auth/login`.
   A 200 or 302 means the app is fine and the problem is purely networking.

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
