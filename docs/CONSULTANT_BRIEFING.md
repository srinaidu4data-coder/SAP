# How this company actually makes and loses money

**For:** process owners and functional consultants  
**Company we studied:** 1710 on APEX-2023, client 100  
**How:** display only. Nothing here was created for this paper.  
**Date:** 13 August 2026

This is not a list of what exists in SAP. It is an argument about how the
pieces fit, where they contradict each other, and which operating model you
should choose. If a sentence does not change a decision, it does not belong.

---

## The diagnosis (not the inventory)

Company 1710 already buys, receives, invoices vendors, takes orders, ships,
bills, manufactures, costs, and collects. Calling this “not implemented” is
the wrong diagnosis. Three things are true at once:

1. **A working path already posted.** Goods receipts on the MZ-RM raw-material
   family, vendor invoices for USSU suppliers, standard sales orders and
   customer invoices on 1710, years of actual costing, a live shop floor.
2. **People keep entering a different path.** Third-party material treated as
   warehouse stock. Buyer group 001 instead of 002. Hold instead of post.
   Whatever order type the search help offers first.
3. **The profit and loss is one company, but the teams behave as if buy, sell,
   make, and collect were four products.** They are not. A wrong purchase
   changes inventory and cost. That cost sits under the customer invoice.
   An invoice that never left the building becomes an unpaid item that credit
   never would have allowed if credit existed.

The operating problem is **disconnected truth**. The book is thick. The daily
habit is thin. The P&L is the place they meet, whether anyone designed it
that way or not.

A useful comparison: a well-run mid-market S/4 shop certifies *one* buy path,
*one* sell path, *one* costing recipe, and a credit-and-collect loop, then
hides the rest. This client has the opposite shape — a global template dump
with a handful of live habits living inside it. That is not richness. It is
an ungoverned menu.

---

## Insight 1 — The commercial funnel leaks in three places, and they compound

Count the book as a conversion story, not as four tables.

| Stage | What is on the books | What the gap is really saying |
|---|---:|---|
| Promise (sales orders) | 12,255 | Demand was taken. |
| Fulfil (deliveries) | 7,959 | About **one order in three never became a delivery** — backlog, rejection, service-only, or a different org mixed in. Either way, cash cannot start. |
| Recognise (customer invoices) | 5,982 | About **one delivery in four was never billed**. That is unbilled inventory or cutoff, not “billing is not implemented.” |
| Collect (paid vs still open) | 5,174 paid · 3,014 still open | Collection *works when someone does it*. A third of the receivable shape is still sitting with the customer. |
| Tell the customer (outputs) | 928 | Most invoices never produced a letter, EDI, or print. Collectors are chasing bills the customer may never have seen. |

These are not four findings. They are **one working-capital machine**.

- If you only fix collections, you call people about invoices they never
  received (928 outputs vs 5,982 bills vs 3,014 open). Disputes go up, not
  cash.
- If you only fix billing, you invoice deliveries into a book with **no
  credit limits** (credit master is empty). You accelerate unsecured AR.
- If you only fix delivery, you push more goods into the unbilled pile.
- If you only restrict order types, you clean the search help and leave
  USD 481,000-per-page order books (2018, sales org 1710) converting poorly.

**Association:** order → delivery → bill → output → cash is a single chain.
The weakest link sets DSO. Today the chain is weak in three places at once,
so local KPIs will lie. Sales will look busy (12k orders). Finance will see
revenue (6k bills). Treasury will see cash stuck. All three can be “right”
and the company still starves.

**Comparison:** a healthy industrial book often sits near
order ≈ delivery ≈ invoice, with open AR a designed DSO (30–45 days), not a
surprise. Here the shape is **promise-heavy, bill-light, remind-almost-never**.
That is either a fulfilment problem, a cutoff problem, or a two-landscape
problem (1710 USD book mixed with other orgs). You cannot know which until
you slice 1710 alone — but you already know you must not treat “implement
billing” as the program. Billing ran 5,982 times.

**Alternatives**

| Choice | What you optimise | What you give up |
|---|---|---|
| A. Close the unbilled first (deliveries with no invoice) | Revenue and cutoff | AR will jump unless credit is on |
| B. Close output first (every invoice must leave the building) | DSO quality, fewer “we never got it” tickets | Does not create missing invoices |
| C. Close credit first | Stops the next unsecured order | Does not collect the 3,014 already open |
| D. Do A then B then C, in that order | A working cash cycle | Needs one owner across SD and AR |

