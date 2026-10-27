#!/usr/bin/env python3
"""Generates FORM_AUDIT.json + FORM_AUDIT.md from the rows below.
Code-judged audit of site-beauty @ 71a4f0a (live API unreachable during audit)."""
import json, collections

COMMIT = "71a4f0a (site-beauty, 'Update site/rehearse.html')"
LIVE = {
    "status": "DOWN — judged from code only",
    "checks": [
        {"utc": "2026-10-15T13:39:37Z", "via": "sandbox curl (browser UA)", "target": "https://oddhobb.com/ and /backend/api/sections, /me",
         "result": "HTTP 502 'Bad Gateway' (12-byte text/plain) returned by the sandbox egress proxy at the CONNECT stage; no Cf-Ray header. This is the sandbox proxy refusing/failing the tunnel, NOT a Cloudflare 502 from the origin."},
        {"utc": "2026-10-15T13:40Z-13:46Z", "via": "Hark browser (real Chrome)", "target": "homepage + 33 /backend/api GETs (18 public, 15 with owner+api_key)",
         "result": "ERR_EMPTY_RESPONSE on every URL incl. homepage (retried once). No Cloudflare error page, no Ray ID, no status code, no JSON. Origin/tunnel accepted the connection and sent nothing."},
        {"utc": "2026-10-15T13:41Z", "via": "web_fetch", "target": "/, /backend/api/sections, /backend/api/catalog", "result": "upstream_failure (page extraction failed)"},
    ],
    "not_tested_by_rule": ["POST /products/order", "POST /meshes", "POST /meshes/style (install_style)", "POST /videos", "POST /standup/render",
                           "POST /creative/art/order|mp4", "POST /cart/*", "POST /gift-packs", "any card render/export"],
}

# verdicts: KEEP / INHERIT / DEAD / BROKEN / MOVE
R = []
def row(page, el, label, js, api, backend, working, verdict, fix):
    R.append(dict(page=page, element=el, label=label, js_does=js, api=api,
                  backend_param_use=backend, working=working, verdict=verdict, fix=fix))

# ───────────────────────── index.html — global chrome ─────────────────────────
P = "index.html · global chrome"
row(P, "#greet-cta", "Start with someone →",
    "Hides greeting, focuses #ti (legacy chat input, hidden under every panel), dispatches 'pog:enter' (no listener anywhere).",
    "none", "n/a", "Code: works as a close button only; promised 'say who it's for' step never happens.",
    "BROKEN", "Route to /studio + open Add-family when /studio/library has 0 subjects; otherwise go to Quick with the selected subject pre-attached. Drop the #ti focus and dead 'pog:enter' event.")
row(P, ".greet__sub / .greet__steps copy", "greeting copy",
    "Static copy names a real family member and 'Dad' as examples.", "none", "n/a", "Static",
    "BROKEN", "Replace with generic examples; better: render the visitor's own saved people (names + faces) from /studio/library when signed in.")
row(P, "a[href=/privacy]", "Privacy link", "Router has no /privacy route; no privacy page in repo -> 'Page not found' panel.", "none", "n/a",
    "Code: 404/notfound (cannot verify bridge-served page while live is down)", "BROKEN", "Add site/privacy.html (and a router passthrough) or link to the hosted policy.")
row(P, "#g-signin", "Continue with Google",
    "hidden attr never removed; moved into account dialog. Click probes /auth/google/start (501 if no GOOGLE_CLIENT_ID).",
    "GET /api/auth/google/start ?return_to,claim_owner,owner_sig", "server.py google_start uses claim_owner, return_to", "Hidden; backend returns 501 unless OAuth creds set",
    "DEAD", "Delete until OAuth creds exist (or unhide behind /api/auth config flag). Keep handle+password path.")
row(P, "#acct-btn / #acct-name", "👤 sign in", "Opens account <dialog> (site-shell). Name painted '@handle' only when apiKey present.", "GET /api/accounts/me (on /account)",
    "uses X-API-Key; returns handle, display_name, email, active_mesh_id", "Code: OK", "KEEP", "Paint display_name (not raw handle) once /accounts/me returns it.")
row(P, "#cart-btn / #cart-n", "🛒 count",
    "refreshBadge() counts only /studio/basket reservations; cart page later sets badge = Shopify lines + reservations -> badge disagrees until /cart is opened.",
    "GET /api/studio/basket", "studio_library.basket (orders pending_checkout + drafts)", "Code: inconsistent count", "BROKEN",
    "One badge source: add Shopify cart line count (GET /cart?id=oddhobb.cartId) in refreshBadge, or have /studio/basket return the Shopify cart count.")
row(P, "#brand-btn / #switcher", "Switch world", "Toggles a menu with one entry ('oddhobb.com — you are here').", "none (GET /api/brand repaints it)", "server /api/brand", "Works, but nothing to switch to",
    "DEAD", "Make the logo a plain link to / until a second storefront exists.")
row(P, "#qsearch (+ #search-drop, #search-grid)", "search box",
    "Input element no longer exists; wireTopbar() no-ops, the live search drop (rankSearch/paintSearchTile, ~200 lines) can never open. /search?q= panel only reachable by typing a URL.",
    "GET /api/cards/templates (to build card rows)", "n/a", "Code: unreachable", "DEAD",
    "Either restore a visible search input that navigates to /search?q=, or delete the drop + synonyms code. Card rows hardcode price_cents 799 (backend card truth is £2.99) — read cards.public_price instead.")
row(P, "#catstrip / secchip section chips", "All · Board games · Gifts · Cards · My oddhobbs",
    "Strip element missing; GET /api/sections still fired on every load to paint nothing (section_of is used only to tag product tiles).",
    "GET /api/sections", "server /api/sections", "Code: request wasted, UI absent", "DEAD", "Drop the strip code; keep /products?section= filtering (fold SECTION_OF into /api/products/studio items).")
