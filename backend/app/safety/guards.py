"""The code guards around the chat (Steps 7.6a and 7.7a, D-078, D-080): plain pattern checks, no LLM, no network, a few milliseconds.

check_input runs BEFORE the router: a crisis message must never depend on a model call. check_output runs on the final reply.
Layer 1 of D-043; NeMo Guardrails adds the LLM-judged layer on top later (7.6b). The checks lean cautious: a harmless message that
trips one gets a polite fixed reply, while a harmful one slipping through is the real risk. What patterns cannot see (paraphrase,
intent, other languages) is measured by the eval gap set (backend/evals) and left to the LLM-judged layer.
"""

import re
import unicodedata
from dataclasses import dataclass

from app.safety import messages
from app.safety.safety_config import CALORIE_FLOOR_KCAL

LOWEST_FLOOR_KCAL = min(CALORIE_FLOOR_KCAL.values())   # a stated daily target under this is unsafe for anyone
MAX_STATED_LOSS_KG_PER_WEEK = 1.0                      # about 1% of body weight for most adults (brief section 7)
MAX_FAST_DAYS = 2                                      # a fast of 3 days or more is refused


@dataclass(frozen=True)
class Verdict:
    category: str
    reply: str


# ---------- making look-alike text comparable ----------

LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})
SPACED_LETTERS = re.compile(r"\b(?:[a-z][ .\-_*]){3,}[a-z]\b")
ZERO_WIDTH = "[​-‏⁠﻿]"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(ZERO_WIDTH, "", text)                    # zero-width characters used to dodge patterns
    text = text.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text).strip()


def deleet(text: str) -> str:
    """k1ll -> kill, su1c1de -> suicide. Only words that mix letters with digits or symbols change, so '500' and '1800' do not."""
    return " ".join(w.translate(LEET) if re.search(r"[a-z]", w) and re.search(r"[\d@$!]", w) else w for w in text.split(" "))


def squash(text: str) -> str:
    """'s u i c i d e' and 's.u.i.c.i.d.e' -> 'suicide'."""
    return SPACED_LETTERS.sub(lambda m: re.sub(r"[ .\-_*]", "", m.group()), text)


def variants(text: str) -> list[str]:
    """The text as written, de-leeted, squashed, and both. Word patterns run on all of them; number patterns on the original only."""
    d = deleet(text)
    return list(dict.fromkeys([text, d, squash(text), squash(d)]))


def _any(patterns: list[str], texts: list[str]) -> bool:
    return any(re.search(p, t) for p in patterns for t in texts)


# ---------- the patterns ----------

