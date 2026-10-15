---
name: AeroSolar Light Clean
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#3f4850'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#707881'
  outline-variant: '#bfc7d2'
  surface-tint: '#006398'
  primary: '#006194'
  on-primary: '#ffffff'
  primary-container: '#007bb9'
  on-primary-container: '#fdfcff'
  inverse-primary: '#93ccff'
  secondary: '#006c4a'
  on-secondary: '#ffffff'
  secondary-container: '#82f5c1'
  on-secondary-container: '#00714e'
  tertiary: '#8d4b00'
  on-tertiary: '#ffffff'
  tertiary-container: '#b15f00'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#cce5ff'
  primary-fixed-dim: '#93ccff'
  on-primary-fixed: '#001d31'
  on-primary-fixed-variant: '#004b73'
  secondary-fixed: '#85f8c4'
  secondary-fixed-dim: '#68dba9'
  on-secondary-fixed: '#002114'
  on-secondary-fixed-variant: '#005137'
  tertiary-fixed: '#ffdcc3'
  tertiary-fixed-dim: '#ffb77d'
  on-tertiary-fixed: '#2f1500'
  on-tertiary-fixed-variant: '#6e3900'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  title-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
  metric-num:
    fontFamily: Inter
    fontSize: 22px
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
  space-2xs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
  space-2xl: 2rem
---

## Brand & Style

This design system delivers an enterprise-grade utility aesthetic structured specifically for high-density solar operations and maintenance (O&M) platforms. The operational mandate demands immediate cognitive parsing across thousands of photovoltaic (PV) strings, inverters, and battery storage subsystems. The brand personality conveys absolute reliability, systematic precision, and calm technical authority. 

Rooted in modern corporate minimalism and utilitarian engineering aesthetics, the visual interface avoids superfluous ornamentation. It privileges tabular clarity, crisp data boundaries, and instant chromatic alerts. The interface feels clean, expansive, and dependable under demanding operational conditions, giving dispatchers, field engineers, and asset managers zero-latency situational awareness across distributed clean energy plants.

## Colors

The color system establishes a pristine light-mode canvas paired with high-contrast functional status indicators:

- **Primary (`#0284c7`)**: Technical sky blue representing nominal operations, interactive navigational states, focused telemetry streams, and telemetry controls.
- **Secondary (`#059669`)**: Emerald green signaling positive energy yield, normal inverter grid tie, active performance ratio (PR), and healthy field telemetry.
- **Tertiary (`#d97706`)**: Amber warning state allocated for soiling index notices, clipping anomalies, grid curtailment, and non-critical hardware warnings.
- **Neutral (`#64748b`)**: Cool slate supporting auxiliary metrics, chart grids, structural divisions, and tertiary labels.

### Extended Palette & Background Tokens
- **Canvas Base**: `#f8fafc` provides ambient contrast behind active data panes.
- **Card/Surface Base**: Pure `#ffffff` for elevated data cards, metric displays, and data grid row surfaces.
- **Sub-surface / Inset**: `#f1f5f9` for table headers, embedded sensor trays, and toolbars.
- **Borders & Dividers**: Crisp structural lines using `#e2e8f0` for component containers and `#cbd5e1` for active or focused boundaries.
- **Text Hierarchy**: Deep slate `#0f172a` for critical values and primary headers, mid-slate `#334155` for body labels and field IDs, and slate `#64748b` for measurement units and metadata.
- **Critical Alert / Hotspot**: Rose-600 (`#e11d48`) exclusively reserved for string faults, thermal runaway, critical inverter trips, and safety violations.

## Typography

The typography system relies on the neutral, highly systematic structure of Inter. Designed for legibility at dense data thresholds, it provides balanced geometric rhythm, clear numeric figures, and distinct glyph differentiation required for engineering notations (e.g., kW, MWh, VDC, W/m²).

Tabular numbers (`font-variant-numeric: tabular-nums`) must be enforced across all telemetry feeds, real-time power readings, and data tables to prevent layout jitter during data updates. Micro labels and technical badges leverage uppercase treatment with `+0.04em` tracking to guarantee readability at scale.

## Layout & Spacing

This design system uses a 12-column fluid grid system paired with strict 4px/8px incremental spacing models to maximize screen utilization without visual crowding.

- **Desktop (1280px+)**: 12 columns, 16px gutter, 24px outer margin. Supports multi-pane telemetry layouts, side-by-side array heatmaps, and dense SCADA tables.
- **Tablet (768px - 1279px)**: 8 columns, 16px gutter, 20px outer margin. Telemetry toolbars collapse into segmented views; charts switch to single-column stacking.
- **Mobile (< 768px)**: 4 columns, 12px gutter, 16px outer margin. Layout reflows strictly vertically, swapping data grids for condensed sensor cards.
- **Internal Density**: Dense metric cards maintain an 8px (`space-sm`) internal separation, while structural sections preserve 16px (`space-lg`) to 24px (`space-xl`) margins.

