# Home and schedule cards

Dev: remove duplicate homepage hero and pre-schedule metrics; upcoming matchday first, complete schedule and latest results links alongside headings. Historical finished state remains explicit. Shared team cards toggle independently on click or Enter/Space, ignore interactive links and text selection, preserve seat order, hide undisclosed players. Current page state persists through rerender in memory.

Schedule: compact month selector, collapsible filters, chronological match rows; positional wind labels only for known order, no per-name wind boxes. Public projection adds seatOrderKnown for drawn or published matches; no business writes.

Artwork application/static/matchday-landscape.png generated with built-in image_gen. Prompt: warm ivory clean upper 65 percent, muted ink mountains/lake/pavilion/bamboo in bottom 30 percent, tiny vermilion sun, no text. Original PNG retained.

Validation: 11 seat-draw tests; browser independent card toggles, keyboard, result links, stable winds, pending avatars, home first section, PNG, filters, historical finished home, desktop 1440 and mobile 390 without overflow. No production release.
