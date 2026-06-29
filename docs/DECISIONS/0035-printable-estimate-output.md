# 0035: Printable Estimate Output

Status: accepted

## Context

Staff need a simple way to present or print an estimate with customer, vehicle,
repair-order, insurance, line-item, total, supplement, and note context.

## Decision

Start with a read-only, browser-printable Django template at
`/estimates/<pk>/print/`. The page reuses repair-order view permission and
plain CSS print media rules. It does not generate or store PDF files.

## Rationale

- Keeps the workflow local-first and dependency-light.
- Avoids storage, file lifecycle, and rendering complexity before estimate
  approval and invoice-generation workflows are clearer.
- Lets staff print or save to PDF from the browser using current estimate data.

## Consequences

- Print output depends on the browser print engine.
- Generated PDF files, signatures, and document storage remain future work.
- The printable page should stay read-only and should not create domain state.