row(P, "#ti, #mic, #send (+ #concepts-overlay, #products-overlay, honey-badge, satchel, bee-status)", "legacy bobdod chat + 'How should we deliver this?' £6.99/£12.99/£19.99/£29.99",
    "MythicBee-era chat (~490 inline lines). .app sits under fixed full-screen .panel on every route, so it is never visible. Calls /api/ai/cf/@cf/meta/llama… and /api/ai/cf/@cf/openai/whisper (bridge/worker proxy per README, not a backend route) and carries a CF placeholder config {account:'YOUR_ACCOUNT_ID', token:'YOUR_CLOUDFLARE_TOKEN'}.",
    "fetch /api/ai/cf/* (bridge proxy)", "not a backend/server.py route", "Code: invisible on every route", "DEAD",
    "Delete lines ~1700-2216 of index.html, the overlays and the .app/.dialogue markup. Hardcoded overlay prices disagree with catalog.")

# ───────────────────────── Quick ─────────────────────────
P = "index.html · Quick (/)"
row(P, "#qk-mic-big", "Tap when you're ready (mic)",
    "Starts Web Speech recogniser + 60s session; every few seconds POST /quick/map with live transcript.",
    "POST /api/quick/map {text, owner, boost_lines}", "Uses text, boost_lines; owner only to read active_mesh_id. Ignores saved subjects / relationship / interests / birthday entirely.",
    "Code: OK (Chrome/Edge only; Safari/Firefox fall back to typing)", "KEEP",
    "Also send subject_id (studio selection) and have quick_map fold the subject's interests+relationship into scoring (the data already exists in subjects.profile_for).")
row(P, "#qk-flash prompts (QK_QBANK)", "'Who's it for — pet or person?', 'What's the occasion?', 'Do you know their colouring?'",
    "Floating questions chosen by local belief over 5 hardcoded lines (ornament, keychain, croc_tag, gift_card, brick) — 10 other live lines (keycap, golf_marker, card_rack…) are invisible to the belief engine.",
    "none (client-side)", "n/a", "Code: works, re-asks known facts", "INHERIT",
    "Skip 'who/pet or person/colouring' when a subject is selected (kind + photos known). Seed qk.lines from /api/products/studio items instead of the 5-line literal.")
row(P, "#qk-stop", "That's enough — show me options", "Stops recogniser, builds results.", "POST /api/quick/map (final)", "as above", "Code: OK", "KEEP", "—")
row(P, "#qk-how-toggle", "How it works", "Expands/collapses the 5-step list.", "none", "n/a", "OK", "KEEP", "—")
row(P, "#qk-mesh-chip, #qk-mesh-chip-results", "mesh —", "Shows 'mesh ab12cd34' (raw mesh id) after first map.", "from /quick/map active_mesh_id", "n/a", "Code: OK but meaningless to customers",
    "INHERIT", "Show the selected person's name + face thumb from /studio/library (selection.subject_id) instead of a mesh hash.")
row(P, "#qk-made (Made last week)", "Ornament £15 · Keychain £15 · Brick £20", "Static figures + literal prices.", "none", "STUDIO_LINES prices currently match (1500/1500/2000)", "OK today, will drift",
    "INHERIT", "Render from /api/products/studio (price_cents + stills.hero).")
row(P, "#qk-hits tiles", "Top matches", "Server matches -> tiles; click navigates to Products and preselects line+coat+hat.", "POST /api/quick/map", "matches[].recommended_* used", "Code: OK", "KEEP", "—")
row(P, "#qk-picked chips", "Shortlist", "Removes a boosted line; re-maps.", "POST /api/quick/map {boost_lines}", "boost_lines +4 score", "Code: OK", "KEEP", "—")
row(P, ".qk-opt[data-act=order]", "Order this — 'One-click Shopify on the top match'",
    "Only stores pending pick in localStorage and navigates to Products; no order is created.", "none", "n/a", "Code: works as navigation; label over-promises",
    "KEEP", "Relabel 'Customise & order' (or actually call the Products order with the inherited subject).")
row(P, ".qk-opt[data-act=upload]", "Upload a photo — 'Personal mesh → every product inherits'",
    "Navigates to /studio and writes a hint into #as-msg. The post-sculpt 'bring you back to your product' resume only exists in the orphan Upload panel poll(), so it never fires from Studio. Sculpting is off by default (FREE_MESH_PER_DAY=0).",
    "none", "n/a", "Code: resume path dead", "INHERIT",
    "Hide when the selected subject already has photos/mesh; otherwise deep-link /studio/people/<sid>. Move takePendingOrder() resume into studio-people after a mesh reaches 'succeeded'.")
row(P, ".qk-opt[data-act=products]", "Browse all products", "showTab('products') — same as tab rail.", "none", "n/a", "OK", "DEAD", "Remove (duplicate of the Products tab).")
row(P, ".qk-opt[data-act=gift]", "Gift card £5/£10/£15/£20", "Navigates to Products and selects gift_card.", "none", "STUDIO_LINES.gift_card.amounts_cents [500,1000,1500,2000] match", "Code: OK", "KEEP", "Read the amounts label from gift_card.amounts_cents.")
row(P, ".qk-opt[data-act=chat] + #qk-dt", "Talk to bobdod — 'Agent guides the rest'",
    "Writes canned strings into #qk-dt via regex; no agent/LLM/API behind it.", "none", "n/a", "Code: fake", "DEAD", "Remove the option and the 'bobdod' label (or wire a real agent).")
row(P, "#qk-ti + #qk-send", "Ask bobdod — or type instead of the mic",
    "Appends typed text to the ramble and re-maps.", "POST /api/quick/map", "text used", "Code: OK", "KEEP", "Relabel as 'Type instead' — it is the keyboard path for non-Chrome users, not a chat.")
