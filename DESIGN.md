---
name: "Dürer's Hoard"
description: "Visual system of the local vector illustration workspace."
colors:
  green: "#566d48"
  green-dark: "#3e5235"
  sage: "#e8eee4"
  ink: "#24261f"
  muted: "#797b71"
  paper: "#f7f7f2"
  panel: "#fff"
  line: "#e7e8df"
  focus: "#8aa27d"
typography:
  display:
    fontFamily: "'Playfair Display', Georgia, serif"
    fontSize: "clamp(42px, 6vw, 68px)"
    fontWeight: 500
    lineHeight: 1.06
    letterSpacing: "-.04em"
  title:
    fontFamily: "'Playfair Display', Georgia, serif"
    fontSize: "30px"
    fontWeight: 500
  section:
    fontFamily: "'Playfair Display', Georgia, serif"
    fontSize: "28px"
    fontWeight: 500
  card:
    fontFamily: "'Playfair Display', Georgia, serif"
    fontSize: "16px"
    fontWeight: 500
  body:
    fontFamily: "'DM Sans', Arial, sans-serif"
    fontSize: "14px"
  button:
    fontFamily: "'DM Sans', Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 600
  tab:
    fontFamily: "'DM Sans', Arial, sans-serif"
    fontSize: "10px"
  native:
    fontFamily: "Consolas, monospace"
    fontSize: "10px"
    lineHeight: 1.5
rounded:
  compact: "5px"
  field: "7px"
  control: "8px"
  button: "9px"
  panel: "10px"
  card: "12px"
spacing:
  tight: "7px"
  compact: "8px"
  control-gap: "10px"
  panel-gap: "12px"
  inset: "15px"
  content: "16px"
  mobile-page: "20px"
  canvas: "34px"
components:
  button-primary:
    backgroundColor: "{colors.green}"
    textColor: "{colors.panel}"
    typography: "{typography.button}"
    rounded: "{rounded.button}"
    padding: "10px 15px"
  button-primary-hover:
    backgroundColor: "{colors.green-dark}"
  button-secondary:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.button}"
    padding: "10px 15px"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.button}"
    rounded: "{rounded.button}"
    padding: "10px 15px"
  input-catalog:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "9px 11px"
  navigation-tab:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.tab}"
    padding: "13px 8px"
  navigation-tab-active:
    textColor: "{colors.green-dark}"
  panel:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.panel}"
  project-card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.card}"
  tool-selected:
    backgroundColor: "{colors.sage}"
    textColor: "{colors.green-dark}"
    rounded: "{rounded.field}"
  object-row:
    backgroundColor: "#f8f9f5"
    textColor: "#5e6258"
    rounded: "{rounded.compact}"
    padding: "8px"
  object-row-selected:
    backgroundColor: "{colors.sage}"
    textColor: "{colors.green-dark}"
---

# Design System: Dürer's Hoard

## Overview

**Creative North Star: "The vector atelier"**

The implemented workshop places an editable illustration at the centre of a quiet, pale workspace. Serif project titles and the existing family icon identify the Hoard; compact sans-serif controls carry the daily editing work. This records the incumbent identity, rather than proposing a replacement visual world.

White panels sit on an ivory page, with sage selection states and muted green actions. The browser editor arranges tools, preview and object inspection around the work. Native command names and editable arguments use monospace where their literal content matters.

**Key Characteristics:**

- Serif titles paired with compact sans-serif controls.
- Ivory page, white panels and muted green actions.
- Visible tool rail, preview and object inspector.
- Existing family icon preserved as the identity asset.
- Responsive reflow of controls and panels.

Scope of evidence: the source is `durer_hoard/static/index.html`, `app.js` and `style.css`. The valid captures are `.impeccable/review/desktop-top.png` and `desktop-bottom.png` (1280 × 720, normal scroll) and `mobile.png` (375 × 1260). The older `desktop.png` and `desktop-r2.png` full-page captures are defective and excluded. The reported finish Pass covers only the truthful owned-engine description in PRODUCT.md and visible mobile actions; it is not a certification of every screen, state, capability or accessibility property. The detector used a degraded regex pass; this record makes no measured contrast claim.

## Colors

The palette combines a pale neutral workspace with one muted green action and selection family. The normative values are in the frontmatter.

### Primary

