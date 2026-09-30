/**
 * MogMug — Pog phrase pack for the Hive Activity Engine.
 * Same schema as js/hive-activity.js HIVE_STATUSES. Character-specific lines so every
 * pet inherits its own loading language (plan: generate_loading_pack(character)).
 * Wire-in: import { POG_STATUSES } from './pog-pack.js'; HIVE_STATUSES.push(...POG_STATUSES);
 */

export const POG_HOSTS = ["buster", "bartholomew", "kevin", "pickles", "mog"];

const T = { minDurationMs: 2200, maxDurationMs: 4600, cooldownMs: 45000 };

export const POG_STATUSES = [
  { id: "pog_buster_001", text: "Locating Buster…", phases: ["listen"], weight: 1, rarity: "common", tags: ["pog"], characters: ["buster"], motionCue: "scribble", ...T },
  { id: "pog_buster_002", text: "Removing forbidden sock…", phases: ["generate-video"], weight: 1, rarity: "common", tags: ["pog", "silly"], characters: ["buster"], motionCue: "inspect", ...T },
  { id: "pog_buster_003", text: "Checking cheese reserves…", phases: ["generate-video"], weight: 1, rarity: "common", tags: ["pog"], characters: ["buster"], motionCue: "scribble", ...T },
  { id: "pog_buster_004", text: "Hiding from Dave next door…", phases: ["generate-image"], weight: 1, rarity: "common", tags: ["pog", "dry"], characters: ["buster"], motionCue: "peek", ...T },
  { id: "pog_buster_005", text: "Teaching basic wizardry…", phases: ["generate-video"], weight: 1, rarity: "common", tags: ["pog", "spectacle"], characters: ["buster"], motionCue: "celebrate", ...T },
  { id: "pog_barth_001", text: "Polishing wings…", phases: ["generate-image"], weight: 1, rarity: "common", tags: ["pog"], characters: ["bartholomew"], motionCue: "scribble", ...T },
  { id: "pog_barth_002", text: "Consulting the hive…", phases: ["ideate"], weight: 1, rarity: "common", tags: ["pog", "hive"], characters: ["bartholomew"], motionCue: "fly-out", ...T },
  { id: "pog_kevin_001", text: "Giving Kevin administrative privileges…", phases: ["council"], weight: 1, rarity: "common", tags: ["pog", "chaos"], characters: ["kevin"], motionCue: "argue", ...T },
  { id: "pog_kevin_002", text: "Removing Kevin's administrative privileges…", phases: ["council"], weight: 1, rarity: "common", tags: ["pog", "dry"], characters: ["kevin"], motionCue: "argue", ...T },
  { id: "pog_pickles_001", text: "Negotiating with Pickles…", phases: ["listen"], weight: 1, rarity: "common", tags: ["pog"], characters: ["pickles"], motionCue: "hover", ...T },
  { id: "pog_pickles_002", text: "Moving glass away from table edge…", phases: ["generate-video"], weight: 1, rarity: "common", tags: ["pog", "dry"], characters: ["pickles"], motionCue: "inspect", ...T },
  { id: "pog_mog_001", text: "Consulting the town goblin…", phases: ["ideate"], weight: 1, rarity: "common", tags: ["pog", "silly"], characters: ["mog"], motionCue: "peek", ...T },
];
