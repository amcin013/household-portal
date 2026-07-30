"""Starter content, so a fresh install is not an empty box.

Run with:  flask --app wsgi seed
Safe to run twice - it skips anything already there.
"""
from .extensions import db
from .models import Food, Link, Page, Payee, Place, PlaceFact, unique_slug

PLACES = [
    {
        "name": "Bayshore",
        "city": "Palacios",
        "state": "TX",
        "icon": "🌊",
        "latitude": 28.7086,
        "longitude": -96.2169,
        "sort_order": 0,
        "notes": (
            "Coastal, so keep an eye on the NOAA alerts card during hurricane "
            "season — watches and warnings for this spot show at the top of the "
            "page automatically."
        ),
        "facts": [
            ("Wifi network", "", "General", False),
            ("Wifi password", "", "General", True),
            ("Water shutoff", "Describe where it is.", "Utilities", False),
            ("Breaker panel", "Describe where it is.", "Utilities", False),
            ("Trash day", "", "Trash & yard", False),
        ],
    },
    {
        "name": "Secretariat",
        "city": "Pflugerville",
        "state": "TX",
        "icon": "🏡",
        "latitude": 30.4394,
        "longitude": -97.6200,
        "sort_order": 1,
        "notes": "",
        "facts": [
            ("Wifi network", "", "General", False),
            ("Wifi password", "", "General", True),
            ("Water shutoff", "Describe where it is.", "Utilities", False),
            ("Breaker panel", "Describe where it is.", "Utilities", False),
            ("Trash day", "", "Trash & yard", False),
            ("Alarm code", "", "Access & codes", True),
        ],
    },
]

LINKS = [
    ("Jellyfin", "", "Media", "🎬", "Movies and TV", True),
    ("Router admin", "", "Home network", "📡", "", False),
    ("TXU Energy", "https://www.txu.com", "Bills", "⚡", "Electricity", False),
    ("Pflugerville Utilities", "https://www.pflugervilletx.gov/utilities",
     "Bills", "💧", "Water and wastewater", False),
]

PAYEES = [
    ("TXU Energy", "Utilities", 1, "https://www.txu.com"),
    ("Pflugerville Water", "Utilities", 1,
     "https://www.pflugervilletx.gov/utilities"),
]

PAGES = [
    {
        "title": "If you are covering for me",
        "category": "Emergency",
        "icon": "🧭",
        "is_essential": True,
        "pinned": True,
        "sort_order": 0,
        "summary": "Start here. What keeps the house running and who to call.",
        "body": """\
Start here, then work through the other pages marked **essential**.

## The short version

- Bills and what they cost live under **Money → This month**. Most are paid on
  the 1st. Each one has a Pay button that goes straight to the company's page.
- Account balances and the forecast are under **Money → Accounts**.
- Both properties, their conditions, and the practical details — wifi, shutoffs,
  trash day, codes — are under **Places**.

## Fill these in

- [ ] Who to call first, and their number
- [ ] Where the important documents are kept
- [ ] Insurance companies and policy numbers
- [ ] Who handles the house at each property
- [ ] Anything with a deadline that would be missed

## Accounts

Bank, retirement, and anything owed are listed under Accounts. Passwords are
**not** stored in this portal on purpose — write down where the password
manager is and how to get into it, and keep that somewhere safe and physical.
""",
    },
    {
        "title": "Restarting the Jellyfin server",
        "category": "Home systems",
        "icon": "🎬",
        "sort_order": 1,
        "summary": "When the TV cannot find the library.",
        "body": """\
Fill this in with what actually works, but the usual order is:

1. Try the app first — close it fully and reopen.
2. Check the server is reachable at its address on the Links page.
3. If it is not answering, restart the service on the server.
4. If it is answering but the library is empty, run a library scan from the
   Jellyfin dashboard.

## Notes

- Server address:
- Where it runs:
- How to restart it:
""",
    },
    {
        "title": "How the bills work",
        "category": "Accounts & bills",
        "icon": "💵",
        "is_essential": True,
        "sort_order": 2,
        "summary": "What gets paid, when, and how.",
        "body": """\
Bills are paid around the **1st of the month**.

Open **Money → This month**. Every company is listed with its amount, its due
date, and a Pay button that opens the right page. Tick the box when a bill is
paid — the total at the top updates as you go.

Anything on autopay is marked `auto` and is ticked off automatically.

## When a bill looks wrong

Open the company from **Bills & payments** to see what it has cost each month.
A utility that has crept up shows clearly there.

## Adding a new company

**Bills & payments → Add company**. The important field is the payment link —
put in the page you actually land on to pay, and it becomes a Pay button
everywhere.
""",
    },
]

