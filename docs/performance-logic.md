# Performance logic — making an audience discover an interpretation

Three layers, frozen:

```text
JOKE BLOCK     what reality/culture contains
PREMISE        the perception-changing interpretation
PERFORMANCE    how you make an audience discover and accept it
```

Artifact is downstream and disposable. The premise
("superintelligence is still vulnerable to its own reward system") is the
asset; it mines for years.

## A great premise

Surprising, funny, and after hearing it you genuinely see the underlying
situation differently. Those are the ones Pogtown mines obsessively.

## A set is a proof

Don't write five minutes of jokes. Take one premise and convince the
audience the absurd interpretation is actually correct:

```text
premise → evidence → audience conversion → implications →
escalation → callback
```

The comedian temporarily persuades you to inhabit their ontology.
Opening material → character establishment → callbacks → escalation →
thematic transitions → closer. Multiple blocks compile into an hour by the
same logic once delivery data exists.

## Delivery traces (schema frozen, harness parked)

Each performed beat fuses Qwen3.8-Omni-Flash semantic interpretation
(premises, punches, tags, callbacks, tone, gaze) with WhisperX word timing,
a laughter detector (onset/peak/decay) and pose extraction:

```json
{
  "beat": "punchline",
  "mechanism": "status_reversal",
  "delivery": {
    "pre_pause_ms": 214, "words_per_second": 2.81,
    "pitch_delta": -0.12, "volume_delta": -0.08,
    "gaze": "audience", "body": "freeze", "gesture": "none"
  },
  "response": {"laugh_onset_ms": 286, "peak_ms": 811, "duration_ms": 2410},
  "next_action": {"tag_started_ms": 1730, "talked_over_laugh": true}
}
```

Validated by `backend/creative/delivery.py`. The payoff is learning things
like: status-reversal punches hit when the new world-model is stated
tersely, then nothing happens for 800ms. Mechanism knowledge becomes
delivery knowledge. Qwen-MM-Plugins `omni-memory` (who was present, who
said what, how) is the long-term memory substrate for exactly this.
