# Card actual

Yes. The clean thesis is much simpler than the repo currently makes it:

> **OddHobb is not an AI design tool. It is a library of finished product recipes that an agent personalizes automatically.**

ChatGPT can already generate arbitrary art through fal/Higgsfield/etc. That makes **raw generation less valuable**, not more. Your value is removing decisions.

The customer should not arrive at:

> “What would you like to create?”

They should arrive at:

> “I made these 8 things for Dad.”

Then swipe, tweak one sentence if they care, and hit **Buy**.

## The canonical OddHobb object should be a `Recipe`

Stop thinking in terms of separate “card engine”, “creative engine”, “template engine”, “meme engine”.

A recipe is an executable personalized product.

For example:

```json
{
  "id": "birthday_four_photos_party_title_v1",

  "product": {
    "type": "greeting_card",
    "sku": "card_5x7",
    "price_cents": 799
  },

  "eligibility": {
    "occasion": ["birthday"],
    "subjects": ["person"],
    "min_photos": 4
  },

  "ranking": {
    "interests": [],
    "tones": ["warm", "funny", "playful"]
  },

  "inputs": {
    "photos": {
      "count": 4,
      "strategy": "best_distinct_memories"
    },
    "title": {
      "source": "occasion"
    },
    "inside_copy": {
      "source": "profile"
    }
  },

  "generation": {
    "title_art": {
      "kind": "image",
      "box": [285, 790, 930, 320],
      "transparent": true,
      "prompt_template": "..."
    }
  },

  "renderer": {
    "layout": "birthday_four_photos_v1"
  },

  "outputs": [
    "front",
    "inside",
    "back",
    "print_master"
  ]
}
```

That is almost your entire business architecture.

The agent never sees coordinates. The buyer never sees prompts. The image model never sees the whole card.

## OddHobb's job becomes three things

### 1. Know the person

Dad has:

```text
photos
interests
relationship
memories
previous likes
voice/motion later
```

### 2. Know the recipes

OddHobb knows:

```text
this recipe needs 4 photos
this one works especially well for golfers
this one needs a full-body photo
this one is dry humour
this one costs £7.99
```

### 3. Compile person × recipe

```text
Dad
+
Birthday
+
"funny but not cringe"
        ↓

rank recipes
        ↓

Recipe A
select 4 photos
write 1 bounded message
generate 1 bounded art asset
render exact card
        ↓

finished product
```

Then repeat in parallel for recipes B–H.

That is it.

---

# The key UX shift

Don't make:

```text
Create card
→ pick template
→ upload photos
→ pick font
→ pick colour
→ type text
→ generate
```

Make:

```text
Dad's birthday

[ finished card ]
[ finished card ]
[ finished card ]
[ finished card ]
[ finished card ]

£7.99 · Buy
```

Maybe underneath:

> Change joke · More like this · Different vibe

That is the whole interface.

People don't want a graphics editor. They want the outcome.

---

# Where external agent generation fits

This actually makes ChatGPT + fal/Higgsfield perfect for you.

OddHobb shouldn't care very much **who produced a generated component**.

A recipe asks for:

```text
capability:
    decorative_title_art

requirements:
    exact_text = "Happy Birthday Dad!"
    transparent = true
    aspect = 930:320
    no_extra_text = true
```

The execution layer can satisfy that using:

```text
ChatGPT → fal
ChatGPT → Higgsfield
OddHobb → fal
OddHobb → Alibaba
local model
future model
```

Then OddHobb validates the result and places it in the slot.

The model is a **supplier of ingredients**.

OddHobb owns the product.

---

# This is also how you avoid model churn

Today:

```text
fal Flux
Higgsfield
Wan
Qwen
```

Next year those names may be irrelevant.

But this remains stable:

```text
identity_scene
decorative_title
background_texture
cutout
motion_transfer
voice
```

Recipes request capabilities.

Providers satisfy capabilities.

Don't let provider names leak into your product definitions.

---

# I would aggressively delete the MCP surface

Your MCP currently exposes far too much internal machinery.

For an external general agent, I want approximately:

| Tool | Purpose |
|---|---|
| `oddhobb_people` | Who can I make things for? |
| `oddhobb_recommend` | Give me finished product ideas |
| `oddhobb_make` | Realize one recommendation |
| `oddhobb_variants` | More like this / change vibe |
| `oddhobb_get` | Status + final artifacts |
| `oddhobb_buy` | Checkout |

That's it.

Not:

```text
font selection
crop selection
save card
render spread
generate title
choose template
create revision
pick provider
run creative matcher
```

Those are backend operations.

A good MCP API should make it **hard for an agent to screw up**.

---

# `oddhobb_recommend` is probably your killer tool

Imagine ChatGPT knows:

```text
recipient = Dad
occasion = birthday
budget = £30
context = golf, dry humour, hates fuss
```

It calls:

```json
{
  "subject_id": "dad",
  "occasion": "birthday",
  "budget_cents": 3000,
  "vibe": "dry, understated, golf"
}
```

