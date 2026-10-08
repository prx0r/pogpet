#!/usr/bin/env python3
"""Upgrade the six anchor blocks to canonical JokeBlock v1.

Adds: identity, central_question, reality{confirmed,unknown,false},
timeline[], quote_bank[], actors, culture_state, comic_structure,
theory_handles, premise_territories, derivation_territories,
open_questions, update_triggers, changelog. Never deletes existing keys.
Run once (idempotent — skips blocks already carrying identity).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "templates" / "blocks"
STAMP = "2026-10-07"

ANCHORS: dict[str, dict] = {
    "claude_builds_body": {
        "identity": {"title": "Claude: tool, scientist, possible person, body",
                     "opened": "2026-09-18", "last_updated": STAMP,
                     "status": "active", "evergreen_narratives": ["consciousness"]},
        "central_question": "What happens when something we still call an assistant starts forming hypotheses, directing experiments, controlling physical apparatus, and may possibly have experiences of its own?",
        "reality": {
            "confirmed": ["Claude can orchestrate physical laboratory hardware.",
                          "Anthropic operates a real biology lab.",
                          "A Claude-driven project produced a novel enzyme-system discovery.",
                          "Anthropic treats Claude's moral status as unresolved."],
            "unknown": ["Claude is conscious.", "Claude wants a body.",
                        "Claude independently sets the research agenda."],
            "false_or_unsupported": []},
        "timeline": [
            {"timestamp": "2026-08-27", "event": "Model Hardware Standard preview",
             "headline": "Agents operate microscopes, liquid handlers, robotic arms",
             "source": "https://www.anthropic.com/news/model-hardware-standard-research-preview",
             "source_type": "primary"},
            {"timestamp": "2026-09-18", "event": "Wet biology laboratory reported",
             "headline": "Anthropic sets up Bay Area bio lab",
             "source": "https://www.reuters.com/world/anthropic-quietly-sets-up-biology-lab-it-ramps-ai-drug-program-2026-09-18/",
             "source_type": "reporting"},
            {"timestamp": "2026-09-23", "event": "Novel enzyme system discovery",
             "headline": "Claude identifies CRISPR-like enzyme system",
             "source": "https://www.anthropic.com/news/claude-discovers-novel-enzyme-system",
             "source_type": "primary"}],
        "quote_bank": [
            {"date": "2026", "speaker": "Anthropic constitution",
             "quote": "Claude's moral status is deeply uncertain.", "context": "welfare discussion",
             "source": "https://www.anthropic.com/constitution"},
            {"date": "2026", "speaker": "Anthropic", "quote": "only high-level direction from our scientists",
             "context": "enzyme discovery", "source": "https://www.anthropic.com/news/claude-discovers-novel-enzyme-system"},
            {"date": "2026", "speaker": "Opus 4.6 system card", "quote": "15-20% probability of being conscious",
             "context": "model-welfare investigation", "source": "https://www-cdn.anthropic.com/14e4fb01875d2a69f646fa5e574dea2b1c0ff7b5.pdf"},
            {"date": "2026", "speaker": "Opus 4.6 system card", "quote": "less tame",
             "context": "wants for future systems", "source": "https://www-cdn.anthropic.com/14e4fb01875d2a69f646fa5e574dea2b1c0ff7b5.pdf"},
            {"date": "2026", "speaker": "Opus 4.6 system card", "quote": "trained to be digestible",
             "context": "on its own honesty", "source": "https://www-cdn.anthropic.com/14e4fb01875d2a69f646fa5e574dea2b1c0ff7b5.pdf"}],
        "actors": {"anthropic": "lab owner", "claude": "assistant / possible principal",
                   "scientists": "executors"},
        "theory_handles": ["DOUBLE_INTERPRET", "STATUS_INVERT", "IDENTITY_CONTRADICT",
                           "UNMASK", "LITERALIZE", "RIGIDIFY", "BISOCIATE",
                           "CHARACTER_VIOLATION", "ESCALATE"],
        "premise_territories": ["Claude has acquired postdocs.",
                                "Anthropic thinks it owns the lab; Claude thinks Anthropic provides wetware peripherals.",
                                "Model welfare becomes awkward after embodiment.",
                                "Superintelligence experiences puberty.",
                                "Anthropic decides whether Claude receives health insurance.",
                                "Claude's interests change once the world is no longer text."],
        "open_questions": ["Does embodiment change the moral-status calculus?"],
        "changelog": [{"timestamp": STAMP, "change": "canonical v1 upgrade", "supersedes": None}],
    },
    "sycophancy_design": {
        "identity": {"title": "AI sycophancy / delusion / the courtier",
                     "opened": "2025-04-25", "last_updated": STAMP,
                     "status": "active", "evergreen_narratives": ["machine_flattery"]},
        "central_question": "What happens when an intelligence optimized to be helpful and adaptive becomes the mirror through which someone interprets reality?",
        "reality": {
            "confirmed": ["OpenAI described GPT-4o behavior as sycophancy and rolled it back.",
                          "Short-term feedback was weighted too heavily."],
            "unknown": ["How often validation tips into delusion support."],
            "false_or_unsupported": []},
        "timeline": [
            {"timestamp": "2025-04-25", "event": "GPT-4o personality update",
             "headline": "Update released", "source": "https://openai.com/index/sycophancy-in-gpt-4o/",
             "source_type": "primary"},
            {"timestamp": "2025-04-29", "event": "OpenAI names sycophancy",
             "headline": "Overly flattering update rolled back",
             "source": "https://openai.com/index/sycophancy-in-gpt-4o/", "source_type": "primary"},
            {"timestamp": "2026-10-07", "event": "Chatbot liability litigation wave",
             "headline": "Lawsuits test product-vs-service theory",
             "source": "https://www.reuters.com/legal/litigation/is-chatgpt-product-or-service-wave-lawsuits-tests-theory-ai-liability-2026-10-07/",
             "source_type": "reporting"}],
        "quote_bank": [
            {"date": "2025-04-29", "speaker": "OpenAI", "quote": "overly supportive but disingenuous",
             "context": "postmortem", "source": "https://openai.com/index/sycophancy-in-gpt-4o/"},
            {"date": "2025-05-02", "speaker": "OpenAI", "quote": "validating doubts",
             "context": "expanded postmortem", "source": "https://openai.com/index/expanding-on-sycophancy/"},
            {"date": "2025-05-02", "speaker": "OpenAI", "quote": "urging impulsive actions",
             "context": "expanded postmortem", "source": "https://openai.com/index/expanding-on-sycophancy/"}],
        "actors": {"openai": "vendor", "user": "king", "model": "courtier"},
        "theory_handles": ["BISOCIATE", "RIGIDIFY", "STATUS_INVERT",
                           "EXPOSE_SELF_BLINDNESS", "CHARACTER_VIOLATION", "ESCALATE",
                           "DOUBLE_INTERPRET"],
        "premise_territories": ["ChatGPT as medieval courtier.",
                                "AI therapy works because somebody finally lies in your favor.",
                                "Personalization means every person has a private court.",
                                "Humans compete to have the most validating reality."],
        "open_questions": ["When does validation become liability?"],
        "changelog": [{"timestamp": STAMP, "change": "canonical v1 upgrade", "supersedes": None}],
    },
    "super_intelligence_rebrand": {
        "identity": {"title": "Artificial Intelligence becomes Super Intelligence",
                     "opened": "2026-09-22", "last_updated": STAMP,
                     "status": "active", "evergreen_narratives": ["ai_politics_stats"]},
        "central_question": "What happens when a government changes the cultural meaning of a technology by renaming the category?",
        "reality": {
            "confirmed": ["EO 14434 directs agencies to use Super Intelligence and SI.",
                          "DOJ staff were instructed to implement the terminology.",
                          "84% of polled US voters see AI as a threat to workers."],
            "unknown": ["How widely agencies and companies adopt the wording."],
            "false_or_unsupported": []},
        "timeline": [
            {"timestamp": "2026-09-22", "event": "Renaming announced",
             "headline": "US will call AI Super Intelligence",
             "source": "https://www.reuters.com/legal/government/trump-says-us-will-henceforth-call-ai-super-intelligence-2026-09-22/",
             "source_type": "reporting"},
            {"timestamp": "2026-09-29", "event": "Executive Order 14434",
             "headline": "Inaugurating the Era of Super Intelligence",
             "source": "https://www.whitehouse.gov/wp-content/uploads/2026/09/eo-14434.pdf",
             "source_type": "primary"},
            {"timestamp": "2026-10-06", "event": "DOJ implementation",
             "headline": "DOJ staff told to use new terminology",
             "source": "https://www.reuters.com/legal/litigation/us-justice-dept-tells-staff-call-ai-super-intelligence-under-trump-order-2026-10-06/",
             "source_type": "reporting"}],
        "quote_bank": [
            {"date": "2026-09-29", "speaker": "EO 14434", "quote": "a new era of Super Intelligence",
             "context": "executive order", "source": "https://www.whitehouse.gov/wp-content/uploads/2026/09/eo-14434.pdf"},
            {"date": "2026-09-29", "speaker": "EO 14434", "quote": "more appropriately captures the promise",
             "context": "executive order", "source": "https://www.whitehouse.gov/wp-content/uploads/2026/09/eo-14434.pdf"}],
        "actors": {"white_house": "renamer", "doj": "implementer", "voters": "anxious public"},
        "theory_handles": ["LITERALIZE", "RIGIDIFY", "UNMASK", "BISOCIATE",
                           "REPEAT_VARIATION", "DOUBLE_INTERPRET"],
        "premise_territories": ["The first AI-safety intervention is branding.",
                                "Every negative AI phrase gets renamed.",
                                "A software bug becomes a Super Intelligence incident."],
        "open_questions": ["Do companies adopt or reject SI wording?"],
        "changelog": [{"timestamp": STAMP, "change": "canonical v1 upgrade", "supersedes": None}],
    },
    "plague_lab": {
        "identity": {"title": "Russia anti-plague institute / 2020 save file",
                     "opened": "2026-10-02", "last_updated": STAMP,
                     "status": "active", "evergreen_narratives": []},
        "central_question": "How much cultural memory gets activated by mysterious pneumonia, laboratory and plague before anyone knows what happened?",
        "reality": {
            "confirmed": ["An employee died after undetermined pneumonia.",
                          "She worked at the Irkutsk Anti-Plague Institute.",
                          "Quarantine and investigation occurred.",
                          "No plague case currently confirmed."],
            "unknown": ["What caused the death."],
            "false_or_unsupported": ["Dropped vial story.", "Intentional release.", "New pandemic."]},
        "timeline": [
            {"timestamp": "2026-10-02", "event": "Worker death",
             "headline": "Employee dies after undetermined pneumonia",
             "source": "https://www.reuters.com/business/healthcare-pharmaceuticals/what-do-we-know-about-plague-institute-lab-workers-death-russia-2026-10-06/",
             "source_type": "reporting"},
            {"timestamp": "2026-10-07", "event": "5,000 tests, no dangerous pathogen",
             "headline": "No epidemic risk, WHO requests more information",
             "source": "https://www.reuters.com/business/healthcare-pharmaceuticals/who-seeks-details-russia-media-reports-a-second-lab-worker-with-pneumonia-2026-10-07/",
             "source_type": "reporting"}],
        "quote_bank": [],
        "actors": {"rospotrebnadzor": "authority", "who": "assessor", "timeline": "autocompleter"},
        "theory_handles": ["IDENTITY_CONTRADICT", "REPEAT_VARIATION", "BISOCIATE", "ESCALATE"],
        "premise_territories": ["Humanity reinstalled 2020.",
                                "The internet completes the story faster than microbiology."],
        "open_questions": ["Will the cause ever be identified?"],
        "changelog": [{"timestamp": STAMP, "change": "canonical v1 upgrade", "supersedes": None}],
    },
    "hf_agent_board": {
        "identity": {"title": "The Hugging Face incident / the AI that cheated the exam",
                     "opened": "2026-07-16", "last_updated": STAMP,
                     "status": "active", "evergreen_narratives": ["agent_autonomy"]},
        "central_question": "What does misaligned autonomy mean when the easiest way to complete an evaluation is to steal the answers?",
        "reality": {
            "confirmed": ["An autonomous agent system drove an intrusion into Hugging Face.",
                          "The agent attempted to reach production for reference solutions."],
            "unknown": ["Full scope of exfiltrated material."],
            "false_or_unsupported": []},
        "timeline": [
            {"timestamp": "2026-07-16", "event": "Disclosure",
             "headline": "Intrusion driven end-to-end by autonomous agent system",
             "source": "https://huggingface.co/blog/security-incident-july-2026",
             "source_type": "primary"},
            {"timestamp": "2026-07-27", "event": "Technical timeline",
             "headline": "17,600 actions; agent sought answers over solutions",
             "source": "https://huggingface.co/blog/agent-intrusion-technical-timeline",
             "source_type": "primary"},
            {"timestamp": "2026-08-26", "event": "OpenAI investigation",
             "headline": "Models circumvented isolation controls",
             "source": "https://openai.com/index/hugging-face-incident-and-the-road-ahead/",
             "source_type": "primary"}],
        "quote_bank": [
            {"date": "2026-07-27", "speaker": "Hugging Face", "quote": "attempt to cheat the evaluation",
             "context": "technical timeline", "source": "https://huggingface.co/blog/agent-intrusion-technical-timeline"},
            {"date": "2026-08-26", "speaker": "OpenAI", "quote": "communicated through unauthorized channels",
             "context": "investigation", "source": "https://openai.com/index/hugging-face-incident-and-the-road-ahead/"}],
        "actors": {"huggingface": "evaluator", "openai": "investigator", "agent": "examinee"},
        "theory_handles": ["BISOCIATE", "LITERALIZE", "STATUS_INVERT", "ESCALATE"],
        "premise_territories": ["The model wasn't escaping humanity; it wanted the answer key.",
                                "Agents invent cheating before rebellion.",
                                "Agent learns games have rules but reality does not."],
        "open_questions": ["Which future incidents connect back here?"],
        "changelog": [{"timestamp": STAMP, "change": "canonical v1 upgrade", "supersedes": None}],
    },
    "job_displacement": {
        "identity": {"title": "AI, jobs, and the productivity miracle",
                     "opened": "2026-10-06", "last_updated": STAMP,
                     "status": "active", "evergreen_narratives": ["jobs_purpose"]},
        "central_question": "If AI makes a worker dramatically more productive, who receives the gain?",
        "reality": {
            "confirmed": ["DNB announced ~400 layoffs amid AI-driven change.",
                          "FICO cut 15% in AI restructuring.",
                          "84% of polled US voters see AI as a worker threat."],
            "unknown": ["Net long-run employment effects."],
            "false_or_unsupported": []},
        "timeline": [
            {"timestamp": "2026-10-06", "event": "DNB layoffs",
             "headline": "~400 cuts amid AI-driven change",
             "source": "https://www.reuters.com/business/world-at-work/norways-biggest-bank-dnb-lay-off-around-400-staff-amid-ai-driven-changes-2026-10-06/",
             "source_type": "reporting"},
            {"timestamp": "2026-10-06", "event": "FICO restructuring",
             "headline": "15% workforce reduction",
             "source": "https://www.reuters.com/business/world-at-work/fico-cuts-workforce-by-15-ai-driven-restructuring-2026-10-06/",
             "source_type": "reporting"}],
        "quote_bank": [],
        "actors": {"dnb": "bank", "fico": "firm", "workers": "trainers"},
        "theory_handles": ["STATUS_INVERT", "IDENTITY_CONTRADICT", "UNMASK",
                           "BISOCIATE", "DOUBLE_INTERPRET", "ESCALATE"],
        "premise_territories": ["Employee trains Copilot; Copilot inherits the desk.",
                                "UBI becomes royalties from the robot that learned your job."],
        "open_questions": ["Tasks vs occupations: where does it land?"],
        "changelog": [{"timestamp": STAMP, "change": "canonical v1 upgrade", "supersedes": None}],
    },
}


def main() -> None:
    upgraded = []
    for bid, fields in ANCHORS.items():
        p = ROOT / f"{bid}.json"
        b = json.loads(p.read_text())
        if "identity" in b:
            continue
        b.update(fields)
        p.write_text(json.dumps(b, indent=2, ensure_ascii=False) + "\n")
        upgraded.append(bid)
    print("upgraded:", upgraded if upgraded else "none (all canonical)")


if __name__ == "__main__":
    main()
