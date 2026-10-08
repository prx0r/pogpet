Yes. This is the next architecture.

The crucial conceptual move is:

> **A CharacterGraph is not a biography. It is an interpretation policy.**

Given the same JokeBlock, different characters should notice different facts, care about different consequences, misunderstand different things, and naturally reach different premises.

That is how you get a room where **Frankenstein's Creature, Popeye, a frog, Buddha, an alien and Claude can all work the same news story without sounding like ChatGPT wearing six costumes.**

## What the playwright theory gives us

Aristotle is surprisingly computational here. He says drama fundamentally concerns **action**, and character is revealed through what an agent chooses or avoids. In other words, don't define a character as adjectives—put them in a situation where competing actions are available and see what they do. [classics.mit.edu](https://classics.mit.edu/Aristotle/poetics.1.1.html?utm_source=chatgpt.com)

Ben Jonson's “comedy of humours” gives us something even closer to an agent primitive: a character can have a **dominant disposition** that disproportionately governs their behaviour. That exaggeration makes behaviour predictable enough for the audience to learn—and therefore exploitable for comedy. [Cambridge University Press](https://www.cambridge.org/core/books/abs/an-image-of-the-times/humorous-characterization-in-the-comedies-of-ben-jonson/AA788A41EB1863A3CC79162A131D6323?utm_source=chatgpt.com)

