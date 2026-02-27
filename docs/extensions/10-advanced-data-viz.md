# Extension 10: Advanced Data Visualisations

## Overview

Replace and extend the existing Chart.js dashboard with richer visualisations: a GitHub-style heatmap calendar showing daily activity, a D3.js Sankey diagram showing how hours flow from activity types into KSBs, and a timeline view of activities. This is primarily a frontend complexity extension.

**Complexity drivers:** D3.js data binding, SVG rendering, responsive design for complex visualisations, data transformation pipelines, tooltip interactions, colour scales, and calendar math.

---

## Prerequisites

- New CDN dependencies: D3.js v7 (no Python packages needed)
- Existing Chart.js can be retained for simpler charts or replaced entirely

---

## Step-by-step Implementation

### 1. Add a data endpoint for visualisations

**New file:** `src/otj_helper/routes/viz.py`

Create a blueprint that serves pre-computed data as JSON for the frontend:

```python
bp = Blueprint("viz", __name__, url_prefix="/viz")
```

| Method | Path | Description |
|--------|------|-------------|
| GET | `/viz/heatmap-data` | Daily hours for the last 365 days as JSON |
| GET | `/viz/sankey-data` | Activity type -> KSB flow data as JSON |
| GET | `/viz/timeline-data` | Activity list with dates for timeline rendering |

#### Heatmap data format:
```json
[
    {"date": "2024-03-15", "hours": 2.5, "count": 1},
    {"date": "2024-03-16", "hours": 0, "count": 0},
    ...
]
```

Query: aggregate `Activity.activity_date` and `sum(duration_hours)` grouped by date for the last 365 days. Fill in missing dates with zeros.

#### Sankey data format:
```json
{
    "nodes": [
        {"id": "self_study", "group": "type"},
        {"id": "K1", "group": "knowledge"},
        ...
    ],
    "links": [
        {"source": "self_study", "target": "K1", "value": 5.5},
        ...
    ]
}
```

Query: for each activity, its type contributes `duration_hours` to each linked KSB. Aggregate across all activities.

#### Timeline data format:
```json
[
    {
        "id": 1, "title": "...", "date": "2024-03-15",
        "hours": 2.5, "type": "self_study",
        "ksbs": ["K1", "S3"]
    },
    ...
]
```

### 2. Create the visualisation page

**New file:** `src/otj_helper/templates/viz/index.html`

A dedicated page (rather than cramming into the dashboard) with three visualisation panels:

```html
{% extends "base.html" %}
{% block title %}Visualisations{% endblock %}

{% block content %}
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"
        integrity="sha384-..."
        crossorigin="anonymous"></script>

<h1 class="text-2xl font-bold text-gray-900 mb-6">Visualisations</h1>

<!-- Heatmap Calendar -->
<div class="bg-white shadow rounded-lg p-6 mb-8">
    <h2 class="text-lg font-medium text-gray-900 mb-4">Activity Heatmap</h2>
    <p class="text-sm text-gray-500 mb-4">Daily OTJ hours over the past year.</p>
    <div id="heatmap" class="overflow-x-auto"></div>
</div>

<!-- Sankey Diagram -->
<div class="bg-white shadow rounded-lg p-6 mb-8">
    <h2 class="text-lg font-medium text-gray-900 mb-4">Hours Flow: Activity Types to KSBs</h2>
    <p class="text-sm text-gray-500 mb-4">Shows how hours from each activity type map to KSBs.</p>
    <div id="sankey" style="min-height: 400px;"></div>
</div>

<!-- Timeline -->
<div class="bg-white shadow rounded-lg p-6 mb-8">
    <h2 class="text-lg font-medium text-gray-900 mb-4">Activity Timeline</h2>
    <div id="timeline" class="overflow-x-auto" style="min-height: 300px;"></div>
</div>

<script>
// JavaScript for each visualisation (see steps below)
</script>
{% endblock %}
```

### 3. Implement the heatmap calendar (D3.js)

Inside the `<script>` block:

