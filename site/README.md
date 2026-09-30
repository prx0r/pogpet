# MythicBee — Consumer-Facing Gift Studio

**Source:** star-at-night.pages.dev (rebranded)
**URL:** mythicbee.com (pending domain)

---

## What This Is

The consumer-facing personalized gift experience. Customers land here and:

1. Tell us about someone they love
2. We generate three unique gift concepts
3. They choose and customize
4. We print and deliver

**Product categories:**
- Books (newspapers, memoirs, magazines, yearbooks)
- Prints (posters, canvases, framed pieces)
- Cards (with a little something inside)
- Ornaments (annual collections, keepsakes)
- Puzzles (crosswords, trivia, memory games)
- Little things (mugs, notebooks, small joys)

---

## How It Works

1. **Tell us about them** — name, relationship, what makes them tick
2. **See what we make** — three unique ideas, crafted from your words
3. **Make it yours** — tweak the message, add a photo, choose the feel
4. **We print and send it** — made after you order, printed locally

---

## Site Structure

```
brands/mythicbee/site/
├── index.html          ← main page (from star-at-night)
├── styles/
│   ├── tokens.css      ← design tokens
│   ├── base.css        ← base styles
│   ├── components.css  ← component styles
│   └── motion.css      ← animations
├── js/
│   ├── state.js        ← app state
│   ├── starfield.js    ← background effect
│   ├── creation-flow.js ← 5-step creation flow
│   └── app.js          ← main app logic
└── assets/
    └── woven-star.svg  ← logo
```

---

## Creation Flow (5 steps)

1. **Recipient** — name + relationship (Mum/Dad/Partner/Friend/Child/Pet)
2. **Occasion** — Birthday/Christmas/Anniversary/New home/Just because
3. **Description** — what makes them, them (memories, jokes, traits)
4. **Photo** — optional upload
5. **Tone** — Funny/Beautiful/Understated/Sentimental/A little ridiculous/Surprise me

---

## Products Generated

After the flow, three products appear:

- **The Times** — "A very serious newspaper about a deeply unserious subject" (From £24)
- **The Biography** — "An unauthorized account of a life well-lived" (From £29)
- **The Story** — "A picture book of memories, moments, and meaning" (From £34)

---

## Connection to StallShark

This site IS the first MythicBee product. StallShark's job is to:
- Drive traffic here (SEO, ads, social)
- Optimize the conversion funnel
- Track what products convert
- Feed learnings back to the production engine

z2m provides the market intelligence that tells us WHAT to make.
MythicBee IS what we make.

---

## To Deploy

This is a static site on Cloudflare Pages. Deploy with:

```bash
# From this directory
npx wrangler pages deploy . --project-name=mythicbee
```

Or connect to GitHub for auto-deploy on push.
