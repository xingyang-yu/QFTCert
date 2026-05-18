# QFTCert Paper

LaTeX source for the QFTCert paper.

## Files

- `QFTCert.tex`: main paper file.
- `QFTCert.bib`: bibliography (biblatex/biber).
- `xy-format.sty`: typography, title, abstract, hyperlink, and bibliography style.
- `xy-math.sty`: common math macros.
- `xy-theorem.sty`: theorem, definition, lemma, proposition, and remark environments.

## Build

```sh
latexmk -pdf QFTCert.tex
```

The bibliography workflow is `biblatex` with `biber`.

## Status

Draft in progress. Build artifacts (*.pdf, *.synctex.gz, *.aux, etc.) are gitignored.
