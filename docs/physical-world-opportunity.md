# Physical-world opportunity (OddHobb × Pogtown × Ochema × Stonedoorway)

Saved 2026-10-10. Thesis: don't compete on generating digital worlds —
build the bridge that makes digital creations giftable and physically
real. Two adjacent markets: things made FOR people, and everything
supplied so they can MAKE the thing. (Pinterest Aug 2026: clay bag
charms +1499%, beaded charms +965%, miniature rooms +296% — search
growth, not sales. Slant 3D's agent-accessible MCP confirms creation →
manufacturing is connecting.)

## Brand opportunities (retail hypotheses, pending Shenzhen quotes)

- OddHobb Tiny Worlds (£35–79) — bedroom/studio/fictional miniature +
  booklet + digital twin; furniture upgrades later.
- Charm Laboratory (£15–29) — pet/object photo → bespoke piece +
  colour-coordinated kit. Easiest compilation test.
- Ochema Grimoire (£29–99) — historical text → edition/annotated
  hardcover/full craft kit; downloads and physical from one spec.
- Stonedoorway Breathing Objects (£39–119) — desk objects that brighten/
  dim with guided patterns (v1: programmable light, no breath claims).
- Pogtown Physical Pogs (£15–49) — agents/characters as figures from
  approved online geometry, with galleries and eventual homes.

## Wilder ideas (same platform)

Agent status room (lamp/window/display respond to agent events); music
taste as tiny room (+QR playlist); rebuild-a-remembered-place (sentimental
kits, human review where geometry is thin); buildable libraries
(grimoire shelves, fairy tales, family histories); weird little computers
(cyberdecks, terminals — Seeed/Elecrow/JLCPCB match). Seeed takes custom
kit BOMs + outside links + packaging from 5 kits. Muse Gadgets direction
(ESP32/Pi open firmware) says: sell beautiful shells/docks for existing
AI hardware, not the intelligence.

## Model: digital first, physical upgrade (both directions)

Discover/create digital → keep digital (editable, viewer, world) → make
physical (object/kit) → persistent ownership + upgrades (reorders,
accessories, twin). Physical-first buyers can activate digital later —
tech must improve the product, never gate it.

## Moat: manufacturability + kit compiler, not prompt-to-CAD

Explicit checks: geometry, materials, tolerances, compatibility, rights,
safety, availability, assembly, packaging, delivery. Manufacturer makes
the part; OddHobb makes buying + building work.

## Experiments (in order)

1. Personalised Charm Lab (consolidation + booklet, low complexity).
2. Tiny World 001 (room + 10 furniture + optional digital world).
3. Ochema Grimoire Project (multi-material, outside miniatures).
4. Then: agent-event RGB room (digital→physical proof before holograms).

## Agent-addressable world (endgame)

Shared object record (appearance, design, manufacturer, behaviour,
world-place). Implemented as `backend/objects.py`: identity + event
protocol + resolve endpoint. Personas persist; rooms reflect states.

## Split

External: Atlas/world models, mesh rigging, MakerWorld, JLC/Seeed/Elecrow/
Slant manufacturing, ChatGPT/Muse/Pogtown agents. Ours: persistent
identities + physical/digital correspondence, templates, discovery +
recipes, validation + routing + orchestration, agent interfaces.
Flagship: Tiny Worlds. Commercial test: Charm Lab. Infrastructure:
Shenzhen compiler. AR glasses improve hardware already in homes.