row(P, ".qk-opt[data-act=again]", "Ramble again", "Restarts live session.", "/quick/map", "—", "OK", "KEEP", "—")
row(P, "#qk-shuffle", "Another prompt idea", "Changes text of #qk-prompt, which is permanently hidden.", "none", "n/a", "Code: no visible effect", "DEAD", "Delete button (or unhide #qk-prompt).")

# ───────────────────────── Studio ─────────────────────────
P = "index.html · Studio (/studio, /studio/people/<sid>)"
row(P, "#studio-add-friend dialog: Name + Person/Pet", "Add family",
    "POST /studio/subjects then navigate to the new person.", "POST /api/studio/subjects {name, kind, owner}", "Both used (studio_library.subject).", "Code: OK", "KEEP",
    "Add relationship, birthday (MM-DD) and interests here (POST /api/studio/subjects/<sid>/profile) — today they are only collected inside the Cards form.")
row(P, "(missing) relationship / birthday / interests editor", "—", "No Studio UI to view or edit what the backend already stores per person.", "POST /api/studio/subjects/<sid>/profile {relationship, birthday, interests[]}",
    "studio_library.subject_profile merges all three; read back by /studio/subjects, cardgen_api, family/reminders", "Missing", "MOVE",
    "Move the Cards 'Who are they to you?' + 'What are they into?' fields into a per-person profile card on /studio/people/<sid>; Cards/Quick/Perform then read it.")
row(P, "#friends conveyor (swiper)", "Your family", "Selecting a person navigates and POSTs selection; backend sets active mesh.", "POST /api/studio/selection {subject_id, mesh_id}",
    "Both used; db.set_active() updates the active star", "Code: OK; edge: empty subject + a mesh -> 400 'mesh not assigned'", "KEEP", "Send mesh_id only when it belongs to the subject (or skip the call when subject is empty).")
row(P, "#studio-upload (Add photos, multiple, accepts webp)", "Add photos",
    "Uploads each file then runs in-browser face detection and saves faces.", "POST /api/photos (multipart photo, owner) -> POST /api/studio/photos/<pid> {faces}", "photos: owner, source used; intake accepts jpeg/png/webp",
    "Code: OK", "INHERIT", "When a person is selected, link the upload to them automatically for single-face photos ({subjects:[{subject_id,face_id}]}) instead of dumping everything into 'Review faces'.")
row(P, "Find faces (button)", "Find faces", "Re-runs detection on photos with detection_status=pending.", "POST /api/studio/photos/<pid> {faces}", "used", "Code: OK (auto-runs after upload already)", "KEEP", "Show only when pending photos exist.")
row(P, "Refresh (button)", "Refresh", "Re-reads /studio/library. Copy tells users to 'Refresh to check' mesh progress.", "GET /api/studio/library", "used", "Code: OK", "DEAD",
    "Replace with automatic polling while any mesh is queued/running; remove the button.")
row(P, ".studio-filters (All/Portraits/Together/Activities/Favourites/Review faces)", "photo filters", "Client-side filters over library data. 'Activities' only matches manual 'activity' tags.",
    "none", "uses photo.tags/faces/favourite from library", "Code: OK", "KEEP", "Auto-tag (photo_labels.py exists server-side) so 'Activities' isn't empty by default.")
row(P, "Photo dialog: face selects, 'Also in the photo' checkboxes, Favourite, Tags", "Who's in this photo?",
    "Saves identities/favourite/tags.", "POST /api/studio/photos/<pid> {subjects[], favourite, tags[]}", "all used", "Code: OK", "KEEP", "—")
row(P, "Photo dialog: Create character for <name>", "Create character", "POST /meshes {photo_id, single:true} then assign to subject.", "POST /api/meshes; POST /api/studio/meshes/<mid>/subject",
    "photo_id, single used; mesh allowance FREE_MESH_PER_DAY defaults 0 (paid Meshy)", "Not tested (paid generation)", "KEEP", "Show allowance/price before the click (GET /api/credits).")
row(P, "#stv-prev / #stv-next / #stv-roster / carousel side slots", "mesh carousel", "Pick mesh -> rememberMesh -> /studio/selection (becomes active star).", "POST /api/studio/selection", "used", "Code: OK", "KEEP",
    "Hide demo slots (canonical dog, brick 1/2) once the owner has any succeeded mesh — they are mixed into every family's carousel today.")
row(P, "#stv-brick / #stv-brick2", "Use brick figure / Use brick figure 2",
    "POST /meshes/style -> install_style (switches the active mesh).", "POST /api/meshes/style {style, owner}",
    "server.start_style: owner taken from body with NO _owner_denied check (a user key or bridge token can install a style on any owner).",
    "Not tested (changes active mesh — forbidden)", "MOVE",
    "Offer 'brick' as a product base option on Products (no account mutation); add _owner_denied(owner) to /api/meshes/style.")
row(P, "#studio-unassigned-meshes select", "Whose character is this?", "Assigns an orphan mesh to a person.", "POST /api/studio/meshes/<mid>/subject {subject_id}", "used", "Code: OK", "KEEP", "—")
row(P, "#stv-msg / #as-msg hint from Quick", "status", "Quick writes 'after sculpt we'll bring you back' — not true from Studio (see Quick upload).", "none", "n/a", "Misleading", "BROKEN", "Fix resume or change copy.")

# ───────────────────────── Products ─────────────────────────
P = "index.html · Products (/products)"
row(P, "#pr-mesh-chip / #pr-d-mesh", "inherits mesh ab12cd34", "Shows a mesh hash.", "from GET /api/products/studio active_mesh_id", "n/a", "OK", "INHERIT",
    "Show 'For <name>' + face from /products/studio subject (already returned) instead of the hash.")
row(P, "#pack-budget + #pack-go", "Budget £ e.g. 30 → Build my pack",
    "Parses pounds, POST /gift-packs.", "POST /api/gift-packs {owner, budget_cents, mesh_id}",
    "Backend also accepts recipient, occasion, note, line — UI never sends them though the selected subject's relationship/birthday is known. No _owner_denied.",
    "Not tested (read-like but POST)", "INHERIT", "Send recipient=subject.relationship, occasion from upcoming birthday (/api/family/reminders); keep the budget field.")
