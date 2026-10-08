# Card P0 — five rigid visual grammars (spec, verbatim founder)

Yes. I reviewed the newer project threads, and the architecture has converged quite a lot. The greeting-card MVP should not be “AI invents a card.” It should be **five rigid visual grammars** into which the system selects the right person assets, writes within tightly bounded text slots, renders the face/body into a controlled scene, and then outputs one deterministic Prodigi print file. The same scene spec can later drive the video version.

For V1 I would standardize on **Prodigi Classic 5×7 portrait**, SKU `CLASSIC-GRE-FEDR-7X5-BLA`. Despite the SKU saying `7X5`, Prodigi gives the finished dimensions as **127 × 178 mm**, which is the portrait shape we want. It is 330gsm Fedrigoni card, gloss UV varnished, supports personalization inside and out, includes an envelope, is API-orderable, and Prodigi currently quotes 24-hour manufacturing from the UK. [Prodigi](https://www.prodigi.com/products/cards-and-stationery/greetings-cards/classic-greetings-cards/?utm_source=chatgpt.com)

Prodigi accepts JPG or PDF at **300dpi recommended** for this product. Importantly, for greeting cards the front, back and inside artwork are supplied as **one image file**; Prodigi’s API exposes the required print area and recommended pixel resolution through product lookup. PDF files are processed at the size supplied, whereas raster images can be resized/cropped depending on the `sizing` setting. Therefore our production renderer—not the AI—should own the vendor template, fold, bleed, safe zones, panel ordering and final PDF. [Prodigi](https://support.prodigi.com/hc/en-us/articles/18857525483164-How-do-I-add-a-message-to-a-card-and-or-a-back-image?utm_source=chatgpt.com)

## The five canonical card grammars

These are the five I would freeze for V1.

| ID | What the buyer sees | Inputs | Why it stays |
|---|---|---|---|
| `comic_4panel` | 2×2 editorial/comic strip | face, optional body, recipient facts | Our strongest current visual grammar; perfect birthday/Christmas/Halloween |
| `hero_scene` | Recipient dropped into one spectacular photoreal hobby/cinematic scene | face + preferably body | Highest “holy shit that’s Dad” factor |
| `interview_scene` | Sports presser / studio couch / red carpet / mock documentary | face + body | Extremely video-ready; lower-third gives easy personalization |
| `news_scene` | Recipient becomes subject of a ridiculous news event | face + optional body | Very clear joke grammar, easy AI writing |
| `meme_2beat` | Two-image setup → payoff / before-after / expectation-reality | 1–2 photos or generated scenes | Closest to viral X/meme grammar and cheapest to generate |

Occasion is **not** baked into these. Birthday, Christmas, Halloween, Father's Day etc. are parameters. Likewise `doomer_ink`, photoreal, retro comic and so on are rendering styles—not separate templates.

That preserves the JokeBlock architecture from the recent work: **JokeBlock → premise → card grammar → rendered artifact**. A winning premise can therefore become a four-panel card, sports interview, X post and video without duplicating the underlying joke data.

---

# 1. Canonical card job schema

This is the object I would make the AI produce. Everything outside these fields is renderer-owned.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://oddhobb.com/schemas/card-job-v1.json",
  "title": "OddHobb Card Job v1",
  "type": "object",
  "additionalProperties": false,

  "required": [
    "schema_version",
    "template_id",
    "occasion",
    "subjects",
    "creative",
    "inside",
    "production"
  ],

  "properties": {
    "schema_version": {
      "const": "1.0"
    },

    "template_id": {
      "enum": [
        "comic_4panel",
        "hero_scene",
        "interview_scene",
        "news_scene",
        "meme_2beat"
      ]
    },

    "occasion": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type"],
      "properties": {
        "type": {
          "enum": [
            "birthday",
            "christmas",
            "halloween",
            "fathers_day",
            "mothers_day",
            "valentines",
            "anniversary",
            "graduation",
            "retirement",
            "new_baby",
            "general"
          ]
        },
        "age": {
          "type": ["integer", "null"],
          "minimum": 1,
          "maximum": 120
        },
        "recipient_label": {
          "type": ["string", "null"],
          "maxLength": 32
        }
      }
    },

    "subjects": {
      "type": "array",
      "minItems": 1,
      "maxItems": 3,
      "items": {
        "$ref": "#/$defs/subjectBinding"
      }
    },

    "creative": {
      "oneOf": [
        { "$ref": "#/$defs/comic4Panel" },
        { "$ref": "#/$defs/heroScene" },
        { "$ref": "#/$defs/interviewScene" },
        { "$ref": "#/$defs/newsScene" },
        { "$ref": "#/$defs/meme2Beat" }
      ]
    },

    "inside": {
      "$ref": "#/$defs/insideCard"
    },

    "production": {
      "$ref": "#/$defs/productionContract"
    }
  },

  "$defs": {
    "subjectBinding": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "subject_id",
        "face_asset_id",
        "identity_strength"
      ],
      "properties": {
        "subject_id": {
          "type": "string"
        },

        "face_asset_id": {
          "type": "string"
        },

        "body_asset_id": {
          "type": ["string", "null"]
        },

        "identity_strength": {
          "const": "locked"
        },

        "body_strategy": {
          "enum": [
            "source_body",
            "source_cutout",
            "pose_transfer",
            "generated_body",
            "crop_to_bust"
          ]
        },

        "preserve": {
          "type": "array",
          "uniqueItems": true,
          "items": {
            "enum": [
              "face_geometry",
              "age",
              "hair",
              "facial_hair",
              "glasses",
              "skin_tone",
              "body_shape"
            ]
          },
          "default": [
            "face_geometry",
            "age",
            "hair",
            "facial_hair",
            "glasses",
            "skin_tone"
          ]
        }
      }
    },

    "insideCard": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "left_panel",
        "right_message",
        "signature"
      ],
      "properties": {
        "left_panel": {
          "type": "object",
          "additionalProperties": false,
          "required": ["mode"],
          "properties": {
            "mode": {
              "enum": [
                "blank",
                "photo",
                "secondary_joke"
              ]
            },
            "asset_id": {
              "type": ["string", "null"]
            },
            "text": {
              "type": ["string", "null"],
              "maxLength": 160
            }
          }
        },

        "right_message": {
          "type": "string",
          "maxLength": 400
        },

        "signature": {
          "type": "string",
          "maxLength": 80
        }
      }
    },

    "productionContract": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "supplier",
        "sku",
        "output_format",
        "colour_space",
        "dpi",
        "layout_source",
        "asset_mode"
      ],
      "properties": {
        "supplier": {
          "const": "prodigi"
        },

        "sku": {
          "const": "CLASSIC-GRE-FEDR-7X5-BLA"
        },

        "finished_width_mm": {
          "const": 127
        },

        "finished_height_mm": {
          "const": 178
        },

        "output_format": {
          "const": "pdf"
        },

        "colour_space": {
          "const": "RGB"
        },

        "dpi": {
          "const": 300
        },

        "layout_source": {
          "const": "prodigi_official_template"
        },

        "asset_mode": {
          "const": "single_flattened_card_file"
        },

        "print_area": {
          "const": "default"
        },

        "sizing": {
          "const": "fillPrintArea"
        }
      }
    }
  }
}
```

One important production choice there: **never give the model coordinates**. It says “headline,” “subject,” “panel 2 dialogue,” etc. The deterministic renderer knows where those go.

---

# 2. `comic_4panel`

This is the Doomer Haunted House grammar. It should be aggressively constrained.

```json
{
  "$defs": {
    "comic4Panel": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "type",
        "premise_id",
        "style_id",
        "panels"
      ],

      "properties": {
        "type": {
          "const": "comic_4panel"
        },

        "premise_id": {
          "type": "string"
        },

        "joke_block_ids": {
          "type": "array",
          "maxItems": 3,
          "items": {
            "type": "string"
          }
        },

        "style_id": {
          "enum": [
            "editorial_ink",
            "doomer_ink",
            "clean_comic",
            "retro_comic"
          ]
        },

        "panels": {
          "type": "array",
          "minItems": 4,
          "maxItems": 4,

          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": [
              "beat",
              "scene",
              "dialogue"
            ],

            "properties": {
              "beat": {
                "enum": [
                  "setup",
                  "development",
                  "turn",
                  "payoff"
                ]
              },

              "scene": {
                "type": "string",
                "maxLength": 240
              },

              "dialogue": {
                "type": "array",
                "maxItems": 2,

                "items": {
                  "type": "object",
                  "additionalProperties": false,
                  "required": [
                    "speaker",
                    "text"
                  ],

                  "properties": {
                    "speaker": {
                      "type": "string",
                      "maxLength": 32
                    },

                    "text": {
                      "type": "string",
                      "maxLength": 90
                    }
                  }
                }
              }
            }
          }
        },

        "bottom_caption": {
          "const": null
        }
      }
    }
  }
}
```

The important decisions are deliberate: **exactly four panels, maximum two bubbles per panel, no explanatory caption beneath it**. Panel four should preferably work visually even before reading its dialogue.

---

# 3. `hero_scene`

This is “Dad at The Open,” “Mum on Strictly,” “child as space commander,” etc.

```json
{
  "$defs": {
    "heroScene": {
      "type": "object",
      "additionalProperties": false,

      "required": [
        "type",
        "world",
        "role",
        "composition",
        "headline"
      ],

      "properties": {
        "type": {
          "const": "hero_scene"
        },

        "world": {
          "enum": [
            "sport",
            "cinematic",
            "stage",
            "fantasy",
            "workplace",
            "holiday",
            "domestic_epic"
          ]
        },

        "role": {
          "type": "string",
          "maxLength": 80
        },

        "world": {
          "enum": [
            "sport",
            "cinematic",
            "stage",
            "fantasy",
            "workplace",
            "holiday",
            "domestic_epic"
          ]
        },

        "role": {
          "type": "string",
          "maxLength": 80
        },

        "composition": {
          "enum": [
            "full_body",
            "three_quarter",
            "waist_up"
          ]
        },

        "headline": {
          "type": "string",
          "maxLength": 54
        },

        "subheadline": {
          "type": ["string", "null"],
          "maxLength": 100
        },

        "props": {
          "type": "array",
          "maxItems": 4,
          "items": {
            "type": "string",
            "maxLength": 32
          }
        },

        "environment_notes": {
          "type": "string",
          "maxLength": 220
        },

        "trademark_policy": {
          "const": "original_unbranded_environment"
        }
      }
    }
  }
}
```

If no reliable body image exists, `full_body` is forbidden by the preflight layer; it falls back to waist-up. The AI should not quietly invent Dad's entire physical appearance when we have only a blurry face photograph.

---

# 4. `interview_scene`

This is possibly the strongest bridge into video.

```json
{
  "$defs": {
    "interviewScene": {
      "type": "object",
      "additionalProperties": false,

      "required": [
        "type",
        "format",
        "headline",
        "lower_third",
        "question",
        "answer"
      ],

      "properties": {
        "type": {
          "const": "interview_scene"
        },

        "format": {
          "enum": [
            "sports_sideline",
            "press_conference",
            "late_night_couch",
            "red_carpet",
            "documentary_confessional"
          ]
        },

        "headline": {
          "type": "string",
          "maxLength": 50
        },

        "lower_third": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "name",
            "descriptor"
          ],

          "properties": {
            "name": {
              "type": "string",
              "maxLength": 28
            },

            "descriptor": {
              "type": "string",
              "maxLength": 55
            }
          }
        },

        "question": {
          "type": "string",
          "maxLength": 110
        },

        "answer": {
          "type": "string",
          "maxLength": 150
        },

        "visual_action": {
          "type": "string",
          "maxLength": 160
        }
      }
    }
  }
}
```

That same `question`, `answer`, `subject_id`, scene and lower third later become a 5–15 second talking-video spec instead of creating a completely different asset.

---

# 5. `news_scene`

```json
{
  "$defs": {
    "newsScene": {
      "type": "object",
      "additionalProperties": false,

      "required": [
        "type",
        "news_format",
        "headline",
        "scene"
      ],

      "properties": {
        "type": "string",
        "maxLength": 50
      }
    }
  }
}
```

Again, all ticker bars, fonts, broadcast graphics and typography are renderer-owned. The model only supplies semantic fields.

---

# 6. `meme_2beat`

This is the generic viral-format engine without copying specific copyrighted meme artwork.

```json
{
  "$defs": {
    "meme2Beat": {
      "type": "object",
      "additionalProperties": false,

      "required": [
        "type",
        "grammar",
        "beat_1",
        "beat_2"
      ],

      "properties": {
        "type": {
          "const": "meme_2beat"
        },

        "grammar": {
          "enum": [
            "expectation_reality",
            "before_after",
            "setup_reaction",
            "confident_failure",
            "calm_chaos",
            "reveal"
          ]
        },

        "beat_1": {
          "$ref": "#/$defs/memeBeat"
        },

        "beat_2": {
          "$ref": "#/$defs/memeBeat"
        }
      }
    },

    "memeBeat": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "scene",
        "text"
      ],

      "properties": {
        "scene": {
          "type": "string",
          "maxLength": 200
        },

        "text": {
          "type": "string",
          "maxLength": 90
        },

        "subject_expression": {
          "enum": [
            "neutral",
            "pleased",
            "confused",
            "concerned",
            "smug",
            "shocked",
            "exhausted",
            "celebrating"
          ]
        }
      }
    }
  }
}
```

This explicitly stores **the meme grammar**, not “recreate Drake meme.jpg.” That's important both strategically and legally.

---

## Asset selection should happen before creative generation

I would make a deterministic `subject_asset_resolver` return something like:

```json
{
  "subject_id": "dad",
  "face_candidates": [
    {
      "asset_id": "photo_12",
      "face_quality": 0.94,
      "frontal": 0.91
    }
  ],

  "body_candidates": [
    {
      "asset_id": "photo_07",
      "visibility": "full_body",
      "quality": 0.88
    },

    {
      "asset_id": "photo_09",
      "visibility": "wais_up",
      "quality": 0.96
    }
  ],

  "allowed_compositions": [
    "waist_up",
    "three_quarter",
    "full_body"
  ]
}
```

The creative model receives **IDs**, not the whole chaotic upload folder. It decides among already-validated candidates. If there is no acceptable full body, `full_body` disappears from `allowed_compositions`.

This is also how you stop personalization from becoming unreliable.

---

## Final production contract

The resulting pipeline should be:

```text
uploaded photos
      ↓
