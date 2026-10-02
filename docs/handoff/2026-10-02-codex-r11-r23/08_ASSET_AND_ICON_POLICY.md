# ASSET / ICON POLICY

1. Inspect `frontend/icons/`, `icon-set.json`, `slots.json`, icon registry and branding service before adding assets.
2. Reuse existing semantic assets where suitable.
3. Define one semantic key per action/menu.
4. Do not bind business code directly to arbitrary image filenames when registry abstraction exists.
5. Preserve brand aspect ratio.
6. No raster stretch/crop for logos. Prefer contain behavior.
7. Main navigation: icon + label.
8. Compact action icon-only: tooltip + accessible label required.
9. No emoji as production icon.
10. Missing asset must degrade predictably; never show broken-image glyph.