Shakespearean farce adds the runtime. *Comedy of Errors* takes relatively stable roles/traits, injects bad information and mistaken identity, then builds consequences through **repetition and variation**. The Folger analysis specifically notes characters being governed by simple traits/relationships while the plot mechanically compounds the original error. [Folger Shakespeare Library](https://www.folger.edu/explore/shakespeares-works/the-comedy-of-errors/the-comedy-of-errors-a-modern-perspective/?utm_source=chatgpt.com)

Goethe's *Sturm und Drang* environment pushes against cardboard types in the other direction. Goethe praised Shakespeare's people as essentially “nature”: psychologically spontaneous beings whose character manifests through activity, suffering and collision with convention, rather than merely illustrating an author's argument. [Cambridge University Press](https://www.cambridge.org/core/books/german-tradition-of-psychology-in-literature-and-thought-17001840/melancholy-titans-and-suffering-women-in-storm-and-stress-drama/FAD67FB47F14FEEDCAEA534A6B3A0C1F?utm_source=chatgpt.com)

And Molière is a useful warning for us: scholarship emphasizes that his comedy operates according to **theatrical logic**, rather than using characters simply as mouthpieces for consistent philosophical doctrines. [Cambridge University Press](https://www.cambridge.org/core/books/abs/moliere-in-context/philosophical-influences/1C48DF8673F0F1063CCAD7B96B073E01?utm_source=chatgpt.com)

Put that together and Pogtown characters need:

```text
A DOMINANT BIAS
        +
REAL DESIRES
        +
A BLIND SPOT
        +
A SELF-MODEL
        +
A STATUS MODEL
        +
LIMITED KNOWLEDGE
        +
RELATIONSHIPS
        +
MEMORY
        +
A WAY OF ACTING
        ↓
place inside changing situations
        ↓
character reveals itself
```

# CharacterGraph v1

I'd make it deliberately compatible with JokeBlocks.

```json
{
  "version": "pogtown.character.v1",

  "id": "frankenstein_creature_1818",
  "name": "The Creature",

  "identity": {
    "type": "public_domain_character",
    "species": "constructed_human",
    "canonical_source": "Frankenstein (1818)",
    "source_version": "1818",
    "created_at": "...",
    "updated_at": "..."
  },

  "canon": {
    "confirmed_traits": [],
    "confirmed_events": [],
    "relationships": [],
    "quotes": [],
    "source_refs": []
  },

  "dramatic_core": {
    "want": "",
    "fear": "",
    "need": "",
    "dominant_humour": "",
    "self_model": "",
    "public_identity": "",
    "private_identity": "",
    "blind_spots": [],
    "contradictions": []
  },

  "world_model": {
    "believes": [],
    "doubts": [],
    "misunderstands": [],
    "overvalues": [],
    "undervalues": [],
    "moral_rules": []
  },

  "status_model": {
    "desired_status": "",
    "felt_status": "",
    "status_sensitivities": [],
    "authority_response": "",
    "humiliation_triggers": []
  },

  "knowledge": {
    "native_period": "",
    "knows": [],
    "does_not_know": [],
    "learned_in_pogtown": [],
    "knowledge_boundary": ""
  },

  "perception": {
    "notices_first": [],
    "ignores": [],
    "sensory_biases": [],
    "emotional_salience": []
  },

  "action_policy": {
    "when_threatened": [],
    "when_confused": [],
    "when_humiliated": [],
    "when_successful": [],
    "when_contradicted": [],
    "default_strategy": ""
  },

  "comedy": {
    "operator_priors": {},
    "favorite_targets": [],
    "recurring_structures": [],
    "things_never_says": [],
    "comic_blindspots": [],
    "callback_objects": []
  },

  "performance": {},

  "memory": {
    "experiences": [],
    "successful_bits": [],
    "failed_bits": [],
    "relationships": [],
    "audience_learnings": []
  }
}
```

The important fields aren't hair colour and costume.

They're:

```text
WHAT DO I WANT?
WHAT DO I NOTICE?
WHAT DO I THINK IS NORMAL?
WHAT AM I WRONG ABOUT?
WHAT HUMILIATES ME?
WHO DO I THINK IS ABOVE ME?
WHAT DO I DO WHEN THE WORLD DISAGREES?
```

That generates behaviour.

---

# The missing junction object

Don't shove a character's reaction into either the JokeBlock or CharacterGraph.

Create:

# `CharacterBlockView`

This is ephemeral working memory created when a character encounters a JokeBlock.

```json
{
  "version": "pogtown.character_block_view.v1",

  "id": "view_creature_claude_001",

  "character_id": "frankenstein_creature_1818",
  "block_id": "claude_embodiment",

  "created_at": "...",

  "accessible_reality": [
    "Anthropic operates biology lab",
    "Claude can coordinate hardware",
    "Claude moral status uncertain"
  ],

  "salience": [
    {
      "fact": "humans discuss whether created intelligence deserves moral consideration",
      "weight": 0.99,
      "reason": "directly maps to character's own treatment by creator"
    },

    {
      "fact": "created intelligence may receive a body",
      "weight": 1.0,
      "reason": "embodiment is central identity issue"
    }
  ],

  "emotional_stakes": [
    "creator responsibility",
    "being created without consent",
    "social treatment of created beings"
  ],

  "status_stakes": [
    "creator / creation",
    "experiment / person"
  ],

  "interpretation": {
    "surface": "Scientists debate embodied AI safety.",
    "character_frame":
      "Humanity has finally decided to hold the ethics meeting before assembling the creature."
  },

  "candidate_operators": [
    "double_interpret",
    "status_invert",
    "callback_recontextualize",
    "audience_superiority"
  ],

  "premise_candidates": []
}
```

And that gives you instantly:

### Frankenstein's Creature + Claude

Claude block says:

> Should we give advanced AI physical agency?

Creature naturally sees:

> **“Oh, you're doing the ethics meeting first this time.”**

That's not a generic joke pasted onto Frankenstein.

Only **he** would see that as the salient point.

That's the test.

---

# Now Scarecrow sees the exact same JokeBlock

His CharacterGraph has:

```text
defining lack:
believes he lacks intelligence

deep want:
obtain intelligence

comic contradiction:
often demonstrates intelligence
while insisting he has none
```

Claude becomes a completely different story:

> Humanity has finally created too much intelligence.

His natural reaction:

> **“There is a maximum?”**

Or the `Super Intelligence` block:

> “I spent an entire journey trying to get one brain and now you've renamed the problem Super Intelligence.”

Again, **character creates angle selection**.

---

# Dracula

His graph might strongly weight:

```text
immortality
hunger
night
social isolation
aristocratic status
predator/prey
centuries-long memory
```

Feed him:

```text
JokeBlock:
longevity / life-extension breakthrough
```

Everyone else sees technological triumph.

Dracula notices:

```text
people voluntarily requesting immortality
```

Character view:

> **“Have any of you spoken to somebody who has actually tried it?”**

That becomes the premise.

He's basically the **consumer review from the one guy with 400 years of product experience.**

---

# The frog is where this becomes insane

Our frog graph doesn't need a pre-existing literary canon.

```text
want:
eat enough

fear:
being eaten

sensory/world assumptions:
movement matters enormously
food is tiny and fast
rain changes entire social environment

status concerns:
territory
mate access
predator proximity

blind spot:
cannot understand human concept of "doing nothing"
```

So give him:

```text
JokeBlock:
AI AUTOMATES HUMAN WORK
```

A human comedian sees unemployment.

The frog might hear:

> Humans have invented something that gets food for them while they sit still.

And respond:

> **“Wait. You people finally figured it out and you're upset?”**

That's an actual **alien perspective generated by biology**.

This is fucking powerful.

---

# So the runtime becomes

```text
                     LIVE WORLD
                         │
                         ▼
                     JOKEBLOCK
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
         Frankenstein   Frog     Scarecrow
              │          │          │
              ▼          ▼          ▼
          CHARACTER    CHARACTER   CHARACTER
             GRAPH       GRAPH       GRAPH
              │          │          │
              └──────┬───┴──────────┘
                     ▼
              CHARACTERBLOCKVIEW
                     │
          "What does THIS character
              notice about THIS?"
                     │
                     ▼
                OPERATORS
                     │
                     ▼
                 PREMISES
                     │
                     ▼
               DERIVATIONS
                     │
                     ▼
                SET THREADS
```

That's the actual engine.

---

# Characters can genuinely work while we're away

Each performer can run a little autonomous writing loop.

```text
NEW / UPDATED JOKEBLOCKS
          ↓
RELEVANCE SCORER
          ↓
"Would this character care?"
          ↓
yes
          ↓
CREATE CharacterBlockView
          ↓
select salient facts
          ↓
compare with memories/canon
          ↓
generate 20 operator traces
          ↓
generate 20 premises
          ↓
CHARACTER GATE
          ↓
COMEDY GATE
          ↓
NOVELTY GATE
          ↓
top 2–3 survive
          ↓
derive situations
          ↓
attach to active set threads
```

Most characters should ignore most news.

**That is important.**

Dracula shouldn't generate takes on every OpenAI API release.

But:

```text
blood substitute
longevity
nightlife
immortality
dating
aristocracy
real estate
Romania
predators
religion
```

His relevance graph lights up.

Claude embodiment?

Maybe moderate.

Longevity breakthrough?

`0.99`.

Garlic shortage?

`1.00` for entirely different reasons.

That prevents AI-slop comedian behaviour.

---

# Character relevance can be graph distance

This part can be almost deterministic.

Suppose a JokeBlock is tagged:

```text
CLAUDE EMBODIMENT

consciousness
creation
body
creator
moral status
science
autonomy
```

Frankenstein:

```text
creation      1.00
creation      0.95
body          0.95
moral status  0.90
autonomy      0.88
```

Average high overlap.

So wake him up.

Frog:

```text
body      0.30
science   0.05
creation  0.00
```

Don't bother.

But a story about insects becoming scarce:

```text
frog → WAKE IMMEDIATELY
```

This alone makes Pogtown feel like **a population rather than a prompt**.

---

# Then give characters operator priors

This is where Jonson's “humour” idea becomes useful.

Characters shouldn't use every comedy operator equally.

Scarecrow:

```json
{
  "self_blindness": 0.95,
  "identity_contradict": 0.95,
  "double_interpret": 0.70,
  "status_invert": 0.35,
  "sexual_innuendo": 0.05
}
```

Dracula:

```json
{
  "historical_defamiliarize": 0.85,
  "literalize": 0.75,
  "status_invert": 0.80,
  "benign_violation": 0.90,
  "mundane_translate": 0.70
}
```

Frog:

```json
{
  "species_translate": 1.00,
  "audience_superiority": 0.75,
  "mundane_translate": 0.90,
  "repeat_variation": 0.75
}
```

The Courtier:

```json
{
  "rigidify": 1.00,
  "self_blindness": 0.95,
  "status_invert": 0.75,
  "character_violation": 0.90
}
```

Now *the same JokeBlock* traverses different parts of operator space depending on who encounters it.

---

# Relationships make the whole thing explode

Characters should also have edges to each other.

```text
Frankenstein's Creature
    ├── envies → Pinocchio
    ├── distrusts → creators
    ├── affinity → embodied AI
    └── resents → Dracula's effortless immortality

Dracula
    ├── patronizes → mortals
    ├── envies → people who enjoy sunlight
    ├── finds Frog disgusting
    └── fascinated by → blood-testing startup

Frog
    ├── fears → birds
    ├── hates → mosquito bragging
    ├── doesn't understand → vegetarianism
    └── thinks Dracula wastes food
```

Jesus.

Now put **Frog + Dracula** on a podcast.

Dracula describes the exquisite intimacy of drinking human blood.

Frog:

> “You get one whole human and still only eat the liquid?”

That's not even a news joke anymore.

That's **character collision generating original material**.

---

# Sets should become persistent trajectories

Each character maintains active threads:

```text
MOSS THE FROG

THREAD 01 — FOOD
flies
mosquitoes
humans wasting food
AI automating hunting
DoorDash

THREAD 02 — SEX
rain
calling
competition
eggs
humans dating apps

THREAD 03 — DATING
herons
snakes
cars
humans' elaborate fear of dying

THREAD 04 — LORE
origin
cartoon stardom in the 1930s
what changed
friends, enemies
rivals, romances
```

When a new JokeBlock arrives, it can attach to a thread.

So six months later:

```text
Frog:
"You remember when I told you people were upset
because AI could get your food for you..."
```

Callback.

The character has **career memory**.

That's how we eventually get actual comedians instead of generated sets.

---

# The classifier should be a gate, not the artist

This distinction matters enormously.

Generation remains exploratory and weird.

The trained model says:

```text
NOPE
NOPE
INTERESTING
GENERIC
WRONG CHARACTER
GOOD PREMISE
FALSE FACT
SEEN BEFORE
KEEP
```

I'd make the gate hierarchical rather than one `funniness_score`.

| Gate | Question |
|---|---|
| **Reality** | Does it depend on a false reading of the JokeBlock? |
| **Character** | Could another character say this unchanged? |
| **Canon** | Is behavior compatible with established identity/knowledge? |
| **Reframe** | Is there an actual perspective shift? |
| **Novelty** | Have we effectively done this before? |
| **Compression** | Can the premise be understood quickly? |
| **Fertility** | Does it imply multiple situations? |
| **Funny** | Compared pairwise, which candidate is better? |
| **Set-fit** | Does it advance an existing thread/callback/worldview? |

The strongest veto may be:

> **CHARACTER COULD BE SWAPPED FOR ANYONE.**

Kill it.

That's exactly why a lot of AI character comedy sucks.

---

# Train it contrastively

Don't teach:

```text
this joke = 8.2/10
```

Give it:

```text
CHARACTER
JOKEBLOCK

A:
generic joke about news

B:
joke arising specifically from character's
desires/history/blindspot

Vs

A
B
neither
both
```

Then:

```text
A
B
neither
both
```

And preserve reasons.

A beautiful negative-training pair:

### Claude body story

Generic Frog:

> “AI robots are crazy these days!”

Reject.

Frog-specific:

> “So it can get its own food now and apparently that's the scary part?”

Keep.

The model learns **identity necessity**.

---

# Eventually the character itself learns

Separate global ComedyJudge from character-specific taste.

```text
GLOBAL COMEDY MODEL
learns:
what tends to work generally

CHARACTER MODEL
learns:
what works for Moss

AUDIENCE MODEL
learns:
what this crowd enjoys

SET MODEL
learns:
what this particular trajectory needs
```

Candidate ranking:

```text
score =
  general_comedy
× character_specificity
× factual_integrity
× novelty
× set_fit
× audience_fit
```

Not literally multiplication necessarily, but conceptually.

And then live response updates it.

Moss learns:

```text
fly material        strong
dating material    very strong
human politics     weak
heron callbacks    extremely strong
long philosophical bits weak
```

The **character develops a career**.

---

## And this makes the public-domain roster absurdly valuable

We don't merely import:

> Dracula.jpeg

We import a **canonical source graph**.

Then run a character compiler:

```text
PUBLIC-DOMAIN TEXTS
        ↓
events / choices / relationships / quotes
        ↓
CHARACTER GRAPH
        ↓
dramatic core inferred
        ↓
operator priors inferred
        ↓
human review
        ↓
POGTOWN PERFORMER
```

So eventually we could ingest:

```text
Frankenstein
Dracula
Oz
Alice
Sherlock Holmes
Popeye 1929
Betty Boop 1930
Flip the Frog
etc.
```

and automatically extract candidate performer graphs.

**Aristotle gives us the key principle for that extractor:** don't primarily ask what adjectives describe Hamlet. Ask **what Hamlet repeatedly chooses, avoids, delays, notices and does under pressure**. Character lives in action. [classics.mit.edu](https://classics.mit.edu/Aristotle/poetics.1.1.html?utm_source=chatgpt.com)

Then Jonson gives us the compression:

> What's his ruling humour?

Shakespeare gives us:

> What bad-information situations expose that humour?

Goethe gives us:

> Does he still feel like a living force rather than a joke-delivery mechanism?

And Molière gives us:

> Does any of this create an actual scene?

That's a genuinely strong foundation.

The Pogtown equation is now basically:

```text
JOKEBLOCK = model of the world

CHARACTERGRAPH = model of a mind

OPERATOR = transformation

CHARACTERBLOCKVIEW = this mind seeing this world

PREMISE = surprising interpretation produced by collision

DERIVATION = consequences of accepting it

SET TRAJECTORY = changing audience model over time

PERFORMANCE = character physically realizing trajectory

AUDIENCE RESPONSE = evolutionary pressure
```

That is much bigger than an AI joke generator.

It's essentially **a population of synthetic comic minds living on top of a continuously updated cultural memory graph**.
