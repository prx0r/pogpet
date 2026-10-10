# Card P0 verdict + coding pass (founder audit, 2026-10-10)

Verdict: ~65–70% constructed, ~40% joined into the customer journey.
Target flow: upload Dad photos → known as Dad → 6 finished cards → tap →
Front/Inside/Back £2.99 → Buy → Value/Speedy + arrival → Shopify pay →
exact card + exact route fulfilled.

## Findings (accepted)

- Two card systems: agent path (matcher/compiler/copy/title-art) advanced;
  website gallery hand-builds ONE birthday_4photo, bypassing it. Fix first:
  gallery = subject → brief → match → compile top 6 → previews.
- Six layouts exist (arch/dots/news/gold/wall/four-photo) but recipes/
  holds ONE. Publish all six; eligibility by photo count (1 → arch/news/
  gold/dots; 2–3 → +wall; 4+ → +four-photo). Never demand 4 uploads.
- Upload: person-selected batch + single-face images → one "Use as Dad?"
  confirm → auto-tag. Face picker only for multi-person ambiguity.
- Gallery button still Reserve→/order (pre-Shopify). Must be Buy/Add to
  basket via Storefront cart path.
- Shipping gaps: compare not connected to Cards; Speed = dispatch not
  delivery; UI shows supplier totals instead of shipping charges + leaks
  supplier names; webhook ignores shipping choice (always Standard);
  picks collapse SKU identity; no robust arrival primitive.
- Fix: GET /api/cards/:id/delivery → {value, speedy} with opaque route
  IDs; checkout carries delivery_option_id frozen; webhook fulfils exact
  route. Arrival = ESTIMATED ranges (production + transit + weekends +
  buffer), labelled as such; provider-ETA confidence later, same UI.
- Price truth: recipes/*.json, mcp_server, oddhobb_change still £7.99 —
  all must read cards.card_price().
- Gates to verify live: dev-vs-live Shopify store; CARD_PANEL_CONFIRMED.

## Pass (P0.1–P0.10)

P0.1 gallery→compiler · P0.2 six recipes · P0.3 one-tap auto-tag ·
P0.4 Buy/Add-to-basket · P0.5 card delivery endpoint · P0.6 shipping
charges (not totals) · P0.7 frozen route honoured post-payment ·
P0.8 estimated arrival ranges · P0.9 purge £7.99 · P0.10 real £2.99
end-to-end test. Freeze Objects/cottages/Atlas meanwhile.
Acceptance: Dad + 4 photos → confirm → ≥5 distinct finished cards →
Front/Inside/Back → Buy → Value/Speedy + arrival → pay £2.99+ship →
exact revision, exact route. Real card at the door = P0 done.
