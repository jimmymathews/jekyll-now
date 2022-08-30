This directory contains the budget projection document and a script needed to generate the totals portion of this document.

To regenerate the totals (e.g. after editing the costs list or parameters), use:

```sh
./parse_budget_tex.py budget_projection.tex && pdflatex budget_projection.tex
```
