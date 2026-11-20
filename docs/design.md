# The design of the page

The page's look and words, written down so that more than one helper — human or AI — keeps them alike. The source of
truth is [web/editor.css](../web/editor.css) and [web/editor/](../web/editor/README.md); this page says what the values
mean and how to choose new ones. Change the tokens here and there together.

## Tokens

### Colours

Every colour is a pair in `:root`: one for the light theme, one for the dark theme. The dark theme applies when the
browser prefers dark (`prefers-color-scheme`) unless the page is pinned light, and always when `data-theme="dark"` is
set on `<html>`.

| Token | Light | Dark | Used for |
|---|---|---|---|
| `--bg` | `#F3F4F8` | `#12141C` | the page behind everything |
| `--panel` | `#FFFFFF` | `#1B1E2A` | cards, the canvas, the log, drawers, inputs |
| `--ink` | `#1B1E2B` | `#E9EBF3` | body text |
| `--muted` | `#5D6278` | `#9AA0B8` | secondary text, labels |
| `--line` | `#DADDE8` | `#2E3243` | borders |
| `--accent` | `#2F4BDB` | `#7C93FF` | primary buttons, focus rings, links' emphasis |
| `--accent-ink` | `#FFFFFF` | `#0E1120` | text on `--accent` |
| `--ok`, `--ok-bg` | `#187652`, `#DFF3EA` | `#5FD3A4`, `#163428` | done, passed, the result box's border |
| `--warn`, `--warn-bg` | `#8A5408`, `#FCEFD9` | `#F2B55B`, `#3A2B12` | warnings, review rounds |
| `--bad`, `--bad-bg` | `#B4344F`, `#FBE3E8` | `#F38BA0`, `#3D1B24` | errors, danger buttons, the acting-block mark |
| `--run-bg` | `#E3E8FD` | `#1F2748` | the Run pill's background, code backgrounds |

Rules:

- **Every text colour reaches 4.5:1 against its background.** For block colours, white bold labels are the test, and
  [tests/editor/hues.test.cjs](../tests/editor/hues.test.cjs) works the contrast out of `HUES`, so a new colour can't
  slip under.
- **Blocks are coloured by job, not by service.** Every connection — Home Assistant, Docker, Plex and the rest — is
  the one `--bad`-family pink `#C2185B`; the remaining hues say what a block does (start, repeat, ask, check, talk,
  show…).
- Add a new state as a `--x` / `--x-bg` pair in both themes, never as a one-off hex in a rule.

### Type

Three typefaces, from [web/editor.css](../web/editor.css), with system fallbacks after each:

- `--font-display`: **Bricolage Grotesque** — the name in the header and every heading.
- `--font-body`: **Atkinson Hyperlegible** — everything else. It is made for legibility at small sizes.
- `--font-mono`: **JetBrains Mono** — pills, status lines, code, and anything that is data rather than prose.

Sizes: body 15px with 1.5 line height; controls 14px; labels and secondary text 13px; the header 20px; pills 11px
mono, uppercase, letterspaced. The typefaces load from Google Fonts today; self-hosting them is G3 (#453).

### Corners

- **8px** on controls (buttons, selects, inputs) and small chips.
- **10px** on menus, cards and run-log steps.
- **12px** on the big panels: the canvas, the run log, drawer cards.
- **999px** (a pill) on pills and round chips.
- 4–6px inside code blocks and small inset fields.

### Shadows and layers

Menus float with `0 10px 28px rgba(10,12,25,.18)`; drawers slide over the canvas with `-14px 0 44px` of the same.
Layers, lowest to highest: the canvas and its zoom buttons (5–6), the first screen (9999), menus (10000), drawers
(10001), the header bars (10002) — so a drawer can open over the first screen, and the header stays clickable above
everything.

### Pills

`.pill` is the small uppercase label on a run-log step: `--run-bg` with `--accent` text by default, and `.ok`,
`.warn`, `.bad` for the three states. Round chips in the review strip use `--warn-bg` / `--warn`.

## Layout

The page is a **workbench**: toolbar on top, block canvas left, run log right — a grid of `1.6fr` and `1fr` with a
12px gap ([F2–F3](../ROADMAP-addendum.md#f-the-page)).

- **One row of controls** at 900px and up: the menus, the Describe field, Step, Stop, Run and Settings share the row,
  and no label wraps — a wrapped label would make the row two lines tall in a long-worded language. At 1280×720 the
  canvas starts within 120px of the top, and Run is on the first row in every language.
- **Panels open as drawers over the canvas**: examples, import/export, programs, memory, the sample house, backups,
  keyboard help, connections and share are fixed to the inline end, `min(640px, 94vw)` wide, with the focus kept
  inside and Esc to close. The canvas never moves underneath.
- **Menus** are `<details>` with an absolute body under the button: at least 230px wide, at most `min(430px, 86vw)`.
- **On a phone (600px and under)** the row wraps; every button, select and summary is at least 44px high and Run is
  52px; and the program shows as a short read-only outline instead of the block editor, with **Edit blocks** in the
  subbar to swap (#450).
- **Right-to-left languages mirror automatically**: always use the logical properties (`inset-inline-end`,
  `padding-inline`, `margin-inline-start`), never `left`/`right`, and flip explicitly with `[dir=rtl]` only where a
  direction genuinely differs.

## Voice

The words are the most consistent part of the design. Write new page text to these rules:

- **Short sentences.** *Press **Run**.* Not: "Pressing the Run button will begin the execution of your program."
- **Plain words.** *Ask* for "authenticate", *run log* for "execution transcript". When a term is needed, explain it
  once in plain words: *an agent, a helper that decides its own steps* ([agent.md](agent.md)).
- **British spelling.** Colour, behaviour, licence.
- **What a thing does before how it works.** *Save log keeps every step, its timing and the result as a file.* — the
  doing first, the mechanics after, or not at all.
- **Name the control the person sees**, in bold, exactly as labelled: **Settings → Connections**, **Copy as text**.
- **Every word the page shows is translated.** Put it through `tr("…")` and add the English to `i18n/` for all 34
  languages ([CONTRIBUTING.md](../CONTRIBUTING.md)). Write plain English first — it is what the translators start from,
  and placeholder names like `{things}` stay as they are.