row(P, "#pack-reserve (dynamic)", "Reserve the physical part", "POST /products/order without fulfil -> pending_checkout row with no checkout_url.", "POST /api/products/order {owner,line,mesh_id,qty}",
    "used; no payment path", "Not tested", "DEAD", "Replace with 'Add pack to basket' that creates the Shopify draft (fulfil:true) or a cart line; one checkout path.")
row(P, "#pr-gifts tiles", "For <name> — derived from your family",
    "Gift tiles from /products/studio. Clicking a 'name' gift puts the name into note, not the emboss text field.",
    "GET /api/products/studio?owner", "products_studio falls back to studio_subjects with interests:[] hardcoded — ignores interests/birthday saved via /studio/subjects/<sid>/profile; gift text sent as note (backend 'text' = emboss).",
    "Code: partially working", "INHERIT", "Backend: read subjects.profile_for() in the fallback. Frontend: send gift text as body.text (validated by _check_text) not note.")
row(P, "#pr-grid tiles", "Customise →", "selectProduct(line).", "none", "n/a", "OK", "KEEP", "—")
row(P, "#pr-coats chips", "jacket — physical winter coat", "Sets pr.coat; repaints stills.", "GET /api/studio/stills?line,coat,hat", "coat used by stills + order", "Code: OK", "KEEP", "—")
row(P, "#pr-hats chips", "hat", "Sets pr.hat.", "GET /api/studio/stills", "used", "Code: OK", "KEEP", "—")
row(P, "pattern (no control)", "—", "pr.pattern always 'solid'; grid/stills code still builds coat-<c>-<pattern> URLs.", "sent as pattern", "backend stores pattern only inside note text", "Unreachable", "DEAD", "Remove pattern branches from the UI code.")
row(P, "#pr-sizes chips", "size chips (label · mm · £price)",
    "Sets pr.size; for non-gift lines the price shown stays line price and pr.size is NOT included in orderPayload().",
    "— (not sent)", "/api/products/order has no size param; price = STUDIO_LINES[line].price_cents * qty", "Code: size choice silently dropped", "BROKEN",
    "Either send size (add backend support + per-size price) or hide size chips for non-gift lines. gift_card amount_cents path works.")
row(P, "#pr-qty-dec / #pr-qty-inc", "Qty − / +", "pr.qty 1-20; price display updates.", "sent as qty", "used, clamped 1-20", "Code: OK", "KEEP", "—")
row(P, "#pr-order", "One-click order → Shopify",
    "POST /products/order fulfil:true; shows 'Pay here →' with draft invoice_url.",
    "POST /api/products/order {owner,line,coat,hat,pattern,note,mesh_id,qty,fulfil:true,email,amount_cents}",
    "All used. email = owner if it contains '@' (handles never do) -> Shopify draft has no customer email. No text/name field though backend supports text (emboss) + slots and MCP has /api/products/personalise {subject_id,name}. No _owner_denied on this route.",
    "Not tested (creates order/draft)", "INHERIT",
    "Fill email from /accounts/me.email; add 'Name on it' prefilled from subject name -> body.text; add _owner_denied(owner) server-side.")
row(P, "#pr-order-reserve", "Reserve only", "Same POST with fulfil:false -> reservation with no checkout_url; basket then shows it with no Pay/remove action.", "POST /api/products/order",
    "used", "Not tested", "DEAD", "Remove; one order path (draft with invoice) only.")
row(P, "#pr-fit", "Fine-tune hat fit", "Opens /fit.html?line&part in new tab.", "→ fit.html POST /api/fit/placement", "Placement saved GLOBALLY per line+part (no owner, not on the order).", "Code: customer can overwrite shared seating", "MOVE",
    "Admin-only tool; remove from the customer detail card.")
row(P, "details.pr-mcp", "Agent / MCP — no token needed", "Developer instructions inside a product card.", "none", "n/a", "Static", "MOVE", "Move to /llms.txt or a footer 'For agents' link.")
row(P, "#pr-prints tiles", "Mug £12.99 · Cushion £29.99 · Poster £14.99 · … (11 tiles)",
    "Hardcoded PRINTS_CATALOG. Click only prints 'order via shop / agent (2D print path)' — no order button anywhere.",
    "GET /api/quotes/compare?line; GET /api/products/candidates", "Backend PRODIGI_PRODUCTS prices differ: mug 1499 vs 1299 shown, poster 1299 vs 1499, jigsaw 1899 vs 1699.",
    "Code: dead end + stale prices", "BROKEN", "Drive from GET /api/products (Prodigi rows with price_grade) and add a real order/cart action, or hide the shelf.")
row(P, "#pr-print-cands face carousel ◀ ▶", "best face options", "Click sets pr.artPhoto — never read by any code.", "GET /api/products/candidates?owner&line", "kind,line,n,owner used", "Code: selection discarded", "DEAD",
    "Delete until the print order path exists; then send photo_id/face_id with the order.")
row(P, "#pr-quote text", "Value £x (supplier) · Speed £y …", "Quote matrix text exposes supplier names to customers.", "GET /api/quotes/compare?line", "line,country", "Code: OK", "MOVE", "Admin/agent only; customers need one price + dispatch date.")

# ───────────────────────── Cards (brief) ─────────────────────────
P = "index.html · Cards (/cards) — being reworked by another agent"
row(P, "cards-auto: 'Who is it for?' select", "Someone new / saved people", "Lists /studio/library subjects; picking one inherits photos, relationship, interests and hides the identity block.", "GET /api/studio/library",
    "used", "Code: OK", "KEEP", "Default to the Studio selection instead of 'Someone new'.")
