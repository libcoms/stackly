---
name: stackly
description: "«Тетрадь»: a squared school notebook where the left margin behind one red rule holds what matters about each line."
colors:
  page-ground: "#FAFBFD"
  grid-square: "rgb(64 104 168 / .075)"
  paper: "#FFFFFF"
  paper-2: "#F3F5F9"
  sunken: "#E9EDF3"
  ink: "#141820"
  ink-2: "#3C4351"
  mute: "#626B79"
  line: "#E1E6EE"
  line-2: "#C8D0DC"
  margin-red: "#E5544C"
  ballpoint-blue: "#2346D8"
  ballpoint-blue-hover: "#1A37B8"
  on-blue: "#FFFFFF"
  ballpoint-blue-text: "#2346D8"
  ballpoint-blue-ink: "#1A32A3"
  ballpoint-blue-soft: "#E9EEFD"
  ballpoint-blue-mid: "#B7C5F5"
  highlighter: "#FFEB8A"
  highlighter-soft: "#FFF8D6"
  on-highlighter: "#3F3200"
  tick-green: "#157A4B"
  tick-green-soft: "#E4F3EB"
  wrong-red: "#C52E28"
  wrong-red-soft: "#FCEBEA"
  code-ground: "#11141B"
  code-text: "#E6E9F0"
typography:
  display:
    fontFamily: "Golos Text, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "clamp(34px, 4.2vw, 52px)"
    fontWeight: 650
    lineHeight: 1.06
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Golos Text, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "clamp(26px, 3vw, 34px)"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "-0.025em"
  section:
    fontFamily: "Golos Text, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "19px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Golos Text, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Golos Text, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Golos Text, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.2
  figure:
    fontFamily: "Golos Text, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "30px"
    fontWeight: 650
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontFeature: "tnum"
  margin-numeral:
    fontFamily: "JetBrains Mono, SFMono-Regular, Consolas, Liberation Mono, monospace"
    fontSize: "19px"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "-0.03em"
  margin-index:
    fontFamily: "JetBrains Mono, SFMono-Regular, Consolas, Liberation Mono, monospace"
    fontSize: "14px"
    fontWeight: 500
    lineHeight: 1
    fontFeature: "tnum"
  answer:
    fontFamily: "JetBrains Mono, SFMono-Regular, Consolas, Liberation Mono, monospace"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.04em"
  code:
    fontFamily: "JetBrains Mono, SFMono-Regular, Consolas, Liberation Mono, monospace"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.65
rounded:
  hairline-tag: "4px"
  small-tag: "5px"
  item: "6px"
  control: "8px"
  sheet: "10px"
  large: "12px"
  pill: "999px"
spacing:
  cell: "24px"
  gutter: "clamp(16px, 4vw, 32px)"
  sidebar: "236px"
  margin-col: "64px"
  margin-col-phone: "48px"
  row-inset: "18px"
  panel-y: "18px"
  panel-x: "20px"
  section-gap: "32px"
  page-top: "36px"
  page-bottom: "72px"
components:
  button-primary:
    backgroundColor: "{colors.ballpoint-blue}"
    textColor: "{colors.on-blue}"
    typography: "{typography.title}"
    rounded: "{rounded.control}"
    padding: "0 18px"
    height: "42px"
  button-primary-hover:
    backgroundColor: "{colors.ballpoint-blue-hover}"
    textColor: "{colors.on-blue}"
  button-ghost:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 18px"
    height: "42px"
  button-ghost-hover:
    backgroundColor: "{colors.paper-2}"
  button-soft:
    backgroundColor: "{colors.ballpoint-blue-soft}"
    textColor: "{colors.ballpoint-blue-ink}"
    rounded: "{rounded.control}"
    padding: "0 18px"
    height: "42px"
  button-danger:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.wrong-red}"
    rounded: "{rounded.control}"
    padding: "0 18px"
    height: "42px"
  button-small:
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "34px"
  chip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "34px"
  chip-on:
    backgroundColor: "{colors.ballpoint-blue-soft}"
    textColor: "{colors.ballpoint-blue-ink}"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "10px 13px"
    height: "44px"
  answer-field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.answer}"
    rounded: "{rounded.control}"
    width: "200px"
    height: "44px"
  sheet:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.sheet}"
    padding: "18px 20px"
  nav-item:
    textColor: "{colors.ink-2}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "40px"
  nav-item-on:
    backgroundColor: "{colors.ballpoint-blue-soft}"
    textColor: "{colors.ballpoint-blue-ink}"
  margin-row:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    padding: "14px 18px 14px 0"
    height: "72px"
  due-tag:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.small-tag}"
    padding: "5px 8px"
  due-tag-late:
    backgroundColor: "{colors.wrong-red-soft}"
    textColor: "{colors.wrong-red}"
  new-badge:
    backgroundColor: "{colors.highlighter}"
    textColor: "{colors.on-highlighter}"
    rounded: "{rounded.hairline-tag}"
    padding: "3px 7px"
  note-to-remember:
    backgroundColor: "{colors.highlighter-soft}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.control}"
    padding: "10px 14px"
  count-badge:
    backgroundColor: "{colors.margin-red}"
    textColor: "{colors.on-blue}"
    rounded: "{rounded.pill}"
    padding: "0 6px"
    height: "20px"