```javascript
// Fetch heatmap data and render a GitHub-style contribution calendar
fetch('/viz/heatmap-data')
    .then(r => r.json())
    .then(data => {
        const cellSize = 14;
        const width = 53 * (cellSize + 2) + 40;  // 53 weeks + label space
        const height = 7 * (cellSize + 2) + 20;

        const svg = d3.select('#heatmap')
            .append('svg')
            .attr('width', width)
            .attr('height', height);

        // Colour scale: white (0h) -> light indigo -> dark indigo
        const maxHours = d3.max(data, d => d.hours) || 1;
        const color = d3.scaleSequential(d3.interpolateBlues)
            .domain([0, maxHours]);

        // Parse dates and position cells
        const parseDate = d3.timeParse('%Y-%m-%d');
        data.forEach(d => { d.dateObj = parseDate(d.date); });

        // Render day cells
        svg.selectAll('rect')
            .data(data)
            .enter()
            .append('rect')
            .attr('width', cellSize)
            .attr('height', cellSize)
            .attr('x', d => {
                const weekOfYear = d3.timeWeek.count(d3.timeYear(d.dateObj), d.dateObj);
                return weekOfYear * (cellSize + 2) + 30;
            })
            .attr('y', d => d.dateObj.getDay() * (cellSize + 2))
            .attr('rx', 2)
            .attr('fill', d => d.hours > 0 ? color(d.hours) : '#f3f4f6')
            .append('title')
            .text(d => d.date + ': ' + d.hours.toFixed(1) + 'h (' + d.count + ' activities)');

        // Day labels
        ['Mon', '', 'Wed', '', 'Fri', '', ''].forEach((label, i) => {
            svg.append('text')
                .attr('x', 20).attr('y', i * (cellSize + 2) + cellSize - 2)
                .attr('font-size', '9px').attr('fill', '#6b7280')
                .attr('text-anchor', 'end')
                .text(label);
        });
    });
```

### 4. Implement the Sankey diagram (D3.js)

Use D3's Sankey layout plugin (`d3-sankey`). The Sankey shows:
- Left nodes: activity types (coloured by type)
- Right nodes: KSBs (coloured by category: blue/green/amber)
- Links: width proportional to hours flowing from type to KSB

Include `d3-sankey` via CDN:
```html
<script src="https://cdn.jsdelivr.net/npm/d3-sankey@0.12.3/dist/d3-sankey.min.js"
        integrity="sha384-..."
        crossorigin="anonymous"></script>
```

Render with proper tooltips showing "Self-Study -> K1: 5.5h".

### 5. Implement the timeline view (D3.js)

A horizontal timeline with:
- X-axis: dates (scrollable for long date ranges)
- Dots/circles for each activity, sized by duration
- Coloured by activity type
- Tooltip with activity title, hours, KSBs on hover
- Click to navigate to activity detail page

### 6. Register the blueprint and add navigation

**File:** `src/otj_helper/app.py`

```python
from otj_helper.routes.viz import bp as viz_bp
app.register_blueprint(viz_bp)
```

**File:** `src/otj_helper/templates/base.html`

Add "Visualisations" link to nav bar.

### 7. Add a mini heatmap to the dashboard

**File:** `src/otj_helper/templates/dashboard.html`

Add a compact version of the heatmap (last 12 weeks only) as a dashboard widget, with a "View all" link to the full visualisations page.

### 8. Write tests

**New file:** `tests/test_viz.py`

```python
import json

def test_heatmap_data_returns_json(_with_spec, client):
    """GET /viz/heatmap-data returns JSON array."""
    resp = client.get("/viz/heatmap-data")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert isinstance(data, list)
    assert len(data) == 365 or len(data) == 366  # Full year

def test_sankey_data_returns_json(_with_spec, client):
    """GET /viz/sankey-data returns nodes and links."""
    resp = client.get("/viz/sankey-data")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "nodes" in data
    assert "links" in data

def test_timeline_data_returns_json(_with_spec, client):
    """GET /viz/timeline-data returns activity list."""
    resp = client.get("/viz/timeline-data")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert isinstance(data, list)

def test_viz_page_accessible(_with_spec, client):
    """Visualisation page returns 200."""
    resp = client.get("/viz/")
    assert resp.status_code == 200
```

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `src/otj_helper/routes/viz.py` | Create | Data endpoints + page route |
| `src/otj_helper/templates/viz/index.html` | Create | D3.js visualisation page |
| `src/otj_helper/app.py` | Edit | Register blueprint |
| `src/otj_helper/templates/base.html` | Edit | Add "Visualisations" nav link |
| `src/otj_helper/templates/dashboard.html` | Edit | Mini heatmap widget |
| `tests/test_viz.py` | Create | Data endpoint tests |

---

## Security Considerations

- **CDN scripts:** Pin D3 and d3-sankey to specific versions with SRI integrity hashes.
- **Data endpoints:** All return user-scoped data via `@login_required`.
- **XSS:** D3 renders SVG elements, not innerHTML. Tooltips use `.text()` not `.html()`.
- **CSRF:** Data endpoints are GET-only, no CSRF concerns.

---

## Testing Checklist

- [ ] `uv run pytest tests/test_viz.py` -- all pass
- [ ] `uv run pytest` -- existing tests still pass
- [ ] Manual: navigate to Visualisations page
- [ ] Manual: verify heatmap renders with correct colours for days with activities
- [ ] Manual: verify Sankey shows type-to-KSB flows
- [ ] Manual: verify timeline shows activities as dots, hover shows tooltip
- [ ] Manual: check responsiveness on mobile
