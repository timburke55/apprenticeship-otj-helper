# OTJ Helper — User Guide

A complete guide to using the Apprenticeship Off-the-Job Training Helper to log activities, track KSB coverage, and prepare evidence for your End-Point Assessment.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Selecting Your Apprenticeship Standard](#2-selecting-your-apprenticeship-standard)
3. [Dashboard](#3-dashboard)
4. [Logging Activities](#4-logging-activities)
5. [CORE Workflow Resources](#5-core-workflow-resources)
6. [Attachments](#6-attachments)
7. [KSB Mapping](#7-ksb-mapping)
8. [Tags](#8-tags)
9. [Activity Templates](#9-activity-templates)
10. [KSB Reference Browser](#10-ksb-reference-browser)
11. [Recommendations](#11-recommendations)
12. [Exporting Your Data](#12-exporting-your-data)
13. [Hour Targets](#13-hour-targets)

---

## 1. Getting Started

### Signing In

The app uses **Google OAuth** for authentication. Click **Sign in with Google** on the login page and use the Google account your training provider has authorised.

If your email is not on the allowlist, you will see an **Access Denied** page. Contact your training provider to be added.

### Local Development Login

When running locally, you can bypass Google OAuth entirely by setting the `DEV_AUTO_LOGIN_EMAIL` environment variable:

```bash
DEV_AUTO_LOGIN_EMAIL=you@example.com uv run otj-helper
```

This creates a local user automatically and logs you in on every request.

---

## 2. Selecting Your Apprenticeship Standard

When you first sign in you land on the **home page**, which shows all available apprenticeship standards. Click **Select this standard** on the card for your programme. This controls:

- Which KSBs appear in activity forms and the KSB browser
- Which KSBs are counted in dashboard stats and recommendations

You can switch standard at any time by returning to the home page (`/`). Your existing activity data is retained; only the filter applied to KSB views changes.

**Available standards:**

| Code | Standard | Level |
|------|----------|-------|
| ST0787 | Systems Thinking Practitioner | 7 |
| ST0763 | AI Data Specialist | 7 |

---

## 3. Dashboard

The dashboard (`/dashboard`) is your central overview. It updates automatically whenever you save or delete an activity.

### Summary Cards

Four cards at the top show at a glance:

| Card | What it shows |
|------|---------------|
| **Total OTJ Hours** | Sum of all logged activity hours, with a progress bar if you have set an OTJ target |
| **This Week** | Hours logged in the current ISO week, with remaining hours to weekly target |
| **Activities Logged** | Total number of activity records |
| **KSBs Covered** | Number of KSBs with at least one linked activity, out of the total for your standard |

### Portfolio Readiness Score

A circular gauge (0–100%) in the top-right summarises how portfolio-ready your evidence is:

- **60%** of the score comes from KSB coverage (how many KSBs have any evidence)
- **40%** comes from evidence quality (how many KSBs have at least one activity marked *Good* or *Review Ready*)

A top-priority action is shown beneath the gauge. Click **View all recommendations** for the full gap analysis.

### Charts

| Chart | Description |
|-------|-------------|
| **12-week bar chart** | Hours logged per ISO week for the last 12 weeks |
| **Seminar vs OTJ doughnut** | Split between seminar hours (training courses + workshops) and other OTJ activity types |
| **KSB progress bars** | Horizontal bars showing total hours per KSB, grouped by category (Knowledge / Skills / Behaviours) |

### KSB Coverage Map

Pill-shaped badges for every KSB in your standard. Blue = Knowledge, green = Skills, amber = Behaviours. Badges for KSBs with no evidence are greyed out. Click any badge to go to that KSB's detail page.

### Top Tags

The 15 most-used tags across your activities, each showing a count. Click a tag to see all activities with that tag.

### Recent Activities

The last 5 activities, with date, title, duration, and KSB badges. Click any activity to open its detail page.

---

## 4. Logging Activities

### Creating a New Activity

Go to **Activities → New activity** or click the **+ New** button from any page.

If you have saved any templates, a **Use template** dropdown appears at the top. Select a template and click **Apply** to pre-fill the form.

### Activity Fields

| Field | Required | Notes |
|-------|----------|-------|
| **Title** | Yes | A short, descriptive name |
| **Date** | Yes | The date the activity took place |
| **Duration (hours)** | Yes | Minimum 0.25 h; use steps of 0.25 |
| **Activity type** | Yes | See types below |
| **Description** | No | Your own account of what you did and learned. This is your evidence — write it yourself. |
| **Notes** | No | Private working notes, not part of the formal evidence record |
| **Evidence quality** | No | *Draft*, *Good*, or *Review ready* (defaults to Draft) |

### Activity Types

| Type | When to use |
|------|-------------|
| Training course | Structured course, e-learning, webinar, or classroom session |
| Self study | Independent reading, research, or practice |
| Mentoring | One-to-one mentoring session (as mentee or mentor) |
| Shadowing | Observing a colleague or process |
| Workshop | Participatory workshop or collaborative session |
| Conference | Conference attendance, including talks and networking |
| Project work | Hands-on work on a work-based or academic project |
| Research | Formal or informal research activity |
| Writing | Writing a report, blog post, documentation, or reflection |
| Other | Anything that does not fit the above |

### Evidence Quality

Use quality to track how polished your evidence is:

| Quality | Meaning |
|---------|---------|
| **Draft** | Raw notes — not yet suitable for submission |
| **Good** | Well-written and complete — could be used in evidence |
| **Review ready** | Polished and ready for EPA review |

The Recommendations page tracks how many KSBs have only Draft evidence and prompts you to improve them.

### Editing and Deleting

Open an activity and click **Edit** or **Delete**. Deleting an activity also removes all its resource links, attachments, and tag associations permanently.

---

## 5. CORE Workflow Resources

Each activity can have resource links organised into four stages of the **CORE workflow**. These represent how you moved from capturing raw material to producing finished evidence.

| Stage | Colour | Purpose | Typical sources |
|-------|--------|---------|-----------------|
| **Capture** | Amber | Raw notes, bookmarks, quick captures | Google Keep, websites |
| **Organise** | Blue | Structured notes, task lists | Google Tasks, Google Docs, Markdown |
| **Review** | Green | Processed notes, diagrams, drafts | Google Docs, diagrams, GitHub |
| **Engage** | Purple | Final outputs, published work | Google Drive, GitHub, websites |

### Adding a Resource Link

In the activity form, each stage has an **Add [stage] link** button. Click it to add a row, then fill in:

- **Title** — descriptive label for the link
- **URL** — must begin with `http://` or `https://`
- **Source type** — the platform or tool (options vary by stage)
- **Description** — optional note about what the resource contains

You can add multiple links to any stage and remove them with the delete button on each row.

### On the Activity Detail Page

The detail view shows a four-stage pipeline indicator with a resource count per stage. Click any stage heading to expand its list of links. Each link shows the title (as a clickable URL), source type badge, and description.

---

## 6. Attachments

You can upload files directly to an activity to keep evidence in one place.

### Uploading Files

On the activity form, use the **Attachments** section to select files. You can also upload to an existing activity from its detail page.

**Allowed file types:** JPEG, PNG, GIF, WebP, PDF, Word (`.doc`, `.docx`), plain text (`.txt`), Markdown (`.md`)

**Maximum size:** 10 MB per file

### Viewing and Managing Attachments

On the activity detail page, attachments appear as a grid. Image files show a thumbnail; other files show a file-type icon. Click any thumbnail or filename to download the original file.

Delete an attachment with the **Delete** button. This removes the file permanently.

---

## 7. KSB Mapping

Each activity can be linked to one or more KSBs from your selected apprenticeship standard. Use the checkboxes in the **KSBs** section of the activity form.

KSBs are colour-coded throughout the app:

| Category | Colour | Codes (ST0787) |
|----------|--------|----------------|
| Knowledge | Blue | K1–K5 |
| Skills | Green | S1–S11 |
| Behaviours | Amber | B1–B6 |

There is no limit on how many KSBs you link to an activity. Link every KSB that the activity genuinely evidences — the recommendations engine uses these links to detect coverage gaps.

---

## 8. Tags

Tags are free-form labels you invent yourself. Use them to group activities that don't share a KSB or activity type — for example, a project name, a topic area, or a sprint.

### Adding Tags

In the activity form, type comma-separated tags in the **Tags** field (e.g. `lean-thinking, sprint-4, stakeholder-mapping`). Tags are created automatically if they don't already exist.

### Managing Tags

Go to **Tags** in the navigation to see all your tags with activity counts. From there you can:

- **Rename** a tag — the rename applies to all activities using it
- **Delete** a tag — removes the tag from all activities (the activities themselves are kept)

### Filtering by Tag

On the Activities list, use the **Tag** filter dropdown to show only activities with a given tag. The CSV export also respects this filter.

---

## 9. Activity Templates

Templates let you save a reusable set of defaults for activities you log repeatedly — for example, a weekly team meeting or a recurring self-study session.

### Creating a Template

Go to **Templates → New template** and fill in:

| Field | Notes |
|-------|-------|
| **Name** | Unique identifier for this template (shown in the dropdown on the activity form) |
| **Title** | Default activity title (you can edit it when using the template) |
| **Activity type** | Default type |
| **Duration** | Default duration in hours (optional) |
| **Description** | Default description text |
| **Evidence quality** | Default quality level |
| **KSBs** | Default KSB codes to pre-check |
| **Tags** | Default comma-separated tags |

You can also create a template from an existing activity using **Save as template** on the activity detail page.

### Using a Template

On the new-activity form, select a template from the **Use template** dropdown and click **Apply**. The form fields are pre-filled with the template's defaults. You still write the description and notes yourself; the template only sets the structural defaults.

### Recurring Templates

Mark a template as **Recurring** and choose a **day of the week**. On that day, the app will automatically create a new activity from the template (the first time you visit any protected page that day). The auto-generated activity has a draft quality and empty description — you still need to open it and fill in your own evidence.

**Last generated** shows when the most recent activity was auto-created from this template.

---

## 10. KSB Reference Browser

Go to **KSBs** to browse the full list of competencies for your selected standard.

### KSB List

KSBs are grouped by category (Knowledge, Skills, Behaviours). Each row shows:

- Code badge and full title
- Number of activities linked to that KSB
- Total hours of evidence

KSBs with **no evidence** are highlighted with an alert at the top of the page — act on these first.

### KSB Detail

Click any KSB to see:

- Full title and description
- Category and spec code
- Every activity linked to this KSB (with date, hours, and type)
- Total hours for this KSB

Use the KSB detail pages when reviewing your evidence before an EPA conversation — you can see all your evidence for a single competency in one place.

---

## 11. Recommendations

Go to **Recommendations** for a detailed gap analysis of your portfolio.

### Readiness Score

The same 0–100% score shown on the dashboard, broken down by:

- **Coverage score** — percentage of KSBs with any evidence (weighted 60%)
- **Quality score** — percentage of KSBs with at least one Good or Review Ready activity (weighted 40%)

Colour coding: green ≥ 75%, amber ≥ 50%, red < 50%.

### Priority Actions

Up to five prioritised suggestions, such as:

- "Log evidence for K1, K2 — no evidence yet" (critical gaps)
- "Try new activity types: Workshop, Conference" (unused types)
- "Add CORE workflow resources: Capture, Organise" (missing workflow stages)
- "Revisit stale KSBs: K1, S3 — not updated in 30+ days"
- "Improve evidence quality: K2, S1 — all evidence is draft"

### KSB Gaps Table

Lists every KSB that needs attention, with:

| Column | Meaning |
|--------|---------|
| **Severity** | Critical = no evidence at all; Warning = fewer than 2 hours |
| **Reason** | Brief explanation |
| **Hours** | Total hours logged |
| **Activities** | Number of linked activities |

### Other Gap Sections

| Section | What it shows |
|---------|---------------|
| **Activity type gaps** | Activity types you have never used |
| **Workflow stage gaps** | CORE stages with no resource links across all activities |
| **Staleness** | KSBs where the most recent linked activity is more than 30 days old |
| **Quality gaps** | KSBs where every linked activity is still at Draft quality |

---

## 12. Exporting Your Data

On the **Activities** page, click **Export CSV** to download a spreadsheet of your activities. The export respects any active filters (KSB, activity type, tag), so you can export a targeted subset of your data.

**Columns exported:**

Date, Title, Hours, Activity type, Evidence quality, Tags, KSBs, Resource link count, Description

Use the CSV export to share evidence summaries with your coach or line manager, or to keep an offline backup.

---

## 13. Hour Targets

Set personal hour targets on the dashboard to track your progress toward programme requirements. Scroll to the **Hour targets** section and enter:

| Target | Description |
|--------|-------------|
| **OTJ target** | Total off-the-job hours required for your programme (e.g. 460 h) |
| **Seminar target** | Required hours in structured seminar activities (training courses + workshops) |
| **Weekly target** | Hours you aim to log per week (e.g. 7.5 h) |

Progress bars on the dashboard summary cards update immediately when you save targets. Leave a field blank to hide its progress bar.

---

## About Evidence and AI

This app is designed to support **your** portfolio — all descriptions, notes, and reflections must be written by you. The app never generates, suggests, or auto-completes your evidence text. The recommendations engine is a read-only gap analysis; it identifies what is missing but does not write anything on your behalf.

This is intentional and required by JGA Group's AI policy (QA-18) and the UK apprenticeship assessment framework. Authentic evidence, in your own words, is what the End-Point Assessment Organisation expects to see.