**D is the only sequence that does not fight itself.** Unbilled → tell the
customer → only then tighten credit on *new* orders. Tightening credit first
is morally tidy and cash-stupid: you freeze the front of the funnel while
the back is still dark.

---

## Insight 2 — Buy and sell are the same P&L. Wrong purchases invent fake margin.

Company 1710 is one legal entity. Vendor invoices already posted here.
Customer invoices already posted here. Cost of goods on those customer
invoices comes from the material’s price, which comes from costing, which
comes from *how you bought and made the thing*.

That is why TG10 is not a “buyer training issue.” It is a **financial-model
switch** that clerks flip by picking a material.

| How you fulfil | What hits the books | What the margin means |
|---|---|---|
| **Stock path (MZ-RM raw materials)** — already received on plant 1710 | Inventory goes up at goods receipt. Cost sits in the material. Actual costing can revalue it. Customer invoice takes cost of goods from that stack. | Margin is *price minus a real inventory cost*. Variance is visible. |
| **Drop-ship / third-party (TG10)** | Often **no warehouse receipt**. No inventory. Cost is the vendor bill, not a standard cost roll-up. | Margin is *price minus purchase*. Shop-floor and material ledger never see it. |
| **Plant-to-plant (stock transport 100011, Pranali)** | Stock moves between plants. Transfer price / in-transit appears. | Margin can hide in the other plant. |
| **Make-to-order (89 sales-order stocks exist)** | Inventory belongs to a sales order, not the warehouse. | If you cost it as warehouse stock, COGS lands in the wrong story. |
| **Project stock** | **Zero records.** | Do not design this. It is not a process here. |

When a buyer uses TG10 “because it is on the screen” and then fails goods
receipt, two errors happen. The obvious one is the error message. The quiet
one is that **even a “successful” TG10 path would have produced a different
P&L** than the MZ-RM path Finance thinks it is looking at. Mix the two in
the same product hierarchy and every margin report is a blend of two
economies.

**Association with Insight 1:** 5,982 customer invoices inherit this mess.
If half the volume is secretly drop-ship economics and half is stock
economics, the average margin is a statistical accident. Pricing, rebates,
and “which products are profitable” become theatre.

**Association with costing:** 3,472 standard estimates and 2,594 materials
in the actual-cost ledger only discipline the *stock* path. Drop-ship
bypasses them. So the more TG10 you use, the more of the commercial book
escapes the cost system you just spent years closing.

**Alternatives**

| Choice | When it is right | When it is wrong |
|---|---|---|
| Make **stock** the default (MZ-RM, goods receipt, ledger) | You hold inventory and promise ATP | You do not want warehouse, insurance, or surplus |
| Make **drop-ship** a named scenario (TG10, no GR, vendor ships to customer) | You are a broker | You pretend it is stock and then wonder why receipt fails |
| Make **STO** the inter-plant scenario (copy 100011) | Multi-plant network | You use it as a hack for a missing vendor |
| Make **sales-order stock** the MTO scenario (the 89 already there) | Engineered / customer-specific | You dump it into unrestricted and lose the link |

**Optimization:** do not delete TG10. **Name it.** Put it in a drop-ship
playbook with no goods receipt. Put MZ-RM in the stock playbook with
receipt and invoice. Two SOPs. Two search-help filters. Same company.
The transformation is not a new module. It is refusing to let one material
type play both roles.

---

## Insight 3 — Costing is not a CO side project. It is the honesty of every sales invoice.

There are 74 ways to roll a cost and **one** overhead sheet. There are 3,472
estimates, 7,647 cost breakdowns, 3,071 materials with a price, and 2,594 of
them in the actual-cost ledger. Period records run to 45,000 quantities and
85,000 values — **years of month-end**, not a pilot.

Read that as a business sentence: **this company already decided to know
what things cost, then under-used the only tool that puts overhead into the
product, then offered clerks 74 recipes.**

Implications that connect outward:

- **Overhead stays in cost centers.** 1,623 cost centers and 10,732 cost
  elements exist. The overhead sheet is basically unused. Labour and
  material get into the product; burden does not. Every manufactured item
  looks cheaper than it is. Every sales margin looks fatter than it is.
  A sales manager can “prove” a price that does not cover the building.
