# Changelog

All notable changes to the **Raydon School Management System** will be documented in this file.

---

## [1.0.0] - 2026-07-10

### Added
- Multi-tenant school billing subscription models, billing invoices, SaaS plans, and management screens.
- Full Human Resources management system including staff contract agreements, payroll metrics, payslip generation, and bank transfer export schedules.
- Complete Student Registry mapping sibling structures, guardian details, and permanently archived behavioral records.
- Results Centre calculations determining GPA grades, student ranks, and compiling customizable report cards.
- Medical module tracking student allergies, clinic logs, and medication histories.

### Changed
- Converted entire legacy codebase to a unified Django-only structure to optimize database query roundtrips.
- Restructured core UI templates using modern Bootstrap grids and custom sidebar layouts.

### Fixed
- Fixed database migration warnings during Django setup.
- Resolved offline sync data conflict flags.
- Re-routed invalid fallback buttons to ensure redirect security.
