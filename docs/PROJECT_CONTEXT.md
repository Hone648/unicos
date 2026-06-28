# Project Context

Unicos is a web-based body shop repair order management app.

The app is intended to help a shop track repair work from intake through
completion and payment. The intended shop has internet access, so the app is
expected to become internet-accessible / hosted in the future. Local Docker
remains the current development runtime.

Primary business needs:

- Customer contact tracking
- One or more vehicles/VINs per customer
- Work intake
- Work-in-progress tracking
- Owed/paid payment tracking
- Web-based browser access for shop staff
- Future internet-accessible hosted deployment

Current implementation scope is foundational. The accounts/auth baseline exists;
domain models, billing, and shop workflows belong in later slices.
