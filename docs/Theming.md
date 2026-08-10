# Theming the Streamlit App

Everything about how this app looks is controlled from one file:

```
app/src/.streamlit/config.toml
```

No CSS, no HTML, no per-page styling code. If you want to change the look of your project, this is the only file you need to touch.

## Seeing your changes

Save the file and the theme updates on the spot — an already-open browser tab will repaint itself without you doing anything. If a change doesn't appear, refresh the tab.

You should not need to restart the container for theme or `[client]` changes. If a setting still seems to have no effect after a refresh, restart the app and reload:

```bash
docker compose restart app
```

(add `-f sandbox.yaml` if you are working in your sandbox).

The most common reason a setting "does nothing" is not caching — it is a misspelled key. Streamlit ignores keys it does not recognize, silently. Check your spelling against the reference linked at the bottom of this page.

## What is in the file now

The shipped theme is deliberately not the Streamlit default. Three choices do most of the work:

1. **A dark sidebar against a light content area.** This is the single biggest visual change; stock Streamlit apps are light-gray-on-white and are recognizable across a room.
2. **Serif headings, sans-serif body, monospace only for code.** The Streamlit default uses one sans font for everything.
3. **The Deploy button is hidden.** `toolbarMode = "minimal"` removes the "Deploy" button that ships in the top-right corner and is a dead giveaway that an app is an unmodified Streamlit project.

## The settings you are most likely to change

### Colors

All colors are hex strings like `"#2C6E63"`.

| Setting | What it colors |
|---|---|
| `primaryColor` | Buttons, sliders, focus rings, selected states — your accent |
| `backgroundColor` | The main page background |
| `secondaryBackgroundColor` | Cards, code blocks, table headers, form fills |
| `textColor` | Body text |
| `linkColor` | Hyperlinks |
| `borderColor` | Outlines on inputs, expanders, and containers |

Changing `primaryColor` alone is the fastest way to make the app feel like yours.

### Fonts

`font`, `headingFont`, and `codeFont` each accept `"sans-serif"`, `"serif"`, or `"monospace"`.

Setting the top-level `font` to `"monospace"` applies monospace to *everything* — headings, prose, and button labels included. That is rarely what you want; keep monospace for `codeFont`.

### Shape

- `baseRadius` / `buttonRadius` — `"none"`, `"small"`, `"medium"`, `"large"`, `"full"`. Smaller reads more businesslike; `"full"` gives pill-shaped buttons.
- `showWidgetBorder = true` draws an outline around inputs so form fields look like form fields.

### The sidebar

`[theme.sidebar]` is a separate section that inherits everything from `[theme]` and overrides what you set. That is how this app gets a dark sidebar without darkening the whole page:

```toml
[theme.sidebar]
backgroundColor = "#232B2B"
textColor = "#E9EDEB"
primaryColor = "#4E9C8D"
```

Note the sidebar has its own `primaryColor`. The accent that works on a light background is often too dark to see on a dark one — the sidebar sliders on the *Classification Demo* page use this lighter green.

## Making your own palette

1. Pick an accent color and set `primaryColor`.
2. Pick a background. Pure `#FFFFFF` is fine; a very slightly warm or cool off-white (this app uses `#FBFAF7`) looks more considered and is easier on the eyes.
3. Set `textColor` dark enough to read comfortably against it.
4. If you want a dark sidebar, set `[theme.sidebar]` `backgroundColor` and a light `textColor`, then bump `primaryColor` lighter.
5. Save the file and look at it. Iterate — the feedback loop is instant, so try a few options rather than settling for your first guess.

Check your colors against a real page with widgets and a table on it — not just the Home page. Contrast problems show up in form fields, dataframe headers, and sidebar sliders first.

### A word on contrast

If you darken the background or lighten the text, check that body text is still comfortably readable. Low-contrast text looks stylish on a designer's monitor and is unreadable on a classroom projector.

## Other things you can set

- **Charts:** `chartCategoricalColors` and `chartSequentialColors` take a list of hex colors and control the default palette for Streamlit charts. Worth setting if your project is chart-heavy and the defaults clash with your accent.
- **Dark mode:** this app pins `base = "light"`. You can instead define `[theme.light]` and `[theme.dark]` sections and let the theme follow the viewer's system setting.
- **The top-right menu:** `toolbarMode` accepts `"minimal"` (current), `"viewer"` to hide the menu entirely, and `"developer"` to restore the full Streamlit toolbar.

The complete list of options lives in the [Streamlit config.toml reference](https://docs.streamlit.io/develop/api-reference/configuration/config.toml). Keys that Streamlit does not recognize are ignored, so a typo fails silently — if a setting seems to do nothing, check the spelling against that page.
