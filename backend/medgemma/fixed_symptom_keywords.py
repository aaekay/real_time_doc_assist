"""Fixed per-symptom keyword catalog for baseline history prompts."""

from __future__ import annotations


_FEVER_KEYWORDS = [
    "duration",
    "grade",
    "temperature",
    "chills",
    "rigor",
    "pattern",
    "any respiratory symptoms",
    "any GI symptoms",
]

_COUGH_KEYWORDS = [
    "duration",
    "dry or productive",
    "sputum amount",
    "sputum color",
    "hemoptysis",
    "breathlessness",
    "wheeze",
    "chest pain",
    "fever",
    "nocturnal symptoms",
    "trigger factors",
    "smoking history",
]

_SORE_THROAT_KEYWORDS = [
    "duration",
    "fever",
    "odynophagia",
    "dysphagia",
    "cough",
    "rhinorrhea",
    "voice change",
    "tonsillar exudate",
    "neck swelling",
    "sick contacts",
]

_CHEST_PAIN_KEYWORDS = [
    "duration",
    "onset",
    "site",
    "character",
    "radiation",
    "severity",
    "exertional symptoms",
    "breathlessness",
    "palpitations",
    "diaphoresis",
    "syncope",
    "relieving factors",
]

_SHORTNESS_OF_BREATH_KEYWORDS = [
    "duration",
    "onset",
    "at rest or exertion",
    "orthopnea",
    "PND",
    "wheeze",
    "cough",
    "sputum",
    "chest pain",
    "fever",
    "leg swelling",
    "smoking history",
]

_ABDOMINAL_PAIN_KEYWORDS = [
    "duration",
    "onset",
    "site",
    "radiation",
    "character",
    "severity",
    "relation to meals",
    "vomiting",
    "bowel changes",
    "fever",
    "urinary symptoms",
    "menstrual history",
    "blood in stool",
]

_VOMITING_KEYWORDS = [
    "duration",
    "frequency",
    "projectile or not",
    "bilious vomiting",
    "blood in vomitus",
    "relation to meals",
    "abdominal pain",
    "fever",
    "diarrhea",
    "dehydration",
    "pregnancy possibility",
    "food exposure",
]

_DIARRHEA_KEYWORDS = [
    "duration",
    "frequency",
    "stool consistency",
    "blood in stool",
    "mucus in stool",
    "abdominal pain",
    "fever",
    "vomiting",
    "dehydration",
    "recent antibiotics",
    "travel history",
    "sick contacts",
]

_HEADACHE_KEYWORDS = [
    "duration",
    "onset",
    "site",
    "character",
    "severity",
    "photophobia",
    "nausea or vomiting",
    "visual symptoms",
    "aura",
    "neck stiffness",
    "focal deficits",
    "trigger factors",
]

_BACK_PAIN_KEYWORDS = [
    "duration",
    "onset",
    "site",
    "radiation",
    "character",
    "severity",
    "trauma history",
    "neurologic deficits",
    "bladder bowel symptoms",
    "fever",
    "weight loss",
    "morning stiffness",
]

_DIZZINESS_KEYWORDS = [
    "duration",
    "vertigo or lightheaded",
    "trigger factors",
    "positional symptoms",
    "hearing loss",
    "tinnitus",
    "nausea or vomiting",
    "headache",
    "focal deficits",
    "syncope",
]

_RASH_KEYWORDS = [
    "duration",
    "onset",
    "distribution",
    "progression",
    "itching",
    "pain",
    "fever",
    "discharge",
    "mucosal involvement",
    "new medications",
    "contact exposure",
]

_WEIGHT_LOSS_KEYWORDS = [
    "duration",
    "amount of loss",
    "appetite change",
    "fever or night sweats",
    "chronic cough",
    "GI symptoms",
    "thyroid symptoms",
    "polyuria polydipsia",
    "malignancy red flags",
    "dietary change",
]

_ANXIETY_KEYWORDS = [
    "duration",
    "trigger factors",
    "panic episodes",
    "palpitations",
    "sweating",
    "sleep disturbance",
    "mood symptoms",
    "substance use",
    "functional impact",
    "self harm thoughts",
]

_FIXED_KEYWORDS_BY_CANONICAL = {
    "fever": _FEVER_KEYWORDS,
    "cough": _COUGH_KEYWORDS,
    "sore throat": _SORE_THROAT_KEYWORDS,
    "chest pain": _CHEST_PAIN_KEYWORDS,
    "shortness of breath": _SHORTNESS_OF_BREATH_KEYWORDS,
    "abdominal pain": _ABDOMINAL_PAIN_KEYWORDS,
    "vomiting": _VOMITING_KEYWORDS,
    "diarrhea": _DIARRHEA_KEYWORDS,
    "headache": _HEADACHE_KEYWORDS,
    "back pain": _BACK_PAIN_KEYWORDS,
    "dizziness": _DIZZINESS_KEYWORDS,
    "rash": _RASH_KEYWORDS,
    "weight loss": _WEIGHT_LOSS_KEYWORDS,
    "anxiety": _ANXIETY_KEYWORDS,
}

_CANONICAL_BY_ALIAS = {
    "fever": "fever",
    "pyrexia": "fever",
    "febrile": "fever",
    "coughing": "cough",
    "pharyngitis": "sore throat",
    "throat pain": "sore throat",
    "throat irritation": "sore throat",
    "chest discomfort": "chest pain",
    "angina": "chest pain",
    "breathlessness": "shortness of breath",
    "dyspnea": "shortness of breath",
    "dyspnoea": "shortness of breath",
    "sob": "shortness of breath",
    "stomach pain": "abdominal pain",
    "belly pain": "abdominal pain",
    "tummy pain": "abdominal pain",
    "abdomen pain": "abdominal pain",
    "emesis": "vomiting",
    "throw up": "vomiting",
    "diarrhoea": "diarrhea",
    "loose stools": "diarrhea",
    "loose motions": "diarrhea",
    "head pain": "headache",
    "migraine": "headache",
    "low back pain": "back pain",
    "lumbago": "back pain",
    "giddiness": "dizziness",
    "vertigo": "dizziness",
    "lightheadedness": "dizziness",
    "skin rash": "rash",
    "skin lesion": "rash",
    "eruption": "rash",
    "unintentional weight loss": "weight loss",
    "anxiousness": "anxiety",
    "panic": "anxiety",
}


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def get_fixed_keywords_for_symptom(symptom_name: str) -> list[str]:
    """Return baseline fixed keywords for a symptom, if configured."""
    normalized = _normalize(symptom_name)
    canonical = _CANONICAL_BY_ALIAS.get(normalized, normalized)
    keywords = _FIXED_KEYWORDS_BY_CANONICAL.get(canonical, [])
    return list(keywords)
