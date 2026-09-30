# figg. / creative studio

**An original, static, offline-friendly brand studio for figg.** Open `index.html` in any modern browser. No account, build system, external service, or runtime dependency is required. The typography prefers locally installed Inter and falls back to system sans-serif; **no font files are included**.

## Inside

- **Beautiful working studio:** a responsive editorial site with an interactive mascot picker, three preview backdrops, a 32-character gallery, brand tokens, campaign mockups, and the original creative archive.
- **32 original vector mascots:** `/assets/mascots/svg/` (editable scalable SVG) and `/assets/mascots/png/` (1024 × 1024 transparent PNG).
- **Reusable identity:** `/assets/logos/` includes the black lowercase `figg.` purple-dot wordmark in editable SVG, a font-independent outlined version for exact printing, white/monochrome alternatives, mascot mark, silhouette, favicon, and a transparent shop avatar.
- **Campaign building blocks:** `/assets/templates/` includes social square, A6 thank-you card, round packaging sticker, a white-background Etsy hero guide, before/after, and a four-step listing process. All are SVG. The social template is self-contained.
- **Repeat pattern:** `/assets/patterns/` includes vector and raster tile versions for draft tissue or wrapping-paper designs.
- **Design handoff:** `/assets/design-tokens.json`, `/assets/design-tokens.css`, `/assets/mascot-manifest.json`, `/assets/previews/32-mascot-asset-sheet.png`.
- **Creative archive:** `/assets/reference/full/` contains the four original concept boards, with resized gallery images under `/assets/reference/thumbs/`.
- **One-click kit:** `/downloads/figg-asset-kit.zip` contains the portable identity/assets collection. Download from the studio navigation or the studio's download bar.

## Start

1. Unzip `figg-studio.zip` and open `figg-studio/index.html`. A local server is optional; if one is desired, run `python3 -m http.server 8000` in this folder and open `http://localhost:8000`.
2. Open **Mascot studio** and select any character. Choose **warm white**, **soft lilac**, or **after dark** for preview. Download the selected SVG or transparent PNG.
3. Open **The collection** to filter all 32 characters. Click one to load it into the studio.
4. Open **Brand kit** to copy hex values or download the logo/icon. Open **Archive** for the original full-resolution design references.
5. Use the editable SVG files in Figma, Inkscape, Illustrator, or your own design workflow. For website use, import `assets/design-tokens.css` and reference the individual SVGs.

## Brand rules

| Token | Hex | Use |
|---|---|---|
| figg violet | `#8B3DFF` | Signature period, mascot, focused accents |
| soft black | `#111111` | Lowercase logo, editorial typography |
| lilac milk | `#EAD8FF` | Soft visual surfaces and backgrounds |
| warm paper | `#FAFAF8` | Main background and product-stage neutral |

The logo is **`figg.`**, never uppercase in primary identity work: black lowercase letters with a **violet period**. The mascot has a rounded fig silhouette, two simple glossy eyes, a tiny mouth and little feet. Let whitespace and carefully chosen visuals carry the page; keep decorative purple restrained outside the character.

For consistent printing use `assets/logos/figg-wordmark-outlined.svg` (vector paths, **no font needed**). For editable typesetting, use `figg-wordmark.svg`; its appearance may change if the system font is replaced. The mascot SVGs are vector illustrations; the transparent PNGs are raster exports of those same drawings. The original 3D exploration boards are **art-direction references**, not the actual output of trained LoRA models.

## Product-truth checklist

This project is an **internal brand and campaign concept studio**, not an ecommerce checkout, printer integration, Meshy replacement, or proof of manufacturing capability. The companion photo examples and original boards are AI-created conceptual illustrations.

For public Etsy listings, photograph **actual multicolour prints**, demonstrate true size, verify each customer's approved mesh against the final physical piece, and show **real** fulfilled packaging. The editable hero thumbnail deliberately includes a placeholder; remove its guide and replace it with an actual product photo before publishing. Supplier location, delivery speed, enhanced gift packaging, print tolerances, and accessory details require independent validation before you promise them. Do not use fictional review screenshots or claim generated imagery documents a delivered product. If offering a physically printed mascot as a standalone item, test print it at actual size first.

## Source and editing notes

The studio is plain HTML, CSS, and vanilla JS; source lives in `index.html`, `css/style.css`, and `js/app.js`. All variants and their category assignments live in `assets/mascot-manifest.json` and the small dataset at the top of `js/app.js`. `build_assets.py` documents how the vector families were authored; the ready-to-use assets are already included, so you do not need to rerun it. If you change the assets, run `python3 scripts/package.py` to refresh `/downloads/figg-asset-kit.zip`.

Optional visual smoke tests: `python3 visual_test.py` requires Python Playwright and local Chromium. Existing screenshots under `assets/previews/` are included for reference. The base site itself has **zero runtime dependencies** and does not call third-party APIs.

**Design references, not copied source:** [Webflow minimal design examples](https://webflow.com/blog/minimalist-design-examples), [Webflow public brand guidelines](https://brand.webflow.com/design-guidelines), [Figma design-system examples](https://www.figma.com/resource-library/design-system-examples/). The page's code, mascot drawings, styling, and layouts are original to figg. Do not represent it as affiliated with those brands. Verify the **figg.** trading name, domain, and appropriate trademarks before launch.
