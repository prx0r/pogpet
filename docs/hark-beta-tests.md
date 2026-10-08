# Hark beta tests — canonical card system (v1.12.0)

Run on MCP, public tier + your own `api_key` (or `owner_sig`) on every call.
Owner for all runs: `hark-dad-a7a5cc`. Subject: Chris
(`person_9fdc85d6730d43e099dc`, father, golf). Report path (MCP/REST),
tool results, and every `card_url`/`proof_url` with each run.

## T1 — acceptance: birthday card for Chris (the whole game)

1. `oddhobb_make_card({subject_id: "person_9fdc85d6730d43e099dc", occasion: "birthday", vibe: "playful_balloons", tone: "funny", signature: "Ben & co"})`
2. Expect: `ok:true`, `template_id birthday_4photo`, revision 1, six previews
   (front, inside_left, inside_right, back, listing, print_pdf), a `proof_url`,
   and a second content block (contact-sheet image).
3. Open `proof_url` → latest revision renders with all four faces.
4. PASS = six views present, contact sheet visible, proof opens the card.

## T2 — one-call photo path

1. `figg_card_for_person({person: "Dad", occasion: "birthday", tone: "funny"})`
2. Expect: subject resolved to Chris, best confirmed photo picked, `via:mcp`,
   £7.99 FIXED product, `card_url` + `proof_url`, contact sheet attached.
3. PASS = no manual photo_id, no invented copy beyond profile facts.

## T3 — copy edit loop

1. Take the T1 `design_id`. `oddhobb_edit_card_copy({design_id, message: "New message here"})`.
2. Expect: new revision (r2), everything else identical, proof_url unchanged.
3. PASS = revision bumped, old revision still renders at `/cards/<id>/r1`.

## T4 — negative: schema caps

Each must fail with the cap named (40 / 240 / 40):

1. `oddhobb_edit_card_copy` with a 41-char headline.
2. `oddhobb_edit_card_copy` with a 241-char message.
3. `figg_card_save` with 3 photos on `birthday_4photo` (needs exactly 4).
4. `oddhobb_regenerate_title_art` with vibe `yolo` (must list the 8 frozen vibes).
5. PASS = all four rejected, no revision minted (latest revision unchanged).

## T5 — negative: fulfil and checkout gates

1. `POST /cards/<id>/order` with `fulfil:true` → expect 410 (use checkout).
2. `oddhobb_checkout_card` on a revision with no export render → expect 409.
3. Re-post checkout with the same `idempotency_key` → expect `reused:true`, no second draft.
4. PASS = 410, 409, reused — in that order.

## T6 — designed lane smoke (art check, not buy)

1. `oddhobb_ideas({person: "Dad", occasion: "birthday"})` → ideas reference golf, not biscuits.
2. `oddhobb_create` with the top `idea_id` → revision frozen.
3. `oddhobb_render` preview → expect either a real artifact or a staged reason naming the missing provider. Silent `done:{}` is a FAIL — report it.
4. `oddhobb_review` on the artifact → blank panels must verdict `revise`, never `ship`.
5. PASS = golf-relevant ideas, no silent empties, blanks fail review.

## T7 — source and tier honesty

1. Save with `"via":"rest"` in the body over MCP → expect stored `via:mcp` (transport wins, spoof ignored).
2. Health `tools_full` (94) vs your `tools/list` count on public tier — report both numbers.
3. PASS = stamp says mcp, counts reported, no 502s without a ray id logged.

## Reporting format (every run)

```
Test: T1 | Path: MCP public+api_key | Result: PASS/FAIL
design_id, revision, proof_url
What I saw (one line per view). What broke (exact error text).
```
