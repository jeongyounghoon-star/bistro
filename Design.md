# BISTRO Design System: Coinbase x JB Financial

This file is the standing UI contract for the BISTRO dashboard.

The primary reference is a Coinbase-inspired institutional finance system:
quiet editorial spacing, near-monochrome surfaces, one disciplined action blue,
rounded product cards, and dark full-bleed hero moments. For this project, the
system is tempered by JB Financial Group's public corporate posture: a serious
Korean financial holding-company feel, strong main message, IR/ESG-style
information cards, and a calm group-dashboard rhythm.

## 1. Visual Theme

- Use an institutional finance mood, not a colorful trading app.
- Default page floor is soft gray, not pure white, to reduce glare.
- Major hero and CTA bands may use a full-width dark editorial canvas.
- The single action color is Coinbase Blue `#0052ff`.
- JB reference: strong group identity, IR/ESG/news card rhythm, polished Korean
  financial institution tone.
- Data density lives inside calm cards; the surrounding chrome is generous.

## 2. Colors

### Brand & Accent
- Primary / Coinbase Blue: `#0052ff`
- Primary active: `#003ecc`
- Primary disabled: `#a8b8cc`
- JB institutional blue overlay: `#0046ad`
- Accent yellow: `#f4b000`, illustrative only

### Surfaces
- Canvas: `#ffffff`
- Page floor: `#f3f5f8`
- Surface soft: `#f7f7f7`
- Surface strong: `#eef0f3`
- Surface dark: `#0a0b0d`
- Surface dark elevated: `#16181c`

### Text
- Ink: `#0a0b0d`
- Body: `#5b616e`
- Muted: `#7c828a`
- Muted soft: `#a8acb3`
- On dark: `#ffffff`
- On dark soft: `#a8acb3`

### Borders & Semantics
- Hairline: `#dee1e6`
- Hairline soft: `#eef0f3`
- Semantic up: `#05b169`, text only
- Semantic down: `#cf202f`, text only

## 3. Typography

- Licensed Coinbase fonts are not bundled here. Use substitutes:
  - Display: Inter / system sans, weight 400
  - Body: Inter / system sans, weights 400 and 600
  - Numbers: JetBrains Mono / Geist Mono / SFMono-Regular fallback
- Display weight stays at 400.
- Body text stays at 400.
- Component titles may use 600.
- Every numerical value uses tabular numerals.
- Implementation note: the source reference uses negative tracking for display,
  but this workspace requires `letter-spacing: 0`; keep implementation at 0.

## 4. Shape Rules

- CTA buttons: pill radius `100px`.
- Search/filter pills: pill radius `100px`.
- Asset/icon plates: full circle.
- Cards and product UI mockups: `24px`.
- Compact rows: `8px`.
- Inputs: `12px`.
- Avoid sharp corners.

## 5. Layout

- Max content width: about `1200px`.
- Base spacing unit: `4px`.
- Major bands use `96px` vertical rhythm when space allows.
- Dashboard cards use 24px gaps on large screens and 16px on smaller screens.
- Mobile collapses to one column; tablet uses two columns.

## 6. Components

### Hero Band
- Use `#0a0b0d` with white text for the main hero.
- Add subtle blue radial/linear accents.
- Treat this as the product mockup stage, visually heavier than the rest.

### Cards
- Light cards: white, 1px hairline, 24px radius.
- Dark cards: `#16181c`, 24px radius, subtle hairline.
- Use one soft shadow tier only: `0 4px 12px rgba(0,0,0,0.04)`.

### Buttons
- Primary: `#0052ff`, white text, pill, 44px height.
- Active/hover: `#003ecc`.
- Secondary light: `#eef0f3`, ink text, pill.
- Tertiary text links: blue text, no fill.

### Tabs
- Tabs behave like segmented pills.
- Active tab uses blue background and white text.
- Inactive tab sits on `#eef0f3`.

### Forms
- Inputs use white fill, hairline border, 12px radius.
- Focus border/ring is Coinbase Blue.
- Search bars may use pill geometry.

### Charts
- History/actual line: ink `#0a0b0d`.
- Baseline forecast: Coinbase Blue `#0052ff`.
- Scenario/alternate forecast: JB blue `#0046ad` or semantic red when showing a down-risk path.
- Grid lines: `#dee1e6`.
- Tooltips: white cards on light surfaces, dark elevated cards on dark surfaces.

### Trading Semantics
- Positive: `#05b169`, text only.
- Negative: `#cf202f`, text only.
- Do not use semantic green/red as button backgrounds.

## 7. Do's

- Use Coinbase Blue sparingly for action and active states.
- Use dark hero bands to reduce brightness and add institutional weight.
- Use rounded product-card geometry consistently.
- Use tabular numerals for metrics and chart values.
- Let JB-style IR/ESG/card rhythm guide information density.

## 8. Don'ts

- Do not return to the earlier dark teal theme.
- Do not make the entire page stark white.
- Do not introduce many accent colors.
- Do not use heavy display weights.
- Do not use green/red as decorative fills.

## 9. JB Financial Reference Notes

Observed from `https://www.jbfg.com/ko/main.do`:
- The main corporate message is "젊고 강한 강소 금융그룹".
- The home structure emphasizes credit rating, IR activity, annual report,
  financial results, stock info, ESG, global footprint, news, and family
  companies.
- For BISTRO, mirror this through a serious hero, IR-like metric tiles,
  ESG/coverage cards, and restrained dashboard panels.