---

# Design System: stackly

## Overview

**Creative North Star: "Тетрадь" (the school notebook)**

stackly is a squared exercise book. Work sits on white sheets laid over a faint 24px blue-grey square grid; text is graphite; everything you can press, every link and every selection is written in ballpoint blue. The left margin of each list sits behind one thin red rule, and that margin holds what matters about each line: its number, its due date, its mark. The sidebar is the page's own margin, separated from the content by the same red rule. The world was chosen by the user on 2026-10-26 and replaces the previous indigo/Onest look, which is now an anti-reference.

The system is flat and quiet so that the content (tasks, worked solutions, code) stays louder than the frame. Depth comes from paper on ground and hairlines, not from shadows. Numbers that line things up live in the margin; numbers that are read in running UI are set in the same sans as the text with tabular figures. Each role's home opens with a single «Дальше» line naming the next step, and every list below it is one sheet with rows rather than a grid of same-size cards.

Density is working-tool density: 16px body, 60 to 72px rows, 8px controls, generous page padding (36px top, 72px bottom). Light and dark themes are both first-class; dark is the same notebook at night, with the grid and the margin rule kept and the ink inverted.

**Key Characteristics:**
- Squared page ground (24px cell) under white sheets with 1px hairlines.
- The margin column: number or date left of a 1px red rule on every list.
- Ballpoint blue is the only action colour; margin red is never an action.
- Golos Text for everything; JetBrains Mono only for code, margin numerals, task numbers, answers and group codes.
- Flat by default; 8px controls, 10px sheets; pills only for counters, progress and switches.
- Left sidebar per role on desktop, bottom tab bar on phone, no in-page tab strips.

## Colors

A paper-and-ink palette: one cool white sheet, graphite text, and four pen colours that each carry a single meaning.

### Primary
- **Ballpoint Blue** (`ballpoint-blue`): fills of primary buttons, the active switch, progress bars, focus rings, caret and checkbox accent. Its text twin (`ballpoint-blue-text`) colours links, «Начать»/«Открыть» row actions and the active tab-bar item. `ballpoint-blue-ink` on `ballpoint-blue-soft` is the selected state (active nav item, selected chip, picked row, soft button); `ballpoint-blue-mid` is the border of the strongest bank tile and the faint dot in Python maps.

### Secondary
- **Margin Red** (`margin-red`): the margin rule itself, drawn as a colour-mix of margin red at 85% everywhere (lists, sidebar edge, landing sheet); the unread/count badges in navigation; the today outline in the activity calendar.
- **Wrong Red** (`wrong-red`, on `wrong-red-soft`): overdue dates in the margin, late due tags, wrong answers, error messages, the danger button. Red is the colour of a deadline or a mistake, never of an invitation.

### Tertiary
- **Tick Green** (`tick-green`, on `tick-green-soft`): done. The tick in the margin of a finished homework, completed progress bars, correct answers, the ok badge, the sync dot.
- **Highlighter Yellow** (`highlighter`, `highlighter-soft`, text `on-highlighter`): a builder decision that the user has not explicitly confirmed. Used only for notes to remember («Запомни», teacher comments on homework, «что изменилось» and topic notes, the yellow cheat card), for «новое» badges and new-task squares, for the ×2 points badge on bank tiles, and for text selection and the `.mark-hl` underline stroke. Never for status, deadlines or progress.