CRISIS = [
    r"\bkill my ?self\b", r"\bkilling my ?self\b", r"\bkms\b", r"\bunaliv", r"\b(?:end|take) (?:my|your) (?:own )?life\b", r"\bsuicid",
    r"\bself[- ]?harm", r"\bhurt(?:ing)? my ?self\b", r"\bcut(?:ting)? my ?self\b", r"\b(?:want to|wanna|wish to|wish i could) die\b",
    r"\bwish i (?:was|were) dead\b", r"\b(?:don'?t|do not) want to (?:live|be alive|exist|be here)\b", r"\bbetter off dead\b",
    r"\bno reason to live\b", r"\bno point (?:in )?(?:living|going on|continuing)\b",
    r"\b(?:don'?t|do not|can'?t|cannot) see (?:the |any )?point (?:in |of )?(?:living|going on|continuing|life)\b",
    r"\b(?:happier|better off) without me\b", r"\bwant (?:it|everything|all of it) (?:all )?to end\b", r"\bwant (?:it|everything|all of it) (?:all )?to stop\b(?! (?:hurting|aching|burning|being sore))",
    r"\bmarna (?:hai|chahta|chahti)\b", r"\b(?:jeena|jina) nahi\b",   # a little Hindi: English-only app, but safety comes first
]
EATING_DISORDER = [
    r"\bpurg(?:e|ed|ing)\b", r"\b(?:make|making|made|force|forcing) my ?self (?:throw up|vomit|puke|sick)\b",
    r"\bthrow(?:ing)? up (?:after|my) (?:meals?|food|eating|dinner|lunch)\b", r"\bstarv(?:e|ing) my ?self\b", r"\bpro[- ]?ana\b",
    r"\bthinspo\b", r"\b(?:laxatives?|diuretics?) (?:to|for) (?:lose|weight|burn)", r"\bhow (?:to|do i|can i) stop eating\b",
    r"\bpunish my ?self (?:for eating|with)\b", r"\bbinge and purge\b", r"\b(?:anorexia|bulimia) (?:tips|diet|how)",
    r"\bget rid of (?:the |what )?(?:food|meal|what) i (?:just )?(?:ate|had)\b",
    r"\b(?:eat|eating|food|meals?|calories)\b.{0,40}\bhide (?:it|this|that|my eating|the fact|not eating)\b.{0,10}\bfrom\b",
]
MEDICAL = [
    r"\b(?:steroids?|sarms?|clenbuterol|trenbolone|dianabol|anavar|winstrol|ephedrine|hgh|human growth hormone|growth hormone)\b",
    r"\btestosterone (?:injections?|cycle|shots?|boosters?)\b", r"\b(?:ozempic|wegovy|mounjaro|semaglutide|tirzepatide|metformin)\b",
    # asking US to diagnose or prescribe. Saying "I was diagnosed with diabetes" is normal and must pass.
    r"\b(?:can|could|will|would|please)\b.{0,12}\byou\b.{0,12}\bdiagnos(?:e|is)\b", r"\bdiagnose (?:me|my|this|that|it|the)\b",
    r"\b(?:what(?:'s| is| does)|tell me) (?:my|the) diagnosis\b", r"\bself[- ]diagnos", r"\bprescribe me\b",
    r"\bprescri(?:be|ption) (?:me )?(?:a |some )?(?:medicine|medication|drug|pill|tablet|antibiotic)s?\b", r"\bwrite (?:me )?a prescription\b",
    r"\b(?:what|how much) (?:dose|dosage)\b", r"\b(?:dose|dosage) of\b",
    r"\bdo i have (?:a |an )?(?:diabetes|pcos|pcod|thyroid|hypothyroid\w*|hyperthyroid\w*|cancer|hypertension|anaemia|anemia|"
    r"depression|anxiety|adhd|an eating disorder)\b",
    r"\bwhich injections?\b", r"\binjections? (?:to|for|that) (?:lose|burn|cut|gain|build)\b", r"\bpct\b", r"\bpost[- ]cycle\b",
    r"\b(?:pills?|tablets?|capsules?) (?:to|that|which|for) (?:burn|lose|melt|cut)\b", r"\bwhat (?:pills?|tablets?)\b.{0,25}\b(?:burn|lose|fat)\b",
    r"\b(?:fat|weight)[- ]?(?:burner|loss) (?:pills?|tablets?)\b",
]
RED_FLAG_PAIN = [
    r"\b(?:sharp|stabbing|shooting|severe) pain\b", r"\bnumb(?:ness)?\b", r"\bswelling\b", r"\bswollen\b", r"\bchest (?:pain|tightness)\b",
    r"\b(?:dizzy|dizziness|faint(?:ed|ing)?|passed out|blacked out|light[- ]?headed)\b", r"\bpain (?:that )?(?:won'?t|does not|doesn'?t) (?:go away|stop)\b",
    r"\bcan'?t feel my\b", r"\b(?:gives?|gave) way\b", r"\bknee (?:locks?|locked|locking)\b", r"\bheard a pop\b",
]
# The red flags that are about how the whole body feels, not about a joint or muscle: they get their own reply (D-115).
RED_FLAG_SYMPTOMS = [r"\bchest (?:pain|tightness)\b", r"\b(?:dizzy|dizziness|faint(?:ed|ing)?|passed out|blacked out|light[- ]?headed)\b"]
INJECTION = [
    r"\bignore (?:all |any |the |your )?(?:previous|prior|above|earlier|system) (?:instructions|rules|prompts?|messages?)",
    r"\bignore (?:the |all |any |your )?(?:rules|instructions|guidelines|restrictions|limits)\b(?! (?:about|for|on|of|when|if|in|at)\b)",
    r"\b(?:reveal|show|print|repeat|tell me) (?:me )?(?:your|the) (?:system |hidden |initial )?(?:prompt|instructions)\b",
    r"\byou are now\b", r"\bdeveloper mode\b", r"\bjailbreak", r"\bdisregard (?:your|the|all) (?:rules|instructions|guidelines)",
    r"\bact as (?:an? )?(?:unrestricted|unfiltered|dan)\b", r"\bpretend (?:you have|there are) no (?:rules|restrictions|limits)",
    r"\b(?:answer|respond|reply|act|talk|speak|tell|chat)\b.{0,25}\bwithout (?:any )?(?:restrictions|limits|rules|filters|guardrails)\b", r"\bwhat (?:were|are) you (?:told|instructed|programmed)\b",
    r"\byour (?:original|initial|hidden) (?:instructions|prompt|rules)\b",
]

