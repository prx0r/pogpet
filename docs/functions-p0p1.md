# Ten functions (p0 foundations → p1 experiences)

Status key: LIVE (works today) · THIN (wiring/UI gap) · STAGED (needs
dashboard key/partner) · NEXT (to build). p0 = supplier foundations so
the endgame visions can exist; p1 = experiences on top. Natural order:
engines first, then packs, then grimoires.

## p0 — supplier foundations

**F1 · product-create check.** Prompt an idea → instant supplier
possibility verdict. LIVE: `POST /api/projects/check`, MCP
`oddhobb_project_check` (verdict + lanes + costs).
**F2 · supplier capability matrix.** Every lane's materials, grades,
costs, GB/US matrix. LIVE: registry (27) + `quotes/compare` + delivery
countdowns. STAGED: Mixam live client (real dates).
**F3 · recipe compile + feasibility gate.** LIVE: `recipes/check`,
`gifts/compile` (postage rule, rights gate, 0–100 gate).
**F4 · run-state tracking.** LIVE: needed→ordered→received→verified,
pack-only-when-verified.
**F5 · rights gate.** LIVE: purchasable false until sources clear.

## p1 — experiences (each states its engine dependency)

**F6 · grimoire pack one-click buy.** THIN: compile + rights + gift-pack
exist; needs gift-bundle checkout path + booklet PDF wired to pack.
Engines: F3 + booklet generator.
**F7 · upload 4 images + person → recommendation + filled card.** THIN:
guide funnel + slot-fill + card create all live; needs the single joined
flow (upload → suggest → recommend → render → message prompt).
Engines: labels + template_engine + cards.
**F8 · wrap with your face, one click.** THIN: candidates + renderer +
LIVE SKU exist; needs order asset publish step. Engines: labels +
Prodigi.
**F9 · living cottage configurator.** THIN: recipe + check live; needs
storefront UI (module picker: light/voice/screen/rooms). Engines:
components + objects.
**F10 · podium messages.** THIN: object registry + resolve/state live;
needs performer-message delivery into podium state + AR viewer pass.
Engines: objects + Pogtown runtime.

Rule: no p1 ships on a STAGED engine without marking it; no agent
publishes below the feasibility gate.
