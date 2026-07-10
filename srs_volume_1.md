# Software Requirements Specification (SRS)
## Raydon School Management System Enterprise Edition
### Volume 1: Chapters 1 to 3.32

---

## Revision History

| Version | Date | Author | Description |
| --- | --- | --- | --- |
| 1.0 | July 2026 | Raidon Magunje | Initial Enterprise Software Requirements Specification |
| 3.0 | July 2026 | Antigravity AI | Upgraded Zimbabwean High School (Forms 1–6) specification alignment |

---

## Table of Contents
- **Chapter 1: Introduction and Project Overview**
  - 1.1 Executive Summary
  - 1.2 Purpose of this Document
  - 1.3 Purpose of the System
  - 1.4 Project Objectives
  - 1.5 Scope of the System
  - 1.6 Intended Audience
  - 1.7 Development Philosophy
- **Chapter 2: Business Requirements and System Context**
  - 2.1 Business Overview
  - 2.2 Problem Statement
  - 2.3 Proposed Solution
  - 2.4 Business Objectives
  - 2.5 Stakeholders
  - 2.6 User Categories
  - 2.7 Business Rules
  - 2.8 School Operational Workflow
  - 2.9 User Roles and Responsibilities
  - 2.10 Assumptions
  - 2.11 Constraints
  - 2.12 Dependencies
  - 2.13 Success Criteria
- **Chapter 3: Functional Requirements**
  - 3.1 Introduction
  - 3.2 Student Registration Module
  - 3.3 Student Admission Workflow
  - 3.4 Student Lifecycle Management
  - 3.5 Forms and Streams Management
  - 3.6 Subject Master Catalog
  - 3.7 Student Subject Registration
  - 3.8 Teacher Subject Allocation
  - 3.9 Results Entry and Mark Sheets
  - 3.10 Result Sheets Verification, Auditing and Publishing
  - 3.11 Student Portal Access and Filters
  - 3.12 Parent Portal Access and Filters
  - 3.13 Fee Structure and Progression Auto-Switching
  - 3.14 Fee Billing, Payments, and Statements
  - 3.15 Reports and PDF Document Generation
  - 3.16 Audit Trail Logging and Security Controls
  - 3.17 Fees Management, Billing, Payments and Financial Controls
  - 3.18 Accounting and General Ledger Module
  - 3.19 Procurement and Supplier Management
  - 3.20 Inventory and Store Management
  - 3.21 Human Resources Management (Premium Module)
  - 3.22 Payroll Management (Premium Module)
  - 3.29 Medical and School Clinic Management
  - 3.30 SaaS Subscription and Module Management
  - 3.31 System Administration and Security
  - 3.32 Reports and Business Intelligence (BI)

---

## Chapter 1: Introduction and Project Overview

### 1.1 Executive Summary
The Raydon School Management System Enterprise Edition is a comprehensive web-based School Enterprise Resource Planning (ERP) solution designed specifically for Zimbabwean secondary schools. The system supports the complete management of academic, administrative, financial and operational activities within a school while remaining scalable enough to support multiple independent schools through a Software-as-a-Service (SaaS) architecture.

Unlike traditional school management systems that focus mainly on student registration and examination processing, the Raydon School Management System provides an integrated platform that manages the entire lifecycle of a learner, from admission through completion of Ordinary Level (O Level) and Advanced Level (A Level), while also supporting enterprise functions such as finance, payroll, procurement, inventory, transport, hostel management, library services, medical records, guidance and counselling, discipline, parent engagement, artificial intelligence analytics and multi-school administration.

The system is designed to support the Zimbabwean education system by aligning its academic structure with Forms 1 to 6, incorporating O Level and A Level workflows, ZIMSEC examination analysis, subject registration rules, and school-specific administrative processes. It also provides flexibility through configurable modules, enabling each school to activate only the features required for its operations while maintaining a common enterprise platform.

### 1.2 Purpose of this Document
This Software Requirements Specification (SRS) defines the complete functional and non-functional requirements for the Raydon School Management System Enterprise Edition. It describes the expected behaviour of every module, the relationships between system components, user roles, business processes, validation rules, security requirements, reporting requirements, database structures and quality standards required for successful implementation.

This SRS is intended to eliminate ambiguity during software development by providing a single authoritative source of requirements. All development activities, testing procedures and future enhancements shall conform to the specifications defined within this document.

### 1.3 Purpose of the System
The purpose of the Raydon School Management System Enterprise Edition is to provide schools with a unified digital platform capable of managing academic administration, student records, financial management, human resources, communication, reporting and institutional operations from a single integrated application.

The system aims to replace fragmented manual processes with automated workflows that improve efficiency, data accuracy, accountability and transparency.

### 1.4 Project Objectives
The primary objectives of the project are to:
- Develop a complete enterprise-grade School Management System tailored to Zimbabwean high schools.
- Support Forms 1 to 6, including both O Level and A Level structures.
- Provide secure management of student academic records throughout their lifecycle.
- Automate school administrative and financial processes.
- Improve communication between schools, parents, teachers and students.
- Generate professional reports, receipts, invoices and official documents.
- Support SaaS architecture for multiple independent schools.
- Provide configurable subscription plans and module management.
- Maintain high security, scalability, reliability and maintainability.
- Prepare the system for future cloud deployment while allowing full local development and testing.

### 1.5 Scope of the System
The system shall provide an integrated platform supporting:
- Student Registration & Admission
- Subject Master Catalog & Registrations
- Class and Stream Allocation
- Teacher Timetable Allocations
- Results Entry & Terminal Reports Processing
- ZIMSEC Examination Performance Analysis
- Fees Management (Structures, Billing & Payments)
- Student, Parent & Teacher Portals
- Audit Logging & Security Administration

### 1.6 Intended Audience
This document is intended for:
- System Owner
- Software Developers & Architects
- Database Administrators
- UI/UX Designers & QA Engineers
- School Administrators & Project Managers
- Future Technical Support Teams

### 1.7 Development Philosophy
The Raydon School Management System shall be developed using a modular, scalable and maintainable architecture. Every module shall be loosely coupled and capable of operating independently while integrating seamlessly with other modules through well-defined interfaces and shared business rules.

The system shall prioritise security, data integrity, performance and usability. Business logic shall be centralised to ensure consistency across all modules, and all critical operations shall be protected by role-based access control and comprehensive audit logging.

---

## Chapter 2: Business Requirements and System Context

### 2.1 Business Overview
The Raydon School Management System Enterprise Edition is designed to provide Zimbabwean secondary schools with a comprehensive digital platform that manages academic, administrative, financial and operational activities within a single integrated environment. The system supports the complete student lifecycle from initial admission through Ordinary Level (O Level), Advanced Level (A Level), graduation, archival and alumni management.

### 2.2 Problem Statement
Many schools continue to rely on paper-based records, spreadsheets or disconnected software applications to manage their daily operations. These approaches result in duplicate data entry, inconsistent information, slow reporting, poor communication, limited visibility into school performance and increased operational costs.

High schools in Zimbabwe face additional challenges because they operate two distinct academic levels: Ordinary Level (Forms 1–4) and Advanced Level (Forms 5–6). Students who complete O Level do not automatically progress to A Level, yet many existing systems lack support for this workflow. Consequently, schools struggle to maintain accurate historical records, analyse ZIMSEC examination performance, reactivate returning students and manage subject registration according to national examination requirements.

### 2.3 Proposed Solution
The proposed solution is the development of the Raydon School Management System Enterprise Edition, a modular web-based ERP platform developed using the Django framework with PostgreSQL as the primary production database and SQLite for local development and testing.

The system will support both single-school and multi-school environments through a SaaS architecture. Each school will operate independently with isolated data, customised settings, subscription plans and configurable modules.

### 2.4 Business Objectives
The primary business objectives of the system are:
- Digitise all major school operations.
- Improve administrative efficiency and reduce manual paperwork.
- Support Zimbabwean secondary school academic structures.
- Improve communication among administrators, teachers, parents and students.
- Provide real-time reporting and analytics.
- Support sustainable multi-school deployment through SaaS architecture.

### 2.5 Stakeholders
- School Owners and Directors
- Headmasters and Academic Administrators
- Finance Officers
- Teachers, Parents, and Students
- System Administrators
- Ministry of Primary and Secondary Education (ZIMSEC)

### 2.6 User Categories
- **Super Administrator**: SaaS-level tenant and subscription control.
- **School Administrator**: Tenant-level configurations and user rights.
- **Academic Administrator**: Class, subject catalog, and timetable management.
- **Finance Officer**: Fees collection, statements, and receipts.
- **Teacher**: Marks entry, attendance, and e-learning allocations.
- **Parent**: Reading child records, viewing fee balances, and report cards.
- **Student**: Accessing assignments, notes, timetables, and personal terminal results.

### 2.7 Business Rules
- **Academic Structure**: The school shall operate only: Form 1, Form 2, Form 3, Form 4, Form 5, Form 6. The term "Grade" shall never appear anywhere within the system.
- **O Level**: Consists of Form 1–4. Streams allowed: `A`, `B`, `C`. Max registered subjects: 10.
- **A Level**: Consists of Form 5–6. Streams allowed: `Arts`, `Commercials`, `Sciences`. Max registered subjects: 5.
- **Student Progression**: Completion of Form 4 shall not automatically promote a student to Form 5. Students completing O Level shall enter a `Pending ZIMSEC Analysis` status until they are reactivated into Form 5 or archived.
- **Reactivation**: Students returning for A Level shall retain their original admission number, personal history, and fee balances.
- **Subject Registrations**: Marks entry is restricted to registered subjects.

### 2.8 School Operational Workflow
The operational workflow consists of:
`Admission -> Registration -> Subject Selection -> Class Allocation -> Teacher Allocation -> Attendance -> Results Entry -> Reporting -> ZIMSEC Analysis -> Archiving/Reactivation -> Alumni`.

### 2.9 User Roles and Responsibilities
Every user shall operate only within assigned permissions. Role-based access control shall ensure users cannot access unauthorised modules or modify records outside their sphere.

### 2.10 Assumptions
- Schools follow the Zimbabwean secondary education structures.
- Local development runs on SQLite; production runs on PostgreSQL.
- School settings correctly reflect the active academic year.

### 2.11 Constraints
- Historical records must be preserved.
- No automatic deletion of archived academic records.
- Complete modularity must be maintained.

