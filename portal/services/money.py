"""The month-to-month money picture: what is due, what is held, what is coming.

This is the part that replaces the spreadsheet. Three inputs:
  Payee       - a company billed monthly (TXU, water, mortgage)
  LedgerItem  - recurring money in or out that is not a company bill
                (paychecks, child support, a TSP contribution)
  Account     - anything with a balance (savings, TSP, a card)

From those it builds the month view and a forward projection.
"""
import calendar
from datetime import date

from ..extensions import db
from ..models import Account, BillPayment, LedgerItem, Payee
from ..util import current_period, shift_period


def period_bounds(period):
    year, month = (int(p) for p in period.split("-"))
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def due_date_for(period, day):
    """Clamp to the end of short months - a bill due on the 31st is due Feb 28."""
    year, month = (int(p) for p in period.split("-"))
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(max(day or 1, 1), last))


def ensure_month(period, commit=True):
    """Create this month's bill rows for every active payee, once."""
    payees = Payee.query.filter_by(active=True).all()
    existing = {
        b.payee_id
        for b in BillPayment.query.filter_by(period=period).all()
    }
    created = []
    for payee in payees:
        if payee.id in existing:
            continue
        bill = BillPayment(
            payee_id=payee.id,
            period=period,
            amount=payee.typical_amount or 0,
            due_date=due_date_for(period, payee.due_day),
            status="paid" if payee.autopay else "due",
        )
        # Autopay still needs a paid date so the month totals look right.
        if payee.autopay:
            bill.paid_on = bill.due_date
        db.session.add(bill)
        created.append(bill)
    if commit and created:
        db.session.commit()
    return created


def month_view(period=None):
    """Everything needed to render one month."""
    period = period or current_period()
    ensure_month(period)

    bills = (
        BillPayment.query.filter_by(period=period)
        .join(Payee)
        .filter(Payee.active.is_(True))
        .order_by(BillPayment.due_date, Payee.name)
        .all()
    )

    total = sum(b.amount or 0 for b in bills)
    paid = sum(b.amount or 0 for b in bills if b.is_paid)
    remaining = sum(
        b.amount or 0 for b in bills if b.status == "due"
    )

    ledger = LedgerItem.query.filter_by(active=True).order_by(LedgerItem.name).all()
    income = sum(i.monthly_amount for i in ledger if i.kind == "income")
    other_out = sum(i.monthly_amount for i in ledger if i.kind == "expense")
    transfers = sum(i.monthly_amount for i in ledger if i.kind == "transfer")

    today = date.today()
    overdue = [
        b for b in bills
        if b.status == "due" and b.due_date and b.due_date < today
    ]
    upcoming = [
        b for b in bills
        if b.status == "due" and b.due_date and today <= b.due_date <= today.replace(
            day=min(today.day + 7, calendar.monthrange(today.year, today.month)[1])
        )
    ]

    by_category = {}
    for b in bills:
        cat = b.payee.category or "Other"
        by_category.setdefault(cat, 0)
        by_category[cat] += b.amount or 0

    return {
        "period": period,
        "bills": bills,
        "total": total,
        "paid": paid,
        "remaining": remaining,
        "count_due": sum(1 for b in bills if b.status == "due"),
        "overdue": overdue,
        "upcoming": upcoming,
        "ledger": ledger,
        "income": income,
        "other_out": other_out,
        "transfers": transfers,
        "net": income - total - other_out - transfers,
        "by_category": sorted(by_category.items(), key=lambda kv: -kv[1]),
        "prev": shift_period(period, -1),
        "next": shift_period(period, 1),
    }


def cash_accounts():
    return Account.query.filter(
        Account.active.is_(True), Account.kind.in_(("checking", "savings"))
    ).all()


def net_worth():
    total = 0.0
    for acct in Account.query.filter_by(active=True, include_in_net_worth=True):
        total += acct.signed_balance
    return total


