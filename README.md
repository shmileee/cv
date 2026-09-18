# CV

LaTeX source for my CV, published to
[cv.oponomarov.com](https://cv.oponomarov.com).

## Build

[Tectonic](https://tectonic-typesetting.github.io) is the entire toolchain
and mise installs it, so a fresh checkout needs nothing else.

```sh
mise install     # tectonic and the linters
mise run build   # -> build/cv.pdf
mise run site    # -> build/site/, exactly what Pages publishes
mise run serve   # preview it on http://localhost:8080
mise run lint    # the prek hook suite
```

## Layout

```text
src/       cv.tex is the skeleton; content/ and sidebars/ hold the prose.
           altacv.cls is vendored, with its local changes documented inline
static/    viewer page, favicon and CNAME
scripts/   the build, called by mise and CI
build/     generated
```

## Publishing

A push to `main` builds the PDF and deploys `build/site` to GitHub Pages.
Pull requests build it without publishing, so a change that breaks the
document fails its check first.