### 2.12 Dependencies
- Python 3.12+, Django 5+, PostgreSQL / SQLite.
- ReportLab for PDF generation.

### 2.13 Success Criteria
- Successful execution of all modules.
- Enforced stream restrictions by Form.
- Auto-billing fee progressions.
- Audited results entry.

---

## Chapter 3: Functional Requirements

### 3.1 Introduction
#### 3.1.1 Overview
The Student Functional Requirements define the detailed behaviors, constraints, validations, and workflows of every module within the system. The central focus is on student admissions, forms, streams, subject catalogs, teacher allocations, fee structures, result entries, portal filters, PDF reporting, and security auditing.

#### 3.1.2 Objectives
Ensure consistent enforcement of all business rules across database operations, view routing, user authorization, and user interfaces.

#### 3.1.3 Scope
Applies to students, academics, exams, portals, and reports modules.

#### 3.1.4 Business Importance
Enforces administrative rigor, prevents duplicate data entry, blocks illegal subject selections, and ensures reliable academic and financial reporting.

#### 3.1.5 Design Principles
- Strict data separation and model validations.
- Clean separation of concerns between view controllers and database layer.
- Enforce audit trails on all sensitive data changes.

#### 3.1.6 Success Criteria
Clean, exception-free compilation, zero validation bypasses, and 100% automated test compliance.

---

### 3.2 Student Registration Module
#### 3.2.1 Module Overview
The Student Registration module handles the creation of a permanent learner profile.
#### 3.2.2 Functional Specifications
- **Automatic Admission Numbering**: Automatically generates unique IDs in the format `A[YY][Index]` (e.g. `A26001`). Admission numbers are immutable once saved.
- **Personal Details**: Captures name, gender, date of birth, optional national ID, parent/guardian contact info, and medical remarks.
- **Photo-Free Interface**: The module contains no photographic captures, placeholders, uploads, or image crop tools.

---

### 3.3 Student Admission Workflow
#### 3.3.1 Overview
A structured flow managing application check, validation, assignment of Form, Stream, Subject list, and initial billing.
#### 3.3.2 Functional Specifications
- **Admission Types**: Supports New Admission, Transfer Admission, and A Level Reactivation.
- **Validations**: Reject registration if:
  - Form/Stream combination is invalid.
  - No subjects are selected.
  - Subject count exceeds academic limits (O Level > 10, A Level > 5).
- **A Level Reactivation**: If an archived student returns, the system reactivates their profile using the same admission number and maintains their historical billing and results.

---

### 3.4 Student Lifecycle Management
#### 3.4.1 Overview
Tracks the student's status throughout their career in the school.
#### 3.4.2 Status Transitions
- **Active**: Student is attending and participating in class.
- **Pending ZIMSEC Analysis**: Student has completed Form 4 and is awaiting results.
- **Archived**: Student has graduated, transferred out, or withdrawn.
- **Rules**:
  - Automatically promote active students at end-of-year except Form 4, which moves to `Pending ZIMSEC Analysis`.
  - Archiving matures `Pending ZIMSEC Analysis` students on 1 March unless they are reactivated into Form 5.
  - Reactivation to Form 5 (A Level) is permitted at any time, changing status back to `Active`.

---

### 3.5 Forms and Streams Management
#### 3.5.1 Overview
Enforces the correct academic hierarchy (Forms 1–6) and stream constraints.
#### 3.5.2 Functional Specifications
- **O Level (Form 1–4)**: Allowed streams are strictly `A`, `B`, and `C`.
- **A Level (Form 5–6)**: Allowed streams are strictly `Arts`, `Commercials`, and `Sciences`.
- **Validations**: Any attempt to save a student with an invalid Form/Stream combination (e.g., Form 3 Stream Sciences or Form 5 Stream A) must be blocked both on the client (via JavaScript) and on the server (via model validations).

---

### 3.6 Subject Master Catalog
#### 3.6.1 Overview
Manages the curriculum catalog of the school.
#### 3.6.2 Functional Specifications
- **Subject CRUD**: Admins can create, retrieve, update, and delete subjects.
- **Delete Dependency Checks**: Deletion of a subject is strictly prohibited if there are active historical records referencing it, including:
  - result entries (exam marks)
  - class timetable entries (timetable allocations)
  - student subjects (active student registrations)
  - teacher allocations (`timetable_subjectallocation`)
  - e-learning assignments & e-learning study notes

---

### 3.7 Student Subject Registration
#### 3.7.1 Overview
Maintains the mapping of registered subjects for each student.
#### 3.7.2 Functional Specifications
- **Mandatory Registration**: Students must register for subjects for the active academic year.
- **Limits**: Maximum 10 subjects for O Level, maximum 5 subjects for A Level.
- **Edit Controls**: Subject registrations can be modified by administrators. Any addition or deletion of a registered subject must require a written reason, which is automatically saved to the audit log trail.

---

### 3.8 Teacher Subject Allocation
#### 3.8.1 Overview
Controls which classes and subjects are taught by each teacher.
#### 3.8.2 Functional Specifications
- **TIMETABLE allocation**: Teachers are assigned to subjects and classes via `timetable_subjectallocation`.
- **Dashboard RBAC**: Teachers' dashboard listings (for e-learning notes, assignments, and results entry) must filter out any classes or subjects that they are not allocated to teach.

---

### 3.9 Results Entry and Mark Sheets
#### 3.9.1 Overview
Handles terminal exam mark entries.
#### 3.9.2 Functional Specifications
- **Student Filtering**: The results class entry sheet must only display students who are active and registered for the selected subject in the selected academic year.
- **Teacher Verification**: Enforce server-side checks that the logged-in teacher is allocated to teach the subject and class before saving any marks.

---

### 3.10 Result Sheets Verification, Auditing and Publishing
#### 3.10.1 Overview
Verifies and locks result entries.
#### 3.10.2 Functional Specifications
- **Verification**: Block publishing if any marks are invalid (not in 0–100 range).
- **Edit Auditing**: Every modification to a student's mark after initial save must log an entry in the audit trail showing:
  - Logged-in user making the change.
  - Student admission number and subject ID.
  - The previous mark value.
  - The new mark value.
  - Timestamp.

---

### 3.11 Student Portal Access and Filters
#### 3.11.1 Overview
Restricts student portal displays.
#### 3.11.2 Functional Specifications
- **Filtering**: Students must only see notes, assignments, submission items, and terminal marks for subjects they are registered for in that academic year. All other curriculum materials must be hidden.

---

### 3.12 Parent Portal Access and Filters
#### 3.12.1 Overview
Restricts parent portal displays.
#### 3.12.2 Functional Specifications
- **Filtering**: Similar to the student portal, parents must only see reports, marks, and e-learning resources for the specific subjects that their child is registered for.

---

### 3.13 Fee Structure and Progression Auto-Switching
#### 3.13.1 Overview
Manages standard fee levels based on academic forms.
#### 3.13.2 Functional Specifications
- **Standard Fees**: O Level (Form 1–4) standard billing is USD 100.00. A Level (Form 5–6) standard billing is USD 150.00.
- **Auto-Billing Progression**: When a student is registered or promoted, the system automatically checks their Form and applies the corresponding fee level.
- **Historical Consistency**: Changing standard fee levels or promoting students must not alter historical bills, payments, or ledger records for prior academic terms.

---

### 3.14 Fee Billing, Payments, and Statements
#### 3.14.1 Overview
Processes payments and ledger sheets.
#### 3.14.2 Functional Specifications
- **Receipts & Statements**: Generate receipts and Statements of Account showing previous balance, payments made, and outstanding arrears.
- **Photo-Free Layout**: Statement PDFs must not contain student photo boxes or placeholders.

---

### 3.15 Reports and PDF Document Generation
#### 3.15.1 Overview
Generates terminal report cards and administrative registers.
#### 3.15.2 Functional Specifications
- **Report Cards**: Auto-calculates averages, aggregates, and positions.
- **Layout Constraints**: No photo rendering logic or image containers are permitted in student PDF reports.

---

### 3.16 Audit Trail Logging and Security Controls
#### 3.16.1 Overview
Centralised logging of critical system operations.
#### 3.16.2 Functional Specifications
- **System Actions Logged**:
  - Student creation and edit logs.
  - Subject deletion attempts (both successful and blocked).
  - Student subject modifications (with the entered change reason).
  - Exam mark updates (recording the user, student, subject, old mark, and new mark).
  - Fee billing and payment entries.
- **Security Constraints**: Audit trails must be read-only for all users, including administrators, and kept permanently in the database.

---

### 3.17 Fees Management, Billing, Payments and Financial Controls
#### 3.17.1 Overview
The Fees Management, Billing, Payments and Financial Controls Module shall provide a comprehensive financial management platform for administering school fees, billing, receipts, payment reconciliation, sponsorships, discounts, payment plans and financial reporting. The module shall support different fee structures for Ordinary Level (Forms 1-4) and Advanced Level (Forms 5-6), while remaining flexible enough to accommodate future fee categories and pricing changes.

The module shall automatically generate student fee accounts during registration and shall integrate with Student Registration, Subject Registration, Results Centre, Parent Portal, Student Portal, Accounting, Reporting, Audit Logging and the SaaS Subscription Management Module.

The system shall maintain complete financial records throughout the student's lifecycle, including archived students and alumni where historical financial information is required.

#### 3.17.2 Objectives
The Fees Management Module shall:
- Automatically create student fee accounts.
- Support configurable fee structures.
- Support O Level and A Level fee structures.
- Manage invoices and billing.
- Record fee payments.
- Generate secure receipts.
- Support payment reconciliation.
- Manage arrears.
- Support payment plans.
- Support scholarships and sponsorships.
- Generate financial reports.
- Maintain complete financial audit trails.

#### 3.17.3 Fee Structures
The system shall support multiple fee structures.

Initially:

**Ordinary Level**

Applicable Forms:
- Form 1
- Form 2
- Form 3
- Form 4

Default Fee Structure:
- USD 100

**Advanced Level**

Applicable Forms:
- Form 5
- Form 6

Default Fee Structure:
- USD 150

Fee structures shall be configurable without modifying the application source code.

#### 3.17.4 Fee Categories
The system shall support configurable fee categories, including:
- Tuition Fees
- Development Levy
- Boarding Fees
- Examination Fees
- Practical Fees
- Sports Fees
- Library Fees
- Laboratory Fees
- ICT Fees
- Transport Fees
- Hostel Fees
- Uniform Fees
- Miscellaneous Charges

