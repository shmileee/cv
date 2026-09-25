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
mise run pack-tags  # measure and repack expertise tags after changing them
```

## Layout

```text
src/       cv.tex is the skeleton; content/ and sidebars/ hold the prose.
           altacv.cls is vendored, with its local changes documented inline
static/    redirect to the PDF, favicon and CNAME
scripts/   build.sh, PDF text normalization and measured expertise-tag packing
build/     generated
```

The tag packer uses the same font and tag boxes as the CV, minimizes rows and
fills earlier rows first. It preserves the groups; check both PDF pages after
adding skills. `python3 scripts/pack-tags.py --check` verifies the packing.

PDF text normalization keeps ASCII hyphens searchable, restores Lato's space
mapping and maps decorative icons to spaces without changing their appearance.
Regression checks run with
`python3 -B -m unittest discover -s tests` (also included in the lint hooks).

## Publishing

A push to `main` builds the PDF and deploys `build/site` to GitHub Pages.
Pull requests build it without publishing, so a change that breaks the
document fails its check first.