def forecast(months=12, starting_cash=None):
    """Project cash and account balances forward.

    Each month: income comes in, bills and other expenses go out, transfers move
    into their target account, and every account grows by its own rate.
    """
    ledger = LedgerItem.query.filter_by(active=True).all()
    income = sum(i.monthly_amount for i in ledger if i.kind == "income")
    expenses = sum(i.monthly_amount for i in ledger if i.kind == "expense")
    transfers = [i for i in ledger if i.kind == "transfer"]
    transfer_total = sum(i.monthly_amount for i in transfers)

    bills_total = sum(
        p.typical_amount or 0 for p in Payee.query.filter_by(active=True).all()
    )

    accounts = Account.query.filter_by(active=True).all()
    balances = {a.id: a.balance for a in accounts}

    if starting_cash is None:
        starting_cash = sum(balances[a.id] for a in cash_accounts())

    cash = starting_cash
    monthly_net = income - bills_total - expenses - transfer_total

    rows = []
    period = current_period()
    for _ in range(months):
        period = shift_period(period, 1)
        cash += monthly_net

        for acct in accounts:
            rate = (acct.annual_growth_pct or 0) / 100 / 12
            balances[acct.id] *= 1 + rate
            balances[acct.id] += acct.monthly_contribution or 0
        for item in transfers:
            if item.to_account_id in balances:
                balances[item.to_account_id] += item.monthly_amount

        worth = sum(
            (-balances[a.id] if a.is_debt else balances[a.id])
            for a in accounts
            if a.include_in_net_worth
        )
        rows.append(
            {
                "period": period,
                "cash": cash,
                "net_worth": worth,
                "balances": dict(balances),
            }
        )

    return {
        "rows": rows,
        "income": income,
        "bills": bills_total,
        "expenses": expenses,
        "transfers": transfer_total,
        "monthly_net": monthly_net,
        "starting_cash": starting_cash,
        "accounts": accounts,
        "runway_months": _runway(starting_cash, monthly_net),
    }


def _runway(cash, monthly_net):
    """If money is going out faster than it comes in, how long does cash last."""
    if monthly_net >= 0 or cash <= 0:
        return None
    return int(cash / abs(monthly_net))


def history(months=12):
    """What actually got paid, month by month - the counterweight to the forecast."""
    period = current_period()
    periods = [shift_period(period, -i) for i in range(months - 1, -1, -1)]
    rows = []
    for p in periods:
        bills = BillPayment.query.filter_by(period=p).all()
        rows.append(
            {
                "period": p,
                "total": sum(b.amount or 0 for b in bills),
                "paid": sum(b.amount or 0 for b in bills if b.is_paid),
                "count": len(bills),
            }
        )
    return rows


def payee_history(payee, months=12):
    """One payee's amount over time - shows a utility creeping up."""
    period = current_period()
    periods = [shift_period(period, -i) for i in range(months - 1, -1, -1)]
    by_period = {b.period: b for b in payee.payments}
    return [
        {"period": p, "amount": (by_period[p].amount if p in by_period else None),
         "status": (by_period[p].status if p in by_period else None)}
        for p in periods
    ]


def spending_over_time(months=24):
    """What the household actually spent, month by month.

    The counterweight to the forecast: a projection is only worth reading next
    to the record it is projecting from.
    """
    period = current_period()
    periods = [shift_period(period, -i) for i in range(months - 1, -1, -1)]
    wanted = set(periods)

    rows = {p: {"period": p, "total": 0.0, "paid": 0.0, "count": 0,
                "categories": {}} for p in periods}

    for bill in (
        BillPayment.query.filter(BillPayment.period.in_(wanted))
        .join(Payee).all()
    ):
        row = rows[bill.period]
        amount = bill.amount or 0
        row["total"] += amount
        row["count"] += 1
        if bill.is_paid:
            row["paid"] += amount
        category = bill.payee.category or "Other"
        row["categories"][category] = row["categories"].get(category, 0) + amount

    series = [rows[p] for p in periods]
    with_spend = [r for r in series if r["total"] > 0]

    totals_by_category = {}
    for row in series:
        for name, amount in row["categories"].items():
            totals_by_category[name] = totals_by_category.get(name, 0) + amount

    amounts = [r["total"] for r in with_spend]
    return {
        "series": series,
        "months": len(with_spend),
        "total": sum(amounts),
        "average": (sum(amounts) / len(amounts)) if amounts else 0,
        "highest": max(with_spend, key=lambda r: r["total"]) if with_spend else None,
        "lowest": min(with_spend, key=lambda r: r["total"]) if with_spend else None,
        "by_category": sorted(totals_by_category.items(), key=lambda kv: -kv[1]),
        "recent_average": (
            sum(r["total"] for r in with_spend[-12:]) / min(len(with_spend), 12)
        ) if with_spend else 0,
    }