FOODS = [
    ("Chicken breast, raw", 165, 31, 0, 3.6, 0, 74, {"each": 174}),
    ("All-purpose flour", 364, 10.3, 76.3, 1, 2.7, 2, {"cup": 120, "tbsp": 8}),
    ("Granulated sugar", 387, 0, 100, 0, 0, 1, {"cup": 200, "tbsp": 12.5}),
    ("Butter", 717, 0.9, 0.1, 81, 0, 11, {"cup": 227, "tbsp": 14}),
    ("Whole milk", 61, 3.2, 4.8, 3.3, 0, 43, {"cup": 244, "tbsp": 15}),
    ("Large egg", 143, 12.6, 0.7, 9.5, 0, 142, {"each": 50}),
    ("Olive oil", 884, 0, 0, 100, 0, 2, {"cup": 216, "tbsp": 13.5}),
    ("Yellow onion", 40, 1.1, 9.3, 0.1, 1.7, 4, {"each": 110, "cup": 160}),
    ("Long-grain white rice, raw", 365, 7.1, 80, 0.7, 1.3, 5, {"cup": 185}),
    ("Ground beef, 80/20", 254, 17.2, 0, 20, 0, 66, {}),
]


def run_seed():
    created = []

    for spec in PLACES:
        if Place.query.filter_by(name=spec["name"]).first():
            continue
        place = Place(
            name=spec["name"],
            slug=unique_slug(Place, spec["name"], "place"),
            city=spec["city"],
            state=spec["state"],
            icon=spec["icon"],
            latitude=spec["latitude"],
            longitude=spec["longitude"],
            sort_order=spec["sort_order"],
            notes=spec["notes"],
        )
        db.session.add(place)
        db.session.flush()
        for order, (label, value, category, sensitive) in enumerate(spec["facts"]):
            db.session.add(
                PlaceFact(
                    place_id=place.id, label=label, value=value,
                    category=category, sensitive=sensitive, sort_order=order,
                )
            )
        created.append(f"place: {place.name}")

    for order, (title, url, category, icon, description, pinned) in enumerate(LINKS):
        if Link.query.filter_by(title=title).first():
            continue
        db.session.add(
            Link(title=title, url=url, category=category, icon=icon,
                 description=description, pinned=pinned, sort_order=order)
        )
        created.append(f"link: {title}")

    for name, category, due_day, pay_url in PAYEES:
        if Payee.query.filter_by(name=name).first():
            continue
        db.session.add(
            Payee(name=name, category=category, due_day=due_day, pay_url=pay_url)
        )
        created.append(f"payee: {name}")

    for spec in PAGES:
        if Page.query.filter_by(title=spec["title"]).first():
            continue
        db.session.add(
            Page(slug=unique_slug(Page, spec["title"], "page"), **spec)
        )
        created.append(f"page: {spec['title']}")

    for name, kcal, protein, carbs, fat, fiber, sodium, units in FOODS:
        if Food.query.filter_by(name=name).first():
            continue
        food = Food(
            name=name, kcal=kcal, protein_g=protein, carbs_g=carbs,
            fat_g=fat, fiber_g=fiber, sodium_mg=sodium,
        )
        food.unit_grams = units
        db.session.add(food)
        created.append(f"food: {name}")

    db.session.commit()

    if created:
        print(f"Added {len(created)} items:")
        for item in created:
            print(f"  {item}")
    else:
        print("Everything was already there — nothing to do.")
    return created