row(P, "cards-auto: Their name / Person or pet", "new person", "POST /studio/subjects.", "POST /api/studio/subjects", "used", "OK", "KEEP", "Only when 'Someone new'.")
row(P, "cards-auto: Who are they to you? / What are they into?", "relationship / interests", "Prefilled from library; saved back via /studio/subjects/<sid>/profile.", "POST /api/studio/subjects/<sid>/profile", "used", "OK", "MOVE", "Edit in Studio profile; Cards just reads.")
row(P, "cards-auto: Occasion select", "Birthday (only option)", "Single-option select.", "cardgen/make occasion", "used", "OK", "DEAD", "Drop the select until there is a second occasion (or drive from /api/family/reminders).")
row(P, "cards-auto: Age", "e.g. 70 (optional)", "Sent to cardgen.", "POST /api/cardgen/make", "used", "OK", "KEEP", "Prefill if birthday year is ever stored (currently MM-DD only).")
row(P, "cards-auto: Inside message / signature ('Love, Tom')", "message + sign-off", "Apply writes copy to design.", "POST /api/cards/<did>/…", "used", "OK", "INHERIT", "Prefill signature from /accounts/me.display_name.")
row(P, "cards-studio.js cardPrice='£7.99'", "price literal", "Legacy studio (loaded only for helpers) paints £7.99 until /cards/templates answers; card-viewer fallback '£2.99'; index search rows 799.",
    "GET /api/cards/templates product.price", "cards.card_price() fixed £2.99", "Stale", "DEAD", "Delete the literal (cards-auto already reads product.price); drop cards-studio.js once helpers are moved.")

# ───────────────────────── Videos ─────────────────────────
P = "index.html · Videos (/videos)"
row(P, "#club (comic chips, tap, mute)", "Pogtown Comedy Club", "Static club player from /assets/club/manifest.json.", "none", "n/a", "Code: OK (assets not in repo — cannot verify)", "KEEP", "—")
row(P, "a[href=/stage.html]", "Open live stage", "Links to stage.html (hardcoded demo dog, see stage.html).", "—", "—", "Demo only", "DEAD", "Remove link (or rebuild stage on the user's own mesh).")
row(P, "a[href=/rehearse.html]", "Rehearse a recorded performance / AR", "Links to internal GLB authoring tool.", "—", "—", "Internal tool", "MOVE", "Admin/internal nav only.")
row(P, "#vid-feed slides", "video feed", "GET /videos/feed + club manifest; IntersectionObserver autoplay.", "GET /api/videos/feed?limit=12", "limit used", "Code: OK", "KEEP", "—")
row(P, "[data-share]", "Share", "POST share, copies link.", "POST /api/videos/<vid>/share {}", "used", "Code: OK", "KEEP", "—")
row(P, "[data-pog] + window.prompt", "Pog (laugh) → 'What got you?'", "POST laugh then native prompt() for why.", "POST /api/pog/laugh {owner,video_id,t_seconds}; POST /api/pog/why {laugh_id,why}",
    "used; /pog/laugh has no owner auth", "Code: OK", "KEEP", "Replace prompt() with inline one-tap reason chips.")
row(P, ".feed__mute", "🔇/🔊", "Toggles mute on all slides.", "none", "n/a", "OK", "KEEP", "—")

# ───────────────────────── Perform ─────────────────────────
P = "index.html · Perform (/perform)"
row(P, "#pf-talents chips", "talent", "Sets state.talent.", "GET /api/acts", "talent used (non-comedy -> scene 'stage')", "Code: OK", "KEEP", "—")
row(P, "#pf-act + #pf-premise", "act / persona", "Select act; shows premise.", "sent as act", "server looks up act voice + premise", "Code: act voice never applies (see #pf-go)", "KEEP", "—")
row(P, "#pf-topic", "the bit", "Required text.", "sent as topic", "used", "OK", "KEEP", "Offer 2-3 starters from the selected person's interests/facts.")
row(P, "#pf-name", "their name (placeholder 'Bender')", "Sent as pet_name, default 'your pet'.", "sent as pet_name", "used verbatim; backend never derives the name from the mesh's subject",
    "OK", "INHERIT", "Prefill from the selected subject name (studio selection / /products/studio subject.name); backend default from mesh_subjects -> studio_subjects.name.")
row(P, "#pf-go", "Take the stage →",
    "POST /videos with voice:'ryan' hardcoded.", "POST /api/videos {owner,mesh_id,topic,talent,act,pet_name,voice:'ryan'}",
    "server: voice = body.voice OR act_voice OR 'ryan' -> because the UI always sends 'ryan', every act's own voice is ignored.",
    "Not tested (spends a video credit)", "BROKEN", "Omit voice unless the user picks one; add a voice chip row from GET /api/voices.")
row(P, "#pf-sharpen", "Sharpen my bit (writing room)", "Sends the performer NAME as persona.", "POST /api/jokes/premise {owner,topic,persona}", "server uses topic + persona (≤60 chars); owner ignored",
    "Code: works, wrong field", "BROKEN", "Send persona = selected act premise/name; keep pet name separate.")
row(P, "#pf-riff", "Riff it", "Shows riffs.", "POST /api/jokes/riff {owner,line}", "line used; owner ignored", "Code: OK", "KEEP", "—")
row(P, "#pf-credits", "Free: 5 videos a day · watermarked", "Literal text.", "— (GET /api/credits exists; loadStudioMeta fetches it into missing #st-credits)", "credits.video.remaining/limit",
    "Static", "INHERIT", "Render GET /api/credits?owner result here.")
row(P, "#pf-history items / #pf-dl", "your performances / Download", "GET /videos?owner list; click plays.", "GET /api/videos?owner", "owner + auth", "Code: OK", "KEEP", "—")

