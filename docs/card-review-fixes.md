# Greeting card review fixes

Delta against `0415a60807abc538ed2128d786a1cfc07619d914`.

## Changes

- Signup checks proof for the anonymous owner and atomically transfers card
  designs, render jobs, cutouts and reservations with the existing assets.
  Revisions, reservation IDs and artwork paths remain stable. A small additive
  SQLite migration stores the original artwork namespace. Referenced photos
  are copied rather than moved; this retains an extra source copy in storage.
- Signup during an active card render returns a retryable 409 before creating
  an account. Card downloads require the current database owner, including
  after claiming. The generic artifact endpoint rejects card subtree keys.
- Python MCP signs GET query owners only when they match `FIGG_OWNER`, fixing
  signed library/scene/job reads without signing requests for another owner.
- The website Pi extension registers all seven `figg_card_*` tools. The bridge
  verifies the browser identity with the backend before passing credentials
  into the isolated Pi process. Tools default to that owner and reject an
  explicitly different owner before making a request. The injected fetch shim
  now attaches its identity headers for URL-string requests as well.
- Text that still cannot fit at the minimum font size fails the render with a
  shortening instruction. A failed print export cannot be reserved.

## Apply

Back up the SQLite database and keep a clean checkout of the base commit.
From the repository root, use the patch in the accompanying ZIP:

```bash
git apply --check /path/to/oddhobb-0415a60-fixes.patch
git apply /path/to/oddhobb-0415a60-fixes.patch
```

The ZIP also includes replacement files under `files/` for inspection. Use
either the patch or the replacement files, once. Restart Flask, bridge and
MCP after applying. Flask startup performs the additive database migration.
Existing accounts that already lost anonymous cards are not automatically
repaired; the migration fixes subsequent account claims.

## Verification

```bash
python -m unittest discover -s tests -p 'test_card*.py' -v
python -m unittest discover -s tests -p 'test_motion_contract.py' -v
# NODE_PATH must contain TypeScript 5.x and typebox; use your Pi dependencies
# or install those in a separate temporary test directory.
NODE_PATH=/path/to/test/node_modules node tests/test_pi_cards.cjs
python -m unittest discover -s tests -v
```

Card/regression/motion tests: 22 passed. Pi tool functional checks passed.
The real bridge + Flask browser flow passed with five uploads, preview, linked
MP4, PDF reservation, reload, account claim and post-signup edit/render. No
page errors or mobile horizontal overflow were observed. Browser R2 was a
local fake; its storage claim operation was stubbed, with copy behavior covered
by the unit regression.
Full offline suite: 33 passed, two existing factory failures because the
checkout lacks the gitignored STL masters (`no-master`). Python compilation
and whitespace checks passed. Tests use actual SQLite, Pillow and ffmpeg,
with fake R2 and mocked segmentation/provider transport. No paid generation,
checkout, publishing or push was performed. Live R2/provider/phone AR behavior
is not established by these checks.
