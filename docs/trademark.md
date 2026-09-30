# Trademark & IP checklist

Status: **required gate** — `backend/concepts_src.py` refuses any listing pack
whose concept has `ip_check != "pass"`. Scan titles/tags against this file,
then set `ip_check: "pass"` in the concept record.

Last updated: 2026-09-30 (Round 6 — doc was referenced but missing).

## Rules we ship under

1. **Our marks:** `oddhobb`, `ochema`, `pog.pet`, `figg.` — use as brand
   only; do not imply partnership with any third party.
2. **Customer pets:** we render *their* animal. No claim of ownership over
   the pet's likeness beyond the print fulfilment the customer ordered.
3. **No third-party characters** in prompts, styles, or concept packs:
   Disney, Nintendo, Pokémon, Marvel, DC, FIFA clubs, Premier League marks,
   band logos, meme formats owned by others, celebrity likenesses.
4. **No trademarked product names** in listings (e.g. "iPad case", "iPhone
   skin") — use generic categories ("tablet sleeve", "phone skin").
5. **Music/voice:** edge-tts system voices only; no imitation of named
   performers; no third-party lyrics.
6. **Stock imagery:** Pixabay-sourced assets keep their licence provenance
   (`premesh/pixabay.py` records it). No scraped Google/Pinterest images as
   product art.
7. **Review screenshots / social proof slots** (concept library): only real
   customer content with permission; never fabricated reviews as fact.

## How to clear a concept

- Read the concept's title, tags, and prompt slots.
- If anything matches rules 2–5 → rewrite to a generic equivalent or drop
  the slot.
- When clean: set `ip_check: "pass"` on the concept record.
- Re-run listing-pack generation only after every included concept passes.

## Escalation

If a customer requests a licensed character (e.g. "make my dog into
Grogu"), the answer is a polite no plus an offer of a generic chibi/scifi
style. Do not generate, store, or list IP-adjacent renders.