Schools shall enable or disable categories according to their operational requirements.

#### 3.17.5 Student Fee Account
Upon successful registration, the system shall automatically create a fee account for each student.

The fee account shall include:
- Admission Number
- Student Name
- Academic Year
- Term
- Form
- Stream
- Fee Structure
- Total Charges
- Amount Paid
- Outstanding Balance
- Arrears
- Credit Balance

The account shall remain linked to the student's permanent admission number throughout their lifecycle.

#### 3.17.6 Billing Workflow
The billing workflow shall proceed as follows:

`Student Registered -> Fee Structure Assigned -> Fee Account Created -> Invoice Generated -> Parent Notified (if enabled) -> Payment Received -> Receipt Generated -> Ledger Updated -> Reconciliation Updated -> Reports Updated`

#### 3.17.7 Invoice Management
The system shall automatically generate invoices.

Each invoice shall include:
- Invoice Number
- Invoice Date
- Due Date
- Student Details
- Fee Breakdown
- Previous Balance
- Current Charges
- Discounts
- Scholarships
- Total Amount Due

Invoice numbers shall be generated sequentially and shall be unique within each school.

#### 3.17.8 Payment Processing
The system shall support:
- Cash
- Bank Transfer
- POS
- Mobile Money
- Online Payment (future-ready)
- Other payment methods configured by the school

Each payment shall record:
- Receipt Number
- Payment Date
- Amount
- Currency
- Payment Method
- Transaction Reference
- Received By

Receipt numbers shall be sequential and unique.

#### 3.17.9 Multi-Currency Support
The system shall support multiple currencies.

Initially:
- USD
- ZiG

The exchange rate shall be configurable through Finance Settings.

The system shall calculate and display values in the selected operating currency while preserving the original payment currency for audit purposes.

#### 3.17.10 Arrears Management
The system shall automatically track outstanding balances.

Business rules:
- Arrears shall be carried forward to the next billing period.
- Payments shall first settle the oldest outstanding arrears before current charges unless the school configures a different allocation policy.
- Arrears shall appear on invoices, statements and dashboards.

#### 3.17.11 Payment Plans
The system shall allow authorised Finance Officers to create payment plans.

Each plan shall include:
- Student
- Total Amount
- Instalment Amount
- Payment Schedule
- Due Dates
- Status

The system shall monitor compliance with the agreed payment plan.

#### 3.17.12 Scholarships and Sponsorships
The system shall support:
- Full Scholarship
- Partial Scholarship
- Government Sponsorship
- NGO Sponsorship
- Corporate Sponsorship
- Parent Sponsorship

Each sponsorship shall record:
- Sponsor
- Coverage Percentage or Amount
- Effective Dates
- Conditions
- Supporting Documents (optional)

Billing shall automatically apply approved sponsorships.

#### 3.17.13 Discounts and Waivers
Authorised users shall apply:
- Percentage Discounts
- Fixed Amount Discounts
- Fee Waivers

Every adjustment shall require:
- Reason
- Approval (if configured)
- User
- Date and Time

The system shall preserve the original fee amount for auditing.

#### 3.17.14 Receipt Generation
Every payment shall generate a professional receipt.

Each receipt shall include:
- Receipt Number
- Student Information
- Payment Breakdown
- Amount Paid
- Outstanding Balance
- Payment Method
- Date and Time
- Cashier Name
- QR Code
- Electronic School Stamp

Receipts shall support PDF generation and reprinting with version control.

#### 3.17.15 Payment Reconciliation
The system shall reconcile:
- Cash Collections
- Bank Deposits
- POS Transactions
- Mobile Money Transactions

The reconciliation process shall identify:
- Matched Transactions
- Unmatched Transactions
- Overpayments
- Underpayments
- Reversals

Finance Officers shall resolve discrepancies before closing the period.

#### 3.17.16 Financial Reports
The system shall generate:
- Fee Statement
- Outstanding Balances Report
- Arrears Report
- Daily Collections Report
- Cashier Report
- Payment Method Report
- Sponsorship Report
- Discount Report
- Reconciliation Report
- Revenue Summary
- Collection Trend Analysis

Reports shall support export to:
- PDF
- Excel
- CSV

#### 3.17.17 Dashboard Widgets
**Finance Dashboard**

Display:
- Total Revenue Collected
- Outstanding Fees
- Arrears
- Daily Collections
- Monthly Collections
- Payments by Method
- Students with Outstanding Balances
- Payment Plan Compliance
- Sponsorship Summary

**Parent Portal**

Display:
- Current Balance
- Payment History
- Due Dates
- Download Receipts
- Download Fee Statements

**Student Portal**

Display:
- Fee Balance
- Recent Payments
- Outstanding Amount
- Payment Receipts

#### 3.17.18 Business Rules
The system shall enforce:
- Every active student shall have one fee account.
- Fee structures shall be determined by Form (O Level or A Level).
- Receipt numbers and invoice numbers shall be unique and sequential.
- Payments shall update balances immediately.
- Arrears shall be tracked automatically.
- Receipts shall include QR codes and electronic school stamps.
- Financial records shall never be deleted; corrections shall be handled through authorised adjustments or reversals.
- Archived students shall retain complete financial history.

#### 3.17.19 User Permissions
| Role | Permissions |
| --- | --- |
| Super Administrator | Full access |
| School Administrator | View and supervise financial operations |
| Finance Officer | Manage billing, payments, receipts, reconciliation and reports |
| Cashier | Record payments and issue receipts only |
| Academic Administrator | Read-only access where required |
| Parent | View balances, statements and download receipts |
| Student | View personal fee information only |

#### 3.17.20 Audit Logging
The system shall record:
- Invoice creation.
- Invoice updates.
- Payment receipt generation.
- Receipt reprints.
- Payment reversals.
- Fee adjustments.
- Sponsorship approvals.
- Discount approvals.
- Reconciliation activities.

Each audit record shall include:
- User
- Date and Time
- School Tenant
- Module
- Action
- Transaction Number
- Previous Value
- New Value
- Reason (where applicable)

#### 3.17.21 Testing Requirements
The module shall be tested to verify:
- Fee account creation.
- Automatic fee structure assignment.
- Invoice generation.
- Payment processing.
- Multi-currency calculations.
- Arrears allocation.
- Payment plan management.
- Scholarship and discount application.
- Receipt generation with QR code and electronic stamp.
- Reconciliation workflow.
- Report generation.
- Permission enforcement.
- Audit logging.

#### 3.17.22 Acceptance Criteria
The Fees Management, Billing, Payments and Financial Controls Module shall be considered complete when:
- Every student automatically receives the correct fee structure based on Form.
- O Level and A Level fee structures are configurable and applied correctly.
- Invoices and receipts are generated automatically with unique numbers.
- Payments update student balances immediately.
- Multi-currency transactions are supported.
- Arrears, sponsorships, discounts and payment plans are managed accurately.
- Payment reconciliation identifies discrepancies and supports resolution.
- Financial reports and dashboards provide accurate real-time information.
- All financial activities are recorded in the audit log.
- The module integrates seamlessly with Student Registration, Parent Portal, Student Portal, Reporting, Accounting and the configurable SaaS module architecture.

**End of Section 3.17**

---

### 3.18 Accounting and General Ledger Module
#### 3.18.1 Overview
The Accounting and General Ledger Module shall provide the core financial accounting foundation for the Raydon School Management System. It shall support structured accounting operations including chart of accounts management, journal entries, ledgers, budgeting, bank reconciliation, financial statements, financial controls and integration with operational finance modules.

The module shall integrate with Fees Management, Payroll, Procurement, Inventory, SaaS Subscription Management, Reporting, Audit Logging and User Permissions. It shall ensure that all school financial transactions are accurately recorded, classified, reviewed and reported in accordance with each school's accounting policies.

The module shall support multi-tenant SaaS architecture, ensuring that each school tenant maintains separate financial records, accounting periods, users, approvals, reports and audit trails.

#### 3.18.2 Objectives
The Accounting and General Ledger Module shall:
- Maintain a configurable chart of accounts.
- Record journal entries.
- Manage general ledger transactions.
- Support income and expense tracking.
- Integrate fee collections into accounting records.
- Integrate payroll expenses.
- Integrate procurement and supplier payments.
- Support budgeting and budget monitoring.
- Support bank reconciliation.
- Generate financial statements.
- Support multi-currency accounting.
- Enforce financial controls and approvals.
- Maintain complete audit trails.

#### 3.18.3 Chart of Accounts
The system shall provide a configurable chart of accounts for each school.

The chart of accounts shall support:
- Assets
- Liabilities
- Equity / Fund Balances
- Income / Revenue
- Expenses

Example account categories shall include:
- Cash on Hand
- Bank Accounts
- Accounts Receivable
- Student Fee Income
- Development Levy Income
- Sponsorship Income
- Payroll Expenses
- Teaching Materials
- Utilities
- Transport Expenses
- Procurement Expenses
- Accounts Payable
- Accrued Expenses
- Retained Funds

Each account shall include:
- Account Code
- Account Name
- Account Type
- Parent Account
- Description
- Currency
- Active / Inactive Status
- School Tenant
- Created By
- Created Date

Account codes shall be unique within each school tenant.

#### 3.18.4 General Ledger
The system shall maintain a general ledger for all approved financial transactions.

The general ledger shall record:
- Transaction Date
- Posting Date
- Account Code
- Account Name
- Debit Amount
- Credit Amount
- Currency
- Exchange Rate
- Source Module
- Reference Number
- Description
- Created By
- Approved By
- School Tenant

The general ledger shall support real-time updates from integrated modules where configured.

#### 3.18.5 Journal Entries
The system shall allow authorised users to create journal entries.

Journal entries shall support:
- Manual journals
- System-generated journals
- Reversing journals
- Adjustment journals
- Opening balance journals
- Year-end closing journals

Each journal entry shall include:
- Journal Number
- Journal Date
- Description
- Debit Lines
- Credit Lines
- Supporting Documents
- Prepared By
- Reviewed By
- Approved By
- Status

Journal entry statuses shall include:
- Draft
- Submitted
- Approved
- Posted
- Rejected
- Reversed

The system shall enforce that every journal entry balances before posting.

#### 3.18.6 Posting Rules
The system shall enforce accounting posting rules.

