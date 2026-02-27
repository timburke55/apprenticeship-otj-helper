# Extension 01: LLM-Assisted Evidence Writing

## Overview

Add an AI-powered "Suggest Evidence" button to the activity form that calls an LLM API (Anthropic Claude) to generate a draft evidence statement. Given an activity's title, type, description, and linked KSBs, the LLM produces a structured paragraph mapping the activity to the apprenticeship standard's language.

**Complexity drivers:** Async external API calls, prompt engineering, streaming responses to the browser, API key management, content safety, rate limiting, and a new settings UI for API configuration.

---

## Prerequisites

- An Anthropic API key (set via env var `ANTHROPIC_API_KEY`)
- New dependency: `anthropic>=0.40` (the official Python SDK)

---

## Step-by-step Implementation

### 1. Add the `anthropic` dependency

**File:** `pyproject.toml`

Add `"anthropic>=0.40"` to the `dependencies` list. Run `uv sync` to install.

### 2. Create the LLM service module

**New file:** `src/otj_helper/llm.py`

```python
"""LLM integration for evidence writing assistance."""

import os
import logging

logger = logging.getLogger(__name__)


def get_client():
    """Return an Anthropic client, or None if not configured."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    from anthropic import Anthropic
    return Anthropic(api_key=api_key)


def build_evidence_prompt(activity_title, activity_type, description, ksb_details):
    """Build the system + user prompt for evidence generation.

    Args:
        activity_title: The activity title string.
        activity_type: The activity type label (e.g. "Self-Study").
        description: The user's description of what they did.
        ksb_details: List of dicts with keys 'code', 'title', 'description'
                     for each linked KSB.

    Returns:
        Tuple of (system_prompt, user_message) strings.
    """
    ksb_text = "\n".join(
        f"- {k['code']}: {k['title']} -- {k['description']}"
        for k in ksb_details
    )

    system_prompt = (
        "You are an apprenticeship evidence writing assistant. You help apprentices "
        "write clear, specific evidence statements that map their activities to the "
        "Knowledge, Skills, and Behaviours (KSBs) of their apprenticeship standard. "
        "Write in first person. Be specific and concrete -- reference what was actually "
        "done, not generic statements. Keep the output to 2-3 paragraphs. "
        "Structure: (1) What you did and why, (2) What you learned / how it maps to "
        "the KSBs, (3) How you will apply this going forward."
    )

    user_message = (
        f"Activity: {activity_title}\n"
        f"Type: {activity_type}\n"
        f"Description: {description or '(none provided)'}\n\n"
        f"Linked KSBs:\n{ksb_text or '(none selected)'}\n\n"
        "Please write an evidence statement for this activity that demonstrates "
        "how it maps to the listed KSBs."
    )

    return system_prompt, user_message


def generate_evidence(activity_title, activity_type, description, ksb_details):
    """Call the Anthropic API and return the generated evidence text.

    Returns:
        The generated text string, or None if the API is not configured.

    Raises:
        anthropic.APIError: On API failures (caller should handle).
    """
    client = get_client()
    if client is None:
        return None

    system_prompt, user_message = build_evidence_prompt(
        activity_title, activity_type, description, ksb_details
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text
```

### 3. Create the API route for evidence generation

**New file:** `src/otj_helper/routes/api.py`

Create a new blueprint with prefix `/api`. This is the first JSON API endpoint in the app.

