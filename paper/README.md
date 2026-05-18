# XY Paper Template

This folder is a cleaned LaTeX paper template derived from the local paper project structure.
It keeps the style files, theorem setup, hyperlink colors, and the `biblatex`/`biber` workflow.

## Files

- `main.tex`: template paper file.
- `ensemble.bib`: bibliography file used by `\addbibresource{ensemble.bib}`.
- `xy-format.sty`: typography, title, abstract, hyperlink, and bibliography style.
- `xy-math.sty`: common math macros.
- `xy-theorem.sty`: theorem, definition, lemma, proposition, and remark environments.

## Build

```sh
latexmk -pdf main.tex
```

The bibliography workflow is `biblatex` with `biber`.