- **Atelier Green** (`green`): primary buttons, identity details and project references.
- **Deep Atelier Green** (`green-dark`): primary hover, active tabs and selected controls.
- **Sage Wash** (`sage`): tool hover/selection and selected object rows.
- **Focus Sage** (`focus`): visible keyboard outlines on buttons and form controls.

### Neutral

- **Warm Ink** (`ink`): body text and control text.
- **Quiet Grey** (`muted`): secondary metadata, navigation and supporting text.
- **Ivory Paper** (`paper`): the page behind the editing surfaces.
- **Panel White** (`panel`): buttons, inspectors, project cards and the artboard.
- **Paper Edge** (`line`): panel boundaries, dividers and field borders.

**The Green State Rule.** Use the existing green family to distinguish primary action, hover and selection; keep artwork colours independent of interface states.

The canvas checkerboard is an implemented transparency cue, not a new accent palette. Engine status uses amber, green and red dots in source; these contextual indicators are not general theme colours.

## Typography

**Display Font:** Playfair Display, with Georgia and serif fallbacks.
**Body Font:** DM Sans, with Arial and sans-serif fallbacks.
**Native Font:** Consolas, with a monospace fallback.

The serif names projects and sections while the sans-serif keeps controls consistent. Monospace marks object rows, native command names, arguments and schemas. Font families are requested from Google Fonts; the fallback stacks remain part of the source.

### Hierarchy

- **Display**: the welcome heading uses the frontmatter's fluid display role; on small screens it becomes a fixed heading (46px).
- **Title**: the workspace project heading uses the title role; on small screens it reduces (25px).
- **Section**: library and modal headings use the section role.
- **Card**: project names use the card role; the brand name is a smaller, heavier serif (15px, 600).
- **Body**: page text uses the body role. Welcome supporting copy has a loose line height (1.7) and a bounded width (420px); mobile reduces it (13px).
- **Button / Tab**: actions and tabs use their frontmatter roles. Object and native argument text uses the native role.

**The Title and Control Rule.** Keep serif type for naming the work and sans-serif type for operating it; keep literal native content in monospace.

Small uppercase labels and widely tracked eyebrows are present in the build. They are recorded as incumbent details, not promoted into reusable typography roles. This inventory does not establish the legibility of every small secondary label.

## Layout

The desktop header is a white strip (70px) with the identity at one end and engine state/language control at the other. Welcome and library sections share a bounded content width (1200px) and side inset (34px). The library grid uses three columns with a narrow gap (17px).

The editor has a broader container (1460px maximum, 25px side inset) and a three-column working grid: tool rail (92px), flexible canvas (minimum 320px), inspector (280px), separated by panel gaps (12px). Its minimum grid height (590px) keeps the rail, canvas and inspector visually aligned. The canvas stage has an initial minimum height (440px) and a generous inset (34px). The artboard has a bounded width (720px maximum) and a desktop aspect-ratio declaration (4:3); the preview image contains the artwork rather than cropping it. These are presentation dimensions, not document dimensions.

At the medium breakpoint (maximum width 1000px), the tool rail narrows (72px), the canvas minimum narrows (260px), the inspector moves below across both columns and uses a two-column interior, and the library becomes two columns.

At the small breakpoint (maximum width 640px), the header shortens (60px), the editor page inset tightens (10px), the project heading and action group stack, the rail narrows (54px), and the inspector becomes a single block below the canvas. The editor gap tightens (7px), the canvas stage minimum reduces (350px) with a smaller inset (17px), and the artboard's aspect-ratio declaration becomes square (1:1). The library becomes one column.

**The Visible Actions Rule.** At the small breakpoint, wrap the workspace actions so desktop opening, project download, undo, redo, format selection and export remain visible. The supplied 375px capture shows them in two rows; the exact wrapping follows available width and translated text.

The small header hides the engine status text through its font size while retaining the dot. The source contains a medium/small rule that hides non-first spans inside action buttons; existing open/download labels remain because each is its first span. These are observed implementation details, not a general permission to hide actions.

## Elevation & Depth

Thin borders and pale surfaces provide the default separation. Hovered project cards lift slightly and receive the shared diffuse shadow (`0 14px 38px #25271d0b`). The artboard carries its own soft shadow (`0 8px 32px #23251e18`) against the checkerboard. Modal cards use a deeper overlay shadow (`0 24px 80px #1d201b33`) over a translucent scrim.

