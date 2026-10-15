---
name: AeroThermal Vision
colors:
  surface: '#0f1418'
  surface-dim: '#0f1418'
  surface-bright: '#353a3e'
  surface-container-lowest: '#0a0f13'
  surface-container-low: '#171c20'
  surface-container: '#1b2024'
  surface-container-high: '#252b2f'
  surface-container-highest: '#30353a'
  on-surface: '#dee3e9'
  on-surface-variant: '#bec8d2'
  inverse-surface: '#dee3e9'
  inverse-on-surface: '#2c3135'
  outline: '#88929b'
  outline-variant: '#3e4850'
  surface-tint: '#89ceff'
  primary: '#89ceff'
  on-primary: '#00344d'
  primary-container: '#0ea5e9'
  on-primary-container: '#003751'
  inverse-primary: '#006591'
  secondary: '#93ccff'
  on-secondary: '#003351'
  secondary-container: '#3198dc'
  on-secondary-container: '#002c47'
  tertiary: '#ffb86e'
  on-tertiary: '#492900'
  tertiary-container: '#de8712'
  on-tertiary-container: '#4d2b00'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#c9e6ff'
  primary-fixed-dim: '#89ceff'
  on-primary-fixed: '#001e2f'
  on-primary-fixed-variant: '#004c6e'
  secondary-fixed: '#cce5ff'
  secondary-fixed-dim: '#93ccff'
  on-secondary-fixed: '#001d31'
  on-secondary-fixed-variant: '#004b73'
  tertiary-fixed: '#ffdcbd'
  tertiary-fixed-dim: '#ffb86e'
  on-tertiary-fixed: '#2c1600'
  on-tertiary-fixed-variant: '#693c00'
  background: '#0f1418'
  on-background: '#dee3e9'
  surface-variant: '#30353a'
  solar-amber: '#F59E0B'
  hotspot-crimson: '#EF4444'
  caution-yellow: '#FBBF24'
  nominal-emerald: '#10B981'
  inference-cyan: '#06B6D4'
typography:
  headline-xl:
    fontFamily: Geist
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Geist
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.015em
  headline-lg:
    fontFamily: Geist
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Hanken Grotesk
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.04em
  label-sm:
    fontFamily: Geist
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.06em
  metric-val:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.02em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-mobile: 0.75rem
  margin: 1.5rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system delivers an enterprise-grade AI telemetry and autonomous avionics inspection environment engineered specifically for high-throughput drone thermal diagnostics. Designed for operational commanders, field solar engineers, and computer-vision analysts, the aesthetic blends the ruthless functional precision of flight-deck instrumentation with the ergonomic refinement of modern observability dashboards.

The design movement combines technical minimalism with subtle tactical HUD (heads-up display) depth. High-contrast dark field surfaces reduce visual fatigue during prolonged monitoring cycles in command vans or control centers, while mission-critical telemetric cues cut through the interface with laser-sharp intent. The emotional signature is calm, surgical, and authoritative—eliminating aesthetic noise so that anomaly patterns, string hotspot alerts, and thermal inference streams demand immediate, unmistakable clarity.

## Colors

The palette is rooted in an abyss-toned slate matrix that anchors visual hierarchy and preserves dynamic contrast for thermal gradients and false-color raster tiles. 

- **Primary (`#0EA5E9`)**: The telemetry beacon. Applied to primary CTAs, active flight tracks, focal sensor states, and system-level focus rings.
- **Secondary (`#0284C7`)**: Tonal reinforcement for sub-navigation, docked inspector headers, and multi-selected asset groupings.
- **Thermal Status Tokens**:
  - `solar-amber` (`#F59E0B`): Irradiance shifts, elevated solar cell delta-T warnings, and tracking hardware alerts.
  - `hotspot-crimson` (`#EF4444`): Severe thermal anomalies, localized bypass diode breakdowns, and flight safety intercepts.
  - `caution-yellow` (`#FBBF24`): Moderate thermal drift, soiling suspicion, and edge-of-envelope drone battery levels.
  - `nominal-emerald` (`#10B981`): Healthy string validation, compliant string strings, and successful autonomous passes.
  - `inference-cyan` (`#06B6D4`): Active edge-AI bounding segmentations, computer vision inference confidence overlays, and telemetry stream heartbeats.

Backgrounds follow a strict surface stepping model: Base Canvas (`#0B0F17`), Elevated Panel (`#111827`), Inset Grouping (`#182234`), and Floating Modals (`#1F2E45`). Borders use low-opacity cyan-tinted slates (`rgba(14, 165, 233, 0.15)`) to delineate dense operational surfaces without visual clutter.

## Typography

Typography prioritizes high data density, tabular numeric scanning, and rapid spatial indexing under severe ambient glare. 

- **Display & Section Headers (`Geist`)**: Chosen for its engineering-grade legibility, mechanical precision, and tight letterforms. Used on operational overviews, flight metrics, and modal headers.
- **Continuous Prose & Diagnostic Logs (`Hanken Grotesk`)**: Provides an open, low-fatigue reading rhythm for descriptive flight incident summaries, model explainability logs, and dispatch tickets.
- **Labels & Micro-Indicators (`Geist`)**: Rendered in uppercase with widened tracking (`0.04em` - `0.06em`) for sensor statuses, coordinate tags, and UAV telemetry streams.
- **Numeric Figures**: All numeric instances within tabular displays, delta temperatures, and coordinates must activate OpenType tabular lining figures (`font-variant-numeric: tabular-nums`) to prevent horizontal jitter during real-time streaming updates.