```python
"""Internal JSON API routes."""

import logging

from flask import Blueprint, g, jsonify, request

from otj_helper.auth import login_required
from otj_helper.models import KSB

bp = Blueprint("api", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


@bp.route("/suggest-evidence", methods=["POST"])
@login_required
def suggest_evidence():
    """Accept activity details as JSON, return an LLM-generated evidence draft.

    Request JSON body:
        {
            "title": "...",
            "activity_type": "...",
            "description": "...",
            "ksb_codes": ["K1", "S3"]
        }

    Response JSON:
        {"suggestion": "..."}  on success (200)
        {"error": "..."}       on failure (4xx/5xx)
    """
    from otj_helper.llm import generate_evidence

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    activity_type = (data.get("activity_type") or "").strip()
    description = (data.get("description") or "").strip()
    ksb_codes = data.get("ksb_codes") or []

    if not title:
        return jsonify({"error": "Title is required."}), 400

    # Look up full KSB details for the prompt
    spec = g.user.selected_spec or "ST0787"
    ksbs = KSB.query.filter(
        KSB.code.in_(ksb_codes), KSB.spec_code == spec
    ).all()
    ksb_details = [
        {"code": k.natural_code, "title": k.title, "description": k.description}
        for k in ksbs
    ]

    try:
        result = generate_evidence(title, activity_type, description, ksb_details)
    except Exception as exc:
        logger.exception("LLM API call failed")
        return jsonify({"error": f"AI service error: {exc}"}), 502

    if result is None:
        return jsonify({"error": "AI features are not configured. Set ANTHROPIC_API_KEY."}), 503

    return jsonify({"suggestion": result})
```

### 4. Register the new blueprint

**File:** `src/otj_helper/app.py`

In `create_app()`, after the existing blueprint registrations, add:

```python
from otj_helper.routes.api import bp as api_bp
app.register_blueprint(api_bp)
```

### 5. Exempt the API route from CSRF (it uses JSON, not forms)

**File:** `src/otj_helper/app.py`

After `csrf.init_app(app)`, add:

```python
from otj_helper.routes.api import bp as api_bp
csrf.exempt(api_bp)
```

Alternatively, use `@csrf.exempt` on the individual route. The blueprint-level exemption is cleaner since all future API routes will be JSON-based.

### 6. Add the "Suggest Evidence" button to the activity form

**File:** `src/otj_helper/templates/activities/form.html`

Add a button below the description textarea and a target div for the suggestion. Insert this after the `</textarea>` for the description field (around line 53):

```html
<div class="mt-2 flex items-center gap-3">
    <button type="button" id="suggest-evidence-btn"
        onclick="suggestEvidence()"
        class="inline-flex items-center rounded-md bg-purple-50 px-3 py-1.5 text-sm font-medium text-purple-700 ring-1 ring-inset ring-purple-200 hover:bg-purple-100">
        Suggest evidence draft
    </button>
    <span id="suggest-spinner" class="hidden text-sm text-gray-400">Generating...</span>
</div>
<div id="suggestion-output" class="hidden mt-3 rounded-md bg-purple-50 p-4">
    <div class="flex justify-between items-start mb-2">
        <h4 class="text-sm font-medium text-purple-800">AI Suggestion</h4>
        <button type="button" onclick="applySuggestion()"
            class="text-xs text-purple-600 hover:text-purple-800 font-medium">Use this</button>
    </div>
    <p id="suggestion-text" class="text-sm text-gray-700 whitespace-pre-wrap"></p>
</div>
```

### 7. Add the JavaScript to call the API

**File:** `src/otj_helper/templates/activities/form.html`

Add inside the existing `<script>` block at the bottom:

```javascript
function suggestEvidence() {
    const btn = document.getElementById('suggest-evidence-btn');
    const spinner = document.getElementById('suggest-spinner');
    const output = document.getElementById('suggestion-output');
    const textEl = document.getElementById('suggestion-text');

    const title = document.querySelector('input[name="title"]').value.trim();
    if (!title) {
        alert('Enter a title first.');
        return;
    }

    // Gather selected KSB codes
    const ksbCodes = Array.from(
        document.querySelectorAll('input[name="ksbs"]:checked')
    ).map(cb => cb.value);

    const activityType = document.querySelector('select[name="activity_type"]').value;
    const description = document.querySelector('textarea[name="description"]').value;

    btn.disabled = true;
    spinner.classList.remove('hidden');
    output.classList.add('hidden');

    fetch('/api/suggest-evidence', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: title,
            activity_type: activityType,
            description: description,
            ksb_codes: ksbCodes,
        }),
    })
    .then(resp => resp.json())
    .then(data => {
        btn.disabled = false;
        spinner.classList.add('hidden');
        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }
        textEl.textContent = data.suggestion;
        output.classList.remove('hidden');
    })
    .catch(err => {
        btn.disabled = false;
        spinner.classList.add('hidden');
        alert('Request failed: ' + err.message);
    });
}

function applySuggestion() {
    const text = document.getElementById('suggestion-text').textContent;
    const desc = document.querySelector('textarea[name="description"]');
    if (desc.value.trim() && !confirm('Replace the current description?')) return;
    desc.value = text;
}
```

