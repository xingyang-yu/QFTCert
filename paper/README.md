# DualityCert Paper

LaTeX source for the DualityCert paper. The paper reports the certificate and
repair experiments; QFTCert appears only as the broader program in the final
outlook paragraph.

## Files

- `main.tex`: canonical paper file.
- `refs.bib`: bibliography (biblatex/biber).
- `xy-format.sty`: typography, title, abstract, hyperlink, and bibliography style.
- `xy-math.sty`: common math macros.
- `xy-theorem.sty`: theorem, definition, lemma, proposition, and remark environments.
- `tables/`: generated LaTeX tables from the frozen analysis output.
- `PAPER_BLUEPRINT.md`: claim architecture, scope constraints, and result wording.

## Build

```sh
latexmk -pdf main.tex
```

The bibliography workflow is `biblatex` with `biber`.

## Status

The stable two-model sections are drafted. MiniMax is intentionally absent until
its frozen runs and validation are complete. Build artifacts (*.pdf,
*.synctex.gz, *.aux, etc.) are gitignored.
