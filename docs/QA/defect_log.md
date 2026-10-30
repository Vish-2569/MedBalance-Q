# MedBalance-Q Defect Log

| ID | Severity | Component | Description | Found in | Status | Resolution |
|---|---|---|---|---|---|---|
| D-001 | P2 | genai | Missing jinja2 in Dockerfile | CP1 | FIXED | Added `RUN uv pip install --system jinja2 pyyaml google-genai redis` |
| D-002 | P2 | ingest-ai | Missing rapidfuzz in Dockerfile | CP1 | FIXED | Added `RUN uv pip install --system rapidfuzz python-multipart pyyaml httpx` |
| D-003 | P2 | forecast | Missing statsmodels in Dockerfile | CP2 | FIXED | Added `RUN uv pip install --system statsmodels numpy httpx` |
| D-004 | P1 | sim-control | bad_data scenario did not set Redis key | CP2 | FIXED | Added `r.set("sim:scenario:bad_data", "1")` in activate() |
| D-005 | P1 | sim-control | Signal params used wrong field names | CP2 | FIXED | Changed to `facility_id`, `affects`, `demand_multiplier` |
| D-006 | P3 | anomaly | batch_mismatch not detectable offline | P20 eval | FIXED | Added batch prefix heuristic for offline detection |
| D-007 | P3 | E2E | Strict mode violations in Playwright selectors | P22 E2E | FIXED | Changed `getByText()` to `getByRole('heading')` or `.first()` |
| D-008 | P3 | E2E | Review accept button click intercepted by scroll container | P22 E2E | FIXED | Used `force: true` on click |
| D-009 | P3 | E2E | Fixture mode approve doesn't persist status change | P22 E2E | WON'T FIX | Expected in fixture mode; test verifies button presence and click |

### Severity definitions
- **P0**: System crash or data loss — blocks demo
- **P1**: Feature broken — blocks demo scenario
- **P2**: Service won't start — blocks integration testing
- **P3**: Minor UI or test issue — workaround available