OddHobb responds:

```json
{
  "recommendations": [
    {
      "id": "idea_1",
      "recipe": "golf_press_conference_card_v2",
      "price": "£7.99",
      "preview_status": "ready"
    },
    {
      "id": "idea_2",
      "recipe": "four_photo_birthday_v1",
      "price": "£7.99",
      "preview_status": "ready"
    },
    {
      "id": "idea_3",
      "recipe": "personalised_golf_marker_v1",
      "price": "£12.99",
      "preview_status": "ready"
    }
  ]
}
```

Ideally **OddHobb renders previews before returning them**.

Then ChatGPT simply shows:

> “I made these for Dad.”

That's much stronger than:

> “Here are some gift ideas.”

---

# The backend should become a compiler

I would reduce the architecture to:

```text
subjects/
recipes/
compiler/
providers/
renderers/
orders/
```

That's nearly all you need.

Conceptually:

```text
backend/
    subjects/
        graph.py
        assets.py

    recipes/
        registry.py
        matcher.py
        schemas.py

    compiler/
        compile.py
        jobs.py
        artifacts.py

    providers/
        router.py
        image.py
        video.py
        voice.py

    renderers/
        cards.py
        physical.py
        video.py

    commerce/
        shopify.py
        fulfilment.py
```

Your current `creative`, `cards`, `jokes`, etc. can gradually become implementations underneath this instead of separate universes.

---

# Keep vs retire

| Keep | Retire from canonical path |
|---|---|
| `studio_subjects` | mesh-as-person concepts |
| subject profiles | generic card editor |
| photo/subject linking | agent-selectable fonts |
| immutable revisions | agent-selectable geometry |
| artifact provenance | 6 competing card creation paths |
| Shopify checkout | direct supplier ordering before payment |
| provider router | provider-specific business logic |
| Freaktown performance kernel | separate performance product architecture |
| existing card renderer code | old templates exposed to agents |
| joke/profile intelligence | canned `message_lines()` |

You don't need to physically delete everything immediately.

Just establish:

```text
CANONICAL PATH
```

and stop allowing anything else to drive the storefront/MCP.

---

# Templates should be authored by you, not generated dynamically

This is important.

You should use all this insane generative tooling to create **excellent reusable recipes**.

For example you personally/design-agent build:

```text
Dad At The Open
Mum On The Dance Floor
Breaking Birthday News
Four Memories
Childhood → Now
Family Mugshots
The Awards Ceremony
Christmas Press Conference
```

For each one you test:

- 20 different people
- bad photos
- long names
- no interests
- weird aspect ratios
- different ages

Once it works, publish it.

Then every future user gets the benefit of that work instantly.

That's the leverage.

You do the art direction **once**.

---

# A published recipe should be immutable

Very important for commerce.

```text
golf_press_card_v1
golf_press_card_v2
```

Never silently alter v1.

Because an order must always mean:

```text
recipe version
+
input assets
+
generated ingredients
+
copy
=
exact print master
```

Then “Buy” always reproduces exactly what the customer previewed.

---

# Your storefront then becomes algorithmic merchandising

This is where it gets really strong.

For Dad:

```text
Because Dad likes golf:
→ golf press conference
→ championship poster
→ golf marker
→ golf keychain

Because Dad is turning 70:
→ birthday newspaper
→ then/now collage

Because you like dry humour:
→ roast variants rank higher
```

OddHobb is basically doing:

```text
Netflix recommendations
        ×
Moonpig templates
        ×
generative media
        ×
Shopify checkout
```

That's much more defensible than “AI greeting cards”.

---

# Don't render every possible combination in advance

You can make it *feel* pre-made without wasting compute.

Use a two-stage approach:

```text
cheap recommendation
        ↓
cheap deterministic preview
        ↓
only top 4–8 candidates get expensive generated ingredients
```

And cache those generated components.

So Dad's birthday page loads with finished-looking products while the expensive generation stays bounded.

---

# The final product loop

This is the loop I'd freeze:

```text
Person created
      ↓
OddHobb indexes assets/profile
      ↓
occasion / request arrives
      ↓
rank published recipes
      ↓
compile top candidates automatically
      ↓
customer sees finished products
      ↓
👍 / 👎 / more like this
      ↓
ranking learns taste
      ↓
Buy
      ↓
Shopify
      ↓
supplier
```

That is the actual company.

And crucially, improvements in AI are **good for you**.

As generation gets cheaper and better, the recipes get better automatically. Your durable assets are the templates, personalization graph, historical preferences, commerce integration and accumulated knowledge of **what personalized things people actually choose to buy**.

For the repo specifically, I'd make the next cleanup pass **subtractive**: establish `recipes/` + one compiler + six external MCP tools, make the existing `birthday_4photo` the first published recipe, and move everything else behind that boundary. Then don't add another creative feature until Dad's profile can produce 5 genuinely good finished birthday options and each one can be bought in one click.