face/person clustering
      ↓
subject_asset_resolver
      ↓
recipient profile + JokeBlock
      ↓
ONE OF FIVE card schemas
      ↓
schema validation
      ↓
scene image generation / compositing
      ↓
deterministic typography
      ↓
front + inside-left + inside-right + back
      ↓
Prodigi official template compositor
      ↓
single RGB PDF
      ↓
preflight against live Product Details printAreaSizes
      ↓
Prodigi Sandbox
      ↓
user approval
      ↓
Prodigi Live order
```

The actual Prodigi order item then stays tiny:

```json
{
  "sku": "CLASSIC-GRE-FEDR-7X5-BLA",
  "copies": 1,
  "sizing": "fillPrintArea",
  "assets": [
    {
      "printArea": "default",
      "url": "https://cdn.oddhobb.com/rendered/card_abc123.pdf"
    }
  ]
}
```

Those fields correspond directly to Prodigi’s v4 item model: SKU, copies, sizing and an array of assets identified by `printArea` and URL. [Prodigi](https://www.prodigi.com/print-api/docs/reference/?utm_source=chatgpt.com)

One production detail I would **not** hard-code as `1500×2100` despite that being the nominal 300dpi size of a 5×7 face. Prodigi’s greeting-card input is the complete folded-card document, and their product API returns the recommended `horizontalResolution` and `verticalResolution` for the actual print area. The renderer should cache those values against the Prodigi SKU and official template revision, then reject anything that does not match. That makes it genuinely supplier-safe rather than “probably 5×7.”

This gives us the clean MVP: **five schemas, one physical SKU, one person resolver, one print compositor.** Everything interesting—the jokes, birthday details, Christmas lore, Dad's golf obsession, Mum dancing, Halloween AI satire—sits upstream and can vary wildly without ever being allowed to break the actual card. [Prodigi](https://www.prodigi.com/print-api/docs/reference/?utm_source=chatgpt.com)
