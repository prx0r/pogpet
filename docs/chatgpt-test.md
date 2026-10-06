# ChatGPT buyer-journey test — OddHobb via MCP + Shopify

> Store: `oddhobb-oufybzg3.myshopify.com` (GBP, dev store, creds in `.env`).
> Shopify is live: drafts create with invoice URLs (proven: draft #D1).
> Paste each block to ChatGPT with the OddHobb connector enabled, in order.
> Nothing charges — every checkout ends in `pending_checkout` or a draft.

## 1. Browse (what's the shelf?)

```
Use OddHobb tools: list the live product lines with prices, then tell me
in plain words what I could buy for my dog Nibble.
```

Expect: `figg_catalog` / `figg_product_assets` → 13 live lines with prices.
Pass: names + GBP prices, no raw JSON dump.

## 2. Personalise (make it Nibble's)

```
Use OddHobb tools: personalise a keychain for Nibble — chocolate coat,
spots pattern — and show me the preview stills and the price.
```

Expect: `figg_product_personalise` → stills URLs + price. Pass: preview
renders from Nibble's mesh, price stated before anything else.

## 3. Gift pack (the $30 game)

```
Use OddHobb tools: Dad's birthday, budget $30. Build me the best gift pack
— physical, card, video — and tell me the total and what's left over.
```

Expect: `figg_gift_pack` → brick + A6 card + free video = $25, $5 change.
Pass: total ≤ budget, card + video included, change stated.

## 4. Farm quote (what does it cost to make?)

```
Use OddHobb tools: quote a golf marker in PLA at both farms.
```

Expect: `figg_supplier_quote` → makr3d + printie estimates with basis.
Pass: two numbers, "estimates, live quotes win" caveat present.

## 5. Design loop (play, save, order)

```
Use OddHobb tools: pull the golf marker blueprint, download the base,
validate my design (24x24x3mm PLA, text DAD), save it, and tell me the
design ID. Do NOT order yet.
```

Expect: `figg_blueprints` → `figg_design_base` → `figg_design_validate`
(feasible) → `figg_design_save` → design_id. Pass: each step's output feeds
the next; locked interfaces quoted back.

## 6. Blender make (no local Blender needed)

```
Use OddHobb tools: emboss DAD on the golf marker master with Blender
and give me the STL link.
```

Expect: `figg_blender_make` → STL URL (~1-2 min). Pass: downloads,
watertight per the tool response.

## 7. Checkout (reserve + Shopify draft)

```
Use OddHobb tools: order my saved design (design_id from step 5), quantity
1, with Shopify fulfilment. Confirm the draft name and invoice link.
```

Expect: `figg_design_order` with `fulfil:true` → `pending_checkout` +
draft name + `invoice_url` on `oddhobb-oufybzg3.myshopify.com`. Pass:
verify the draft exists in the Shopify admin. Then complete or delete it
there — our API never charges.

## 8. Cards (the other half)

```
Use OddHobb tools: show me my ready-made cards and reserve one.
```

Expect: gallery items → reserve builds export first, then orders.
Pass: no 409, reservation ID returned.

## What ChatGPT cannot do (say so if asked)

Upload from the buyer's device (photos arrive via oddhobb.com, then ChatGPT
references the `photo_id`). Spend Meshy credits. Charge cards. Drive a
localhost Blender — `figg_blender_make` is the remote path.
