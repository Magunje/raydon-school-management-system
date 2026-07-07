# Software Requirements Specification (SRS)
## Raydon School Management System Enterprise Edition
### Volume 1: Chapters 1 to 3.16

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