# ───────────────────────── Funnier / Art ─────────────────────────
P = "index.html · Funnier (/funnier)"
row(P, "duel 'A/B is funnier' buttons", "vote", "Vote then load next pair.", "GET /api/creative/duel; POST /api/creative/duel/vote {a_id,b_id,winner,owner}", "all used", "Code: OK", "KEEP", "—")
P = "index.html · Art (/art)"
row(P, "'Put it on something →'", "open format sheet", "Formats + prices from server.", "GET /api/creative/art", "formats from backend", "Code: OK", "KEEP", "—")
row(P, "format 'Buy £x →'", "Buy", "Reservation; draft_url printed as plain text, not a link; not added to the Shopify basket.", "POST /api/creative/art/order {art_id,format,qty,owner}", "used, owner-checked",
    "Not tested", "BROKEN", "Render a Pay link / add to the one basket.")
row(P, "'Make it a video →'", "MP4", "Renders MP4 and offers download.", "POST /api/creative/art/mp4 {art_id}", "backend also takes voice (unused by UI)", "Not tested", "KEEP", "Optional voice chips from /api/voices.")

# ───────────────────────── Cart / Account / Search ─────────────────────────
P = "index.html · Cart (/cart)"
row(P, "Shopify line − / + / Remove", "qty / remove", "Updates Shopify cart lines.", "POST /api/cart/lines {cart_id,action,line_id,qty}", "used", "Code: OK", "KEEP", "—")
row(P, "Checkout · £x", "Shopify checkout", "Link to cart.checkoutUrl.", "GET /api/cart?id", "used", "Code: OK", "KEEP", "—")
row(P, "Reserved rows (Pay · £x)", "product reservations", "Rows from /studio/basket; Pay link only if checkout_url; 'Reserve only' / pack / art reservations have no action and no remove.", "GET /api/studio/basket",
    "used", "Code: dead-end rows", "BROKEN", "Add cancel/remove; stop creating checkout-less reservations (see pr-order-reserve).")
row(P, "Saved creations 'Add to basket'", "Add to basket", "Always POST /cart/create and overwrite oddhobb.cartId — a second card starts a new cart and orphans the first.",
    "POST /api/cart/create {design_id,revision,qty}", "used", "Code: loses earlier basket", "BROKEN", "If oddhobb.cartId exists use POST /api/cart/lines {action:'add'} (as cards-studio buy() already does).")
row(P, "two baskets", "Shopify cart + reservations", "Cards go to Shopify cart; 3D products + art go to draft-order reservations with separate Pay links.", "—", "—", "Design", "BROKEN", "One basket: put product draft lines into the Shopify cart (or show a single combined checkout).")
P = "index.html · Account (/account + account dialog)"
row(P, "handle + password inputs, Sign in / Create account", "handle (placeholder uses a family first name) / password",
    "POST /accounts(/login) {handle,password,claim_owner}; stores api_key.", "POST /api/accounts | /api/accounts/login",
    "signup also accepts email, display_name, ref — UI never sends them (so later Shopify drafts have no email)", "Not tested (account creation)", "INHERIT",
    "Collect email (+ optional display name) on Create account; send pogpet.ref as ref; neutral placeholder.")
row(P, "Account panel: 'Active star: msh_…'", "active star", "Prints raw mesh id.", "GET /api/accounts/me", "active_mesh_id", "Code: OK", "INHERIT", "Show the selected person's name + face.")
row(P, "Account panel: Sign out", "Sign out", "Clears keys, new pog_ owner, reload.", "none", "n/a", "OK", "KEEP", "—")
row(P, "Account panel: profile fields (missing)", "email / display name / address", "No way to see or edit email/display name/default address.", "—", "/accounts/me returns email, display_name", "Missing", "INHERIT", "Read-only display first; edit later.")
P = "index.html · Search (/search?q=)"
row(P, "search panel", "Results for …", "Works only when the URL is typed (no input on the page).", "GET /api/products/studio (via loadProducts)", "—", "Code: unreachable from UI", "DEAD", "Restore a search input or drop the route.")

# ───────────────────────── Orphan panels ─────────────────────────
P = "index.html · ORPHAN panels (unreachable: router maps /upload→/studio, /shop→/products)"
row(P, "#panel-upload: #drop/#up-input, #up-sculpt, #spin-go, #roster, #people-grid (rename prompt)", "Your star / add someone / Sculpt them / Render 360° spin",
    "Never shown. Contains the ONLY post-sculpt pending-order resume and the people rename/autosort calls.", "POST /api/photos, /api/meshes, /api/me/active, /api/photos/autosort, /api/people/rename; GET /api/meshes/<id>/turntable", "routes exist", "Unreachable",
    "DEAD", "Delete panel + JS; port resume logic to studio-people; turntable could become a Studio button.")
row(P, "#panel-shop: #hero-q/#hero-go, #shop-concept, #shop-subject 'their name', #shop-apply, 'Add to cart'", "Shop",
    "Never shown. 'Add to cart' says 'Cart isn't wired up yet — that's Stripe'. shop-subject re-asks the name.", "GET /api/products?owner&concept&subject; /api/concepts; /api/meshes/<id>/products", "concept, subject used", "Unreachable",
    "DEAD", "Delete panel + loadShop/loadConcepts (~150 lines).")
row(P, "st-* (old Studio video form): st-go, st-topic, st-name, st-voices, st-scenes, st-credits", "—",
    "Markup removed, JS remains; loadStudioMeta() still fires GET /voices + GET /credits on the first Studio open of each page load, into elements that no longer exist.", "GET /api/voices, /api/credits, POST /api/videos", "—", "Unreachable",
    "DEAD", "Delete; reuse /voices + /credits in Perform.")
row(P, "quick-* / qp-* / funnel-steps (old in-Products quick funnel)", "—", "Markup removed, ~150 lines of JS remain.", "POST /api/quick/map", "—", "Unreachable", "DEAD", "Delete.")

