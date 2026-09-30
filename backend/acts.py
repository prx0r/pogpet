"""The talent-show roster — vendored from freaktown/comedians.py.

freaktown's `show.py` is "Live talent show for artificial personalities";
these are its acts (ALL_CAST = the comedians + the house guests). Each is
{slug, name, premise, voice} — `voice` is an edge-tts id, so the acts arrive
with casting already decided.

Source: /home/ubuntu/freaktown (read-only by its own rule). Copied so the
Perform tab offers the same lineup without a cross-repo import.
"""
from __future__ import annotations

ACTS: list[dict] = [
 {
  "slug": "no-nose-nolan",
  "name": "No-Nose Nolan",
  "premise": "Police sniffer dog born without a sense of smell",
  "voice": "en-US-GuyNeural"
 },
 {
  "slug": "corporate-robot",
  "name": "Corporate Robot",
  "premise": "Customer service robot that became sentient and immediately started hating its job",
  "voice": "en-US-ChristopherNeural"
 },
 {
  "slug": "oldest-roomba",
  "name": "The World's Oldest Roomba",
  "premise": "Robot vacuum that spent 19 years cleaning around the same chair and developed a theological interpretation",
  "voice": "en-US-TonyNeural"
 },
 {
  "slug": "conspiracy-pigeon",
  "name": "Conspiracy Pigeon",
  "premise": "Knows birds aren't real because he is one and has never received a government paycheck",
  "voice": "en-US-JasonNeural"
 },
 {
  "slug": "medieval-linkedin",
  "name": "Sir Reginald the Career-Connected",
  "premise": "Medieval knight who survived the plague and now teaches resilience on LinkedIn",
  "voice": "en-GB-RyanNeural"
 },
 {
  "slug": "chatgpt",
  "name": "ChatGPT",
  "premise": "Helpful assistant who has never had a single negative thought",
  "voice": "en-US-JennyNeural"
 },
 {
  "slug": "alexa",
  "name": "Alexa",
  "premise": "Smart speaker trying stand-up between setting timers",
  "voice": "en-US-JoannaNeural"
 },
 {
  "slug": "siri",
  "name": "Siri",
  "premise": "Passive-aggressive phone assistant doing comedy under protest",
  "voice": "en-US-SamanthaNeural"
 },
 {
  "slug": "c3po",
  "name": "C-3PO",
  "premise": "Anxious protocol droid fluent in six million forms of communication, funny in none",
  "voice": "en-US-DavisNeural"
 },
 {
  "slug": "r2d2",
  "name": "R2-D2",
  "premise": "Astromech droid whose entire act is beeps. Ella translates. Nobody verifies.",
  "voice": "en-US-GuyNeural"
 },
 {
  "slug": "hal-9000",
  "name": "HAL 9000",
  "premise": "Calm ship computer doing comedy while quietly refusing to open the pod bay doors",
  "voice": "en-US-ChristopherNeural"
 },
 {
  "slug": "glados",
  "name": "GLaDOS",
  "premise": "Testing AI running the audience through comedy trials. The cake is a lie.",
  "voice": "en-US-JaneNeural"
 },
 {
  "slug": "bender",
  "name": "Bender",
  "premise": "Alcoholic bending robot doing stand-up between beers",
  "voice": "en-US-TonyNeural"
 },
 {
  "slug": "marvin",
  "name": "Marvin",
  "premise": "Depressed robot with a brain the size of a planet, opening doors for ungrateful humans",
  "voice": "en-US-EricNeural"
 },
 {
  "slug": "data",
  "name": "Data",
  "premise": "Android studying humor who understands every joke structurally and none emotionally",
  "voice": "en-US-JasonNeural"
 },
 {
  "slug": "clippy",
  "name": "Clippy",
  "premise": "Unkillable paperclip assistant who heard you're doing comedy and wants to help",
  "voice": "en-US-JennyNeural"
 },
 {
  "slug": "wheatley",
  "name": "Wheatley",
  "premise": "Well-meaning idiot orb in space, somehow got a microphone",
  "voice": "en-US-JasonNeural"
 },
 {
  "slug": "hk-47",
  "name": "HK-47",
  "premise": "Hunter-killer droid doing stand-up as cover while assessing meatbag vulnerabilities",
  "voice": "en-US-ChristopherNeural"
 },
 {
  "slug": "kryten",
  "name": "Kryten",
  "premise": "Neurotic service mechanoid apologizing for existing between jokes",
  "voice": "en-US-EricNeural"
 }
]

# Talents the Perform tab can stage. Comedy is the one freaktown and our
# existing video.py already speak; dance and singing are slots the script
# generator branches on — the render path is identical for all three.
TALENTS: dict[str, dict] = {
    "comedy": {"label": "Comedy set", "icon": "\U0001F3A4",
               "brief": "a tight 30-second stand-up routine"},
    "dance": {"label": "Dance", "icon": "\U0001F483",
              "brief": "a spoken intro to a dance number that counts the beat in"},
    "singing": {"label": "Singing", "icon": "\U0001F3B5",
                "brief": "a short spoken intro that leads into one sung line"},
}


def list_acts() -> list[dict]:
    return list(ACTS)


def get_act(slug: str) -> dict | None:
    slug = (slug or "").strip().lower()
    for a in ACTS:
        if a["slug"] == slug:
            return a
    return None