- **Activity price of zero is a margin weapon.** If the work center posts
  time and the rate is empty, the estimate’s labour line is nothing. Same
  effect as missing overhead, quieter.
- **More estimates than materials (3,472 vs 3,071)** means versions and
  dates. Someone rolled costs often. The question is whether the *released*
  price on the material is the latest, or a ghost. Goods receipt against a
  zero or ancient standard price explodes price difference into the P&L —
  which Finance will blame on purchasing, and purchasing will blame on
  “SAP.”
- **Actual costing is on and old.** If month-end is not closed, “not
  distributed” appears and the close slips. If it *is* closed but sales
  still uses standard for pricing, you have two truths: the ledger knows
  the actual, the quote does not.

**Comparison:** a disciplined plant picks one legal costing recipe, one
group recipe if needed, a monthly roll, a mark-and-release tied to the
close calendar, and rates that are never zero. This plant has the
*machinery* of that discipline and the *menu* of a template dump.

**Association with the funnel:** understated product cost + 5,982 invoices
= systematically optimistic gross margin. That optimism funds discounts,
rebates, and “we can afford to wait on the 3,014.” It is the same cash
problem wearing a CO badge.

**Alternatives**

| Choice | Effect on margin | Effect on people |
|---|---|---|
| A. One recipe for 1710, hide the other 73 | Comparable costs, less noise | Clerks stop inventing | 
| B. Keep 74, publish a “which to use” matrix | Looks complete | Nobody reads it; same chaos |
| C. Turn on overhead rates on the one sheet | Products carry burden | Cost center owners will fight the rates |
| D. Price from actual (ledger) instead of standard | Quotes follow reality, lag the month | Sales will hate the lag |

**A + C** is the adult combination. B is how you got here. D is a later
transformation, after A and C make standard worth reading.

**Optimization this month:** list materials you sell on 1710 whose standard
price is zero or older than two closes. Release current estimates *before*
the next goods receipt. That single act stops a class of P&L fires that
look like purchasing errors.

---

## Insight 4 — The shop floor is live, and it is only three-quarters finished

This is not a trading company with a costing sandbox.

- ~2,950 orders exist (production plus internal / CO).
- ~2,479 are shop-floor headers.
- ~1,021 shop-floor items — **headers outnumber items**. Many orders are
  not “make this finished good” in the simple sense, or they were created
  and never itemised.
- ~10,666 component reservations — about **four components per shop-floor
  order**. Bills of material really explode.
- ~1,838 confirmations against 2,479 headers — roughly **a quarter of
  orders were never confirmed**.

**What that means in money:** unconfirmed orders are **WIP on the balance
sheet**, not variance on the P&L. You can look profitable because cost is
still hanging on the order. Confirm, and variance lands. A controller who
pushes confirmations in week four of the close will “create” losses that
were always there.

**Association with Insight 3:** those confirmations feed actual costing.
Incomplete confirmations + a live ledger = a close that cannot tell the
truth, and a sales margin that still thinks the standard is fine.

**Association with buy-side:** 10,666 reservations are demand on components.
If those components are TG10, the reservation is a fantasy (no warehouse).
If they are MZ-RM, they are real procurement. The shop floor is silently
choosing the buy path.

**Alternative:** finish the open orders (confirm or close) before you
redesign costing. Otherwise you will roll a beautiful standard onto a
backlog of zombie orders and call the variance “the new recipe.”

---

## Insight 5 — Credit, collections, and output are one process wearing three hats

Credit master: **empty**.  
Unpaid customer invoices: **3,014**.  
Paid invoices: **5,174**.  
Outputs: **928**.  
Orders taken: **12,255**.

A company that can collect (5,174 times) but does not remind (928) and does
not check credit (0) is not “bad at FSCM.” It is **good at receiving money
when the customer feels like paying**, and silent the rest of the time.

Put the hats back on one head:

1. **Credit** decides whether the next promise is allowed.
2. **Output** decides whether the customer knows they owe you.
3. **Collections** decides whether anyone asks.
4. **Dispute** decides whether “I won’t pay” has a reason or is just delay.
5. **Cash application** decides whether the bank file finds the invoice.