Business rules:
- Total debits must equal total credits.
- Only approved journal entries may be posted.
- Posted entries shall not be deleted.
- Corrections shall be handled through reversals or adjustment journals.
- Closed accounting periods shall not accept new postings unless reopened by an authorised user.
- Every system-generated posting shall retain a reference to the source transaction.

#### 3.18.7 Integration with Fees Management
The Accounting Module shall integrate with the Fees Management Module.

Fee-related accounting postings may include:
- Student invoices
- Fee payments
- Discounts
- Sponsorships
- Waivers
- Refunds
- Payment reversals
- Arrears adjustments

Example postings:

| Transaction | Debit | Credit |
| --- | --- | --- |
| Invoice Generated | Accounts Receivable | Fee Income |
| Payment Received | Cash / Bank | Accounts Receivable |
| Discount Approved | Discount Expense / Contra Income | Accounts Receivable |
| Refund Issued | Accounts Receivable / Refund Expense | Cash / Bank |

The system shall allow schools to configure how fee categories map to ledger accounts.

#### 3.18.8 Integration with Payroll
The module shall integrate with Payroll where enabled.

Payroll-related postings may include:
- Salary expenses
- Allowances
- Deductions
- PAYE / tax liabilities
- Pension contributions
- Net salary payable
- Payroll payments

Example postings:

| Transaction | Debit | Credit |
| --- | --- | --- |
| Payroll Processed | Salary Expense | Salary Payable |
| Statutory Deduction | Salary Payable | Statutory Liability |
| Salary Paid | Salary Payable | Bank Account |

Payroll postings shall be traceable to payroll periods, employees and payment batches.

#### 3.18.9 Integration with Procurement
The Accounting Module shall integrate with Procurement and Supplier Management.

Procurement-related postings may include:
- Purchase orders
- Goods received
- Supplier invoices
- Supplier payments
- Expense recognition
- Inventory purchases

Example postings:

| Transaction | Debit | Credit |
| --- | --- | --- |
| Supplier Invoice Recorded | Expense / Inventory | Accounts Payable |
| Supplier Payment Made | Accounts Payable | Bank Account |

Each procurement transaction shall retain links to supplier records, invoices, purchase orders and payment references.

#### 3.18.10 Budgeting
The system shall support budgeting by account, department, term, month or academic year.

Budgets shall include:
- Budget Name
- Academic Year
- Accounting Period
- Account Code
- Department
- Budgeted Amount
- Actual Amount
- Variance
- Status
- Approved By

Budget statuses shall include:
- Draft
- Submitted
- Approved
- Revised
- Closed

The system shall compare actual income and expenditure against approved budgets.

#### 3.18.11 Budget Controls
The system shall support budget control rules.

Configurable controls may include:
- Warning when expenditure approaches budget limit.
- Blocking expenditure above approved budget.
- Requiring approval for over-budget spending.
- Allowing budget transfers between accounts.
- Tracking budget revisions.

Budget changes shall be fully audited.

#### 3.18.12 Bank Accounts
The system shall allow each school to configure bank accounts.

Each bank account shall include:
- Bank Name
- Branch
- Account Number
- Account Name
- Currency
- Ledger Account Mapping
- Opening Balance
- Active Status

Bank accounts shall be linked to payment processing, supplier payments, payroll payments and reconciliation.

#### 3.18.13 Bank Reconciliation
The system shall support bank reconciliation.

The reconciliation process shall compare:
- System bank ledger transactions
- Bank statement transactions
- Deposits
- Withdrawals
- Bank charges
- Interest
- Reversals
- Unmatched transactions

Reconciliation statuses shall include:
- Unreconciled
- Matched
- Partially Matched
- Disputed
- Reconciled

Finance Officers shall be able to upload or manually enter bank statement transactions.

#### 3.18.14 Multi-Currency Accounting
The system shall support multi-currency accounting.

Initially supported currencies:
- USD
- ZiG

The system shall:
- Preserve original transaction currency.
- Store exchange rate used.
- Calculate base currency equivalent.
- Support currency-specific bank accounts.
- Record exchange gains or losses where applicable.

Exchange rates shall be configurable through Finance Settings.

#### 3.18.15 Accounting Periods
The system shall support accounting periods.

Accounting periods may be configured by:
- Month
- Term
- Quarter
- Academic Year
- Financial Year

Each period shall have a status:
- Open
- Closed
- Locked
- Reopened

Only authorised users shall close or reopen accounting periods.

#### 3.18.16 Financial Statements
The system shall generate standard financial statements, including:
- Trial Balance
- Income Statement
- Statement of Financial Position / Balance Sheet
- Cash Flow Statement
- General Ledger Report
- Account Transactions Report
- Budget vs Actual Report
- Bank Reconciliation Report
- Accounts Receivable Report
- Accounts Payable Report

Reports shall support export to:
- PDF
- Excel
- CSV

#### 3.18.17 Financial Dashboard
The Accounting Dashboard shall display:
- Total Income
- Total Expenses
- Net Surplus / Deficit
- Cash and Bank Balances
- Accounts Receivable
- Accounts Payable
- Budget Utilisation
- Bank Reconciliation Status
- Recent Journal Entries
- Pending Approvals
- Monthly Income and Expense Trends

Dashboard data shall respect user permissions and school tenant boundaries.

#### 3.18.18 Financial Controls
The system shall enforce financial controls.

Controls shall include:
- Segregation of duties.
- Approval workflows.
- Posting restrictions.
- Period closing controls.
- Reversal controls.
- Audit logging.
- Role-based access.
- Tenant-level data isolation.
- Sequential numbering of journals and accounting documents.

No posted accounting transaction shall be permanently deleted.

#### 3.18.19 Approval Workflows
The system shall support approval workflows for:
- Journal entries
- Budget approvals
- Budget revisions
- Supplier payments
- Bank reconciliations
- Accounting period closure
- Transaction reversals

Each approval shall record:
- Requester
- Approver
- Date and Time
- Status
- Comments
- Reason

Approval workflows shall be configurable by school.

#### 3.18.20 Numbering Sequences
The system shall generate unique sequential numbers for:
- Journal Entries
- Bank Reconciliations
- Budget Records
- Reversals
- Adjustment Entries
- Financial Period Closures

Numbering sequences shall be unique within each school tenant.

#### 3.18.21 Offline Support
Where offline capability is enabled, the module shall allow authorised users to capture selected accounting transactions offline.

Offline records shall:
- Be queued locally.
- Sync when connectivity is restored.
- Preserve timestamps.
- Detect conflicts.
- Prevent duplicate postings.
- Require validation before final posting.

Critical actions such as period closure and final approval may require online verification.

#### 3.18.22 User Permissions
| Role | Permissions |
| --- | --- |
| Super Administrator | Full access across all tenants where authorised |
| School Administrator | View accounting dashboards and supervise finance operations |
| Finance Officer | Manage journals, ledgers, budgets, reconciliations and reports |
| Accountant | Manage chart of accounts, postings, reconciliations and financial statements |
| Cashier | View limited payment-related accounting records only |
| Procurement Officer | View procurement-related financial records only |
| Payroll Officer | View payroll-related financial records only |
| Auditor | Read-only access to accounting records and audit logs |
| Parent | No access to internal accounting records |
| Student | No access to internal accounting records |

#### 3.18.23 Audit Logging
The system shall record all accounting activities.

Audit events shall include:
- Chart of accounts creation.
- Chart of accounts updates.
- Journal creation.
- Journal approval.
- Journal posting.
- Journal reversal.
- Budget creation.
- Budget approval.
- Budget revision.
- Bank reconciliation.
- Period closure.
- Period reopening.
- Financial report generation.

Each audit record shall include:
- User
- Date and Time
- School Tenant
- Module
- Action
- Transaction Number
- Previous Value
- New Value
- Reason
- IP Address / Device Identifier where available

#### 3.18.24 Testing Requirements
The module shall be tested to verify:
- Chart of accounts configuration.
- Journal entry creation.
- Debit and credit balancing.
- Journal approval and posting.
- Ledger updates.
- Fee transaction postings.
- Payroll transaction postings.
- Procurement transaction postings.
- Budget creation and variance reporting.
- Bank reconciliation.
- Multi-currency accounting.
- Exchange rate calculations.
- Financial statement generation.
- Accounting period closure.
- Permission enforcement.
- Audit logging.
- Offline sync where enabled.

#### 3.18.25 Acceptance Criteria
The Accounting and General Ledger Module shall be considered complete when:
- Each school tenant can configure its own chart of accounts.
- Journal entries can be created, approved, posted and reversed.
- The system enforces balanced debit and credit postings.
- Fees, payroll and procurement transactions post correctly to the ledger.
- Bank accounts and reconciliations are managed accurately.
- Budgets can be created, approved and monitored against actual performance.
- Financial statements are generated accurately.
- Multi-currency transactions preserve original currency and exchange rate values.
- Closed periods prevent unauthorised posting.
- All accounting activities are recorded in the audit log.
- Reports can be exported to PDF, Excel and CSV.
- The module integrates seamlessly with Fees Management, Payroll, Procurement, Reporting, Audit Logging and the SaaS module architecture.

**End of Section 3.18**

---

### 3.19 Procurement and Supplier Management
#### 3.19.1 Overview
The Procurement and Supplier Management Module shall provide a complete procurement lifecycle for acquiring goods and services required by the school. The module shall manage supplier registration, purchase requisitions, quotations, purchase orders, goods receipts, supplier invoices, supplier payments, procurement reporting and procurement audit controls.

The module shall integrate with Inventory Management, Accounting, Budgeting, Fixed Assets, Payments, Audit Logging and the SaaS Module Management System.

#### 3.19.2 Objectives
The Procurement Module shall:
- Manage supplier records and preferred supplier lists.
- Create purchase requisitions with automatic numbering.
- Support multi-level approval workflows.
- Verify budgets before final approval.
- Manage supplier quotations and quotation comparison.
- Generate sequential purchase orders.
- Record goods received and inspection notes.
- Match purchase orders, goods receipts and supplier invoices.
- Process supplier payments.
- Integrate with inventory and accounting.
- Maintain complete procurement audit history.

#### 3.19.3 Supplier Management
The system shall maintain a Supplier Register including supplier code, supplier name, company registration number, tax number, contact person, mobile number, email address, physical address, postal address, bank details, payment terms, supplier category, preferred supplier status, performance score and supplier status.