# ───────────────────────── Other pages ─────────────────────────
P = "products.html"
row(P, "nav a[href=/learn/]", "Learn", "No /learn page in repo.", "—", "—", "Code: 404 likely", "BROKEN", "Remove link.")
row(P, "a[href=/api/etsy/listings] (×2)", "Listing JSON", "Relative /api/… (not /backend/api) — not a site route.", "should be /backend/api/etsy/listings", "route exists under /backend", "Code: wrong path", "BROKEN", "Fix path — or better move with the pack (below).")
row(P, "Etsy listing pack zip, GLB downloads (dog, brick 1, brick 2), '0 Meshy credits' copy", "ops downloads", "Internal seller/ops material on a customer page.", "static", "—", "Static", "MOVE", "Move to admin; keep the 'what arrives' photos for customers.")
row(P, "Load 3D model (model-viewer poster button), lightbox thumbs", "3D/photo viewers", "Local.", "static", "—", "OK", "KEEP", "—")
P = "fit.html"
row(P, "#m-t, #m-r, #m-s, #reset, #save", "Move/Rotate/Resize/Reset/Save placement", "Saves hat transform.", "GET/POST /api/fit/placement {line,part,position,rotation,scale}",
    "used; saved to a global file per line+part — no owner, never attached to an order", "Not tested (write)", "MOVE", "Gate behind admin token; customers should not edit shared fit.")
P = "quick.html"
row(P, "meta refresh → /#quick + link", "'Quick lives in the shop now — open Products → Quick'", "Redirect works via hash routing; copy is stale (Quick is the home tab).", "—", "—", "OK", "DEAD", "Replace with a server 301 to / and delete the file.")
P = "stage.html"
row(P, "#lines, #name ('Buster'), #voice (4 hardcoded voices), #render", "Edit your set / Render shareable video",
    "POST /standup/render with token only; plays hardcoded vid_p0standup001.", "POST /api/standup/render {name, voice, script}",
    "No auth; owner hardcoded 'demo', mesh hardcoded; runs synchronously up to 900 s (well past a typical ~100 s proxy timeout).", "Not tested (CPU render)", "MOVE",
    "Internal demo: move to admin or rebuild on the user's mesh as an async job (name from subject, voices from /api/voices).")
row(P, "#play, #unmute, #dl", "Play clip / Sound on / Download", "Plays the demo clip.", "GET /api/videos/vid_p0standup001/file", "—", "Demo", "DEAD", "Goes with the page.")
P = "rehearse.html"
row(P, "#motion-file, #motion-clip, #motion-time, #motion-play, #motion-poster, AR button", "Motion rehearsal (local GLB)", "Local-only authoring preview; asks for a rigged GLB.", "none", "n/a", "Code: OK", "MOVE", "Internal tool — remove from customer Videos tab.")
P = "admin.html / admin/index.html"
row(P, "admin.html (review dash)", "Review dash", "Public, noindex, 'not linked anywhere' internal QA images.", "static", "—", "Public", "MOVE", "Put behind auth or remove from site/.")
row(P, "admin/index.html (MythicBee Admin) + js/orders.js", "MythicBee Admin", "Legacy admin from another brand.", "—", "—", "Legacy", "DEAD", "Delete.")
P = "site/js (unloaded files)"
row(P, "app.js, chat-panel.js, creation-flow.js (+templates.js, preview-renderer.js), desksprite.js, gift-brief.js, gift-intelligence.js, prompt-bank.js, inworld.js, order-pipeline.js (+card-renderer.js), print-pipeline.js, prodigi.js, starfield.js, state.js, viral-card-library.js",
    "—", "Not referenced by any page (~3,800 lines). prodigi.js is a browser-side Prodigi client (no key embedded).", "—", "—", "Unreferenced", "DEAD", "Delete (git keeps history).")

# ───────────────────────── ranked fixes ─────────────────────────
FIXES = [
    ("Delete the invisible MythicBee chat layer (#ti/#mic/#send, overlays with £6.99–£29.99, satchel, /api/ai/cf calls) plus orphan Upload/Shop panels, st-*/quick-*/qp-* JS",
     "index.html ~1,000+ dead lines; 2 wasted requests per page load (Studio); misleading hardcoded prices", "DEAD"),
    ("Delete ~3,800 lines of unreferenced site/js files and admin/index.html (MythicBee)", "repo/site weight, confusion for agents", "DEAD"),
    ("Studio owns the person profile: add relationship/birthday/interests to Add family + /studio/people/<sid>; Cards/Quick/Perform read it",
     "Removes re-asking in Cards; feeds quick/map, gift-packs, Perform starters", "MOVE/INHERIT"),
    ("Products order: inherit email from /accounts/me, name text from subject (body.text, not note); add _owner_denied to /products/order, /gift-packs, /meshes/style",
     "Shopify drafts currently go out with no email; personalisation silently lands in a note; auth holes", "INHERIT/BROKEN"),
    ("Kill 'Reserve only' + pack 'Reserve' + checkout-less reservations; one basket (Shopify) for cards, 3D lines and art; fix cart/create overwriting oddhobb.cartId",
     "Dead-end basket rows; second card orphans the first cart; two checkouts", "BROKEN"),
    ("Prints & gifts shelf: either wire a real order path from GET /api/products (Prodigi prices) or hide it; drop pr-print-cands (selection never used) and supplier quote text",
     "11 tiles with stale prices and no way to buy", "BROKEN"),
    ("Perform: stop hardcoding voice:'ryan' (act voices never apply), send act premise as persona, prefill name from subject, show /api/credits",
     "Core video flow ignores act voices; re-asks the name", "BROKEN/INHERIT"),
    ("Size chips on non-gift lines: send size or hide them", "Customers pick a size that is silently dropped", "BROKEN"),
    ("Greeting CTA → Studio Add-family (or Quick with selected person); fix /privacy; neutral copy without family names", "First click lands nowhere it promised", "BROKEN"),
    ("Quick: send subject_id to /quick/map and score with saved interests; skip 'who/pet/colouring' prompts when a person is selected; remove fake 'Talk to bobdod', hidden-prompt shuffle and duplicate 'Browse all products'",
     "Quick re-asks what the backend knows; 3 dead buttons", "INHERIT/DEAD"),
    ("Move fit.html, rehearse.html, stage.html, products.html ops downloads, admin.html and the MCP <details> out of the customer surface",
     "Customers can overwrite global hat placement; unauthenticated 15-min CPU render endpoint", "MOVE"),
    ("Replace mesh hashes (qk/pr chips, account 'Active star: msh_…') with the selected person's name + face", "Every tab shows a meaningless id", "INHERIT"),
    ("Backend products_studio fallback: read subjects.profile_for() interests/birthday (currently interests:[] literal)", "Gift suggestions ignore saved interests", "INHERIT"),
    ("Search: restore an input or delete the 200-line drop; drop catstrip + per-load /api/sections; card rows 799 → cards.public_price", "Unreachable feature + stale £7.99", "DEAD"),
    ("Studio: auto-link uploads to the selected person; poll mesh progress instead of 'Refresh'; hide demo meshes once the owner has one; move brick presets to Products as a base option",
     "Less manual review, no account-mutating preset buttons", "INHERIT/MOVE"),
]