Today (2) is thin, (1) is absent, (4) is email, (3) is heroic, (5) works.
Heroic collections on a book that does not send invoices and does not stop
bad orders is how you burn collectors and still grow AR.

**Hidden association:** empty credit plus a fat order book is a *sales*
success metric and a *treasury* time bomb. If you pay sales on bookings
(12,255) not cash (5,174), you are incenting the leak in Insight 1.

**Comparison:** classic credit vs FSCM vs “price the risk.”

| Alternative | Fits this book if… | Fails if… |
|---|---|---|
| Load classic credit limits | You want a block at order entry, fast | You never maintain limits; then everything blocks or everything passes |
| FSCM (worklists, cases, promises) | You have collectors and want a factory | You install it on top of 928 outputs — cases about invisible invoices |
| Formally unsecured + wider margin | You are a spot trader | You tell the board you have “SAP credit” and you do not |
| Agency / write-off after N days | The tail of the 3,014 is junk | You have not sent a statement yet — you will write off good cash |

**Do not buy FSCM this quarter.** It will digitise a broken letter. Send
statements. Work the 3,014 oldest-first. *Then* decide classic vs FSCM.
The transformation is “we collect as a process.” The software is later.

---

## Insight 6 — Unused configuration is not an asset. It is a ticket machine.

This client was loaded like a global template:

- 376 sales order types  
- 139 purchasing document types  
- 98 release strategies  
- 462 buyer groups  
- 74 costing recipes  
- 591 controlling areas  
- 837 company-to-controlling-area assignments  
- 1,004 valuation areas  

Used on 1710, day to day: **a handful.** Standard PO, standard sales order,
standard customer invoice, buyer group 002, cost center 1710-10, one plant.

Every extra choice in a search help is a future wrong document. The ticket
will sound like “SAP will not receive,” “vendor not valid,” “enter a cost
object,” “invalid date,” “cannot convert requisition.” The root is almost
never a missing type. It is **the wrong type from a generous menu**.

**Comparison:** unused config looks like “readiness” in a sales demo and
like “entropy” in production support. Here it is entropy. The 6–60 month
program is not to *use* all 376 types. It is to **certify twenty and hide
the rest**.

**Association:** this is the same disease in four modules. Treating them as
four clean-up projects wastes the insight. One design rule: *if it is not
on the 1710 certified list, it is not in the search help.* MM, SD, CO, FI
the same week.

**Alternatives**

| Choice | Speed | Risk |
|---|---|---|
| Hide in search help (keep in the system) | Days | Reversible. Best. |
| Delete unused types | Months, transports, fights | You will delete something a country still uses |
| Train “please pick NB and OR” | Weeks | Relapses the first time a new contractor arrives |
| Build a front-end that only offers certified types | A project | Useful later; do not wait for it |

Hide first. Measure tickets. Delete only what has been unused for a year
*and* is not in another landscape on this client (there are signs of an
India book next to the 1710 USD book — two companies in one box).

---

## Insight 7 — The first leak is master data, before anyone hits Create

1,283 customers exist. **795** have a sales view. About **490 customers
cannot take a sales order** in a sales area. That is not a sales-order-type
problem. It is why “I cannot sell to this customer” tickets appear, and why
a consultant then offers to create a 377th type.

Source lists exist (173) on **other plants**, not 1710. Requisitions exist
in volume. Auto-PO dies. Buyers type POs by hand, pick TG10, Hold, buyer
group 001. The “purchasing process problem” started as a **plant assignment
problem**.

Two landscapes live in one client (1710 USD commercial book vs other orgs /
India-style customers). Incomplete views plus two landscapes means every
global search returns the wrong country’s truth.

**Association:** master-data gaps *feed* Insights 1, 2, and 6. Fixing
transactions without finishing sales views and 1710 source lists is
rearranging the funnel’s mouth while the teeth are missing.

**Optimization:** a weekly “completeness” list is cheaper than a new
process. Customers without a sales view. Vendors without a 1710 purchasing
view. Materials without a 1710 plant view or with a zero price. Source
list rows not on 1710. That list *is* the transformation backlog.

---

## Insight 8 — Integration is thinner than the commercial book. Do not automate the wrong path.

About 1,239 electronic messages vs 12,255 orders. Most of this company is
still typed at the glass. 928 outputs vs 5,982 invoices. The digital layer
is a garnish.