Supplier categories shall be configurable and may include Stationery, Uniforms, Food Supplies, ICT Equipment, Laboratory Equipment, Furniture, Building Materials, Fuel, Transport Services and Maintenance Services.

#### 3.19.4 Purchase Requisition
Departments shall request goods and services through purchase requisitions. Each requisition shall include a requisition number, request date, department, requested by, item description, quantity, estimated cost, priority, justification, required date and approval status.

Requisition numbers shall be generated automatically.

#### 3.19.5 Approval Workflow
The procurement workflow shall support:
- Department Request
- Department Head Approval
- Finance Verification
- Budget Availability Check
- School Administrator Approval
- Purchase Order Creation
- Supplier Selection
- Goods Delivery
- Goods Inspection
- Inventory Update
- Supplier Invoice
- Payment

Approval stages shall be configurable and may vary according to transaction value.

#### 3.19.6 Budget Verification
Before approval, the system shall verify department budget, remaining budget, available funds and procurement limits. Purchases exceeding the approved budget shall require higher-level override approval.

#### 3.19.7 Quotation Management
The system shall support supplier quotations. Quotations shall include supplier, item, unit price, total price, delivery period, warranty and validity period. The system shall compare quotations automatically and allow the selected quotation to drive the purchase order.

#### 3.19.8 Purchase Order Management
Approved requisitions shall generate purchase orders. Purchase orders shall include purchase order number, supplier, delivery address, delivery date, ordered items, quantity, unit price, total amount, payment terms and approval details.

Purchase order numbers shall be sequential and unique.

#### 3.19.9 Goods Receipt
Receiving officers shall record goods receipt number, purchase order, supplier, delivery date, items received, quantity received, quantity rejected and inspection notes. Accepted goods shall update inventory automatically.

#### 3.19.10 Inventory Integration
Upon successful goods receipt, the Inventory Module shall update current stock, stock value, batch or serial details where applicable and store location.

#### 3.19.11 Supplier Invoice Management
Supplier invoices shall record invoice number, supplier, purchase order, goods receipt reference, invoice date, due date, amount, tax and status.

The system shall enforce three-way matching:

`Purchase Order -> Goods Receipt -> Supplier Invoice`

Only matched invoices shall proceed to payment unless an authorised override is recorded.

#### 3.19.12 Supplier Payments
Supplier payments shall support bank transfer, cheque, cash and mobile money. Each payment shall record payment voucher number, supplier, invoice reference, payment date, payment method, amount, bank account and authorised by.

Payments shall update Accounts Payable, General Ledger, Cash Book and Bank Accounts.

#### 3.19.13 Procurement Reports
The system shall generate supplier register, purchase requisition report, purchase order report, goods receipt report, outstanding purchase orders, supplier invoice report, supplier payment report, budget utilisation report, procurement summary, procurement by department and procurement by supplier.

Reports shall support PDF, Excel and CSV export.

#### 3.19.14 Dashboard Widgets
The Procurement Dashboard shall display pending requisitions, pending approvals, purchase orders issued, goods awaiting delivery, outstanding supplier payments, budget utilisation, monthly procurement value and top suppliers.

#### 3.19.15 Business Rules
The system shall enforce:
- Every purchase shall originate from an approved requisition.
- Budget availability shall be verified before approval.
- Purchase orders shall be generated only after approval.
- Goods receipts shall update inventory automatically.
- Supplier invoices shall match purchase orders and goods receipts before payment.
- Procurement history shall never be deleted.
- Financial transactions shall post automatically to Accounting.

#### 3.19.16 User Permissions
| Role | Permissions |
| --- | --- |
| Super Administrator | Full access |
| School Administrator | Approve procurement and oversee operations |
| Procurement Officer | Manage suppliers, requisitions, quotations and purchase orders |
| Finance Officer | Verify budgets and process supplier payments |
| Department Head | Create and approve requisitions for their department |
| Storekeeper | Record goods received and update inventory |
| Auditor | Read-only access to procurement records |

#### 3.19.17 Audit Logging
The system shall record supplier creation, supplier updates, requisition creation, approval actions, purchase order generation, goods receipt, invoice processing, supplier payment and procurement report generation.

Each audit record shall include user, date and time, school tenant, module, action, reference number, previous value, new value and reason where applicable.

#### 3.19.18 Testing Requirements
The module shall be tested to verify supplier registration, purchase requisition workflow, approval workflow, budget validation, quotation comparison, purchase order generation, goods receipt processing, inventory integration, supplier invoice matching, payment processing, accounting integration, report generation, permission enforcement and audit logging.

#### 3.19.19 Acceptance Criteria
The Procurement and Supplier Management Module shall be considered complete when suppliers can be managed, requisitions follow approval workflow, budget verification prevents unauthorised expenditure, purchase orders are generated only after approval, goods receipts update inventory, supplier invoices are matched, supplier payments update accounting, reports and dashboards reflect purchasing activity and all procurement actions are audited.

**End of Section 3.19**

---

### 3.20 Inventory and Store Management
#### 3.20.1 Overview
The Inventory and Store Management Module shall provide a complete solution for managing school inventory, stock movements, consumables, assets and store operations. The module shall monitor stock levels, automate stock transactions, manage multiple stores and provide real-time inventory visibility across the school.

The module shall integrate with Procurement, Accounting, Fixed Assets, Budget Management and Dashboard Analytics.

#### 3.20.2 Objectives
The Inventory Module shall:
- Manage inventory items and configurable categories.
- Support multiple stores.
- Track all stock movements.
- Manage stock levels and reorder alerts.
- Support stock receipts, issues, transfers, adjustments and counts.
- Support FIFO and weighted average valuation.
- Integrate with procurement and accounting.
- Maintain complete inventory audit history.

#### 3.20.3 Inventory Categories
The system shall support categories including Stationery, Uniforms, Books, Laboratory Equipment, Laboratory Chemicals, ICT Equipment, Sports Equipment, Furniture, Cleaning Materials, Food Supplies, Fuel and Lubricants, Maintenance Materials, Medical Supplies and Examination Materials.

Administrators shall create additional categories.

#### 3.20.4 Inventory Item Master
Each item shall include item code, item name, description, category, unit of measure, minimum stock level, maximum stock level, reorder level, purchase price, selling price where applicable, current quantity, store location, status, valuation method, barcode and QR code identifiers.

#### 3.20.5 Store Management
The system shall support multiple stores including Main Store, Uniform Store, Science Laboratory Store, ICT Store, Hostel Store, Sports Store and Canteen Store. Each store shall include store code, store name, storekeeper, location and status.

#### 3.20.6 Stock Receiving
Stock shall enter inventory through procurement goods receipts, donations, opening balances, transfers and authorised adjustments. Each receipt shall record receipt number, supplier, date, store, items received, quantity, unit cost and total cost.

#### 3.20.7 Stock Issues
Stock may be issued to departments, teachers, laboratories, hostel, sports, maintenance or school events. Each issue shall record issue number, date, requesting department, items issued, quantity, issued by and received by.

#### 3.20.8 Stock Transfers
The system shall support transfers between stores. Each transfer shall record transfer number, source store, destination store, items, quantity, date and approved by.

#### 3.20.9 Stock Adjustments
The system shall support damaged stock, lost stock, expired stock, stock corrections and inventory write-offs. Every adjustment shall require reason, approval and supporting notes.

#### 3.20.10 Stock Counts
The system shall support annual stock take, periodic stock counts, cycle counts and spot checks. Stock count variances shall generate adjustment recommendations.

#### 3.20.11 Reorder Management
The system shall monitor minimum stock levels, reorder levels and critical stock levels. When stock reaches reorder level, the system shall generate an alert, purchase recommendation and storekeeper notification.

#### 3.20.12 Inventory Valuation
The system shall support FIFO and weighted average cost valuation. Valuation reports shall show quantity on hand, unit cost and total stock value.

#### 3.20.13 Fixed Asset Integration
Capital purchases such as computers, vehicles, furniture and laboratory equipment may automatically become fixed assets for depreciation and asset management.

#### 3.20.14 Accounting Integration
Inventory transactions shall automatically generate accounting entries. Goods received shall debit Inventory and credit Accounts Payable. Stock issues shall debit Expense and credit Inventory. Write-offs shall debit Loss and credit Inventory.

#### 3.20.15 Reports
The system shall generate stock register, stock movement report, stock valuation report, reorder report, stock adjustment report, stock count variance report, store balance report, inventory consumption report, department usage report and inventory ageing report.

Reports shall support PDF, Excel and CSV export.

#### 3.20.16 Dashboard Widgets
The Inventory Dashboard shall display total inventory value, low stock items, out-of-stock items, pending reorders, recent stock movements, top consumed items, inventory by category and store utilisation.

#### 3.20.17 Business Rules
The system shall enforce:
- Negative stock is prohibited.
- Every stock movement must be recorded.
- Inventory adjustments require approval.
- Stock counts shall not delete historical records.
- Inventory valuation methods shall be configurable.
- Every inventory transaction shall update accounting automatically.

#### 3.20.18 User Permissions
| Role | Permissions |
| --- | --- |
| Super Administrator | Full access |
| School Administrator | Full inventory management |
| Storekeeper | Manage stock and stores |
| Procurement Officer | View inventory and reorder items |
| Finance Officer | View inventory value and reports |
| Department Head | Request stock |
| Auditor | Read-only access |

#### 3.20.19 Audit Logging
The system shall record item creation, stock receipts, stock issues, stock transfers, stock adjustments, stock counts, inventory valuation and reorder generation.

Each audit record shall include user, date and time, school tenant, module, action, reference number, previous value, new value and reason.

#### 3.20.20 Testing Requirements
The module shall be tested to verify item management, multi-store operations, stock receipts, stock issues, stock transfers, reorder alerts, stock counts, inventory valuation, accounting integration, report generation, permission enforcement and audit logging.

#### 3.20.21 Acceptance Criteria
The Inventory and Store Management Module shall be considered complete when inventory items and stores can be managed, stock levels update accurately, reorder alerts work correctly, inventory valuation is calculated correctly, stock counts and adjustments are auditable, inventory integrates with procurement and accounting, reports and dashboards display accurate inventory information and all inventory activities are audited.

**End of Section 3.20**

---