**The Surface Separation Rule.** Use borders for panels at rest, the shared hover shadow for project cards, and the existing artboard/modal depth treatments in their own contexts.

Buttons transition over a short interval (.15s) and move slightly on hover (−1px); project cards transition (.18s) and move on hover (−3px). Toasts fade and rise (.2s) and remain briefly visible (2500ms). No reduced-motion override is present in this stylesheet; this documentation does not assert one.

## Shapes

The system uses gently rounded rectangular controls and panels, with the radius roles in the frontmatter. Compact numeric fields and object rows use the smallest corners; buttons, panels and project cards increase the radius by role. Borders are generally thin (1px), while active tabs use a coloured bottom edge (2px). The artboard remains a plain rectangle.

**The Role Corner Rule.** Preserve the existing radius by component role rather than assigning one corner size to every surface.

The brand uses the existing raster family icon at `/static/icon.png`, sized by its identity container (36px with 10px corners). It is an asset constraint, not a request to replace the icon with a letter, glyph or newly drawn mark.

## Components

### Buttons

Primary actions are filled green with white text; secondary actions are white with a pale border; quiet actions use muted text on a transparent background. Shared padding, type and corners are in the frontmatter. Workspace actions use a slightly tighter local padding (9px 11px). Hover changes the border and gives a small lift; primary hover deepens the green. Keyboard focus uses the shared sage outline (2px, 2px offset).

Standalone run/close controls are compact squares (32px) with field-style corners. Their existing glyphs are not a new icon vocabulary.

### Inputs / Fields

Catalog search and native argument fields use thin pale borders and softly rounded corners. Arguments and schemas are monospace; the native arguments textarea can resize vertically and starts at a compact height (94px). Paint and transform fields remain in the inspector. Disabled paint fields are visibly faded (opacity .62) and retain an explanatory field-state line when the engine does not report an editable value.

The creation modal groups project name, width, height and document units. Transform controls group Move X, Move Y, Scale % and Rotation ° in two columns. The scale field displays and sends a percentage, with a default value (100); do not describe it as a fractional scale.

### Navigation

The brand link and back link return to the illustration library. Inspector and catalog tabs use a bottom border for the active item, with deeper green text. Their active state remains visible after the inspector reflows below the canvas.

### Cards / Containers

Panels are white bordered containers. Project cards combine a contained preview thumbnail, serif project name and muted timestamp. The thumbnail area changes height on small screens (180px to 210px). Card hover is described under Elevation & Depth. No chip/tag component is implemented in these sources.

### Tool Rail and Object List

Tools are vertically arranged with a label under each existing glyph. Sage backgrounds indicate hover and the active tool. Selecting an object row marks it with the same sage state and opens the Properties tab. The object list has a bounded scroll area (265px maximum) and indentation for nested items.

**The Shared Selection Rule.** Use the same sage/deep-green treatment for selected tools and selected object rows, while retaining the active-tab underline.

### Preview and Native Controls

The canvas toolbar holds zoom controls and preview refresh; status text sits below the canvas. Zoom is a presentation transform with a range (50–200%) and steps (10%). The preview image explicitly disables browser image dragging. Shape dragging uses pointer events on the artboard, not dragging the preview image; the JavaScript maps pointer coordinates to document geometry.

The Objects pane exposes a native tool selector, Run control and JSON arguments. The catalog dialog provides tool/command tabs, search and literal schemas. Desktop editor opening and native project download are separate actions, and the project metadata identifies the owned document as `.durer`. These controls describe the implemented workflow; they do not establish universal native feature coverage.

## Do's and Don'ts

### Do:

- **Do** preserve the existing family icon, serif titles and sans-serif controls.
- **Do** use sage selection states consistently across tools and object rows.
- **Do** keep workspace actions visible through wrapping at the small breakpoint.
- **Do** keep native names, object details and arguments literal and readable in their existing contexts.
- **Do** distinguish presentation zoom from document scale percentages.

### Don't:

- **Don't** replace the incumbent visual identity while extending the editor.
- **Don't** hide desktop opening, project download, undo, redo, format selection or export to simplify mobile.
- **Don't** turn existing glyph icons or tracked uppercase labels into a required pattern for new surfaces.
- **Don't** infer measured contrast, complete accessibility or native feature parity from this record.

