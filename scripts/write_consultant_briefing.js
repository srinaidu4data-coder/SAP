const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
        ShadingType, PageNumber, LevelFormat } = require("docx");
const fs = require("fs");
const path = require("path");

const NAVY = "1B365D";
const TEAL = "1F4E5F";
const GOLD = "C4A35A";
const ROW = "F4F1EA";
const HEAD = "1B365D";
const WHITE = "FFFFFF";
const RULE = "C9C2B2";
const border = { style: BorderStyle.SINGLE, size: 4, color: RULE };
const borders = { top: border, bottom: border, left: border, right: border };
const W = 10080;

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after ?? 140, before: opts.before ?? 0, line: 276 },
    alignment: opts.align,
    children: [new TextRun({
      text, font: "Calibri", size: opts.size ?? 22,
      bold: !!opts.bold, italics: !!opts.italics, color: opts.color || "222222",
    })],
  });
}
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 320, after: 140 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: GOLD, space: 4 } },
    children: [new TextRun({ text, font: "Calibri", size: 26, bold: true, color: NAVY })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 100 },
    children: [new TextRun({ text, font: "Calibri", size: 23, bold: true, color: TEAL })],
  });
}
function bullet(text, ref = "bullets") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 70, line: 276 },
    children: [new TextRun({ text, font: "Calibri", size: 21, color: "222222" })],
  });
}
function cell(text, width, fill, bold, color) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: fill || WHITE, type: ShadingType.CLEAR },
    margins: { top: 60, bottom: 60, left: 80, right: 80 },
    children: [new Paragraph({
      children: [new TextRun({
        text, font: "Calibri", size: 17, bold: !!bold,
        color: color || (fill === HEAD ? WHITE : "222222"),
      })],
    })],
  });
}
function table(headers, rows, widths) {
  return new Table({
    width: { size: W, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ children: headers.map((h, i) => cell(h, widths[i], HEAD, true, WHITE)) }),
      ...rows.map((r, ri) => new TableRow({
        children: r.map((c, i) => cell(String(c), widths[i], ri % 2 ? ROW : WHITE, false)),
      })),
    ],
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Calibri", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Calibri", color: NAVY },
        paragraph: { spacing: { before: 320, after: 140 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 23, bold: true, font: "Calibri", color: TEAL },
        paragraph: { spacing: { before: 240, after: 100 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
        alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 180 } } } }] },
      { reference: "actions", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
        alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 180 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: { size: { width: 12240, height: 15840 },
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 } },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: GOLD, space: 6 } },
        spacing: { after: 120 },
        children: [
          new TextRun({ text: "Company 1710  ·  Connected process analysis", font: "Calibri", size: 16, color: TEAL }),
          new TextRun({ text: "     Display only — nothing created", font: "Calibri", size: 16, italics: true, color: "888888" }),
        ],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        border: { top: { style: BorderStyle.SINGLE, size: 8, color: GOLD, space: 6 } },
        spacing: { before: 80 },
        children: [
          new TextRun({ text: "For process owners  ·  Page ", font: "Calibri", size: 16, color: "666666" }),
          new TextRun({ children: [PageNumber.CURRENT], font: "Calibri", size: 16, color: "666666" }),
        ],
      })] }),
    },
    children: [
      p("CONNECTED ANALYSIS", { size: 18, bold: true, color: GOLD, after: 60 }),
      new Paragraph({ spacing: { after: 80 }, children: [
        new TextRun({ text: "How this company actually makes and loses money", font: "Calibri", size: 36, bold: true, color: NAVY }),
      ]}),
      p("An argument about how buy, sell, make, cost, and collect fit together on company 1710 — and which operating model to choose. Display only. 13 August 2026.", { italics: true, color: "555555", after: 220 }),

      h1("The diagnosis (not the inventory)"),
      p("Company 1710 already buys, receives, invoices vendors, takes orders, ships, bills, manufactures, costs, and collects. Calling this “not implemented” is the wrong diagnosis. Three things are true at once:"),
      bullet("A working path already posted — MZ-RM goods receipts, USSU vendor invoices, 1710 sales orders and customer invoices, years of actual costing, a live shop floor."),
      bullet("People keep entering a different path — third-party material as warehouse stock, buyer group 001, Hold instead of post, whatever the search help offers first."),
      bullet("The profit and loss is one company, but the teams behave as if buy, sell, make, and collect were four products. They are not."),
      p("A wrong purchase changes inventory and cost. That cost sits under the customer invoice. An invoice that never left the building becomes an unpaid item that credit never would have allowed if credit existed."),
      p("A well-run mid-market shop certifies one buy path, one sell path, one costing recipe, and a credit-and-collect loop, then hides the rest. This client has the opposite shape: a global template dump with a handful of live habits inside it. That is not richness. It is an ungoverned menu."),

      h1("Insight 1 — The commercial funnel leaks in three places, and they compound"),
      p("Read the book as a conversion story, not as four lists."),
      table(
        ["Stage", "On the books", "What the gap is really saying"],
        [
          ["Promise (orders)", "12,255", "Demand was taken."],
          ["Fulfil (deliveries)", "7,959", "About one order in three never became a delivery. Cash cannot start."],
          ["Recognise (customer invoices)", "5,982", "About one delivery in four was never billed. Unbilled inventory or cutoff — not “billing is missing.”"],
          ["Collect", "5,174 paid · 3,014 open", "Collection works when someone does it. A third of the receivable shape is still out."],
          ["Tell the customer (outputs)", "928", "Most invoices never produced a letter, EDI, or print."],
        ],
        [2880, 2520, 4680]
      ),
      p("These are not four findings. They are one working-capital machine."),
      bullet("If you only fix collections, you call people about invoices they never received. Disputes go up, not cash."),
      bullet("If you only fix billing, you invoice into a book with no credit limits. You accelerate unsecured receivables."),
      bullet("If you only fix delivery, you push more goods into the unbilled pile."),
      bullet("If you only restrict order types, you clean the search help and leave a multi-million-dollar book converting poorly. One 2018 page of 1710 orders was about USD 481,000."),
      p("Sales can look busy, Finance can see revenue, Treasury can see cash stuck — all three “right,” and the company still starves. The weakest link sets DSO. Today three links are weak at once."),
      h2("Sequence that does not fight itself"),
      table(
        ["Choice", "What you optimise", "What you give up"],
        [
          ["Close unbilled first", "Revenue and cutoff", "Receivables jump unless credit is on"],
          ["Close output first", "DSO quality; fewer “we never got it” tickets", "Does not create missing invoices"],
          ["Close credit first", "Stops the next unsecured order", "Does not collect the 3,014 already open"],
          ["Unbilled, then output, then credit", "A working cash cycle", "Needs one owner across sales and receivables"],
        ],
        [2880, 3600, 3600]
      ),
      p("The last row is the only sequence that does not fight itself. Tightening credit first is morally tidy and cash-stupid: you freeze the front of the funnel while the back is still dark."),

      h1("Insight 2 — Buy and sell are the same P&L. Wrong purchases invent fake margin."),
      p("Company 1710 is one legal entity. Vendor invoices and customer invoices already posted here. Cost of goods on those customer invoices comes from the material’s price, which comes from costing, which comes from how you bought and made the thing."),
      p("That is why TG10 is not a buyer-training issue. It is a financial-model switch that clerks flip by picking a material."),
      table(
        ["How you fulfil", "What hits the books", "What the margin means"],
        [
          ["Stock (MZ-RM) — already received on 1710", "Inventory up at receipt. Actual costing can revalue it. The customer invoice takes cost from that stack.", "Price minus a real inventory cost. Variance is visible."],
          ["Drop-ship (TG10)", "Often no warehouse receipt. Cost is the vendor bill.", "Price minus purchase. The ledger and the shop floor never see it."],
          ["Plant-to-plant (stock transport 100011, Pranali)", "Stock moves. Transfer price / in-transit appears.", "Margin can hide in the other plant."],
          ["Make-to-order (89 sales-order stocks)", "Inventory belongs to a sales order.", "If you cost it as warehouse stock, cost of goods lands in the wrong story."],
          ["Project stock", "Zero records.", "Do not design this. It is not a process here."],
        ],
        [2880, 3600, 3600]
      ),
      p("When a buyer uses TG10 “because it is on the screen” and goods receipt fails, two errors happen. The obvious one is the message. The quiet one: even a successful TG10 path would have produced a different P&L than the MZ-RM path Finance thinks it is looking at. Mix them in one product hierarchy and every margin report is a blend of two economies."),
      p("The 5,982 customer invoices inherit this mess. The 3,472 cost estimates and the actual-cost ledger only discipline the stock path. The more TG10 you use, the more of the commercial book escapes the cost system you have been closing for years."),
      p("Optimization: do not delete TG10. Name it. Drop-ship playbook, no goods receipt. MZ-RM stock playbook, with receipt. Two SOPs. Two search-help filters. Same company. The transformation is refusing to let one material play both roles."),

      h1("Insight 3 — Costing is the honesty of every sales invoice"),
      p("Seventy-four ways to roll a cost. One overhead sheet. 3,472 estimates. 3,071 materials with a price. 2,594 in the actual-cost ledger. Tens of thousands of period records — years of month-end, not a pilot."),
      p("This company already decided to know what things cost, then under-used the only tool that puts overhead into the product, then offered clerks 74 recipes."),
      bullet("Overhead stays in cost centers. 1,623 cost centers and 10,732 cost elements exist; the sheet is basically unused. Every manufactured item looks cheaper than it is. Every sales margin looks fatter than it is. A sales manager can “prove” a price that does not cover the building."),
      bullet("A zero activity rate is a margin weapon. Time posts; labour in the estimate is nothing."),
      bullet("More estimates than materials means versions. If the released price is a ghost, the next goods receipt explodes price difference into the P&L — which Finance will blame on purchasing."),
      bullet("Actual costing is on and old. If the close is late, “not distributed” appears. If it is closed but quotes still use a stale standard, you have two truths."),
      p("Understated product cost plus 5,982 invoices is systematically optimistic gross margin. That optimism funds discounts and “we can afford to wait on the 3,014.” It is the cash problem wearing a costing badge."),
      p("Adult combination: one recipe for 1710, hide the other 73, and put live rates on the one overhead sheet. Keeping 74 with a matrix is how you got here. Pricing from actuals is a later transformation, after standard is worth reading."),
      p("This month: list materials you sell on 1710 whose standard price is zero or older than two closes. Release current estimates before the next receipt. That stops a class of P&L fires that look like purchasing errors."),

      h1("Insight 4 — The shop floor is live, and only three-quarters finished"),
      p("About 2,950 orders (production plus internal). About 2,479 shop-floor headers. About 1,021 items — headers outnumber items; many orders were never a simple “make this.” About 10,666 component reservations: bills of material really explode. About 1,838 confirmations: roughly a quarter of orders were never confirmed."),
      p("Unconfirmed orders are work-in-process on the balance sheet, not variance on the P&L. You can look profitable because cost is still hanging on the order. Confirm, and variance lands. A controller who pushes confirmations in week four of the close will “create” losses that were always there."),
      p("Those confirmations feed actual costing. Incomplete confirmations plus a live ledger means a close that cannot tell the truth. And those 10,666 reservations are demand on components: if the component is TG10, the reservation is a fantasy; if it is MZ-RM, it is real procurement. The shop floor is silently choosing the buy path."),
      p("Finish or close the open orders before you redesign costing. Otherwise you will roll a beautiful standard onto zombie orders and call the variance “the new recipe.”"),

      h1("Insight 5 — Credit, collections, and output are one process wearing three hats"),
      p("Credit master: empty. Unpaid invoices: 3,014. Paid: 5,174. Outputs: 928. Orders taken: 12,255."),
      p("A company that can collect (5,174 times) but does not remind (928) and does not check credit (0) is not “bad at collections software.” It is good at receiving money when the customer feels like paying, and silent the rest of the time."),
      bullet("Credit decides whether the next promise is allowed."),
      bullet("Output decides whether the customer knows they owe you."),
      bullet("Collections decides whether anyone asks."),
      bullet("Dispute decides whether “I will not pay” has a reason or is just delay."),
      bullet("Cash application decides whether the bank file finds the invoice."),
      p("Today output is thin, credit is absent, dispute is email, collections is heroic, and cash application works. Heroic collections on a book that does not send invoices and does not stop bad orders is how you burn collectors and still grow receivables."),
      p("Empty credit plus a fat order book is a sales success metric and a treasury time bomb. If you pay sales on bookings (12,255) not cash (5,174), you are incenting the leak in Insight 1."),
      p("Do not buy a collections suite this quarter. It will digitise a broken letter. Send statements. Work the 3,014 oldest-first after a statement exists. Then decide classic credit versus a collections suite versus formally unsecured and priced into the margin. The transformation is “we collect as a process.” The software is later."),

      h1("Insight 6 — Unused configuration is a ticket machine, not an asset"),
      p("376 sales types. 139 purchasing types. 98 release strategies. 462 buyer groups. 74 costing recipes. 591 controlling areas. Used on 1710, day to day: a handful."),
      p("Every extra choice in a search help is a future wrong document. The ticket will sound like “SAP will not receive” or “vendor not valid.” The root is almost never a missing type. It is the wrong type from a generous menu."),
      p("Unused config looks like readiness in a demo and like entropy in support. Here it is entropy. The program is not to use all 376 types. It is to certify about fifteen and hide the rest — one design rule, four modules, the same week."),
      p("Hide in the search help first (reversible). Do not delete until something has been unused for a year and is not part of the other landscape on this client. There are signs of a second book next to 1710. Training “please pick the standard ones” relapses the first time a contractor arrives."),

      h1("Insight 7 — The first leak is master data, before anyone hits Create"),
      p("1,283 customers exist. 795 have a sales view. About 490 cannot take a sales order in a sales area. That is why “I cannot sell to this customer” tickets appear — and why someone then offers a 377th order type."),
      p("Source lists exist on other plants, not 1710. Requisitions exist in volume. Auto-PO dies. Buyers type POs by hand, pick TG10, Hold, buyer group 001. The “purchasing process problem” started as a plant-assignment problem."),
      p("Master-data gaps feed Insights 1, 2, and 6. A weekly completeness list is cheaper than a new process: customers without a sales view, vendors without a 1710 purchasing view, materials without a 1710 plant view or with a zero price, source-list rows not on 1710. That list is the transformation backlog."),

      h1("Insight 8 — Do not automate the wrong path"),
      p("About 1,239 electronic messages versus 12,255 orders. Most of this company is still typed at the glass. If you put an API in front of SAP now, you will encode TG10, buyer group 001, no credit, and silent invoices — at machine speed. That is industrialising the leak."),
      p("Certify the path. Make it honest. Make it collect. Then put a bot or an interface on the certified path only."),

      h1("Insight 9 — Follow one dollar through the company"),
      p("A dollar of sales on 1710 began as a promise. Chance it never shipped: material. If it shipped, chance it was never billed: still material. If billed, chance the customer never got a document: high. Chance we checked whether they should have been sold to: none."),
      p("The cost under that dollar came from a stock standard (maybe stale, maybe missing overhead), or a drop-ship purchase, or a plant transfer, or a sales-order stock. Four cost stories. One invoice layout. If the factory made it, a quarter of sister orders were never confirmed, so some “profit” may still be sitting in work-in-process. If they pay, cash application can find it. If they do not, we mostly do not ask."),
      p("A dollar of spend on MZ-RM, plant 1710, buyer group 002, purchasing org 1710 can be received and invoiced. That is the dollar to copy. A dollar on TG10 is a different economy — unless someone tries to receive it, in which case it is a stuck dollar. A dollar on buyer group 001 never becomes a purchase order without a human retyping it. A dollar on Hold is a dollar Finance cannot see."),
      p("Spend and revenue meet in 1710’s P&L. Treating them as two implementations is how you get a clean purchasing project, a clean sales project, a clean costing project, and a dirty company."),

      h1("What good looks like here"),
      table(
        ["Today", "A year from now if you choose the connected program"],
        [
          ["376 types in the search help", "About 15 certified; the rest hidden"],
          ["TG10 and MZ-RM used interchangeably", "Two named scenarios, two playbooks"],
          ["74 costing recipes, one dead overhead sheet", "One recipe, live rates, monthly release"],
          ["No credit, 928 outputs, 3,014 open", "Statements go out; credit on new orders; open items worked weekly"],
          ["About a quarter of shop-floor orders unconfirmed", "Confirmation is a close step, like a bank rec"],
          ["Auto-PO dead; source list on other plants", "Source list on 1710; buyer group 002; auto-PO from the pile"],
          ["Margin is a blend of four fulfilment economies", "Margin by scenario: stock / drop-ship / plant transfer / make-to-order"],
          ["Projects to implement what already posted", "Projects to stop using what should stay on the shelf"],
        ],
        [5040, 5040]
      ),
      p("That is transformation. It is mostly subtraction and ritual, not new modules."),

      h1("Optimizations that do not require a program"),
      bullet("Search-help diet. One change per module. Biggest ticket reduction per hour of work.", "actions"),
      bullet("Material personality. TG10 labelled “drop-ship only” in the description users see. MZ-RM labelled “stock 1710.”", "actions"),
      bullet("Lock buyer group 001 for 1710. The auto-PO failure disappears without a new program.", "actions"),
      bullet("Copy a working source-list row onto plant 1710. That is the whole auto-PO project.", "actions"),
      bullet("Output as a close step. No period close if invoices without output exceed a threshold.", "actions"),
      bullet("Zero-price hunt. Release before next receipt. Stops P&L explosions mislabelled as purchasing.", "actions"),
      bullet("Confirmation Friday. Work-in-process stops being a surprise in week four.", "actions"),
      bullet("Unbilled Monday. Deliveries without invoices, 1710 only.", "actions"),
      bullet("Oldest-open Wednesday — after you know a statement exists. Do not call into a vacuum.", "actions"),
      bullet("Display before design. Open 100011, an MZ-RM receipt, a USSU invoice, a 1710 customer invoice. Copy those.", "actions"),

      h1("Five forks you have to write down"),
      p("“All of the above” is how you got 376 types."),
      bullet("What kind of company is 1710? The data says mostly stock, some plant transfer, a little make-to-order, accidental drop-ship. Pick “stock manufacturer with a named drop-ship exception.”"),
      bullet("Is credit a control or a story for auditors? Control: load limits; sales will shrink; that is the point. Story: stop saying you have credit; price the risk."),
      bullet("Is margin a sales number or a cost number? Sales: you will keep under-absorbing overhead and celebrating. Cost: one recipe, live rates, actual-costing close, uglier margins you can bank."),
      bullet("Fewer tickets or more capability? Tickets fall from hiding types. Capability is contracts and scheduling — already configured, almost unused. Tickets first (90 days). Capability second (the next year). The usual order is the reverse."),
      bullet("One landscape or two? If 1710 and the other orgs are two businesses, split the operating model. If they are one, finish the 1710 views and stop borrowing other plants’ source lists."),

      h1("Next steps — this order is the analysis"),
      p("First, stop mixing economies. Name stock versus drop-ship. Hide the dangerous types. Lock buyer group 002. A week of design, a week of search help. This prevents new damage."),
      p("Second, finish the dollars already in motion. Unbilled deliveries. Outputs on existing invoices. Confirm or close shop-floor orders. Oldest unpaid after a statement exists. This turns working capital, not a slide."),
      p("Third, make the next dollar honest. One costing recipe. Overhead rates. Zero-price materials released. Customer sales views completed. Source list on 1710."),
      p("Fourth, only then add capability or software. Auto-PO. Contracts. Collections software. A bot. An API. Multipliers on a certified path are transformation. Multipliers on TG10 plus empty credit are a faster mess."),
      p("Do not start implement-goods-receipt, implement-billing, implement-costing, or implement-credit-software in parallel with step one. Those projects are how this client acquired 376 types and still cannot receive TG10."),

      h1("What to tell a steering committee"),
      p("1710 already buys, sells, makes, and collects. The P&L is one company and we have been running it as four modules. We leak cash three times — we do not ship everything we promise, we do not bill everything we ship, and we do not send or chase a large share of what we bill. We then invent margin by costing without overhead and by mixing drop-ship with stock. We will not implement SAP. We will certify one stock journey and one drop-ship exception, hide the rest of the menu, make costing tell the truth on the invoices we already send, and collect the invoices we already raised — in that order. The prize is working capital and honest margin, not a new document type.", { italics: true }),
    ],
  }],
});

const out = path.join(__dirname, "..", "docs", "CONSULTANT_BRIEFING.docx");
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(out, buf);
  console.log("wrote", out, buf.length);
});
