- [x] Update `fees/views.py::record_payment` to reliably resolve the student even when the hidden `admission_no` field is missing/wrong.
- [x] Use `pupil_by_identifier()` fallback logic: prefer POST `admission_no`, else use POST `pupil_query`.
- [x] Improve error message to display the submitted identifier.
- [x] Sanity check for imports (add `pupil_by_identifier` where needed).
- [x] Verify `record_payment` works end-to-end by recording a payment for a student.




