# Integrations

What is wired up, what is not, and what it would take.

---

## Home Assistant (working)

The easiest way to get real indoor temperatures in. If Home Assistant already
talks to your thermostat, the portal only has to ask Home Assistant.

**Getting a token.** In Home Assistant, click your user name at the bottom of
the sidebar → *Security* → *Long-lived access tokens* → *Create token*. Copy it
straight away; it is only shown once.

**Adding the sensor.** On a place's page, *Add a sensor* → provider **Home
Assistant**, then fill in:

| Field | Example | Notes |
|---|---|---|
| Base URL | `http://192.168.1.10:8123` | No trailing slash |
| Token | *the long-lived token* | Stored in the database as given |
| Entity ID | `sensor.living_room_temperature` | From Developer Tools → States |
| Attribute | *(blank)* | Only for thermostats — see below |

**For a thermostat**, use the `climate.*` entity and set the attribute to
`current_temperature`. A `climate` entity's plain state is its mode (`heat`,
`cool`, `off`), not a number, so without the attribute the reading fails with a
clear message.

Test it by saving — the portal reads it immediately and either shows the value
or tells you exactly what went wrong.

---

## Any JSON URL (working)

For a DIY sensor, or a vendor API the portal does not know about. Give it a URL
and a dotted path to the number in the response.

```json
{ "data": { "readings": [ { "temp": 72.4 } ] } }
```

Path: `data.readings.0.temp`

Use numbers for positions in a list. If the response is bare (`72.4` and nothing
else), leave the path empty. A bearer token can be supplied and is sent as an
`Authorization` header.

---

## Ecobee (not wired up)

Ecobee's API needs a registered developer application and a refresh-token dance
that has to be re-run when the token expires. That is a real piece of work and
it is not built.

**In the meantime**, if the thermostat is in Home Assistant, add it that way and
it works today. That is the recommended route regardless — one integration to
maintain instead of two.

If you want it native later, the shape is:
1. Register an app at <https://www.ecobee.com/developers/> for an API key.
2. PIN authorisation to get an initial refresh token.
3. Store the refresh token; exchange it for an access token on each poll.
4. `GET /1/thermostat` with `selection.includeRuntime=true`, then read
   `runtime.actualTemperature` (it comes back in tenths of a degree F).

The place to put it is `read_ecobee()` in `portal/services/sensors.py` — the
provider is already registered and returns a clear "not available yet" message,
so it is a matter of filling in that one function plus config fields on the
sensor form.

---

## Smart Meter Texas (working)

The route to electricity usage in Texas, and worth understanding because it is
not where most people look first.

Texas is deregulated: you buy electricity from a retailer (TXU and the like),
but the meter on the house belongs to the wires company — Oncor around
Pflugerville, CenterPoint and AEP elsewhere. The readings are the wires
company's, so they come from
[smartmetertexas.com](https://www.smartmetertexas.com), not from your retailer's
website.

Two consequences worth knowing:

- **Switching retailer does not lose the history.** The meter did not change,
  so neither did the data.
- **You do not need your retailer's cooperation.** Register directly at Smart
  Meter Texas with the ESIID off a bill.

It holds **13 months** of 15-minute interval data and offers two exports:
*Export* gives a CSV (`USAGE_DATE`, `USAGE_START_TIME`, `USAGE_KWH`), and *Green
Button Download My Data* gives ESPI XML. The portal reads both, and totals
either to months.

Gas and water are patchier. Atmos and most city water utilities show usage in
the account portal but have no Green Button; if all you can get is a table on
screen, typing one number off each bill is twelve numbers a year.

---

## Bills by email (not built — worth discussing)

You asked whether bill amounts could be pulled out of Gmail automatically. It is
possible, and the groundwork is here — the portal already knows which companies
you pay and what each bill usually costs, and Google sign-in is already in
place. But it is a genuinely separate piece of work, and there are two things
worth deciding before building it.

**What it would take.**

1. Add `https://www.googleapis.com/auth/gmail.readonly` to the OAuth scopes and
   store a refresh token per user (right now the portal keeps no Google tokens
   at all — it only uses Google to confirm who you are).
2. A scheduled job searching for bill mail, e.g.
   `from:txu.com newer_than:35d`, one query per payee.
3. Per-payee extraction rules to pull the amount and due date out of the body.

**The catch is step 3.** Every company formats its email differently, and they
change them. A regex that reads TXU's email correctly today may quietly read the
wrong number in six months — and a wrong number in a bill tracker is worse than
no number, because you would trust it. Any sensible version of this proposes
values for you to confirm rather than writing them in silently.

**The other consideration** is that `gmail.readonly` grants read access to your
entire mailbox, not just bill mail. Google has no narrower scope. For a personal
server that may be perfectly fine — worth deciding deliberately rather than by
default.

**A cheaper 80% version**, if the goal is mainly "don't miss a bill": the portal
already knows every due date. A nightly job that emails or notifies *"three
bills due in the next five days"* gets most of the value with none of the
mailbox access or parsing fragility. Say the word and it is a short job.

---

## Notifications (not built)

Nothing is sent out at the moment; the portal only shows things when you open
it. Overdue bills are flagged at the top of the home page.

If you want reminders, the options in rough order of effort:
- A cron job that emails a summary through the server's local mail.
- A push notification via ntfy or Pushover — both are a single HTTP request, no
  account juggling, and work well on phones.
- Home Assistant notifications, if you are already running it — then the
  reminder lands wherever your other home alerts do.

The data needed is all there — `month_view()` in `portal/services/money.py`
already returns `overdue` and `upcoming` lists.