If you “put an API in front of SAP” now, you will encode TG10, buyer group
001, no credit, and silent invoices — at machine speed. That is not
transformation. That is **industrialising the leak**.

**Sequence that actually transforms**

1. Certify the path (Insights 2, 6, 7).  
2. Make the path honest (Insights 3, 4).  
3. Make the path collect (Insights 1, 5).  
4. *Then* put BAPI / IDoc / a bot on the certified path only.

The display wing exists for step 1: walk what already posted, in display,
and copy it. The analysis wing exists to stop you automating the rest.

---

## Insight 9 — One dollar of revenue, followed through the company

Take a dollar of sales on 1710.

- It began as a promise (one of 12,255). Chance it never shipped: material.
- If it shipped (one of 7,959), chance it was never billed: still material.
- If it was billed (one of 5,982), chance the customer never got a document:
  high (928 outputs).
- Chance we checked whether they should have been sold to: **none**.
- The cost under that dollar came from either a stock standard (maybe stale,
  maybe missing overhead) or a drop-ship purchase (if someone used TG10), or
  a plant transfer (if it was an STO cousin of 100011), or a sales-order
  stock (if it was one of the 89). Four cost stories. One invoice layout.
- If the factory made it, a quarter of sister orders were never confirmed,
  so some of the “profit” may still be sitting in WIP.
- If they pay, cash application can find it (5,174 times it has). If they
  do not, we mostly do not ask.

That is not a system that needs more types. It is a system that needs
**one certified journey for a dollar**, and a monthly ritual that keeps the
journey honest (costing close, confirmation, output, collect).

Now a dollar of spend:

- If it is MZ-RM on plant 1710, buyer group 002, purchasing org 1710, it
  can be received, invoiced, and (we have not proven payment, but the
  vendor book exists). That is the dollar to copy.
- If it is TG10, it is a different dollar — no warehouse, different COGS —
  unless someone tries to receive it, in which case it is a stuck dollar.
- If it is a requisition with buyer group 001, it is a dollar that never
  becomes a PO without a human retyping it.
- If it is Hold, it is a dollar Finance cannot see.

Spend and revenue meet in company 1710’s P&L. Treating them as two
implementations is how you get a clean MM project, a clean SD project, a
clean CO project, and a dirty company.

---

## What “good” would look like here (the comparison that matters)

Not SAP Best Practice slides. This specific book, cleaned.

| Today | A year from now if you choose the connected program |
|---|---|
| 376 types in the search help | ~15 certified, the rest hidden |
| TG10 and MZ-RM used interchangeably | Two named scenarios, two SOPs |
| 74 costing recipes, 1 dead overhead sheet | 1 recipe, live rates, monthly release |
| 0 credit, 928 outputs, 3,014 open | Statements go out; credit on new orders; open AR worked weekly |
| ~25% of shop-floor orders unconfirmed | Confirmation is a close step, like bank rec |
| Auto-PO dead, source list on other plants | Source list on 1710, buyer group 002, auto-PO from the pile |
| Margin is a blend of four fulfilment economies | Margin by scenario: stock / drop-ship / STO / MTO |
| Projects to “implement” what already posted | Projects to *stop using* what should stay on the shelf |

That is transformation. It is mostly subtraction and ritual, not new
modules.

---

## Optimizations that do not require a program

These are the creative near-term moves — same SAP, different habit.

1. **Search-help diet.** One transport per module. Biggest ticket reduction
   per hour of work.
2. **Material personality.** TG10 labelled “drop-ship only” in the
   description users see. MZ-RM labelled “stock 1710.” People pick what
   they can read.
3. **Buyer group 001 renamed or locked** for 1710. The auto-PO failure
   disappears without a new program.
4. **Source list copy.** Take a working row from the other plants and plant
   it on 1710. That is the whole “ME59N project.”
5. **Output as a close step.** No period close if invoices without output
   exceed a threshold. DSO falls because customers can pay.
6. **Zero-price hunt.** Materials you sell, standard price zero or stale.
   Release before next receipt. Stops P&L explosions mislabelled as MM.
7. **Confirmation Friday.** Shop-floor confirms or closes. WIP stops being
   a surprise in week four.
8. **Unbilled Monday.** Deliveries without invoices, 1710 only. This is
   Insight 1, made into a meeting.