### 3.21 Human Resources Management (Premium Module)
#### 3.21.1 Overview
The Human Resources Management Module shall provide a comprehensive platform for managing employee information, recruitment, contracts, leave management, attendance, performance evaluations, disciplinary actions, training and staff records throughout the employee lifecycle.

The module shall support teaching and non-teaching staff and shall integrate with Payroll, Timetable, Teacher Management, Accounting, Notifications and Dashboard Analytics.

The Human Resources Module shall be classified as a Premium SaaS Module and shall only be available to schools subscribed to the Premium Package or higher.

#### 3.21.2 Objectives
The HR Module shall:
- Manage employee records.
- Manage staff recruitment.
- Manage contracts and expiry alerts.
- Manage leave applications and leave balances.
- Track staff attendance, lateness, absenteeism and overtime.
- Manage staff performance evaluations.
- Manage disciplinary actions.
- Manage staff training and certifications.
- Store staff documents.
- Generate HR reports.
- Integrate with Payroll and Accounting.

#### 3.21.3 Employee Categories
The system shall support academic staff, teachers, heads of department, deputy headmasters, headmaster, non-teaching staff, finance officers, administrators, secretaries, librarians, laboratory technicians, security personnel, drivers, cleaners and hostel staff.

#### 3.21.4 Employee Profile
Each employee profile shall contain employee number, title, names, gender, date of birth, national ID, marital status, address, phone number, email, employment date, department, position, employment type, contract type, qualification, specialisation, years of experience, next of kin and emergency contact details.

Employee numbers shall be unique.

#### 3.21.5 Recruitment Management
The system shall support vacancy creation, applicant management, interview scheduling, interview results, appointment approval and employee onboarding.

#### 3.21.6 Employment Contracts
The system shall manage permanent contracts, temporary contracts, part-time contracts, contract renewals and contract expiry notifications. Administrators shall be notified before contract expiry.

#### 3.21.7 Leave Management
The system shall support annual leave, sick leave, maternity leave, compassionate leave, study leave and unpaid leave.

The leave workflow shall be:

`Employee Application -> Supervisor Approval -> HR Approval -> Leave Calendar Updated -> Notification Sent`

Leave balances shall update automatically after HR approval.

#### 3.21.8 Staff Attendance
The system shall support daily attendance, clock in, clock out, late arrivals, overtime and absenteeism. The module shall remain future-ready for biometric devices, fingerprint systems and facial recognition.

#### 3.21.9 Performance Management
The system shall support performance reviews, teacher evaluations, KPI management, annual appraisals and promotion recommendations.

#### 3.21.10 Training Management
The system shall maintain training programs, workshops, seminars, professional development courses and certificates, including certificate expiry tracking.

#### 3.21.11 Disciplinary Management
The system shall support warnings, suspension, investigations, hearings and appeals. Historical disciplinary records shall never be deleted.

#### 3.21.12 Staff Documents
The system shall store employment contracts, qualifications, certificates, national IDs, CVs, performance reports and disciplinary documents.

#### 3.21.13 Dashboard Widgets
The HR Dashboard shall display total employees, teachers, non-teaching staff, employees on leave, contract expiry alerts, attendance statistics and performance reviews due.

#### 3.21.14 Reports
The system shall generate employee register, leave report, attendance report, performance report, contract expiry report, training report and disciplinary report. Reports shall support PDF, Excel and CSV export.

#### 3.21.15 Business Rules
The system shall enforce:
- Employee numbers shall be unique.
- Leave balances shall update automatically.
- Contract expiry alerts shall be generated automatically.
- Historical staff records shall never be deleted.
- HR shall integrate with Payroll and Teacher Management.

#### 3.21.16 User Permissions
| Role | Permissions |
| --- | --- |
| Super Administrator | Full Access |
| School Administrator | Full HR Management |
| HR Officer | Manage Employee Records |
| Head of Department | Approve Leave |
| Employee | View Own Records |
| Auditor | Read-Only Access |

#### 3.21.17 Audit Logging
The system shall record employee creation, employee updates, leave approvals, performance evaluations, contract changes, disciplinary actions and document uploads.

#### 3.21.18 Testing Requirements
The module shall be tested to verify employee creation, leave workflow, attendance tracking, contract management, performance reviews, training management, reporting, permission enforcement and audit logging.

#### 3.21.19 Acceptance Criteria
The HR Module shall be considered complete when employee records are managed successfully, leave management operates correctly, staff attendance is tracked accurately, performance evaluations are supported, HR reports are generated, historical records remain available, integration with Payroll and Teacher Management works and all activities are audited.

**Premium SaaS Rule:** The Human Resources Module shall be marked as Premium, hidden from schools without Premium subscriptions, removed from menus and dashboards when unsubscribed, and historical data shall be preserved if the subscription expires.

**End of Section 3.21**

---

### 3.22 Payroll Management (Premium Module)
#### 3.22.1 Overview
The Payroll Management Module shall provide a comprehensive payroll processing system for managing employee salaries, allowances, deductions, statutory obligations, loans, overtime and payslips. The module shall automate payroll calculations and integrate with Human Resources, Accounting and Banking.

The Payroll Module shall support teaching and non-teaching staff and Zimbabwean payroll requirements including PAYE, NSSA contributions, pension contributions, medical aid deductions, trade union deductions, staff loans and salary advances.

The Payroll Module shall be classified as a Premium SaaS Module and shall only be available to schools with an active Premium subscription or higher.

#### 3.22.2 Objectives
The Payroll Module shall:
- Manage salary structures.
- Process monthly payroll.
- Manage allowances and deductions.
- Generate payslips with QR verification and electronic stamp.
- Manage loans and salary advances.
- Calculate overtime.
- Calculate statutory deductions.
- Generate bank transfer files.
- Generate payroll reports.
- Integrate with Accounting and Banking.

#### 3.22.3 Employee Payroll Profile
Each employee payroll profile shall contain employee number, employee name, department, position, employment type, bank name, branch, account number, account name, optional mobile money number, basic salary, salary grade, payment method, tax status, pension scheme and medical aid scheme.

#### 3.22.4 Salary Structures
The system shall support multiple salary structures for teachers, administrators, finance officers, drivers, security personnel and general staff. Each structure shall include basic salary, housing allowance, transport allowance, responsibility allowance and other allowances.

#### 3.22.5 Allowance Management
The system shall support fixed and variable allowances including housing, transport, responsibility, communication, overtime, acting allowance, special duty allowance and performance bonus. Allowances may be taxable or non-taxable.

#### 3.22.6 Deduction Management
The system shall support PAYE, NSSA, pension, medical aid, loans, salary advance, union subscription, insurance and savings schemes. Deduction formulas shall be configurable.

#### 3.22.7 Payroll Processing Workflow
The workflow shall be:

`Open Payroll Period -> Import Attendance (Optional) -> Calculate Overtime -> Calculate Allowances -> Calculate Deductions -> Generate Payroll -> Review Payroll -> Approve Payroll -> Generate Payslips -> Post to Accounting -> Generate Bank Transfer File -> Close Payroll Period`

#### 3.22.8 Payroll Period Management
The system shall support monthly, weekly and fortnight payroll periods. Payroll periods shall include start date, end date, payroll status and approval status. Closed payroll periods shall become read-only.

#### 3.22.9 Overtime Management
The system shall support hourly overtime, daily overtime, weekend overtime and public holiday overtime. Overtime calculations shall be configurable.

#### 3.22.10 Loan Management
The system shall support staff loans, salary advances and emergency loans. Each loan shall record loan number, employee, loan amount, interest rate, repayment period, monthly deduction and outstanding balance. Loan deductions shall be processed automatically.

#### 3.22.11 Payroll Calculations
The system shall calculate gross salary as basic salary plus allowances and overtime. Net salary shall equal gross salary less deductions. Payroll formulas shall be configurable.

#### 3.22.12 Payslip Generation
Each payslip shall include employee information, employee number, employee name, department, position, basic salary, allowances, overtime, bonuses, PAYE, NSSA, pension, medical aid, loans, other deductions, gross pay, total deductions, net pay, payroll period, payslip number, QR code and electronic school stamp.

#### 3.22.13 Bank Transfer Files
The system shall generate CSV, Excel and future bank-specific transfer files. Files shall include employee, account number, bank and amount.

#### 3.22.14 Accounting Integration
Payroll posting shall automatically generate accounting entries. Salary expense shall debit Salaries Expense and credit Salaries Payable. Statutory deductions shall debit Salaries Payable and credit PAYE Payable, NSSA Payable and Pension Payable.

#### 3.22.15 Reports
The system shall generate payroll register, payslip register, salary analysis report, allowance report, deduction report, loan report, overtime report, PAYE report, NSSA report, pension report, bank transfer report and payroll summary. Reports shall support PDF, Excel and CSV export.

#### 3.22.16 Dashboard Widgets
The Payroll Dashboard shall display employees paid, total payroll cost, payroll by department, outstanding loans, overtime cost, statutory liabilities and payroll trends.

#### 3.22.17 Business Rules
The system shall enforce:
- Employee numbers shall be unique.
- Payroll periods shall not overlap.
- Closed payroll periods shall be read-only.
- Payroll approval shall be required before payment.
- Payslips cannot be modified after approval.
- Payroll postings shall update Accounting automatically.
- Historical payroll records shall never be deleted.

#### 3.22.18 User Permissions
| Role | Permissions |
| --- | --- |
| Super Administrator | Full Access |
| School Administrator | View Payroll |
| HR Officer | Maintain Employee Payroll Profiles |
| Payroll Officer | Process Payroll |
| Accountant | View and Post Payroll |
| Employee | View Own Payslips |
| Auditor | Read-Only Access |

#### 3.22.19 Audit Logging
The system shall record payroll creation, payroll approval, payslip generation, loan creation, loan deduction, salary changes, payroll posting and bank file generation.

#### 3.22.20 Testing Requirements
The module shall be tested to verify payroll calculations, allowance calculations, deduction calculations, loan deductions, payslip generation, accounting integration, bank file generation, report generation, permission enforcement and audit logging.

#### 3.22.21 Acceptance Criteria
The Payroll Module shall be considered complete when payroll calculations are accurate, statutory deductions are calculated correctly, payslips are generated, payroll integrates with Accounting, bank transfer files are generated, payroll reports are accurate, historical records remain available and all activities are recorded in audit logs.

**Premium SaaS Rule:** The Payroll Module shall be marked as Premium, hidden for schools without Premium subscriptions, preserve payroll data if subscriptions expire and automatically re-enable data when the subscription is renewed.

