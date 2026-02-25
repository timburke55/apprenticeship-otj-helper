# TODO

## Accessibility

- **Keyboard focus indicators** — All interactive elements (buttons, links) should use
  `focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2` instead of
  `focus:outline-none`, which suppresses the browser's default focus ring for keyboard users.
  Needs a codebase-wide pass rather than a one-off fix. Flagged during PR #14 review.
