# Renderer Coverage Report

Date: 2026-06-07

Scope: `TemplateDefinition` DSL support in the current ReportLab renderer at `backend/app/services/dynamic_template_renderer.py`.

## Summary

The current renderer is a Platypus story-flow renderer. It can render basic document content well, but it does not yet consume the full visual blueprint Gemini extracts from uploaded PDFs.

Current practical coverage is about 45-55% of the DSL, depending on the uploaded template. It is strongest for typography, sections, simple cards, simple columns, dividers, and basic field mapping. It is weakest for page-level layout features: `layout_regions`, sidebars, full-page backgrounds, fixed headers, fixed footers, and positioned content.

Target: reach at least 80% renderer coverage before introducing a completely new renderer architecture.

Recommended path: keep the current renderer, but extend it with a small region-aware layer using ReportLab `Frame`s and canvas callbacks. This gives most of the benefit without a full rewrite.

## Coverage Matrix

| DSL feature | Status | Current behavior | Effort | Platypus feasible? | Needs canvas/Frame renderer? |
|---|---|---|---:|---|---|
| `schema_version` | SUPPORTED | Validated by schema; not used by renderer. | XS | Yes | No |
| `name` | SUPPORTED | Stored/logged; not visual. | XS | Yes | No |
| `description` | SUPPORTED | Stored/logged; not visual. | XS | Yes | No |
| `page_size` | SUPPORTED | Uses `letter` or `a4`. | XS | Yes | No |
| `margins` | SUPPORTED | Applied to `SimpleDocTemplate`. | XS | Yes | No |
| `colors` | PARTIALLY_SUPPORTED | Captured in DSL but only indirectly used if referenced by typography/blocks. No global palette resolution. | S | Yes | No |
| `typography` | SUPPORTED | Builds `title`, `heading`, `body`, `bullet`, `small` paragraph styles. | XS | Yes | No |
| `style_definitions` | PARTIALLY_SUPPORTED | Text-style definitions can now be resolved from string block styles. Non-text layout styles are mostly ignored. | M | Yes | No |
| `section_styles` | UNSUPPORTED | Not consumed when rendering sections. | M | Yes | No |
| `spacing` | PARTIALLY_SUPPORTED | Some hardcoded spacers exist. DSL spacing values like `section_gap` and `card_padding` are not consistently applied. | S | Yes | No |
| `layout_regions` | UNSUPPORTED | Defined in schema but ignored by renderer. | L | Partly | Yes |
| `background` | UNSUPPORTED | Page background is not painted. | S | No | Yes |
| page backgrounds | UNSUPPORTED | No full-page canvas fill or region background painting. | S | No | Yes |
| `header` | PARTIALLY_SUPPORTED | Header blocks are rendered at the top of the story, not as a fixed page header. | M | Partly | Yes for fixed headers |
| `footer` | PARTIALLY_SUPPORTED | Draws a hardcoded page-number footer; ignores most footer blocks/styles. | M | Partly | Yes for fixed footer zones |
| `sections` | PARTIALLY_SUPPORTED | Main source of rendered content, but layout/style fidelity depends on supported block types. | M | Yes | No |
| `section_order` | SUPPORTED | Adds missing section blocks in order. | XS | Yes | No |
| `metadata` | PARTIALLY_SUPPORTED | Used for diagnostics and field data; visual metadata is not consumed. | S | Yes | No |

## Block Coverage

