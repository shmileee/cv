#!/bin/sh

set -eu

# Compile src/cv.tex into build/cv.pdf, and with --site also assemble the
# directory GitHub Pages publishes.
#
# tectonic runs from src/ so that every \input inside the document resolves
# against the document's own directory rather than the caller's; only the
# finished PDF is written back out into build/.

document=cv
source_directory=src
static_directory=static
output_directory=build
site_directory=build/site

build_site=false
keep_logs=false
repository_root=

phase() {
  printf '[cv] %s\n' "$1"
}

fail() {
  printf '[cv] Error: %s\n' "$1" >&2
  exit "${2:-1}"
}

usage() {
  cat << 'EOF'
Usage: ./scripts/build.sh [--site] [--keep-logs]

Compile src/cv.tex into build/cv.pdf with tectonic.

--site       Also assemble build/site: the viewer page, the PDF it embeds and
             the CNAME, exactly as the Pages workflow uploads them.
--keep-logs  Keep cv.log next to the PDF; useful when a run reports warnings.
EOF
}

validate_arguments() {
  while [ "$#" -gt 0 ]; do
    case $1 in
      --site)
        build_site=true
        ;;
      --keep-logs)
        keep_logs=true
        ;;
      -h | --help)
        usage
        exit 0
        ;;
      *)
        usage >&2
        fail "unrecognised argument: $1" 2
        ;;
    esac
    shift
  done
}

require_command() {
  if ! command -v "$1" > /dev/null 2>&1; then
    fail "$1 is not on PATH; run 'mise install' first."
  fi
}

find_repository_root() {
  if ! script_directory=$(CDPATH='' cd -P "$(dirname "$0")" 2> /dev/null && pwd); then
    fail 'could not resolve the directory holding this script.'
  fi
  if ! repository_root=$(CDPATH='' cd -P "$script_directory/.." 2> /dev/null && pwd); then
    fail 'could not resolve the repository root.'
  fi
  if [ ! -f "$repository_root/$source_directory/$document.tex" ]; then
    fail "expected $source_directory/$document.tex beneath $repository_root."
  fi
}

compile_document() {
  phase "Compiling $source_directory/$document.tex with $(tectonic --version)"
  mkdir -p "$repository_root/$output_directory"

  # --untrusted refuses shell-escape and absolute-path reads. Nothing in this
  # document needs either, and the build also runs unattended on a runner.
  set -- -X compile "$document.tex" \
    --outdir "$repository_root/$output_directory" \
    --outfmt pdf \
    --untrusted
  if [ "$keep_logs" = true ]; then
    set -- "$@" --keep-logs
  fi

  if (cd "$repository_root/$source_directory" && tectonic "$@"); then
    :
  else
    compile_status=$?
    fail 'tectonic could not compile the document; its diagnostics are above.' "$compile_status"
  fi

  pdf_path=$repository_root/$output_directory/$document.pdf
  if [ ! -f "$pdf_path" ]; then
    fail "tectonic reported success but $pdf_path does not exist."
  fi
  phase "Wrote $output_directory/$document.pdf ($(wc -c < "$pdf_path" | tr -d ' ') bytes)"
}

assemble_site() {
  site_path=$repository_root/$site_directory

  # Rebuilt from scratch so a renamed or deleted static file cannot survive in
  # the published output as a stale copy.
  rm -rf "$site_path"
  mkdir -p "$site_path"

  # The trailing /. copies the directory's contents, dotfiles included.
  cp -R "$repository_root/$static_directory/." "$site_path/"
  cp "$repository_root/$output_directory/$document.pdf" "$site_path/$document.pdf"

  published_files=$(find "$site_path" -type f | wc -l | tr -d ' ')
  phase "Assembled $site_directory/ ($published_files files)"
}

main() {
  validate_arguments "$@"
  require_command tectonic
  find_repository_root
  compile_document
  if [ "$build_site" = true ]; then
    assemble_site
  fi
}

main "$@"
