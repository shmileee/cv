# CV

The LaTeX source of my CV and the pipeline that publishes it to
[cv.oponomarov.com](https://cv.oponomarov.com).

## Layout

```text
src/              LaTeX sources
  cv.tex          document skeleton: preamble, header, two sections
  preamble.tex    engine setup, palette, clickable contact details
  content/        the name block and the roles
  sidebars/       the margin column printed beside each section
  assets/         profile photo
  altacv.cls      vendored AltaCV v1.1.5, one documented local change
static/           published alongside the PDF: viewer page and CNAME
scripts/          the build itself, called by mise and CI
build/            generated, never committed
```

## Building

[Tectonic](https://tectonic-typesetting.github.io) is the whole toolchain: a
single binary that downloads only the LaTeX packages this document actually
uses and caches them, instead of a multi-gigabyte TeX Live installation.
mise installs it, so a fresh checkout needs nothing else.

```sh
mise install         # tectonic and the validation tooling
mise run build       # -> build/cv.pdf
mise run site        # -> build/site/, byte for byte what Pages publishes
mise run serve       # preview that directory on http://localhost:8080
```

`mise run lint` runs the full prek hook suite and `mise run prek:install`
installs the git shims so it also runs on commit. `mise tasks` lists
everything.

## Publishing

`.github/workflows/publish.yaml` builds `build/site` and deploys it to GitHub
Pages. Pull requests build the PDF but never publish, so a change that breaks
the document fails its check first.

The site is the PDF plus a viewer page that embeds it full-screen; phones get
a hand-off link instead, because mobile browsers do not render embedded PDFs.

Two settings live outside this repository and are needed once:

*   **Repository → Settings → Pages → Source**: *GitHub Actions*.
*   **DNS**: a `CNAME` record for `cv` pointing at `shmileee.github.io`. The
    `static/CNAME` file only tells Pages which domain to answer to.

## Notes

*   `src/altacv.cls` is upstream AltaCV v1.1.5 with its unconditional
    `biblatex` load disabled, because that pulled in `biber` as a second
    toolchain for a publications section this CV does not have. The block is
    commented out in place, with the reasoning next to it.
*   The published PDF carries a phone number and a personal email address.
    Anything committed here is public the moment it is pushed.