**End of Section 3.22**

### 3.29 Medical and School Clinic Management

#### 3.29.1 Overview
The Medical and School Clinic Management Module shall provide a secure platform for managing student and staff medical profiles, clinic visits, medication administration, emergencies, referrals, immunisations, appointments, sick bay admissions and medical attendance excuses. The module shall support both day-to-day clinic operations and emergency response, while preserving confidential health records throughout the learner or employee lifecycle.

The module shall integrate with Student Registration, Human Resources, Attendance, Inventory, Parent Portal, Notifications, Reporting, Audit Logging and the SaaS Module Management architecture.

#### 3.29.2 Objectives
The Medical Module shall:
- Maintain student and staff medical profiles.
- Track allergies, chronic illnesses, disabilities and emergency contacts.
- Record clinic visits and treatment notes.
- Manage medication stock and dispensing.
- Record medical emergencies and referrals.
- Manage immunisations and health appointments.
- Support sick bay admissions and discharges.
- Create attendance excuses for illness-related absence.
- Notify parents, guardians and authorised staff where required.
- Maintain privacy-aware medical audit logs.

#### 3.29.3 Medical Profiles
Each medical profile shall include the linked student or employee, blood group, allergies, chronic conditions, disabilities, current medication, family doctor, medical aid information, emergency contact details, consent status and clinical risk flags.

Each active student or employee shall have at most one active medical profile.

#### 3.29.4 Clinic Visits
The system shall record date and time, patient, visit type, symptoms, diagnosis, treatment, attending nurse, follow-up requirement, referral requirement and parent notification status.

Clinic visit numbers shall be unique and sequential within each school tenant.

#### 3.29.5 Medication Management
The module shall maintain clinic medication stock including medicine name, strength, dosage form, batch number, expiry date, quantity on hand, reorder level and optional inventory item link.

Medication dispensing shall reduce clinic stock immediately and shall block expired medicine, negative quantities and insufficient stock.

#### 3.29.6 Emergencies and Referrals
The system shall record emergencies including incident details, severity, first aid given, ambulance requirement, hospital destination, parent notification, outcome and responsible staff member.

The system shall support referrals to hospitals, doctors, counsellors, psychologists and external specialists. Referral notifications shall be generated for the relevant responsible person.

#### 3.29.7 Immunisation and Preventive Health
The system shall maintain immunisation records for vaccines, doses, administration dates, due dates, next dose dates, provider and certificate references.

The dashboard shall identify overdue and upcoming immunisations.

#### 3.29.8 Appointments and Sick Bay
The module shall manage medical appointments, follow-up visits, routine checks and sick bay admissions. Sick bay records shall track bed number, admission time, discharge time, observation notes and outcome.

#### 3.29.9 Attendance Integration
Authorised medical users shall generate medical attendance excuses. The system shall update attendance records as Sick or Excused where attendance integration is enabled and shall preserve the clinical reason in medical records.

#### 3.29.10 Dashboard Widgets
The Medical Dashboard shall display clinic visits today, active sick bay admissions, emergencies, low stock medications, expired medications, upcoming appointments, overdue immunisations and pending referrals.

#### 3.29.11 Reports
The system shall generate clinic visit reports, medication stock reports, medication dispensing reports, emergency reports, referral reports, immunisation reports, sick bay reports, attendance excuse reports and medical audit reports.

Reports shall support PDF, Excel and CSV export where applicable.

#### 3.29.12 Business Rules
The system shall enforce:
- Medical records shall be confidential and role-restricted.
- Medical records shall never be deleted; corrections shall be handled through authorised updates.
- Expired medication shall not be dispensed.
- Medication quantities shall not become negative.
- Emergency contacts shall be available on every medical profile.
- Parent or guardian notifications shall be recorded.
- Medical audit logs shall avoid storing unnecessary sensitive clinical detail.

#### 3.29.13 User Permissions
| Role | Permissions |
| --- | --- |
| Super Administrator | Full system access |
| School Administrator | Supervise medical operations |
| Nurse | Manage medical profiles, visits, medicine, emergencies and referrals |
| Headmaster | View operational medical summaries |
| Teacher | View limited emergency medical alerts |
| Parent | View authorised student medical notices |
| Student | View authorised personal medical notices |
| Auditor | Read-only access to authorised audit records |

#### 3.29.14 Audit Logging
The system shall record medical profile creation, profile updates, clinic visits, medication dispensing, emergency records, referrals, immunisations, appointments, sick bay admissions, attendance excuses and notifications.

Each audit record shall include user, date and time, school tenant, module, action, object reference, previous value, new value and reason where applicable.

#### 3.29.15 Testing Requirements
The module shall be tested to verify medical profile creation, clinic visit recording, medication dispensing controls, emergency workflows, referrals, immunisation due tracking, appointment scheduling, sick bay admissions, attendance integration, permissions and audit logging.

#### 3.29.16 Acceptance Criteria
The Medical Module shall be considered complete when medical profiles are managed securely, clinic visits and medication dispensing operate correctly, emergencies and referrals are recorded, stock controls prevent unsafe dispensing, attendance excuses integrate with attendance records, reports are available and all medical activities are audit logged.

**End of Section 3.29**

### 3.30 SaaS Subscription and Module Management

#### 3.30.1 Overview
The SaaS Subscription and Module Management Module shall provide a multi-tenant administration platform for managing school tenants, subscription plans, module availability, premium feature gating, subscription billing, renewals, usage tracking, branding and SaaS audit controls.

The module shall allow Raydon School Management System to operate as a configurable SaaS platform where each school may subscribe to the modules required for its package while preserving tenant isolation, historical data and operational continuity.

#### 3.30.2 Objectives
The SaaS Module shall:
- Manage school tenant profiles.
- Manage subscription plans and billing cycles.
- Define compulsory, standard and premium modules.
- Activate and deactivate modules per tenant.
- Enforce module dependencies.
- Hide unsubscribed modules from menus and dashboards.
- Preserve historical data when subscriptions expire.
- Manage subscription invoices and payments.
- Track tenant usage metrics.
- Support custom school branding.
- Maintain SaaS audit logs.

#### 3.30.3 Tenant Management
Each school tenant shall record school name, school code, registration number, ministry number, school type, province, district, contact details, operating domain, database identifier, active status, subscription tier, subscription dates and branding settings.

Tenant data shall remain logically separated from other schools.

#### 3.30.4 Subscription Plans
The system shall support Starter, Standard, Premium, Enterprise, Custom and legacy package mappings where required. Each plan shall define module access, billing cycle, base price, currency, student limit, staff limit, storage limit and premium module permissions.

#### 3.30.5 Module Definitions
Each module definition shall include module code, module name, category, description, premium flag, compulsory flag, menu visibility flag, dependency modules, display order and active status.

Compulsory modules shall not be disabled for active tenants.

#### 3.30.6 Module Activation Workflow
The workflow shall be:

`Tenant Created -> Subscription Assigned -> Compulsory Modules Enabled -> Optional Modules Selected -> Dependency Check -> Premium Check -> Module Activated -> Menus Updated -> Audit Log Recorded`

#### 3.30.7 Premium Module Rules
Premium modules such as Human Resources, Payroll, Advanced Business Intelligence, API Integrations and Custom Branding shall only be available to tenants with eligible plans.

When a subscription expires, premium modules shall be hidden but historical data shall remain preserved and shall become available again after renewal.

#### 3.30.8 Module Dependencies
The system shall enforce dependencies such as Payroll requiring Human Resources, Library Fines requiring Fees Management, Transport Fees requiring Fees Management and Asset Depreciation requiring Accounting.

Dependency activation shall occur automatically when authorised by the tenant plan.

#### 3.30.9 SaaS Billing
The system shall generate subscription invoices with invoice number, tenant, plan, billing period, issue date, due date, currency, amount due, amount paid and status.

The system shall record subscription payments, payment references, payment methods, received by, receipt status and payment allocation.

#### 3.30.10 Usage Tracking
The system shall capture usage snapshots including student count, staff count, active users, enabled modules, storage usage, invoice count, payment count and reporting period.

Usage metrics shall support billing decisions, capacity planning and dashboard analytics.

#### 3.30.11 Branding and Customisation
Eligible tenants shall configure school logo, report header, electronic stamp, colour theme and portal display settings. Branding shall apply to reports, receipts, payslips and tenant-facing portals where configured.

#### 3.30.12 Dashboard Widgets
The SaaS Dashboard shall display active tenants, expired subscriptions, trial tenants, premium module usage, monthly recurring revenue, unpaid subscription invoices, module adoption, tenant usage trends and renewal alerts.

#### 3.30.13 Reports
The system shall generate tenant register, subscription status report, module activation report, premium module report, subscription invoice report, payment report, usage report, renewal report and SaaS audit report.

Reports shall support PDF, Excel and CSV export where applicable.

#### 3.30.14 Business Rules
The system shall enforce:
- Every school tenant shall have a subscription status.
- Compulsory modules shall remain enabled.
- Premium modules shall require eligible subscriptions.
- Module dependencies shall be satisfied before activation.
- Subscription invoices and payments shall be sequentially numbered.
- Expired subscriptions shall not delete historical tenant data.
- Renewed subscriptions shall restore authorised module access.
- Module visibility shall respect subscription state and permissions.

#### 3.30.15 User Permissions
| Role | Permissions |
| --- | --- |
| Super Administrator | Full SaaS administration |
| SaaS Administrator | Manage tenants, plans, modules and billing |
| School Administrator | View own subscription and enabled modules |
| Finance Officer | View and record subscription billing where authorised |
| Auditor | Read-only SaaS audit access |

#### 3.30.16 Audit Logging
The system shall record tenant creation, tenant updates, subscription creation, subscription renewal, module activation, module deactivation, invoice generation, subscription payment, branding changes and usage snapshot generation.

Each audit record shall include user, date and time, tenant, module, action, object reference, previous value, new value and reason where applicable.

#### 3.30.17 Testing Requirements
The module shall be tested to verify tenant creation, subscription assignment, compulsory module enforcement, premium module gating, dependency activation, module visibility, invoice creation, payment recording, renewal processing, usage snapshot creation, permissions and audit logging.

