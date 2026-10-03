"""Stream categorization for Classes 11-12 (Science / Commerce / Arts &
Humanities / Vocational).

Single source of truth: every surface (textbooks, courses via Subject,
materials, doubts, reading picks, finder queue) derives or stores the same
`stream` code through `stream_for`. The empty string means *common* — a
subject every stream takes (languages, Mathematics which HSC offers in both
Science and Commerce, EVS, Health & PE) — so a stream filter always matches
`stream == X OR stream == ""` and can never hide a shared book.

Streams only exist where they actually exist: `stream_for` returns "" for
grades below 11, so classes 1-10 keep today's flat subject list untouched.
"""

STREAMS: list[tuple[str, str, str, str]] = [
    # (code, en, hi, mr)
    ("science", "Science", "विज्ञान", "विज्ञान"),
    ("commerce", "Commerce", "वाणिज्य", "वाणिज्य"),
    ("arts", "Arts & Humanities", "कला व मानविकी", "कला व मानविकी"),
    ("vocational", "Vocational", "व्यावसायिक", "व्यावसायिक"),
]

STREAM_CODES = {code for code, _, _, _ in STREAMS}

# Deliberately NOT here: Mathematics and Computer Science are offered in
# multiple HSC streams, so they stay common ("") and show up under all of
# them — hiding them from Commerce would be worse than showing them to Arts.
_SCIENCE = {"physics", "biology", "chemistry", "science"}
_COMMERCE = {
    "economics",
    "पुस्तपालन व लेखाकर्म",       # Book-keeping & Accountancy
    "वाणिज्य संघटन व व्यवस्थापन",  # Organisation of Commerce & Management
    "चिटणिसाची कार्यपध्दती",       # Secretarial Practice
    "सहकार",                        # Co-operation
}
_ARTS = {
    "history", "civics", "geography",
    "तत्वज्ञान",    # Philosophy
    "तर्कशास्त्र",   # Logic
    "मानसशास्त्र",  # Psychology
    "समाजशास्त्र",  # Sociology
    "शिक्षणशास्त्र",  # Education
    "संरक्षणशास्त्र",  # Defence Studies
    "भूशास्त्र",      # Geology
}
_VOCATIONAL = {
    "गृहव्यवस्थापन",            # Home Management
    "बाल विकास",                 # Child Development
    "वस्त्रशास्त्र",              # Textile Science
    "ग्रंथालय व माहितीशास्त्र",  # Library & Information Science
}


def stream_for(class_grade: int | None, subject_name: str) -> str:
    """Stream code for one (grade, subject), or "" when the subject is common
    to all streams — or when streams don't apply at all (below class 11)."""
    if not class_grade or class_grade < 11:
        return ""
    name = (subject_name or "").strip().lower()
    if name in _SCIENCE:
        return "science"
    if name in _COMMERCE:
        return "commerce"
    if name in _ARTS:
        return "arts"
    if name in _VOCATIONAL:
        return "vocational"
    return ""


def stream_label(code: str, lang: str = "en") -> str:
    """Display label for a stream code in en/hi/mr (falls back to English)."""
    idx = {"hi": 2, "mr": 3}.get(lang, 1)
    for c, en, hi, mr in STREAMS:
        if c == code:
            return (en, hi, mr)[idx - 1]
    return code