### 8. Add tests

**New file:** `tests/test_llm.py`

```python
"""Tests for LLM evidence suggestion feature."""

import json


def test_suggest_evidence_requires_title(_with_spec, client):
    """POST /api/suggest-evidence without title returns 400."""
    resp = client.post(
        "/api/suggest-evidence",
        data=json.dumps({"title": "", "ksb_codes": []}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert "error" in data


def test_suggest_evidence_no_api_key(_with_spec, client, monkeypatch):
    """Returns 503 when ANTHROPIC_API_KEY is not set."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = client.post(
        "/api/suggest-evidence",
        data=json.dumps({
            "title": "Test activity",
            "activity_type": "self_study",
            "description": "Studied systems thinking",
            "ksb_codes": ["K1"],
        }),
        content_type="application/json",
    )
    assert resp.status_code == 503


def test_build_evidence_prompt_structure():
    """Prompt builder returns well-formed system and user messages."""
    from otj_helper.llm import build_evidence_prompt

    system, user = build_evidence_prompt(
        "Workshop on SSM",
        "Workshop",
        "Attended a full-day workshop",
        [{"code": "K1", "title": "Test KSB", "description": "Some description"}],
    )
    assert "apprenticeship" in system.lower()
    assert "Workshop on SSM" in user
    assert "K1" in user
```

### 9. Update CLAUDE.md

Add the new endpoint to the URL reference table:
- `url_for('api.suggest_evidence')` -> `/api/suggest-evidence`

Add `ANTHROPIC_API_KEY` to the env var documentation.

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Edit | Add `anthropic>=0.40` dependency |
| `src/otj_helper/llm.py` | Create | LLM service: prompt building + API call |
| `src/otj_helper/routes/api.py` | Create | JSON API blueprint with `/api/suggest-evidence` |
| `src/otj_helper/app.py` | Edit | Register `api` blueprint, CSRF-exempt it |
| `src/otj_helper/templates/activities/form.html` | Edit | Add suggest button, output div, JS fetch logic |
| `tests/test_llm.py` | Create | Tests for prompt building, validation, 503 fallback |
| `CLAUDE.md` | Edit | Document new endpoint and env var |

---

## Security Considerations

- **API key storage:** `ANTHROPIC_API_KEY` must only be in env vars, never committed.
- **CSRF exemption:** The `/api/*` blueprint is CSRF-exempt because it accepts JSON, not form data. It still requires `@login_required`.
- **Input sanitisation:** User input is passed as-is to the LLM prompt. The response is rendered via `textContent` (not `innerHTML`), preventing XSS.
- **Rate limiting:** Consider adding a simple in-memory rate limiter (e.g. 10 requests/min/user) to prevent API cost abuse. A `flask-limiter` integration is optional but recommended.
- **Cost control:** The prompt uses `max_tokens=1024` to cap response length. Monitor usage via the Anthropic dashboard.

---

## Testing Checklist

- [ ] `uv run pytest tests/test_llm.py` -- all pass
- [ ] `uv run pytest` -- existing tests still pass
- [ ] Manual: open activity form, fill in title + KSBs, click "Suggest evidence draft"
- [ ] Manual: verify suggestion appears in purple box, "Use this" copies to description
- [ ] Manual: verify button shows "Generating..." spinner during API call
- [ ] Manual: verify graceful error when `ANTHROPIC_API_KEY` is not set