| Block type / property | Status | Current behavior | Effort | Platypus feasible? | Needs canvas/Frame renderer? |
|---|---|---|---:|---|---|
| `field` | SUPPORTED | Renders runtime JD field value. | XS | Yes | No |
| `paragraph` | PARTIALLY_SUPPORTED | Renders static text; may be suppressed during sanitization to avoid copied PDF body content. | XS | Yes | No |
| `section` | PARTIALLY_SUPPORTED | Renders heading plus field content. Styling is now partly resolvable. Does not apply `section_styles`. | S | Yes | No |
| `bullet_list` | PARTIALLY_SUPPORTED | Renders field lists as bullets. Bullet glyph/indent/style mostly hardcoded. | S | Yes | No |
| `table` | PARTIALLY_SUPPORTED | Renders a simple 2-column metadata table. Ignores `column_widths`, `text_color`, zebra rows, and richer row definitions. | M | Yes | No |
| `columns` | PARTIALLY_SUPPORTED | Renders nested blocks in a ReportLab table. Good for simple columns, weak for complex grids. | M | Yes | Frame optional |
| `container` | PARTIALLY_SUPPORTED | Rendered as a single-cell table with background/border/padding. | S | Yes | No |
| `card` | PARTIALLY_SUPPORTED | Same implementation as container. Radius is ignored. | S | Yes | No |
| `banner` | PARTIALLY_SUPPORTED | Same implementation as container; does not span full page/region unless placed in flow width. | M | Partly | Canvas/Frame for page-spanning banners |
| `sidebar` | PARTIALLY_SUPPORTED | Rendered like an inline container, not a fixed page sidebar. | L | Partly | Yes for real sidebars |
| `divider` | SUPPORTED | Renders a horizontal line with width/color/spacing. | XS | Yes | No |
| `spacer` | SUPPORTED | Renders vertical space. | XS | Yes | No |
| `logo` | PARTIALLY_SUPPORTED | Renders hardcoded Wissen logo/table; does not use uploaded template logo placement. | M | Yes | Canvas/Frame if fixed |
| `page_number` | PARTIALLY_SUPPORTED | Recognized in footer only; style/position mostly hardcoded. | S | Partly | Yes for precise footer |
| nested `blocks` | PARTIALLY_SUPPORTED | Works for containers/cards/banners/sidebars and recursive rendering. | S | Yes | No |
| `columns.widths` | PARTIALLY_SUPPORTED | Honored when widths count matches columns. | XS | Yes | No |
| `style` inline object | SUPPORTED | Converts to `ParagraphStyle`. | XS | Yes | No |
| `style` string reference | PARTIALLY_SUPPORTED | Resolved for text styles from `style_definitions`. Layout style refs need more work. | M | Yes | No |
| `style_ref` property | UNSUPPORTED | Schema has the field but renderer does not use it. | S | Yes | No |
| `box.background_color` | SUPPORTED | Applied to containers/cards/banners/sidebar wrappers. | XS | Yes | No |
| `box.border_color` | SUPPORTED | Applied to container wrapper border. | XS | Yes | No |
| `box.border_width` | SUPPORTED | Applied to container wrapper border. | XS | Yes | No |
| `box.radius` | UNSUPPORTED | ReportLab table wrapper does not render rounded corners. | M | No | Yes |
| `box.padding` | SUPPORTED | Applied to wrapper padding. | XS | Yes | No |
| directional padding | SUPPORTED | Applied when present. | XS | Yes | No |
| `background_color` on block | PARTIALLY_SUPPORTED | Used for container-like wrappers; ignored on many text-only blocks. | S | Yes | No |
| `name` / `role` on block | UNSUPPORTED | Stored but not used by renderer. | S | Yes | No |

## Style Model Coverage

| Style feature | Status | Current behavior | Effort | Platypus feasible? | Needs canvas/Frame renderer? |
|---|---|---|---:|---|---|
| `TextStyle.font_name` | SUPPORTED | Applied to `ParagraphStyle`. | XS | Yes | No |
| `TextStyle.font_size` | SUPPORTED | Applied. | XS | Yes | No |
| `TextStyle.leading` | SUPPORTED | Applied; defaults to `font_size + 3`. | XS | Yes | No |
| `TextStyle.color` | SUPPORTED | Applied. | XS | Yes | No |
| `TextStyle.alignment` | SUPPORTED | Applied to paragraph style. | XS | Yes | No |
| `TextStyle.space_before` | SUPPORTED | Applied. | XS | Yes | No |
| `TextStyle.space_after` | SUPPORTED | Applied. | XS | Yes | No |
| `TextStyle.uppercase` | PARTIALLY_SUPPORTED | Applied for section headings; not all paragraphs/fields. | S | Yes | No |
| `DividerStyle` | SUPPORTED | Color, width, before/after spacing are used. | XS | Yes | No |
| `TableStyleDef.header_background` | SUPPORTED | Used for left label column background. | XS | Yes | No |
| `TableStyleDef.border_color` | SUPPORTED | Used for grid border. | XS | Yes | No |
| `TableStyleDef.text_color` | UNSUPPORTED | Not applied to table cell text. | S | Yes | No |
| `TableStyleDef.cell_padding` | SUPPORTED | Applied. | XS | Yes | No |
| `TableStyleDef.zebra_rows` | UNSUPPORTED | Not implemented. | S | Yes | No |
| `TableStyleDef.column_widths` | UNSUPPORTED | Table uses hardcoded 32/68 widths. | S | Yes | No |

## Highest-Impact Unsupported Features

### 1. `layout_regions`

Status: UNSUPPORTED

Effort: L

Can be done in existing Platypus renderer: partly.

Requires canvas/Frame renderer: yes, for realistic sidebars and fixed page regions.

Recommendation: introduce a region planning layer:

- Convert `layout_regions` into named page zones.
- Use ReportLab `Frame`s for `left sidebar`, `right sidebar`, `main`, `top hero`, `metadata`, and `footer` regions.
- Keep existing `render_blocks()` to produce flowables inside each region.

