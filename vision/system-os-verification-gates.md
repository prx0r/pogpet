# System OS: verification gates for an agent-run OddHobb (notes, 2026-10-10)

> Reference: `prx0r/dash` (agent-commerce kernel), `prx0r/influence`
> (influencer flow plane on the cmail graph), `prx0r/qprivately` (A-COM
> formal spec). Studied 2026-10-10; mechanisms below are what our system
> OS grows into. What we already have is §1; the rest is the build list.

## The vision in one line

Every state change in OddHobb — a photo confirmed as Dad, a quote
accepted, a pack listed, money moved — happens because an agent proposed
it, deterministic gates passed it, and a signed receipt settled it. Agents
run everything; nothing they say is true until a gate says so. The value
is the packs as hard validated gates plus the dependency graph that shows
exactly why each thing is allowed. Done right this is beautiful: a shop
you can watch thinking, where every product carries its proof.

## 1. What we already have (keep)

- `catalog/tools/validate_pack.py` G01–G14 + levels
  DRAFT/PRINT_READY/LISTABLE/PROVEN. Closest thing in the whole system to
  a real gate runner: deterministic, sha-pinned print files, re-render on
  any change so photos can never drift from what prints.
- `catalog/tools/build_graph.py` → `graph.json` + `STATUS.md`:
  supplier/template/product nodes, occasions/interests/slots vocabulary.
- `studio/` trial invariants (power cap, flash < 3 Hz, night brightness)
  enforced device-side; the agent cannot override them.
- MCP full/public tiers, owner-from-key enforcement, secrets scrubbed.
- Money gates in embryo: Shopify fulfil on `orders/paid` only, no card
  charge from our API, Meshy spend ask-first with ledger.

## 2. Steal from dash (agent commerce, live on VPS)

- **Agent decides WHAT, never WHETHER** (`kernel/policy`: PURE→PRIVILEGED
  side-effect levels, verdicts ALLOW/HUMAN/DENY/FORBIDDEN). Our version:
  agents compose packs, pick photos, write copy — promotion to LISTABLE or
  any money movement needs a gate verdict, never the agent's word.
- **Approvals agents can't mint** (`kernel/approvals`: parameter-bound,
  single-use, hash-bound, only `human:*` approves; agents REQUEST/CONSUME).
  Our order/quote approvals and theinka-print runs want exactly this shape.
- **Append-only audit exported** (`kernel/audit`: every gate decision +
  security violation → BigQuery). Our `data/*.jsonl` ledgers are the seed;
  add gate-decision rows and stop letting history be rewritable.
- **UNKNOWN blocks, never passes** (campaign gates; `test_no_invented_numbers`,
  TBD never invented). Copy verbatim: missing quote, missing measurement,
  missing sample = FAIL, and no gate may invent a number (no estimated
  costs passing G07, no guessed dims passing G05 — already our rule, now
  make it structural).
- **Peer-review verdicts** (`CONFIRMED/CORRECTED/REJECTED/CARRIED`,
  re-checked against primary sources). Supplier quotes and listing claims
  get the same treatment: quote PDF or it didn't happen.
- **Graph discipline**: namespaced IDs, edge vocabulary (`USES/GOVERNED_BY/
  MAPS_TO`), PROPOSED nodes hidden from served views, promotion only by
  audited update. `graph.json` should grow edge types and stop serving
  DRAFT nodes to customers.

## 3. Steal from influence (receipts + chains)

- **TransitionReceipt as the only artifact**: canonical JSON, content-hash
  id, append-only hash-chained store with `replay`/`verify_chain`. Every
  pack promotion, every face confirmation, every quote acceptance mints
  one. FAIL is first-class — a failed gate writes a receipt too.
- **Gates versioned and content-addressed** (`evidence-fresh-v1`,
  `no-duplicate-v1`, `two-sources-v1`). Name ours the same way
  (`quote-fresh-v1`, `slot-measured-v1`, `sample-photo-v1`) so old packs
  keep their meaning when gates improve.
- **Settle by independent re-execution**: a second runner replays the
  receipt from bytes. Our `validate_pack.py` already re-runs preflight on
  the exact sha — extend the pattern to the whole promotion.
- **Private vs public chain**: raw evidence (customer photos, faces, cost
  breakdowns) stays private; only evidence roots, receipt hashes and
  PII-scanned manifests go public. Directly answers where customer face
  data lives in an auditable shop.
- **Human loop as banked intent** (`HLoop`: single-use prediction hash,
  409 without present, APPROVED = intent only). Our fulfil approvals and
  Meshy-spend approvals want this instead of chat messages.
- **Money as ledger + grants**: propose/authorize/settle with Ed25519
  grants (payload hash, subject, expiry, single-use) and drift flags.
  Shopify drafts and supplier orders get grant objects, not vibes.
- **Reputation from verified runs, never a score column**: a pack's
  PROVEN status and a supplier's reliability derive from receipts under a
  tree head. No star ratings, no trust-me fields.

## 4. Steal from qprivately (the math)

- **`S(t+1) = T(S(t), P) iff ∧ Gᵢ = PASS`** as the house law, written down.
  Cognition (any agent, any model) is unlimited and untrusted; only gates
  + grants move canonical state. Agents fill proposals, never STATE.
- **Content-address everything**: pack = receipt over
  (dependency graph + photo hashes + print sha). `no-duplicate` kills
  duplicate face jobs and duplicate packs structurally.
- **FAIL-closed grants with minimum proof levels** (V0–V12): preview
  needs V2, quote V7, $50 action V9, policy V12. Map our capabilities the
  same way — face-ID → pack-ship needs a high bar plus a signed grant
  with `max_risk_usd`, expiry, and predicates.
- **`settle()` + `verify_chain()`** for audit: who approved which pack,
  replayable years later.
- **Evidence/truth split with UNKNOWN default**: photo provenance as
  `{source.class, artifact_hash, max_age_days, min_sources: 2}` —
  one face crop is never enough to confirm a person.
- **ATASK discipline**: tasks need acceptance + evidence_required,
  `goal.done` is derived, never stored. No agent may declare "faces done"
  or "pack done" — only gates say so.

## 5. Build list (in order)

1. Gate-name and version every check we already run (packs, studio
   invariants, card export gate) — `*-v1` everywhere.
2. Receipts: one JSONL hash-chained log for promotions, face
   confirmations, quote acceptances, money moves. FAIL receipts included.
3. Human approvals as single-use hash-bound grants (spend, print, list).
4. Proof levels per capability; FAIL-closed MCP tools (unknown = deny).
5. Private/public chain split for customer photo/face data.
6. Independent settle runner + verify command; STATUS.md derives from
   receipts, not from whoever ran the tool last.
7. Supplier reliability + pack PROVEN derived from receipt history.