#### 3.30.18 Acceptance Criteria
The SaaS Subscription and Module Management Module shall be considered complete when tenants are managed correctly, subscription plans control module access, premium modules are gated correctly, dependencies are enforced, subscription billing and payments are recorded, usage tracking is available, historical data is preserved after expiry and all SaaS actions are audit logged.

**End of Section 3.30**

### 3.31 System Administration and Security

#### 3.31.1 Overview
The System Administration and Security Module shall provide comprehensive administration, configuration, user management, authentication, authorisation, security monitoring and system auditing capabilities for the Raydon School Management System.

The module shall protect confidentiality, integrity and availability of school data across multi-school SaaS deployments.

#### 3.31.2 Objectives
The module shall manage users, roles, permissions, authentication, password policies, session controls, account security, system configuration, API credentials, file security, notifications, security reports and audit trails.

#### 3.31.3 User Management
The system shall support user registration, activation, suspension, deactivation and reinstatement. Each user shall record user ID, username, full name, email address, phone number, role, school tenant, status and last login details.

#### 3.31.4 User Types
The system shall support Super Administrator, SaaS Administrator, School Administrator, Academic Administrator, Finance Officer, Accountant, HR Officer, Payroll Officer, Teacher, Hostel Warden, Librarian, Transport Manager, Student, Parent and Auditor.

#### 3.31.5 Role-Based Access Control
The system shall support module-level, menu-level, page-level, action-level and record-level permissions. Supported actions shall include create, read, update, delete, approve, export and print.

#### 3.31.6 Permission Management
Administrators shall create roles, edit roles, assign permissions, remove permissions, clone roles and create custom roles. Role inheritance shall allow child roles to be based on existing roles.

#### 3.31.7 Authentication and MFA
The system shall support username/password authentication, email authentication, multi-factor authentication devices, OTP-ready flows and future single sign-on integration.

#### 3.31.8 Password Management
Password policies shall define minimum length, uppercase requirements, lowercase requirements, numeric requirements, special character requirements, password expiry, password history, failed login limits and lockout duration.

#### 3.31.9 Password Recovery
The system shall support reset links, OTP verification and optional security questions. Password reset activities shall generate security notifications and audit logs.

#### 3.31.10 Session Management
The system shall support session timeout, automatic logout, concurrent session detection, session termination, remember-me options, IP tracking, user-agent tracking and device fingerprint references.

#### 3.31.11 Account Security
The system shall support account lockout, failed login monitoring, suspicious login detection, IP address monitoring, device monitoring and security incident creation.

#### 3.31.12 System Configuration
Administrators shall configure school information, academic years, terms, grading systems, fee structures, currency settings, notification settings, security policies and audit policies.

#### 3.31.13 Security Policies
The system shall enforce password policies, session policies, data retention policies, user access policies, backup policies, audit policies and API rate limits.

#### 3.31.14 Data Protection
Sensitive records such as passwords, financial records, medical records, counselling records and authentication tokens shall be protected through appropriate hashing, access restrictions, secure storage and audit controls.

#### 3.31.15 API Security
The system shall support API credentials, token hashing, token expiry, API permissions, rate limits and future JWT/SSO integration.

#### 3.31.16 File Security
The system shall support allowed file extensions, file size limits, future virus scanning and secure file downloads.

#### 3.31.17 Login History
The system shall record user, username, date and time, IP address, device, browser, geolocation, status and failure reason for login attempts.

#### 3.31.18 Security Monitoring
The system shall monitor failed logins, account lockouts, permission changes, suspicious activities, data exports, unusual usage patterns and active security incidents.

#### 3.31.19 Notifications
Automatic notifications shall be generated for password reset, failed login attempts, new device login, permission changes, account suspension and security incidents.

#### 3.31.20 Reports
The system shall generate user register, user activity report, login history report, permission report, security incident report, system configuration report and suspicious activity report. Reports shall support PDF, Excel and CSV export where applicable.

#### 3.31.21 Dashboard Widgets
The Security Dashboard shall display total users, active users, online users, failed login attempts, locked accounts, security alerts and recent user activity.

#### 3.31.22 Business Rules
The system shall enforce:
- Usernames shall be unique.
- Email addresses shall be unique.
- Users shall only access authorised modules.
- Sensitive information shall be protected.
- Failed login thresholds shall lock accounts automatically.
- User activities and security events shall be audited.
- Historical audit records shall never be deleted.

#### 3.31.23 User Permissions
| Role | Permissions |
| --- | --- |
| Super Administrator | Full System Access |
| SaaS Administrator | Multi-school administration |
| School Administrator | School administration |
| Auditor | Read-only security and audit access |

#### 3.31.24 Audit Logging
The system shall record user creation, user updates, permission changes, login attempts, password changes, role assignments, system configuration changes, API key creation, session termination and security incidents.

#### 3.31.25 Testing Requirements
The module shall be tested to verify user management, authentication controls, authorisation, password policies, session management, role management, security monitoring, API credential management, reports and audit logging.

#### 3.31.26 Acceptance Criteria
The System Administration and Security Module shall be considered complete when user and role management work correctly, authentication and authorisation are secure, password policies are enforced, security monitoring functions correctly, audit logs capture critical activities, reports and dashboards are accurate, sensitive information is protected and the module supports future multi-school SaaS deployment.

**End of Section 3.31**

### 3.32 Reports and Business Intelligence (BI)

#### 3.32.1 Overview
The Reports and Business Intelligence Module shall provide comprehensive reporting, analytics, dashboards, KPI monitoring, scheduled reporting, predictive insights and decision-support capabilities across all operational modules.

The BI platform shall collect and analyse data from academic, financial, HR, payroll, library, hostel, transport, medical, asset, SaaS and security modules.

#### 3.32.2 Objectives
The BI Module shall generate operational reports, management reports, real-time dashboards, graphical analytics, KPI monitoring, custom reports, scheduled reports, predictive analytics and executive summaries.

#### 3.32.3 Dashboard Categories
The system shall support Executive, Academic, Financial, Human Resources, Student, Parent, Library, Hostel, Transport, Medical and SaaS Administration dashboards.

#### 3.32.4 Executive Dashboard
The Executive Dashboard shall display total students, total staff, revenue collected, outstanding fees, examination pass rate, attendance rate, enrolment trends, subscription status and system health indicators.

#### 3.32.5 Academic Dashboard
The Academic Dashboard shall display student enrolment, subject registration statistics, class performance, teacher performance, pass rates, ZIMSEC analysis, examination statistics, attendance trends and dropout statistics.

#### 3.32.6 Financial Dashboard
The Financial Dashboard shall display revenue collected, outstanding balances, arrears, collection trends, expense analysis, budget utilisation, cash position, profit and loss summary and payment method analysis.

#### 3.32.7 Human Resources Dashboard
The HR Dashboard shall display total employees, teachers, non-teaching staff, leave statistics, payroll costs, attendance statistics, training statistics and performance indicators.

#### 3.32.8 Student Analytics
The system shall analyse enrolment trends, gender distribution, form distribution, stream distribution, promotion rates, dropout rates and student movement.

#### 3.32.9 Examination and ZIMSEC Analytics
The system shall analyse subject performance, pass rates, failure rates, merit analysis, distinction analysis, form performance, stream performance, teacher performance, O Level analysis, A Level analysis, points distribution, university qualification statistics and historical trends.

#### 3.32.10 Attendance and Behaviour Analytics
The system shall analyse student attendance, teacher attendance, chronic absenteeism, attendance trends, discipline trends, repeat offenders, suspension statistics, behaviour categories and counselling statistics.

#### 3.32.11 Operational Analytics
The system shall provide financial, library, transport, hostel, medical, asset and SaaS analytics including revenue trends, collection rates, route utilisation, occupancy, clinic visits, medication usage, asset values, subscription revenue and module usage.

#### 3.32.12 Report Designer
The system shall support custom report templates, selected fields, filters, saved reports, shared reports and report parameters.

#### 3.32.13 Report Scheduling
Users shall schedule reports daily, weekly, monthly, quarterly and annually. Reports may be delivered through system notifications, email in future releases and the download centre.

#### 3.32.14 Report Export
The system shall support PDF, Excel, CSV and Word export where applicable.

#### 3.32.15 Data Visualisation
The system shall support bar charts, pie charts, line graphs, area charts, heat maps, KPI cards and tabular reports.

#### 3.32.16 Predictive Analytics
The system shall support student performance prediction, dropout prediction, fee collection forecasting, enrolment forecasting, resource utilisation forecasting and future SaaS churn prediction.

#### 3.32.17 Key Performance Indicators
The system shall support pass rate, collection rate, student retention rate, teacher attendance rate, student attendance rate, revenue growth, expense ratio and resource utilisation KPIs.

#### 3.32.18 Data Refresh
The system shall refresh dashboard and analytics snapshots automatically or on demand and shall maintain data refresh logs.

#### 3.32.19 Dashboard Widgets
Dashboards shall support KPI cards, charts, tables and configurable widgets with module-level permissions.

#### 3.32.20 Reports
The system shall generate operational, management, academic, financial, HR, payroll, library, hostel, transport, medical, asset, SaaS and audit reports.

#### 3.32.21 Business Rules
The system shall enforce:
- Reports shall respect user permissions.
- Users shall only access authorised data.
- Scheduled reports shall execute automatically.
- Historical report executions shall remain available.
- Data shall be refreshed automatically or on demand.
- Report exports shall be audit logged.

#### 3.32.22 User Permissions
| Role | Permissions |
| --- | --- |
| Super Administrator | Full Access |
| School Administrator | Full Reporting |
| Academic Administrator | Academic Reports |
| Finance Officer | Financial Reports |
| HR Officer | HR Reports |
| Teacher | Limited Reports |
| Parent | Child Reports Only |
| Student | Personal Reports Only |
| Auditor | Read-Only Access |

#### 3.32.23 Audit Logging
The system shall record report generation, report export, scheduled reports, dashboard access, report customisation, analytics execution and predictive insight generation.

#### 3.32.24 Testing Requirements
The module shall be tested to verify dashboard functionality, report generation, scheduling, data visualisation metadata, analytics snapshots, export formats, permission enforcement and audit logging.

#### 3.32.25 Acceptance Criteria
The Reports and Business Intelligence Module shall be considered complete when reports are generated accurately, dashboards display current information, analytics provide meaningful insights, predictive analytics records are supported, scheduled reports work properly, permissions are enforced, historical reports remain available and all activities are recorded in audit logs.

**End of Section 3.32**
