# CV

LaTeX source for my CV, published to
[cv.oponomarov.com](https://cv.oponomarov.com).

## Build

[Tectonic](https://tectonic-typesetting.github.io) is the whole LaTeX
toolchain and mise installs it. The build also shells out to `python3` for a
post-processing step, using nothing outside the standard library, so a fresh
checkout needs no third dependency.

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
static/    redirect to the PDF, favicon and CNAME
scripts/   build.sh, called by mise and CI, and the ToUnicode fixup it runs
build/     generated
```

## Publishing

A push to `main` builds the PDF and deploys `build/site` to GitHub Pages.
Pull requests build it without publishing, so a change that breaks the
document fails its check first.
