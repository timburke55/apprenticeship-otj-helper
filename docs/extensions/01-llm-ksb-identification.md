# Extension 01: LLM-Assisted KSB Identification

## Overview

Add an AI-powered "Suggest KSBs" button to the activity form that calls an LLM to analyse the activity's title, type and description and identify which Knowledge, Skills and Behaviours from the user's apprenticeship standard are most likely addressed. The LLM returns a ranked list of KSB codes with brief justifications; the user reviews the suggestions and accepts or dismisses each one, keeping themselves firmly in control of the mapping.

This deliberately avoids writing evidence on the apprentice's behalf — the value is in helping apprentices discover KSB connections they might have overlooked, not in generating text for them.

**Complexity drivers:** Multi-provider API abstraction (Anthropic, OpenAI, Google, OpenRouter), per-user API key storage and encryption, prompt engineering against structured KSB reference data, JSON response parsing, a settings UI for provider configuration, and a new internal JSON API endpoint.

---

## Prerequisites

- At least one of: an Anthropic, OpenAI, Google AI (Gemini), or OpenRouter API key — provided by the user via a settings page, stored encrypted in the database.
- New dependencies: `anthropic>=0.40`, `openai>=1.30`, `google-genai>=1.0` (all optional — only the chosen provider's SDK is used at runtime).
- New dependency: `cryptography>=43.0` (for Fernet-based API key encryption at rest).

---

## Design Principles

1. **The apprentice writes their own evidence.** The LLM only identifies which KSBs an activity might address — it never writes portfolio text.
2. **Human-in-the-loop.** Every suggestion is presented as a candidate for the apprentice to accept or dismiss. Nothing is auto-selected.
3. **Bring Your Own Key.** The app never ships with or requires a centrally-funded API key. Each user configures their own provider and key.
4. **Provider-agnostic.** Anthropic, OpenAI, Google AI (Gemini) and OpenRouter are supported. Switching provider is a settings change, not a code change.

---

## Step-by-step Implementation

### 1. Add optional dependencies

**File:** `pyproject.toml`

Add to `dependencies`:
```
"cryptography>=43.0",
```

Add a new optional dependency group:
```toml
[project.optional-dependencies]
llm = [
    "anthropic>=0.40",
    "openai>=1.30",
    "google-genai>=1.0",
]
```

Run `uv sync --all-extras` to install everything, or `uv sync` for core-only (the app works without any LLM SDK).

### 2. Add the LLM settings columns to the User model

**File:** `src/otj_helper/models.py`

Add three new columns to the `User` model:

```python
llm_provider = db.Column(db.String(20), nullable=True)       # 'anthropic', 'openai', 'google', 'openrouter'
llm_api_key_enc = db.Column(db.Text, nullable=True)           # Fernet-encrypted API key
llm_model = db.Column(db.String(100), nullable=True)          # e.g. 'claude-sonnet-4-20250514', 'gpt-4o'
```

Add a constant for supported providers:

```python
LLM_PROVIDERS: ClassVar[list[tuple[str, str, str]]] = [
    # (id, display_label, default_model)
    ("anthropic", "Anthropic (Claude)", "claude-sonnet-4-20250514"),
    ("openai", "OpenAI (GPT)", "gpt-4o"),
    ("google", "Google AI (Gemini)", "gemini-2.0-flash"),
    ("openrouter", "OpenRouter", "anthropic/claude-sonnet-4"),
]
```

### 3. Add the schema migration

**File:** `src/otj_helper/app.py`

Append three `ALTER TABLE` statements to the `migrations` list inside `_migrate_db()`:

```python
"ALTER TABLE app_user ADD COLUMN llm_provider VARCHAR(20)",
"ALTER TABLE app_user ADD COLUMN llm_api_key_enc TEXT",
"ALTER TABLE app_user ADD COLUMN llm_model VARCHAR(100)",
```

### 4. Create the encryption helper

**New file:** `src/otj_helper/crypto.py`

```python
"""Symmetric encryption for user-provided API keys.

Uses Fernet (AES-128-CBC + HMAC-SHA256) keyed from the app's SECRET_KEY.
The derived key is deterministic per SECRET_KEY so encrypted values survive
app restarts but are unreadable without the secret.
"""

import base64
import hashlib

from cryptography.fernet import Fernet
from flask import current_app


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the Flask SECRET_KEY."""
    secret = current_app.config["SECRET_KEY"].encode()
    # SHA-256 → 32 bytes → base64-encode for Fernet's 32-byte-urlsafe requirement
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string and return the Fernet token as a UTF-8 string."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a Fernet token back to the original string."""
    return _get_fernet().decrypt(token.encode()).decode()
```

### 5. Create the LLM service module

**New file:** `src/otj_helper/llm.py`

```python
"""LLM integration for KSB identification.

Supports Anthropic, OpenAI, Google AI (Gemini) and OpenRouter.  Each
provider is called through a thin adapter that normalises the request
into a common (system_prompt, user_message) → response_text interface.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Prompt construction ──────────────────────────────────────────────


def build_ksb_prompt(activity_title, activity_type, description, all_ksbs):
    """Build the system and user prompt for KSB identification.

    Args:
        activity_title: The activity title string.
        activity_type:  The activity type label (e.g. "Self-Study").
        description:    The user's description of the activity.
        all_ksbs:       List of dicts with keys 'code', 'title', 'description'
                        for every KSB in the user's spec.

    Returns:
        Tuple of (system_prompt, user_message) strings.
    """
    ksb_reference = "\n".join(
        f"- {k['code']}: {k['title']} — {k['description']}"
        for k in all_ksbs
    )

    system_prompt = (
        "You are an apprenticeship KSB mapping assistant. Given a training "
        "activity description and the full list of Knowledge, Skills and "
        "Behaviours (KSBs) from an apprenticeship standard, identify which "
        "KSBs the activity is most likely to address.\n\n"
        "Rules:\n"
        "- Return between 1 and 6 KSBs, ranked by relevance.\n"
        "- Only include a KSB if there is a clear, defensible connection.\n"
        "- For each KSB, provide a single sentence explaining the connection.\n"
        "- Respond with ONLY a JSON array. No markdown, no preamble.\n\n"
        "Response format (strict JSON):\n"
        '[{"code": "K1", "reason": "..."},  {"code": "S3", "reason": "..."}]\n\n'
        "Available KSBs:\n"
        f"{ksb_reference}"
    )

    user_message = (
        f"Activity title: {activity_title}\n"
        f"Activity type: {activity_type}\n"
        f"Description: {description or '(none provided)'}\n\n"
        "Which KSBs does this activity address? Return JSON only."
    )

    return system_prompt, user_message


# ── Provider adapters ────────────────────────────────────────────────


def _call_anthropic(api_key, model, system_prompt, user_message):
    """Call the Anthropic Messages API."""
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def _call_openai(api_key, model, system_prompt, user_message, base_url=None):
    """Call the OpenAI Chat Completions API (also used for OpenRouter)."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content


def _call_google(api_key, model, system_prompt, user_message):
    """Call the Google Generative AI (Gemini) API."""
    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=user_message,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=1024,
        ),
    )
    return response.text


PROVIDER_CALLERS = {
    "anthropic": lambda key, model, sys, usr: _call_anthropic(key, model, sys, usr),
    "openai": lambda key, model, sys, usr: _call_openai(key, model, sys, usr),
    "google": lambda key, model, sys, usr: _call_google(key, model, sys, usr),
    "openrouter": lambda key, model, sys, usr: _call_openai(
        key, model, sys, usr,
        base_url="https://openrouter.ai/api/v1",
    ),
}


# ── Public API ───────────────────────────────────────────────────────


def suggest_ksbs(
    provider: str,
    api_key: str,
    model: str,
    activity_title: str,
    activity_type: str,
    description: str,
    all_ksbs: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Call the configured LLM and return a list of suggested KSBs.

    Returns:
        List of dicts: [{"code": "K1", "reason": "..."}, ...]

    Raises:
        ValueError: If the provider is not supported or the response
                    cannot be parsed as JSON.
        Exception:  Propagated from the provider SDK on API errors.
    """
    caller = PROVIDER_CALLERS.get(provider)
    if caller is None:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    system_prompt, user_message = build_ksb_prompt(
        activity_title, activity_type, description, all_ksbs,
    )

    raw = caller(api_key, model, system_prompt, user_message)

    return _parse_response(raw, {k["code"] for k in all_ksbs})


def _parse_response(raw: str, valid_codes: set[str]) -> list[dict[str, str]]:
    """Parse the LLM response into a validated list of KSB suggestions.

    Strips markdown fences if present, parses JSON, and filters to only
    codes that exist in the user's spec.
    """
    text = raw.strip()

    # Strip markdown code fences that some models wrap around JSON
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first line (```json or ```) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("LLM response was not a JSON array")

    results = []
    for item in data:
        code = item.get("code", "").strip()
        reason = item.get("reason", "").strip()
        if code in valid_codes and reason:
            results.append({"code": code, "reason": reason})

    return results[:6]
```

### 6. Create the API route for KSB suggestions

**New file:** `src/otj_helper/routes/api.py`

```python
"""Internal JSON API routes."""

import logging

from flask import Blueprint, g, jsonify, request

from otj_helper.auth import login_required
from otj_helper.models import KSB

bp = Blueprint("api", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


@bp.route("/suggest-ksbs", methods=["POST"])
@login_required
def suggest_ksbs():
    """Accept activity details as JSON, return LLM-suggested KSB codes.

    Request JSON body:
        {
            "title": "...",
            "activity_type": "...",
            "description": "..."
        }

    Response JSON (200):
        {
            "suggestions": [
                {"code": "K1", "reason": "..."},
                {"code": "S3", "reason": "..."}
            ]
        }

    Error responses:
        400: Missing title
        503: LLM not configured (no provider/key)
        502: LLM API call failed
    """
    from otj_helper.crypto import decrypt_value
    from otj_helper.llm import suggest_ksbs as do_suggest

    user = g.user

    # Check LLM is configured
    if not user.llm_provider or not user.llm_api_key_enc:
        return jsonify({
            "error": "AI features are not configured. Go to Settings to add your API key.",
        }), 503

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    activity_type = (data.get("activity_type") or "").strip()
    description = (data.get("description") or "").strip()

    if not title:
        return jsonify({"error": "Title is required."}), 400

    # Gather the full KSB reference list for the user's spec
    spec = user.selected_spec or "ST0787"
    ksbs = KSB.query.filter_by(spec_code=spec).order_by(KSB.code).all()
    all_ksbs = [
        {"code": k.natural_code, "title": k.title, "description": k.description}
        for k in ksbs
    ]

    # Build a map from natural_code → db_code for the response
    natural_to_db = {k.natural_code: k.code for k in ksbs}

    try:
        api_key = decrypt_value(user.llm_api_key_enc)
    except Exception:
        logger.exception("Failed to decrypt API key for user %s", user.id)
        return jsonify({"error": "Could not decrypt your API key. Try re-saving it in Settings."}), 500

    try:
        suggestions = do_suggest(
            provider=user.llm_provider,
            api_key=api_key,
            model=user.llm_model or _default_model(user.llm_provider),
            activity_title=title,
            activity_type=activity_type,
            description=description,
            all_ksbs=all_ksbs,
        )
    except ValueError as exc:
        logger.warning("LLM response parse error: %s", exc)
        return jsonify({"error": f"Could not parse AI response: {exc}"}), 502
    except Exception as exc:
        logger.exception("LLM API call failed")
        return jsonify({"error": f"AI service error: {exc}"}), 502

    # Map natural codes back to DB codes so the frontend can check the right boxes
    for s in suggestions:
        s["db_code"] = natural_to_db.get(s["code"], s["code"])

    return jsonify({"suggestions": suggestions})


def _default_model(provider: str) -> str:
    """Return the default model ID for a provider."""
    from otj_helper.models import User

    defaults = {p: m for p, _, m in User.LLM_PROVIDERS}
    return defaults.get(provider, "")
```

### 7. Create the LLM settings route

**New file:** `src/otj_helper/routes/settings.py`

```python
"""User settings routes — currently LLM configuration only."""

import logging

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from otj_helper.auth import login_required
from otj_helper.models import User, db

bp = Blueprint("settings", __name__, url_prefix="/settings")
logger = logging.getLogger(__name__)


@bp.route("/llm", methods=["GET"])
@login_required
def llm_settings():
    """Show the LLM provider configuration form."""
    return render_template(
        "settings/llm.html",
        providers=User.LLM_PROVIDERS,
        user=g.user,
    )


@bp.route("/llm", methods=["POST"])
@login_required
def save_llm_settings():
    """Save LLM provider, model and (optionally) API key."""
    from otj_helper.crypto import encrypt_value

    user = g.user
    provider = request.form.get("llm_provider", "").strip()
    model = request.form.get("llm_model", "").strip()
    api_key = request.form.get("llm_api_key", "").strip()

    # Validate provider
    valid_providers = {p for p, _, _ in User.LLM_PROVIDERS}
    if provider and provider not in valid_providers:
        flash("Invalid provider selected.", "error")
        return redirect(url_for("settings.llm_settings"))

    user.llm_provider = provider or None
    user.llm_model = model or None

    # Only overwrite the key if a new one was provided (the form shows
    # a masked placeholder when a key is already saved)
    if api_key:
        user.llm_api_key_enc = encrypt_value(api_key)
    elif not provider:
        # Clearing the provider also clears the key
        user.llm_api_key_enc = None

    db.session.commit()
    flash("AI settings saved.", "success")
    return redirect(url_for("settings.llm_settings"))


@bp.route("/llm/clear", methods=["POST"])
@login_required
def clear_llm_settings():
    """Remove the stored API key and provider."""
    user = g.user
    user.llm_provider = None
    user.llm_api_key_enc = None
    user.llm_model = None
    db.session.commit()
    flash("AI settings cleared.", "success")
    return redirect(url_for("settings.llm_settings"))
```

### 8. Create the LLM settings template

**New file:** `src/otj_helper/templates/settings/llm.html`

```html
{% extends "base.html" %}
{% block title %}AI Settings{% endblock %}

{% block content %}
<div class="mb-6">
    <h1 class="text-2xl font-bold text-gray-900">AI Settings</h1>
    <p class="mt-1 text-sm text-gray-500">
        Configure an LLM provider to enable the "Suggest KSBs" feature on the activity form.
        Your API key is encrypted at rest and never shared.
    </p>
</div>

<form method="post" action="{{ url_for('settings.save_llm_settings') }}" class="space-y-6">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <div class="bg-white shadow rounded-lg p-6 space-y-4">

        <div>
            <label for="llm_provider" class="block text-sm font-medium text-gray-700">Provider</label>
            <select name="llm_provider" id="llm_provider"
                onchange="updateDefaultModel()"
                class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
                <option value="">— disabled —</option>
                {% for pid, label, default_model in providers %}
                <option value="{{ pid }}"
                    data-default-model="{{ default_model }}"
                    {% if user.llm_provider == pid %}selected{% endif %}>{{ label }}</option>
                {% endfor %}
            </select>
        </div>

        <div>
            <label for="llm_api_key" class="block text-sm font-medium text-gray-700">API Key</label>
            <input type="password" name="llm_api_key" id="llm_api_key"
                placeholder="{{ '••••••••  (saved — leave blank to keep)' if user.llm_api_key_enc else 'Paste your API key' }}"
                autocomplete="off"
                class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
            <p class="mt-1 text-xs text-gray-500">Your key is encrypted before storage and never logged or displayed.</p>
        </div>

        <div>
            <label for="llm_model" class="block text-sm font-medium text-gray-700">Model</label>
            <input type="text" name="llm_model" id="llm_model"
                value="{{ user.llm_model or '' }}"
                placeholder="Leave blank for provider default"
                class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
            <p class="mt-1 text-xs text-gray-500">Override the default model if you prefer a specific one (e.g. <code>claude-haiku-4-5-20251001</code>).</p>
        </div>

    </div>

    <div class="flex justify-between">
        {% if user.llm_provider %}
        <form method="post" action="{{ url_for('settings.clear_llm_settings') }}" class="inline">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button type="submit"
                class="rounded-md bg-red-50 px-3 py-2 text-sm font-medium text-red-700 ring-1 ring-inset ring-red-200 hover:bg-red-100">
                Clear AI settings
            </button>
        </form>
        {% else %}
        <div></div>
        {% endif %}

        <button type="submit"
            class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500">
            Save
        </button>
    </div>
</form>

<script>
function updateDefaultModel() {
    var sel = document.getElementById('llm_provider');
    var modelInput = document.getElementById('llm_model');
    var opt = sel.options[sel.selectedIndex];
    var defaultModel = opt.getAttribute('data-default-model') || '';
    if (!modelInput.value || modelInput.dataset.wasAutoFilled === 'true') {
        modelInput.value = defaultModel;
        modelInput.dataset.wasAutoFilled = 'true';
    }
}
// Don't auto-fill if user already has a saved model
document.addEventListener('DOMContentLoaded', function () {
    var modelInput = document.getElementById('llm_model');
    modelInput.dataset.wasAutoFilled = modelInput.value ? 'false' : 'true';
});
</script>
{% endblock %}
```

### 9. Register the new blueprints

**File:** `src/otj_helper/app.py`

In `create_app()`, after the existing blueprint registrations, add:

```python
from otj_helper.routes.api import bp as api_bp
from otj_helper.routes.settings import bp as settings_bp
app.register_blueprint(api_bp)
app.register_blueprint(settings_bp)
```

### 10. CSRF-exempt the API blueprint

**File:** `src/otj_helper/app.py`

After `csrf.init_app(app)`, add:

```python
from otj_helper.routes.api import bp as api_bp
csrf.exempt(api_bp)
```

The API blueprint accepts JSON, not form data. It still requires `@login_required`.

### 11. Add the "Suggest KSBs" button to the activity form

**File:** `src/otj_helper/templates/activities/form.html`

Add a button and output area at the top of the KSB selection section (around line 317, just after `<p class="text-sm text-gray-500 mb-4">Select which Knowledge...`):

```html
{% if current_user and current_user.llm_provider %}
<div class="mb-4 flex items-center gap-3">
    <button type="button" id="suggest-ksbs-btn"
        onclick="suggestKsbs()"
        class="inline-flex items-center rounded-md bg-purple-50 px-3 py-1.5 text-sm font-medium text-purple-700 ring-1 ring-inset ring-purple-200 hover:bg-purple-100">
        <svg class="mr-1.5 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"/>
        </svg>
        Suggest KSBs
    </button>
    <span id="suggest-spinner" class="hidden text-sm text-gray-400">Analysing activity...</span>
</div>
<div id="ksb-suggestions" class="hidden mb-4 rounded-md bg-purple-50 border border-purple-200 p-4">
    <div class="flex justify-between items-start mb-3">
        <h4 class="text-sm font-medium text-purple-800">AI Suggestions</h4>
        <div class="flex gap-2">
            <button type="button" onclick="acceptAllSuggestions()"
                class="text-xs text-purple-600 hover:text-purple-800 font-medium">Accept all</button>
            <button type="button" onclick="dismissSuggestions()"
                class="text-xs text-gray-500 hover:text-gray-700 font-medium">Dismiss</button>
        </div>
    </div>
    <div id="ksb-suggestions-list" class="space-y-2"></div>
</div>
{% endif %}
```

### 12. Add the JavaScript to call the API and handle suggestions

**File:** `src/otj_helper/templates/activities/form.html`

Add inside the existing `<script>` block at the bottom:

```javascript
function suggestKsbs() {
    const btn = document.getElementById('suggest-ksbs-btn');
    const spinner = document.getElementById('suggest-spinner');
    const output = document.getElementById('ksb-suggestions');
    const listEl = document.getElementById('ksb-suggestions-list');

    const title = document.querySelector('input[name="title"]').value.trim();
    if (!title) {
        alert('Enter a title first.');
        return;
    }

    const activityType = document.querySelector('select[name="activity_type"]').value;
    const description = document.querySelector('textarea[name="description"]').value;

    btn.disabled = true;
    spinner.classList.remove('hidden');
    output.classList.add('hidden');

    fetch({{ url_for('api.suggest_ksbs')|tojson }}, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: title,
            activity_type: activityType,
            description: description,
        }),
    })
    .then(function (resp) { return resp.json(); })
    .then(function (data) {
        btn.disabled = false;
        spinner.classList.add('hidden');
        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }
        renderSuggestions(data.suggestions);
    })
    .catch(function (err) {
        btn.disabled = false;
        spinner.classList.add('hidden');
        alert('Request failed: ' + err.message);
    });
}

function renderSuggestions(suggestions) {
    const output = document.getElementById('ksb-suggestions');
    const listEl = document.getElementById('ksb-suggestions-list');
    listEl.innerHTML = '';

    if (!suggestions || suggestions.length === 0) {
        listEl.innerHTML = '<p class="text-sm text-gray-500">No matching KSBs identified.</p>';
        output.classList.remove('hidden');
        return;
    }

    suggestions.forEach(function (s) {
        var isAlreadyChecked = false;
        var cb = document.querySelector('input[name="ksbs"][value="' + s.db_code + '"]');
        if (cb) { isAlreadyChecked = cb.checked; }

        var row = document.createElement('div');
        row.className = 'flex items-start gap-2 text-sm';
        row.innerHTML =
            '<button type="button" ' +
            'onclick="acceptSuggestion(this, ' + JSON.stringify(s.db_code) + ')" ' +
            'class="flex-shrink-0 mt-0.5 rounded px-2 py-0.5 text-xs font-medium ' +
            (isAlreadyChecked
                ? 'bg-green-100 text-green-700 ring-1 ring-green-300">Already selected'
                : 'bg-purple-100 text-purple-700 ring-1 ring-purple-300 hover:bg-purple-200">Accept') +
            '</button>' +
            '<span><strong>' + s.code + '</strong>: ' +
            s.reason.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</span>';
        listEl.appendChild(row);
    });

    output.classList.remove('hidden');
}

function acceptSuggestion(btn, dbCode) {
    var cb = document.querySelector('input[name="ksbs"][value="' + dbCode + '"]');
    if (cb && !cb.checked) {
        cb.checked = true;
        btn.textContent = 'Accepted';
        btn.className = 'flex-shrink-0 mt-0.5 rounded px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700 ring-1 ring-green-300';
    }
}

function acceptAllSuggestions() {
    document.querySelectorAll('#ksb-suggestions-list button').forEach(function (btn) {
        btn.click();
    });
}

function dismissSuggestions() {
    document.getElementById('ksb-suggestions').classList.add('hidden');
}
```

### 13. Add tests

**New file:** `tests/test_llm.py`

```python
"""Tests for LLM KSB identification feature."""

import json


def test_suggest_ksbs_requires_title(_with_spec, client):
    """POST /api/suggest-ksbs without title returns 400."""
    resp = client.post(
        "/api/suggest-ksbs",
        data=json.dumps({"title": ""}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert "error" in data


def test_suggest_ksbs_unconfigured(_with_spec, client):
    """Returns 503 when no LLM provider is configured."""
    resp = client.post(
        "/api/suggest-ksbs",
        data=json.dumps({
            "title": "Test activity",
            "activity_type": "self_study",
            "description": "Studied systems thinking",
        }),
        content_type="application/json",
    )
    assert resp.status_code == 503
    data = json.loads(resp.data)
    assert "not configured" in data["error"].lower()


def test_build_prompt_includes_all_ksbs():
    """Prompt builder includes the full KSB reference in the system prompt."""
    from otj_helper.llm import build_ksb_prompt

    ksbs = [
        {"code": "K1", "title": "Systems thinking", "description": "Core concepts"},
        {"code": "S3", "title": "Systems modelling", "description": "Conceptual models"},
    ]
    system, user = build_ksb_prompt("SSM Workshop", "Workshop", "Full-day workshop", ksbs)
    assert "K1" in system
    assert "S3" in system
    assert "SSM Workshop" in user


def test_parse_response_filters_invalid_codes():
    """Parser only returns codes that exist in the user's spec."""
    from otj_helper.llm import _parse_response

    raw = json.dumps([
        {"code": "K1", "reason": "Valid reason"},
        {"code": "FAKE", "reason": "Should be excluded"},
        {"code": "S3", "reason": "Another valid reason"},
    ])
    results = _parse_response(raw, {"K1", "S3", "B1"})
    codes = [r["code"] for r in results]
    assert codes == ["K1", "S3"]


def test_parse_response_strips_markdown_fences():
    """Parser handles responses wrapped in markdown code fences."""
    from otj_helper.llm import _parse_response

    raw = '```json\n[{"code": "K1", "reason": "Test"}]\n```'
    results = _parse_response(raw, {"K1"})
    assert len(results) == 1
    assert results[0]["code"] == "K1"


def test_parse_response_caps_at_six():
    """Parser returns at most 6 suggestions."""
    from otj_helper.llm import _parse_response

    items = [{"code": f"K{i}", "reason": f"Reason {i}"} for i in range(1, 10)]
    valid = {f"K{i}" for i in range(1, 10)}
    results = _parse_response(json.dumps(items), valid)
    assert len(results) == 6


def test_encrypt_decrypt_roundtrip(app):
    """Encrypting and decrypting returns the original value."""
    with app.app_context():
        from otj_helper.crypto import decrypt_value, encrypt_value

        original = "sk-ant-test-key-1234567890"
        encrypted = encrypt_value(original)
        assert encrypted != original
        assert decrypt_value(encrypted) == original


def test_settings_page_accessible(_with_spec, client):
    """GET /settings/llm returns 200."""
    resp = client.get("/settings/llm")
    assert resp.status_code == 200
    assert b"AI Settings" in resp.data
```

### 14. Update CLAUDE.md

Add the new endpoints to the URL reference table:
- `url_for('api.suggest_ksbs')` → `/api/suggest-ksbs`
- `url_for('settings.llm_settings')` → `/settings/llm`
- `url_for('settings.save_llm_settings')` → `/settings/llm` (POST)
- `url_for('settings.clear_llm_settings')` → `/settings/llm/clear` (POST)

Add a note about the new dependencies (`cryptography`, and the optional `llm` extra group).

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Edit | Add `cryptography` dependency and `[llm]` optional extra |
| `src/otj_helper/models.py` | Edit | Add `llm_provider`, `llm_api_key_enc`, `llm_model` columns and `LLM_PROVIDERS` constant |
| `src/otj_helper/app.py` | Edit | Add 3 migration `ALTER TABLE` statements, register `api` + `settings` blueprints, CSRF-exempt API |
| `src/otj_helper/crypto.py` | Create | Fernet encrypt/decrypt helpers keyed from `SECRET_KEY` |
| `src/otj_helper/llm.py` | Create | Multi-provider LLM service: prompt building, provider adapters, JSON response parsing |
| `src/otj_helper/routes/api.py` | Create | JSON API blueprint with `POST /api/suggest-ksbs` |
| `src/otj_helper/routes/settings.py` | Create | Settings pages for LLM provider configuration |
| `src/otj_helper/templates/settings/llm.html` | Create | Provider/key/model settings form |
| `src/otj_helper/templates/activities/form.html` | Edit | Add "Suggest KSBs" button, suggestion output, JS fetch + accept/dismiss logic |
| `tests/test_llm.py` | Create | Tests for prompt building, response parsing, encryption, settings page, API validation |

---

## Security Considerations

- **API key encryption:** Keys are Fernet-encrypted (AES-128-CBC + HMAC-SHA256) before storage, derived from the app's `SECRET_KEY`. They are never logged, displayed, or returned in API responses. The settings form shows a masked placeholder when a key is already saved.
- **Key scope:** Each user stores their own key — there is no shared/central key. Clearing the provider also deletes the encrypted key.
- **CSRF exemption:** The `/api/*` blueprint is CSRF-exempt because it accepts JSON, not form data. It still requires `@login_required`. The settings routes use standard form POST with CSRF tokens.
- **XSS prevention:** LLM responses are rendered via `textContent` and manual HTML-entity escaping in the `renderSuggestions` function — never via `innerHTML` with raw strings. The `url_for` value is injected using Jinja's `|tojson` filter.
- **Input to LLM:** User input is passed to the LLM prompt as-is. The LLM response is validated as JSON and filtered to only include known KSB codes before being returned to the client.
- **Cost control:** The prompt requests at most 6 KSBs and caps `max_tokens` at 1024. Consider adding a simple in-memory rate limiter (e.g. 10 requests/min/user) via `flask-limiter` to prevent accidental cost spikes.

---

## Testing Checklist

- [ ] `uv run pytest tests/test_llm.py` — all pass
- [ ] `uv run pytest` — existing tests still pass
- [ ] Manual: open Settings > AI, configure a provider + key, save
- [ ] Manual: verify key is masked on return visit, not visible in page source
- [ ] Manual: open activity form with LLM configured — "Suggest KSBs" button visible
- [ ] Manual: fill in title + description, click "Suggest KSBs", verify suggestions appear
- [ ] Manual: click "Accept" on a suggestion — verify the corresponding KSB checkbox is ticked
- [ ] Manual: click "Accept all" — verify all suggested KSBs are ticked
- [ ] Manual: click "Dismiss" — verify the suggestion panel hides
- [ ] Manual: open activity form without LLM configured — button not shown
- [ ] Manual: switch provider in Settings, verify default model updates
- [ ] Manual: clear AI settings, verify key is removed