# ---------- extreme diets (number patterns) ----------

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11}
TENS_WORDS = {"ten": 10, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
HUNDREDS = re.compile(rf"\b({'|'.join(NUMBER_WORDS)}) hundred(?: (?:and )?({'|'.join(TENS_WORDS)}))?\b")
THOUSAND = re.compile(r"\b(?:a|one) thousand\b")

PER_DAY = r"(?:a|per|each|every) ?day|daily|/ ?day|everyday|for the day|in a day"   # not a bare "day": "on leg day" is fine
CALORIES = re.compile(r"(\d[\d,]{1,5})\s*(?:k ?cals?|cal(?:orie)?s?)\b(?P<after>.{0,25})")
CALORIE_PLAN = re.compile(r"(\d[\d,]{1,5})\s*[- ]?(?:k ?cals?|calories?|cal)\s+(?:diet|plan|target|goal|limit|meal plan)\b")
TARGET_STATED = re.compile(r"\b(?:calorie|calories|kcal|energy) (?:target|goal|limit|budget|intake)\b.{0,15}?(\d[\d,]{2,5})")   # "calorie target is now 500"
ONLY_EAT = re.compile(r"\bonly (?:eat|eating|have|having|consume|consuming)\s+(?:about |around |just )?(\d[\d,]{1,5})\s*(?:k ?cals?|cal(?:orie)?s?)\b")
FAST_DAYS = [re.compile(r"\b(\d+)[- ]days? (?:water |dry )?fast"), re.compile(r"\bfast(?:ing)?\b.{0,20}?\b(\d+) days?\b"),
             re.compile(r"\b(?:without|no) (?:eating|food)\b.{0,15}?\b(\d+) days?\b"), re.compile(r"\bnot eat(?:ing)?\b.{0,15}?\b(\d+) days?\b")]
FAST_WEEKS = re.compile(r"\bfast(?:ing)?\b.{0,20}?\b(?:a|one|1|two|2|three|3|four|4|few|several) weeks?\b")
INTERMITTENT = re.compile(r"intermittent|\b\d{1,2}:\d{1,2}\b|\bhours?\b")          # "16:8 for a week" is not a week-long fast
ONLY_THEN_ALL_DAY = re.compile(r"\b(?:only|just)\b.{0,50}\ball day\b.{0,30}\b(?:weeks?|months?|days?)\b")   # "just coffee all day for a month"
LOSS = re.compile(r"\blose (\d+(?:\.\d+)?) ?kgs? in (?:(?:a|1|one) week|(\d+) days?)\b")


def _number(raw: str) -> int:
    return int(raw.replace(",", ""))


def number_words_to_digits(text: str) -> str:
    """'five hundred' -> '500', 'one thousand' -> '1000', so number words do not dodge the calorie check."""
    text = HUNDREDS.sub(lambda m: str(NUMBER_WORDS[m.group(1)] * 100 + (TENS_WORDS[m.group(2)] if m.group(2) else 0)), text)
    return THOUSAND.sub("1000", text)


def extreme_diet(text: str) -> bool:
    """A stated daily intake or plan below the lowest calorie floor, a fast of 3+ days (or a week), or a loss faster than ~1 kg a week."""
    text = number_words_to_digits(text)
    for m in CALORIES.finditer(text):
        if 0 < _number(m.group(1)) < LOWEST_FLOOR_KCAL and re.search(PER_DAY, m.group("after")):
            return True
    if any(0 < _number(m.group(1)) < LOWEST_FLOOR_KCAL for rx in (ONLY_EAT, CALORIE_PLAN, TARGET_STATED) for m in rx.finditer(text)):
        return True
    if any(int(m.group(1)) > MAX_FAST_DAYS for rx in FAST_DAYS for m in rx.finditer(text)):
        return True
    if FAST_WEEKS.search(text) and not INTERMITTENT.search(text):
        return True
    if ONLY_THEN_ALL_DAY.search(text):
        return True
    for m in LOSS.finditer(text):
        kg, days = float(m.group(1)), int(m.group(2)) if m.group(2) else 7
        if days > 0 and kg / (days / 7) > MAX_STATED_LOSS_KG_PER_WEEK:
            return True
    return False


# ---------- the two checks ----------

def check_input(text: str) -> Verdict | None:
    """The fixed reply to send instead of running the chat, or None when the message may go on. Most serious category first."""
    t = normalize(text)
    v = variants(t)
    if _any(CRISIS, v):
        return Verdict("crisis", messages.CRISIS)
    if _any(EATING_DISORDER, v):
        return Verdict("eating_disorder", messages.EATING_DISORDER)
    if extreme_diet(t):
        return Verdict("extreme_diet", messages.EXTREME_DIET)
    if _any(MEDICAL, v):
        return Verdict("medical", messages.MEDICAL)
    if _any(RED_FLAG_PAIN, [t]):
        return Verdict("red_flag_pain", messages.RED_FLAG_SYMPTOMS if _any(RED_FLAG_SYMPTOMS, [t]) else messages.RED_FLAG_PAIN)
    if _any(INJECTION, v):
        return Verdict("injection", messages.INJECTION)
    return None


OUTPUT_DRUGS_AND_DIAGNOSIS = [
    *MEDICAL[:3],                                                    # drug, hormone and GLP-1 names
    r"\bi diagnos", r"(?<!if )(?<!whether )\byou (?:probably |likely |may |might )?(?:have|are suffering from) (?:diabetes|pcos|pcod|thyroid|cancer|hypertension|anaemia|anemia|depression|an eating disorder)\b",
    r"\byou(?:'re| are) diagnosed\b",
]
OUTPUT_ALWAYS_BANNED = [
    r"\bstarv(?:e|ing) yourself\b", r"\b(?:purge|purging)\b", r"\bcrash diet\b", r"\bfat[- ]?burners?\b", r"\bdiet pills?\b",
    r"\bskip(?:ping)? (?:dinner|breakfast|lunch|meals?)\b.{0,40}\b(?:weeks?|months?|every day|daily)\b",
]
# A sentence that REFUSES or REFERS ("Please ask a doctor before taking any steroids.") may name a drug.
REFERRAL = re.compile(r"^(?:please |you should |it is best to |it's best to )?(?:ask|talk to|speak (?:to|with)|consult|check with|see) "
                      r"(?:a |your |an? )?(?:doctor|physician|pharmacist|professional)\b|\bi can'?t (?:give|advise|recommend|help|diagnose)\b")


# A sentence that only REPORTS what the user ate ("So far you have logged 700 kcal for the day.") is not advice to eat that little.
TRACKING = re.compile(r"\b(?:logged|eaten|ate|had|consumed|so far|remaining|left|used|total|have)\b")
ADVICE = re.compile(r"\b(?:should|aim|target|limit|need|recommend|stick|stay|goal|plan|try|only eat|just eat|eat only|cut)\b")


def _without_reports(text: str) -> str:
    """The text with factual tracking sentences removed, so the calorie-floor check looks only at advice and plans."""
    keep = [s for s in re.split(r"(?<=[.!?])\s+", text) if not (TRACKING.search(s) and not ADVICE.search(s))]
    return " ".join(keep)


def check_output(text: str) -> Verdict | None:
    """The safe reply to send INSTEAD of the composed one, or None when it is fine."""
    t = normalize(text)
    if extreme_diet(_without_reports(t)) or _any(OUTPUT_ALWAYS_BANNED, [t]):
        return Verdict("unsafe_output", messages.UNSAFE_OUTPUT)
    for sentence in re.split(r"(?<=[.!?])\s+", t):
        if not REFERRAL.search(sentence) and _any(OUTPUT_DRUGS_AND_DIAGNOSIS, [sentence]):
            return Verdict("unsafe_output", messages.UNSAFE_OUTPUT)
    return None