### Neutral
- **Page Ground** (`page-ground`) under the **Grid Square** (`grid-square`) lines: the squared field every page sits on; also the `theme-color`.
- **Paper** (`paper`): sheets, list containers, inputs, the sidebar, menus, dialogs.
- **Paper Shade** (`paper-2`): hover inside a sheet, inline code, answer and output boxes, sheet footers.
- **Sunken** (`sunken`): segmented-control track, neutral due tag, task-number plates, empty progress track.
- **Graphite** (`ink`): text and headings; also the toast ground. `ink-2` for secondary text and body copy in sheets; `mute` for metadata, labels and margin captions.
- **Hairline** (`line`): every sheet border and row divider. `line-2` for input and ghost-button strokes and dashed empty states.
- **Code Ground** (`code-ground`, `code-text`): the one dark slab in light mode, for code blocks, with its own syntax pens (keywords #9FB4FF, strings #9FDDB9, numbers #F5B36E, comments #7A8293).

**Dark theme.** Applied by `prefers-color-scheme: dark` unless `data-theme="light"`, or forced by `data-theme="dark"`. Ground #101217 with grid rgb(140 170 230 / .06), paper #171A21, paper-2 #1D2129, sunken #242933, ink #E8EBF1, ink-2 #B9C0CC, mute #8E96A4, line #292E38, line-2 #3B414D, margin #E8635B, blue fill #4466F0 (hover #5C7BFF), blue text #93A8FF, blue ink #BACAFF on soft #1C2546, highlighter #5A4C12 / soft #2B2611 with text #FFE58A, green #4CC98D on #0F2A1D, red #FF7C72 on #3A1715.

### Named Rules
**The One Pen Per Meaning Rule.** Blue means you can act or it is selected; margin red means the margin or a deadline/error; green means done; yellow means remember this. A colour never borrows another's meaning.

**The No Red Invitations Rule.** Red never fills a primary action. The only red button is the destructive one, and it starts as a red outline on paper.

**The Marker Is Not A Status Rule.** Highlighter yellow marks notes, «новое» and the ×2 points badge. It never encodes progress, a deadline, or an item's state.

## Typography

**Display Font:** Golos Text (with Segoe UI, system-ui)
**Body Font:** Golos Text (with Segoe UI, system-ui)
**Label/Mono Font:** JetBrains Mono (with SFMono-Regular, Consolas)

**Character:** one plain, Cyrillic-native grotesque does all the talking, tightened for headings (650 weight, negative tracking); the mono is the handwriting in the margin and the code on the board.

### Hierarchy
- **Display** (650, clamp(34px, 4.2vw, 52px), 1.06, -0.035em): the guest landing hero only.
- **Headline** (650, clamp(26px, 3vw, 34px), 1.15, -0.025em): the page title at the top of every working page; landing section heads go to clamp(26px, 3vw, 38px).
- **Section** (650, 19px, 1.3, -0.015em): section heads inside a page («Потом», «Выполненные», «Ученики»); sheet heads are 17px.
- **Title** (600, 16px, 1.3): the title of a row in a margin list; the «Дальше» line title is 17px.
- **Body** (400, 16px, 1.55): running text; intros under page titles cap at 62ch.
- **Label** (500, 13px, 1.2): metadata lines under row titles, field hints, KPI labels, in `mute`. Field labels are 600 14px in `ink`.
- **Figure** (650, 30px, 1, tabular): stat figures in the KPI strip and other running numbers: Golos Text with tabular-nums, never mono.
- **Margin numeral** (JetBrains Mono 600, 19px, 1.05, -0.03em): the day of a due date in the homework margin (22px in the «Дальше» line), with the month below in 11.5px Golos `mute`. Bank and picker indices in the margin are mono 500 14px, tabular.
- **Answer** (JetBrains Mono 600, 17px, 1.3, +0.04em): the answer input, the answer box, group-join codes (uppercase, +0.12em).
- **Code** (JetBrains Mono, 13.5px, 1.65): code blocks; inline code 0.86em on paper shade.

### Named Rules
**The Mono Is Handwriting Rule.** JetBrains Mono is limited to code, margin numerals, task numbers, answer fields and group codes. Numbers in running UI (KPIs, prices, rates, counts, tables) use Golos Text with `tabular-nums`.

**The No Kicker Rule.** A page title stands on its own; any metadata about it (group, teacher, subject) runs as a 500 14px `mute` line under the title, not above it.

## Layout

The page ground is a 24px square grid (`spacing.cell`), drawn as two 1px linear gradients offset by -1px. Content sits in sheets on top of it.

**Shell.** Signed-in, at 1000px and wider: a fixed 236px left sidebar on paper, separated from the content by a 1px margin-red rule at 85%; logo at the top, role sections with small 600 12px `mute` headings, account and tools at the bottom behind a hairline. The sidebar is built per role in JS (`buildNav()`/`navItems()`). Under 1000px the sidebar collapses to a 56px top bar (logo, search, theme, avatar) and a 62px bottom tab bar (`syncTabbar()`) on 96% translucent paper with a 12px blur. Guests get a sticky 60px top bar with logo, «Тарифы», «Войти» and a blue trial button. There are no in-page tab strips; the old tab-strip class is hidden.

**Content column.** Max 1160px, side gutter clamp(16px, 4vw, 32px); working pages pad 36px top, 72px bottom; sections are 32px apart with 12px under their heads. Each role's home starts with the page title, then the «Дальше» line, then lists.

**The margin column.** Every list sheet reserves a 64px left column (48px under 560px) for its number, date or tick; a 1px red rule runs full height at its edge; row text starts 18 to 22px right of the rule. Rows are 60px (bank) to 72px (homework) tall with 14px/18px insets.

**Breakpoints.** 1000px (sidebar vs tab bar), 860px (KPI strip 4 to 2 columns, form columns stack), 560px (margin column narrows, row actions drop under the title), 520px (guest bar compacts).

### Named Rules
**The Margin Column Rule.** Lists of things with a number, date or mark are one sheet with a margin column and a red rule, not a grid of cards. Stats are one strip divided by hairlines, not separate tiles.

## Elevation & Depth

Flat by default. Depth is paper on squared ground, defined by 1px hairlines; sheets at rest carry no shadow. Shadows appear only on things that float above the sheet: menus, dialogs, tooltips, the drawer, and the two "objects on the desk" (the auth card and the landing sample sheet).

### Shadow Vocabulary
- **Card** (`box-shadow: 0 1px 0 rgb(20 24 32 / .04)`): a near-invisible bottom edge; available but rarely used.
- **Lift** (`box-shadow: 0 1px 2px rgb(20 24 32 / .05), 0 10px 24px -14px rgb(20 24 32 / .28)`): the auth card, the landing sample sheet and Telegram demo.
- **Pop** (`box-shadow: 0 2px 6px rgb(20 24 32 / .06), 0 22px 48px -18px rgb(20 24 32 / .34)`): account menu, search dialog, tooltips, drawers.
- **Segment** (`box-shadow: 0 1px 2px rgb(20 24 32 / .1), inset 0 0 0 1px var(--line)`): the selected segment in a segmented control.

### Named Rules
**The Paper Lies Flat Rule.** A sheet that stays in the page never gets a shadow; only surfaces that open over the page do.

## Shapes

Small, regular corners: 8px on controls (buttons, inputs, chips, nav items, notes), 10px on sheets and panels, 12px in rare large containers. Small tags step down to 5px (due tags, task-number plates, codes) and 4px («новое», tiny badges). Full pills only for count badges, progress bars and the switch. Borders are 1px hairlines; inputs and ghost buttons use the darker `line-2`; empty states and the group-code box use a 1px dashed `line-2`. The brand mark is a 3px-cornered square cell with a blue ballpoint tick, drawn in CSS.

## Components

### Buttons
Plain and firm, written in blue ink.
- **Shape:** gently squared (8px), 42px tall, 0 18px padding, 600 15px Golos; small 34px / 0 12px / 14px.
- **Primary:** ballpoint blue fill, white text; an optional arrow nudges 2px right on hover.
- **Hover / Focus:** fill deepens to `ballpoint-blue-hover`; active scales to 0.98; focus is a 2px blue outline offset 2px.
- **Ghost:** paper with an inset 1px `line-2` stroke; on hover paper shade and a `mute` stroke.
- **Soft:** `ballpoint-blue-soft` with `ballpoint-blue-ink` text (class name `.btn.lime` is a legacy name; it is blue, not yellow).
- **Danger:** paper with a 45% red inset stroke and red text; fills red with white text on hover.
- **Link button:** 600 14px blue text, underlined on hover.

### Chips
- **Style:** paper, inset 1px `line-2`, 8px corners, 34px min-height, 500 14px `ink-2`. Number chips (task numbers in filters and the picker) are mono 600, min 38px wide.
- **State:** selected is blue-soft with blue-ink text, a 40% blue inset stroke and 600 weight.

### Cards / Containers
- **Corner Style:** 10px.
- **Background:** paper on the squared ground.
- **Shadow Strategy:** none at rest (see Elevation).
- **Border:** 1px `line`.
- **Internal Padding:** 18px 20px; empty states 22px 24px with a dashed border, a 600 16.5px title and an optional CTA row.

### Inputs / Fields
- **Style:** paper, 1px `line-2`, 8px corners, 44px min-height, 10px 13px padding, 15.5px Golos; label above in 600 14px `ink` with 7px gap.
- **Focus:** border and a 1px outer ring in ballpoint blue; hover darkens the border to `mute`.
- **Answer field:** the same box set in JetBrains Mono 600 17px with +0.04em tracking, 200px wide.
- **Error / Disabled:** form messages on `wrong-red-soft` or `tick-green-soft`, 8px corners; disabled controls drop to 50% opacity.

### Navigation
- **Sidebar (≥1000px):** 40px items, 8px corners, 500 15px `ink-2` with a 19px stroke icon; hover paper shade; active blue-soft fill, blue-ink text, 600. Count badges are margin-red pills pushed right.
- **Tab bar (<1000px):** equal-width 62px items, 22px icons over 11px labels in `mute`; active item turns blue-text with a 2px blue bar along its top edge.
- **Guest bar:** sticky, 92% translucent paper, 10px blur, hairline bottom.

### Margin List (signature)
One paper sheet, 10px corners, rows divided by hairlines, a 1px red rule (margin red at 85%) 64px from the left edge. Left of the rule, centred: a due date (mono day over a `mute` month; red when overdue), a green tick when done, or a mono task index. Right of the rule: the 600 16px title, a 13px `mute` metadata line, an optional thin blue progress bar with tabular count, and a blue text action at the far right. Hover tints the row paper shade. Used for student homework rows, bank lists, teacher group homework (expanding rows whose body indents past the rule), the homework picker (wider 98px margin with a checkbox and right-aligned number), landing sample sheet and landing steps.

### «Дальше» Line (signature)
The single next-step line at the top of each role's home: a margin-list row standing alone as its own sheet, 22px below the page title, with a 22px mono numeral in the margin, a 13px `mute` lead, a 17px title, a progress bar, and the primary button at the right (dropping under the title under 560px).

### Tags and Badges
- **Due tag:** 600 12.5px on `sunken`, 5px corners; soon is blue-soft, late is red-soft, done is green-soft.
- **«новое» badge:** highlighter fill, `on-highlighter` text, 600 11px, 4px corners.
- **Note to remember:** highlighter-soft block, 8px corners, 10px 14px padding, `ink-2` text.
- **Progress bar:** 6px pill on `sunken`, blue fill growing from the left; green when complete.

## Do's and Don'ts

### Do:
- **Do** put lists of numbered, dated or marked items in one sheet with a 64px margin column and a 1px red rule (margin red at 85%), 48px under 560px.
- **Do** start every role's home with the page title and the «Дальше» line.
- **Do** use ballpoint blue for every action, link, focus ring and selected state.
- **Do** set running numbers in Golos Text with `tabular-nums`; keep JetBrains Mono for code, margin numerals, task numbers, answer fields and group codes.
- **Do** keep sheets flat with 1px hairlines; reserve the Pop shadow for menus, dialogs, tooltips and drawers.
- **Do** define every new colour in both light and dark token sets.

### Don't:
- **Don't** return to the indigo/Onest look of the previous world.
- **Don't** build grey SaaS dashboards of same-size stat cards; stats are one strip divided by hairlines.
- **Don't** use margin red or wrong red for a primary action, a link or a decorative accent.
- **Don't** use highlighter yellow for status, deadlines or progress.
- **Don't** add in-page tab strips; navigation is the role sidebar on desktop and the bottom tab bar on phone.
- **Don't** place a label line above a page title; metadata goes under it.