9. **Oldest-open Wednesday.** The 3,014, oldest first, after you know a
   statement exists. Do not call into a vacuum.
10. **Display before design.** Open stock transport 100011, an MZ-RM
    receipt, a USSU vendor invoice, a 1710 customer invoice. Copy those.
    Do not workshop a to-be that already exists.

---

## Transformation choices (you have to pick; “all” is how you got the 376 types)

These are real forks. Write the choice down.

**Fork 1 — What kind of company is 1710?**  
Stock manufacturer, drop-ship trader, multi-plant network, or MTO shop?
The data says *mostly stock + some STO + a little MTO + accidental
drop-ship.* Pick “stock manufacturer with a named drop-ship exception.”
Design everything else as exception.

**Fork 2 — Is credit a control or a story you tell auditors?**  
If control: load limits before the next order wave. Sales will shrink.
That is the point. If story: stop saying you have credit. Price the risk
into the 5,982 invoices.

**Fork 3 — Is margin a sales number or a cost number?**  
If sales: you will keep under-absorbing overhead and celebrating. If cost:
one recipe, live rates, actual-costing close on the calendar, and sales
lives with uglier margins that you can take to the bank.

**Fork 4 — Do you want fewer tickets or more capability?**  
Capability is contracts, scheduling agreements, consignment, subcontract —
all already configured, almost unused. Tickets fall from *hiding* types.
Capability rises from *using* three of them on purpose after the path is
certified. Do tickets first (90 days). Capability second (the next year).
The usual consultant order is the reverse, which is why the menu grew and
the habit did not.

**Fork 5 — One landscape or two?**  
If 1710 and the other orgs are two businesses, split the operating model
(separate SOPs, separate search helps, separate credit). If they are one
business, finish the 1710 views and stop using the other plants’ source
lists as if they applied here.

---

## Next steps that fall out of the insights (not a generic plan)

Order matters. This order is the analysis.

**First, stop mixing economies (Insights 2, 6)**  
Name stock vs drop-ship. Hide the dangerous types. Lock buyer group 002.
This is a week of design and a week of search-help work. It prevents new
damage while you clean the book.

**Second, finish the dollars already in motion (Insights 1, 4, 5)**  
Unbilled deliveries. Outputs on existing invoices. Confirm or close
shop-floor orders. Oldest unpaid *after* a statement exists. This turns
working capital, not a slide.

**Third, make the next dollar honest (Insights 3, 7)**  
One costing recipe. Overhead rates. Zero-price materials released. Customer
sales views completed. Source list on 1710. Now a new order and a new PO
can be compared to the last one.

**Fourth, only then add capability or software (Insights 8, Fork 4)**  
Auto-PO. Contracts. FSCM. A bot. An API. Each of these is a multiplier.
Multipliers on a certified path are transformation. Multipliers on TG10
plus empty credit are faster mess.

**Do not** start an implement-GR, implement-billing, implement-costing, or
implement-credit-*software* project in parallel with step one. Those
projects are how this client acquired 376 types and still cannot receive
TG10.

---

## What to tell a steering committee (the connected version)

> 1710 already buys, sells, makes, and collects. The P&L is one company and
> we have been running it as four modules. We leak cash three times — we
> do not ship everything we promise, we do not bill everything we ship, and
> we do not send or chase a large share of what we bill. We then invent
> margin by costing without overhead and by mixing drop-ship with stock.
> We will not implement SAP. We will certify one stock journey and one
> drop-ship exception, hide the rest of the menu, make costing tell the
> truth on the invoices we already send, and collect the invoices we
> already raised — in that order. The prize is working capital and honest
> margin, not a new document type.

---

## Where the object names live

If an analyst needs the tables behind a sentence, they are in the
appendices. They are not the argument.

| Sentence in this paper | Appendix |
|---|---|
| Buy path, TG10 vs MZ-RM, buyer group, source list | `PTP_OPPORTUNITY_MAP.md` |
| Funnel counts, order types, outputs | `OTC_EXHAUSTIVE_ANALYSIS.md` |
| Credit empty, unpaid vs paid, dunning | `COLLECTIONS_DISPUTES_MINDMAP.md` |
| Recipes, ledger, shop floor, overhead | `PRODUCT_COSTING_MINDMAP.md` |
| Display walk of stock transport 100011 | `DISPLAY_WALK_PTP.md` |
