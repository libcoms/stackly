---
version: 1
slug: "public-index-html"
primary_target: "public/index.html"
related_targets: []
---

# stackly app (public/index.html)

Scope: the whole single-page app — guest landing and pricing (Persuade), student/teacher/admin cabinets, bank, materials and the EGE guide (Operate/Read). Redesign of 2026-10-26: new visual world «Тетрадь», old indigo/Onest look is anti-reference.

Audience and jobs: see PRODUCT.md. Student: see what is due, solve, read. Teacher: groups → homework → who submitted. Admin: overview, users, bank, stats.

Navigation decision (user): left sidebar per role on desktop, bottom tab bar on phone; no nested tab strips.

## Direction contract

THESIS: stackly is a school notebook: work sits on a squared sheet, the left margin behind one red rule holds what matters about each line (number, due date, mark). Refuses the grey SaaS dashboard of same-size stat cards.

OWN-WORLD: white sheet with a faint 24px blue-grey square grid on the page ground; graphite ink text; ballpoint blue for every action, link and selection; margin red only for the margin rule, deadlines, overdue and wrong answers; green tick for done. Highlighter yellow only for notes the reader must remember («Запомни», teacher comments) and for «новое»; never for status or deadlines. Golos Text for all UI and headings, JetBrains Mono for code and margin numerals. Flat: hairlines aligned to the grid, almost no shadow, small 8px radius, no pills except tags.

STORY: on opening, each role sees its next step at the top of its home; everything else is one sidebar click away.

FIRST VIEWPORT: sidebar (paper, separated from content by the red margin rule) with logo, role sections, account at the bottom; content column starts with page title and the «next step» line; lists below with numbers/dates in the margin column.

FORM: pick card «Тетрадь», #1 of my ordered list, seed key 9943759d. Signature move: margin column — numbers and due dates set in the margin left of a red rule on homework, bank and task lists.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