This is an extension, not a full rewrite.

### 2. Page backgrounds and region backgrounds

Status: UNSUPPORTED

Effort: S-M

Can be done in existing Platypus renderer: no, not as real page background.

Requires canvas/Frame renderer: yes.

Recommendation:

- Add `draw_page_background(canvas, doc, definition)`.
- Paint `definition.background.color`.
- Paint `layout_regions` with `position=full_page`, `sidebar`, `header`, `footer`, etc.

### 3. Real sidebars

Status: PARTIALLY_SUPPORTED as inline containers, UNSUPPORTED as page-level sidebars.

Effort: L

Can be done in existing Platypus renderer: only as a table approximation.

Requires canvas/Frame renderer: yes for full-height sidebars.

Recommendation:

- Use a fixed sidebar `Frame`.
- Main content flows in a separate `Frame`.
- Sidebar background is drawn on canvas for each page.

### 4. Fixed headers and footers

Status: PARTIALLY_SUPPORTED

Effort: M

Can be done in existing Platypus renderer: partly.

Requires canvas/Frame renderer: yes for fixed, styled zones.

Recommendation:

- Stop rendering header as first story content.
- Draw header/footer regions in `onFirstPage` / `onLaterPages`.
- Render header/footer blocks into fixed frames where possible.

### 5. `section_styles`

Status: UNSUPPORTED

Effort: M

Can be done in existing Platypus renderer: yes.

Requires canvas/Frame renderer: no.

Recommendation:

- When rendering a `section` block, look up `definition.section_styles[field]`.
- Apply container/card/divider options around that section.
- This should be one of the first improvements because it directly improves visual variety.

### 6. Layout style references

Status: PARTIALLY_SUPPORTED

Effort: M

Can be done in existing Platypus renderer: yes.

Requires canvas/Frame renderer: no.

Recommendation:

- Support `style_ref` as an alias to `style` string refs.
- Split `style_definitions` into text style properties and box/table/layout properties.
- Apply box/table/layout style definitions to wrappers, not only text.

## 80% Coverage Plan

### Phase 1: Maximize current Platypus renderer

Estimated coverage after phase: 65-70%.

Implement:

- `section_styles` rendering for cards/dividers/containers.
- global `spacing` values: `section_gap`, `card_padding`, `paragraph_gap`, `column_gap`.
- `style_ref` support.
- layout-style resolution from `style_definitions`.
- table `column_widths`, `text_color`, and `zebra_rows`.
- `TextStyle.uppercase` for paragraphs/fields, not just section headings.
- better `banner` rendering inside story flow.
- remove silent corporate fallback or log it more loudly with `CUSTOM_TEMPLATE_RENDER_FALLBACK`.

These are all feasible inside the existing Platypus story renderer.

### Phase 2: Add canvas background callbacks

Estimated coverage after phase: 72-78%.

Implement:

- page background color.
- header/footer background bands.
- full-width hero/background bands when declared.
- repeated page sidebar background painting without sidebar content flow.
- rounded card drawing only where necessary.

This still keeps the current renderer, but uses canvas callbacks for page-level painting.

### Phase 3: Add Frame-based region rendering

Estimated coverage after phase: 80-88%.

Implement:

- `layout_regions` page planner.
- sidebar `Frame` plus main-content `Frame`.
- top/header/hero `Frame`.
- footer `Frame`.
- map `layout_regions.blocks` into their frames.
- keep existing `render_blocks()` as the flowable generator inside each frame.

This is the minimum architecture extension needed for faithful uploaded-template rendering. It is not a complete renderer rewrite.

## Features That Probably Need a New Renderer Later

These can be approximated in ReportLab, but may become painful if exact visual matching is required:

- arbitrary absolute positioning for every block.
- overlapping elements.
- complex multi-page content flowing around fixed sidebars.
- exact reproduction of imported PDF coordinates.
- rounded/clipped/transparent shapes at scale.
- image-heavy layouts with precise crop modes.

If Gemini starts emitting coordinate-level layout data, a dedicated canvas/Frame renderer or HTML/CSS-to-PDF renderer will eventually be cleaner.

## Recommendation

Do not replace the renderer yet.

First, raise coverage with targeted improvements:

1. Add `section_styles`, `spacing`, `style_ref`, table styling, and layout style refs.
2. Add canvas page background/header/footer/sidebar painting.
3. Add `layout_regions` via ReportLab `Frame`s.

That should get the current system above the 80% target while preserving the existing pipeline:

PDF -> PNG -> Gemini Vision -> Blueprint DSL -> Validation -> Store in DB -> Dynamic renderer.
