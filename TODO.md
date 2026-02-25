# TODO

## Accessibility

- **Keyboard focus indicators** — All interactive elements (buttons, links) should use
  `focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2` instead of
  `focus:outline-none`, which suppresses the browser's default focus ring for keyboard users.
  Needs a codebase-wide pass rather than a one-off fix. Flagged during PR #14 review.

- **Touch target sizing** — Interactive elements (buttons, links, checkboxes) should meet the
  44×44 CSS px minimum defined by WCAG 2.1 SC 2.5.5 (Level AAA). The KSB checkbox grid in the
  activity form and the small "Save" / "Delete" buttons on the tags page are the most likely
  offenders. Needs audit on an actual mobile device.

## Mobile / Responsive

- **Dashboard chart heights on narrow screens** — KSB progress charts use a fixed pixel height
  calculated server-side (`{{ k_items|length * 28 + 10 }}px`). On very narrow viewports the
  bars become too thin to read comfortably. Consider using a JS `ResizeObserver` to reflow the
  chart height when the container width changes, or increase the per-item multiplier on small
  screens.

- **Activity form on mobile** — The CORE workflow resource-link rows (`grid grid-cols-1
  sm:grid-cols-12`) stack to a single column on mobile but the stacked inputs lack visible
  labels (only placeholders). Adding `<label>` elements (or `aria-label` attributes) for each
  field would improve both mobile usability and screen reader support.

- **Tags rename on mobile** — The rename form is currently hidden on mobile with a "view on a
  larger screen" note. A better UX would be an inline-edit pattern or a dedicated rename page
  that works at any width.

## Code Quality

- **Remaining hardcoded `href` paths** — The following template files still contain hardcoded
  paths instead of `url_for()` calls. They were not in scope for PR #18 but should be cleaned
  up in a dedicated pass:
  - `templates/activities/detail.html` — 4 occurrences (`/activities/<id>`, `/activities/<id>/edit`, `/ksbs/<code>`, `/activities?tag=`)
  - `templates/ksbs/detail.html` — 3 occurrences (`/activities/<id>`, `/activities/new`, `/ksbs`)
  - `templates/auth/login.html` — 1 occurrence (`/auth/google`)
  - `templates/auth/denied.html` — 1 occurrence (`/auth/login`)