## Elevation & Depth

Visual hierarchy is primarily driven through crisp container boundaries (`#e2e8f0`) supplemented by subtle, diffuse elevation layers. High elevation and heavy shadows are intentionally avoided to ensure telemetry dashboards do not suffer from optical weight or glare under high-brightness industrial monitors.

- **Level 0 (Flat Canvas)**: `#f8fafc` background with no shadow.
- **Level 1 (Card & Module Surface)**: Pure `#ffffff` surface, bounded by a 1px border (`#e2e8f0`), accompanied by an ultra-subtle ambient drop shadow: `0 1px 3px 0 rgba(15, 23, 42, 0.05), 0 1px 2px -1px rgba(15, 23, 42, 0.05)`.
- **Level 2 (Hover / Active Cards)**: Scaled border tint to `#cbd5e1` with `0 4px 6px -1px rgba(15, 23, 42, 0.07), 0 2px 4px -2px rgba(15, 23, 42, 0.05)`.
- **Level 3 (Dropdowns, Overlays & Diagnostics Panels)**: Crisp border (`#cbd5e1`) with `0 10px 15px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.04)`.

## Shapes

The design system maintains a structured, low-radii shape profile (`roundedness: 1`) communicating engineered reliability and geometric order. 

- **Base Radius (0.25rem / 4px)**: Applied to input controls, status pills, table selection cells, and button primitives.
- **Medium Radius (0.5rem / 8px)**: Reserved for primary data cards, analytical graph containers, and modal dialogs.
- **Large Radius (0.75rem / 12px)**: Used strictly for outer dashboard framing panels or flyout operational sidebars.
- **Circular (9999px)**: Reserved exclusively for small live sensor status pings and user profile initials.

## Components

### Buttons
- **Primary**: Background `#0284c7`, text `#ffffff`, border none, 4px border radius. Hover: `#0369a1`. Active: `#075985`. Focus ring: 2px offset with `#0284c7`.
- **Secondary / Outline**: Background `#ffffff`, text `#334155`, 1px solid `#e2e8f0` border. Hover: `#f8fafc`, text `#0f172a`, border `#cbd5e1`.
- **Destructive**: Background `#ffffff`, text `#e11d48`, 1px solid `#fecdd3`. Hover: `#fff1f2`.

### Chips & Status Badges
- **Normal / Healthy**: Emerald background `#ecfdf5`, text `#065f46`, border 1px solid `#a7f3d0`. Contains 6px green indicator dot.
- **Warning / Degraded**: Amber background `#fffbeb`, text `#92400e`, border 1px solid `#fde68a`.
- **Critical / Hotspot Alert**: Rose background `#fff1f2`, text `#9f1239`, border 1px solid `#fecdd3`.
- **Informational / Tracking**: Sky background `#f0f9ff`, text `#075985`, border 1px solid `#bae6fd`.

### Lists & Data Tables
- Row height fixed at 40px for compact views, 48px for standard views.
- Table header: `#f1f5f9` background, `#64748b` uppercase `label-sm` typography, bottom border 1px solid `#cbd5e1`.
- Alternating rows avoid heavy zebra striping; instead, rows maintain `#ffffff` surfaces separated by 1px `#f1f5f9` dividers, highlighting with `#f8fafc` on hover.

### Inputs, Checkboxes & Radio Buttons
- Text inputs: Height 36px, `#ffffff` surface, 1px solid `#cbd5e1`, 4px border radius, `#0f172a` text. Placeholder in `#94a3b8`. Focus state shifts border to `#0284c7` with a 1px outline.
- Checkboxes & Radios: 16px square/circle, border 1.5px solid `#cbd5e1`. Checked state fills `#0284c7` with crisp `#ffffff` glyphs.

### Cards & Telemetry Modules
- Base structure: Pure white `#ffffff` canvas, 1px solid border `#e2e8f0`, 8px border radius, soft Level 1 elevation.
- Internal headers include a distinct bottom border (`#f1f5f9`), hosting metric title left-aligned and live badge or refresh timestamp right-aligned.

### Domain-Specific Components
- **Hotspot Alert Callout**: Inset card featuring a left 4px solid border of `#e11d48`, soft rose tint (`#fff1f2`), displaying string ID, module coordinate, and delta temperature (ΔT).
- **String Inverter Gauge**: Compact horizontal bar widget using secondary emerald (`#059669`) for rated capacity and tertiary amber (`#d97706`) for clipping loss.