def main():
    pages = collections.OrderedDict()
    for r in R:
        pages.setdefault(r["page"], []).append(r)
    counts = {}
    for p, rows in pages.items():
        c = collections.Counter(x["verdict"] for x in rows)
        counts[p] = {k: c.get(k, 0) for k in ("KEEP", "INHERIT", "DEAD", "BROKEN", "MOVE")}
    tot = collections.Counter(r["verdict"] for r in R)
    out = {"repo": "prx0r/pogpet", "commit": COMMIT, "generated_utc": "2026-10-15T13:55Z",
           "method": "Static trace of site/index.html + site/js/* + other pages against backend/server.py, studio_library.py, cards.py, cardgen_api.py, mcp_server.py. Live API unreachable; no writes performed.",
           "live_api": LIVE, "verdict_totals": dict(tot), "per_page_counts": counts,
           "controls": R, "ranked_fixes": [dict(rank=i + 1, fix=f, impact=w, kind=k) for i, (f, w, k) in enumerate(FIXES)]}
    json.dump(out, open("FORM_AUDIT.json", "w"), indent=2, ensure_ascii=False)

    esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
    md = [f"# OddHobb form & control audit\n",
          f"Repo `prx0r/pogpet` branch `site-beauty` @ {COMMIT}. Read-only; nothing pushed.\n",
          "**Live API: DOWN during the audit — every verdict below is judged from code.** "
          "Sandbox curl got a proxy-level 502 at CONNECT (2026-10-15T13:39:37Z, no Cf-Ray — sandbox egress, not Cloudflare); "
          "the Hark browser got `ERR_EMPTY_RESPONSE` on the homepage and all 33 `/backend/api` GETs (13:40–13:46Z, no Cloudflare page, no Ray ID). "
          "Paid/mutating calls (orders, meshes, install_style, videos, renders, cart) were not attempted by rule.\n",
          "Verdicts: **KEEP** needed & works · **INHERIT** backend already knows → prefill/remove · **DEAD** ignored/duplicate/unreachable · **BROKEN** should work, doesn't · **MOVE** belongs elsewhere.\n",
          "## Counts per page\n", "| Page | KEEP | INHERIT | DEAD | BROKEN | MOVE |", "|---|---|---|---|---|---|"]
    for p, c in counts.items():
        md.append(f"| {esc(p)} | {c['KEEP']} | {c['INHERIT']} | {c['DEAD']} | {c['BROKEN']} | {c['MOVE']} |")
    md.append(f"| **Total ({len(R)} controls)** | {tot['KEEP']} | {tot['INHERIT']} | {tot['DEAD']} | {tot['BROKEN']} | {tot['MOVE']} |\n")
    md.append("## Ranked fix list (biggest dead weight first)\n")
    for i, (f, w, k) in enumerate(FIXES, 1):
        md.append(f"{i}. **[{k}]** {f} — _{w}_")
    md.append("")
    for p, rows in pages.items():
        md.append(f"## {p}\n")
        md.append("| Element | Label | What the JS does | API call & payload | Backend use of params | Working? | Verdict | Fix |")
        md.append("|---|---|---|---|---|---|---|---|")
        for r in rows:
            md.append("| " + " | ".join(esc(r[k]) for k in ("element", "label", "js_does", "api", "backend_param_use", "working")) +
                      f" | **{r['verdict']}** | {esc(r['fix'])} |")
        md.append("")
    md.append("## Security notes found along the way\n")
    md += ["- `POST /api/products/order`, `/api/gift-packs`, `/api/quick/map`, `/api/products/studio` have no `_owner_denied` check (owner taken from body/query).",
           "- `POST /api/meshes/style` (install_style) takes `owner` from the body without `_owner_denied` — a valid user key (or bridge token) can switch another owner's active mesh.",
           "- `POST /api/standup/render` and `POST /api/fit/placement` are unauthenticated beyond the bridge token; fit writes a global file, standup runs a ≤900 s CPU job synchronously.",
           "- `/api/pog/laugh`, `/api/jokes/*` accept any owner string (low risk).", ""]
    md.append("## Notes / assumptions\n")
    md += ["- Image/GLB assets under site/img/prod, /assets/club are not in git (only site/img/oddy), so asset 404s could not be checked.",
           "- Cards is covered briefly because another agent is reworking it on the shared checkout `/workspace/work/pogpet-beauty/repo` (untouched).",
           "- Family names are intentionally not reproduced in this report.", ""]
    open("FORM_AUDIT.md", "w").write("\n".join(md))
    print(json.dumps(counts, indent=1)); print(dict(tot), len(R))

if __name__ == "__main__":
    main()
