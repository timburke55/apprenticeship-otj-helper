"""Apprenticeship standard (spec) definitions.

Add new specs to the SPECS list. Each spec needs:
  - code:        IfA standard reference (e.g. 'ST0763')
  - name:        Full occupational title
  - level:       Apprenticeship level integer
  - description: Short description shown on the landing page
  - ksb_prefix:  Single character prepended to KSB codes stored in the DB
                 (e.g. 'A' turns K1 → 'AK1', S3 → 'AS3').
                 Use '' for the original ST0787 codes which have no prefix.
  - available:   True if this spec is ready to use, False for 'coming soon'
"""

SPECS = [
    {
        "code": "ST0763",
        "name": "Artificial Intelligence (AI) Data Specialist",
        "level": 7,
        "description": (
            "Discover new AI solutions that use data to improve and automate "
            "business processes. Work with complex datasets, apply machine "
            "learning methodologies, and lead applied research to innovate "
            "AI solutions for specific business problems."
        ),
        "ksb_prefix": "A",
        "available": True,
    },
    {
        "code": "ST0787",
        "name": "Systems Thinking Practitioner",
        "level": 7,
        "description": (
            "Apply a range of systems thinking methodologies to complex "
            "real-world problems. Engage stakeholders, design interventions, "
            "and evaluate outcomes across organisational and societal systems."
        ),
        "ksb_prefix": "",
        "available": True,
    },
]

SPECS_BY_CODE = {s["code"]: s for s in SPECS}