## Layout & Spacing

The interface employs a dense, fluid 12-column grid system tuned for multi-window telemetry boards, video split-screens, and GIS map views.

- **Desktop (>1280px)**: 12-column fluid grid, 16px (`1rem`) gutters, and 24px (`1.5rem`) outer frame margins. Inspector panels lock to a 380px contextual side rail, leaving the central viewport fluid for real-time orthophoto mapping or orthomosaic analysis.
- **Tablet (768px - 1279px)**: 8-column layout with collapsable inspector panes that slide over the main view as contextual sheets.
- **Mobile (<768px)**: 4-column layout, 12px gutters, and 16px canvas margins. Real-time video docks to the top third of the viewport while telemetry scrolls independently below.

Padding rhythms adhere strictly to base-4 multiples (`0.25rem`, `0.5rem`, `1rem`, `1.5rem`, `2rem`). Compact component padding preserves real estate, allowing data tables to display critical fault parameters within a single viewport without vertical scroll fatigue.

## Elevation & Depth

Depth in this system avoids heavy, blurred dropshadows that dilute dark-mode visual clarity. Instead, elevation is communicated through **structural tonal stepping** paired with **hairline HUD borders**.

- **Level 0 (Canvas Base)**: Deepest surface (`#0B0F17`). Unbordered, holding base map imagery and background data grids.
- **Level 1 (Card / Grid Container)**: Layered surface (`#111827`) with a 1px ghost border (`rgba(255, 255, 255, 0.08)`).
- **Level 2 (Active Widget / Telemetry Inset)**: Raised surface (`#182234`) with a 1px border (`rgba(14, 165, 233, 0.25)`) and a subtle ambient blue glow: `0 0 16px rgba(14, 165, 233, 0.08)`.
- **Level 3 (Tactical Floating Flyouts & Modals)**: `#1F2E45` supported by a sharp 1px border (`rgba(14, 165, 233, 0.4)`) and dark occlusion: `0 12px 32px rgba(0, 0, 0, 0.6)`.

Backdrop filters (`backdrop-filter: blur(12px)`) are applied strictly to hovering drone telemetry pills and pinned map toolbars to maintain continuous visual context of the underlying thermal landscape.

## Shapes

The design uses roundedness level `1` (soft). This maintains a sharp, technical, and calibrated character suited for enterprise avionics.

- **Standard Elements (Buttons, Inputs, Metric Tiles)**: `0.25rem` (4px). Provides enough softness to avoid brittle edges while maintaining geometric discipline.
- **Containers & Data Modules (`rounded-lg`)**: `0.5rem` (8px). Encapsulates complex composite panels, thermal histograms, and flight log views.
- **Overlays & Floating Modals (`rounded-xl`)**: `0.75rem` (12px). Differentiates floating tactical dialogs and video HUD controls from the rigid underlying dashboard grid.
- **Status Indicators & Micro Tags**: Fixed pill styling is restricted entirely to binary signal badges (e.g., `RTK FIX`, `ARMED`, `LIVE`) to visually contrast them against rectangular metric cards.

## Components

### Buttons
- **Primary**: Solid background in `#0EA5E9` with deep navy text (`#08121E`), font `Geist` medium, border-radius `4px`. Hover triggers `#38BDF8`. Focus reveals a 2px offset ring in `rgba(14, 165, 233, 0.5)`.
- **Secondary / Outline**: Background in `rgba(14, 165, 233, 0.05)`, 1px border in `rgba(14, 165, 233, 0.3)`, text in `#E0F2FE`.
- **Danger / Abort**: Background in `rgba(239, 68, 68, 0.15)`, 1px border in `#EF4444`, text in `#FCA5A5`. Used for RTL (Return-to-Launch) triggers and emergency mission interrupts.

### Metric Cards & Thermal Insets
- Structured with Level 1 elevation, featuring an uppercase `label-sm` heading in `#94A3B8`, an oversized `metric-val` in `#F8FAFC`, and an inline status indicator.
- Cards tracking anomaly count display a 2px left border keyed to the severity token (`hotspot-crimson`, `solar-amber`, or `nominal-emerald`).

### Status Badges & Chips
- Compact HUD indicators (`height: 20px`, padding `2px 8px`, border-radius `4px`).
- Built with a 10% opacity tint fill of the respective status color, a 1px matching border at 30% opacity, and bright foreground text.
- Critical badges feature a pulsing 6px focal dot (`animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite`).

### Form Controls & Inputs
- Text inputs, sliders, and coordinate selectors utilize `#0E1420` backgrounds, 1px border `rgba(255, 255, 255, 0.12)`, text `#F1F5F9`, and `4px` corner radii.
- Focus state shifts border color to `#0EA5E9` with a zero-offset box-shadow of `0 0 0 1px #0EA5E9`.

### Checkboxes & Segment Switches
- Compact square profiles (`16x16px`, `2px` corner radius). Checked states display `#0EA5E9` fill with deep navy check glyphs.
- Multi-state mode selectors (Manual, AI-Guided, Fully Autonomous) use dense segmented button bars enclosed in a Level 1 container.

### Thermal Anomaly Overlays (Platform-Specific)
- Bounding inference boxes overlaying thermal feeds feature high-contrast `06B6D4` hairline borders (`1.5px`) with corner targeting ticks.
- Hotspot temperature callouts sit in a micro-pill pinned directly above the bounding geometry with tabular max/min delta-T values.