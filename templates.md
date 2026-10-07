# Templates — viral meme grammars + recipient data + render styles

Yes — **that’s the wedge**.

Not “we make cards.”

More like:

> **we turn proven viral joke formats into personalised card templates**

That is much stronger.

## The actual OddHobb thesis

Moonpig = mostly **static personalisation**
OddHobb = **dynamic personalisation inside culturally familiar formats**

So instead of:

- upload photo
- add name
- done

you do:

- choose **viral format**
- fill it with **recipient-specific facts**
- render in a chosen **style**
- optionally turn into **short video**

That’s way more native to how people already joke online.

---

# Core model

I think the combinatorial structure should be:

## 1. Occasion
- Christmas
- Birthday
- Father’s Day
- Mother’s Day
- New baby
- Graduation
- Valentine’s
- Just because

## 2. Theme / format
This is the important bit — the **viral joke engine**.

Examples:
- fake tweet / timeline post
- text message thread
- breaking news
- sports interview
- late-night interview
- reaction meme
- comic strip
- movie poster
- mock documentary confessional
- fake product review
- fantasy quest
- courtroom
- school report
- tier list
- “my honest reaction”
- “meanwhile in the group chat”
- “how it started / how it’s going”
- “I can explain”
- “nobody / absolutely nobody”
- “things dad says”
- “caught on CCTV”
- “before / after”
- “top 10 moments”

## 3. Style
- `xmasaisketch`
- `comicstory`
- `studioroast`
- `sportspresser`
- `newsparody`
- `cinechaos`
- meme screenshot
- scrapbook / handmade
- premium editorial
- cute cartoon
- children’s book
- retro comic
- photoreal candid

## 4. Personalization inputs
- recipient relationship: dad / mum / child / partner / friend
- name
- photos / faces
- pets
- running jokes
- hobbies
- favourite phrases
- big life events
- personality traits
- “what they’re like”
- buyer tone: wholesome / savage / absurd / cute / dry

## 5. Output type
- print card
- digital card
- image pack
- short talking video
- comic strip
- slideshow
- mock trailer

---

# This is where Mythic Bee mattered

The **67 jokes for kids** idea wasn’t random.
It was really a **premise bank**.

That means your durable asset is not only art styles. It’s also:

1. **format library**
2. **joke/premise library**
3. **slot-filling rules**
4. **tone rules**
5. **render styles**

So each product becomes:

> `occasion + meme format + joke premise + recipient data + visual style`

That is insanely reusable.

---

# The key shift

Don’t think “template” as a finished image.

Think of it as a **joke machine**.

A template should contain:

- setup pattern
- caption pattern
- visual scene pattern
- personalization slots
- escalation rule
- ending/payoff rule

---

# Example

## Template family: `newsparody`
**Premise:** child causes chaos

**Slots:**
- child_name
- chaos_object
- quote
- location
- parent_reaction

**Generated outputs:**
- “BREAKING: Oliver has once again hidden the remote in the freezer.”
- live reporter outside living room
- parent quote: “We are monitoring the situation.”

Same exact engine can be:
- Christmas
- birthday
- back to school
- sibling rivalry
- pet chaos

---

# Meme formats are perfect because they already carry meaning

That’s why this works.

If someone sees:

- fake news lower third
- tweet layout
- comic strip
- sports post-match interview
- apology statement
- group chat screenshot

…they instantly understand the joke structure.

So you’re borrowing **recognition**, then adding **personalisation**.

That massively lowers the creative burden for the buyer.

---

# Best initial template families for OddHobb

I’d prioritise these:

## A. Screenshot-native meme templates
Very shareable, fast to give.
- fake tweet
- fake text conversation
- fake family group chat
- fake note app apology
- fake search history
- fake review / Amazon listing
- fake calendar / reminders
- fake Spotify wrapped / yearly recap style
- fake school report
- fake Slack / office message

## B. Scene-based photoreal templates
Best for high-value premium cards.
- studio interview
- sports interview
- breaking news
- awards acceptance speech
- red carpet
- courtroom
- reality show confessional
- mock documentary
- action hero family scene
- Christmas morning chaos

## C. Illustrated narrative templates
Best for kids / warmth / giftability.
- comic strips
- storybook cover
- strip cartoon
- treasure map
- adventure quest
- superhero page
- fantasy party
- cute family chaos sketches
- pet adventure
- holiday mini-story

---

# Comic strips are especially good

Because comic strips let you personalise **multiple beats**, not just one joke.

A good comic template has:

1. setup
2. escalation
3. reversal
4. payoff

Example:

## “Dad vs Technology”
Panel 1: Dad says he’ll fix it
Panel 2: makes it worse
Panel 3: blames Wi-Fi
Panel 4: asks child for help

This is perfect because the text can be remixed using their real habits.

---

# I’d define “theme” very specifically

For `pogpet`, I would make **theme = meme/premise family**, not just “Christmas” or “cute.”

So:

- Occasion = Christmas
- Theme = Breaking News
- Style = Photoreal newsroom
- Personalization = dad, dog, local town, running joke

That separation is important.

---

# Recommended schema

Something like:

```json
{
  "id": "xmas_breakingnews_petchaos",
  "occasion": ["christmas"],
  "theme_family": "newsparody",
  "premise": "pet_caused_holiday_incident",
  "style": "photoreal_newsroom",
  "tone": ["funny", "warm", "lightly absurd"],
  "slots": [
    "recipient_name",
    "pet_name",
    "incident",
    "location",
    "quote"
  ],
  "caption_pattern": "BREAKING: {pet_name} reportedly {incident} in {location}.",
  "image_pattern": "live reporter outside festive home with chaos hinted in background",
  "video_ready": true,
  "face_swap_ready": true
}
```

That gives you something you can actually scale.

---

# A really important split

You should maintain **two libraries**:

## 1. Viral format library
The recognisable structure:
- tweet
- news headline
- talk show
- sports interview
- roast panel
- comic strip

## 2. Premise library
The joke content:
- dad thinks he’s a hero
- child runs the house
- dog ruined Christmas
- mum saved everything
- sibling rivalry
- partner overthinks everything
- kid negotiates bedtime like a lawyer
- grandad acts like a war veteran about DIY
- pet is clearly the favourite child

That massively lowers the creative burden for the buyer.

---

# Best wedge for launch

If I were choosing the first strongest set, I’d go:

### Launch pack 1: “viral family formats”
- Breaking News
- Group Chat
- Late Night Interview
- Sports Interview
- Comic Strip
- Movie Poster

### Then add premise packs
- dads
- mums
- kids
- pets
- couples
- Christmas chaos
- birthdays
- sibling banter

That gives you a clean system:
**format pack × audience pack × occasion pack**

---

# What to avoid
Avoid building a library that is just:
- “funny card 1”
- “funny card 2”
- “funny card 3”

Too flat.

Instead build:
- **format**
- **premise**
- **slots**
- **tone**
- **style**

That becomes programmable.

---

# My main conclusion

Yes — the OddHobb template engine should be based on:

## **viral meme grammars + recipient-specific data + flexible render styles**

That’s much more powerful than ordinary photo cards.

And yes, **comic strips should absolutely be one of the first core families**.

If you want, I can do the next step properly and lay out:

1. **the first 25 OddHobb template families**, or  
2. **a full JSON/data model for `prx0r/pogpet`**, or  
3. **a 67-premise joke bank for kids / dads / pets / couples**.
