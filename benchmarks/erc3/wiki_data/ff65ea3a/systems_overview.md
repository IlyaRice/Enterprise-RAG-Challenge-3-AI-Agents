# Systems Overview

Bellini Coatings runs its core business on a set of **legacy but robust systems** built on **Progress OpenEdge** more than 30 years ago. These systems are centralised at HQ and accessed from Italy, Serbia and all EU branches.

The main systems visible to most employees are:

- **CRM – Customer Relationship Management**
- **Project Registry**
- **Employee Registry (including skills & wills)**
- **Time Tracking / Timesheets**
- **Knowledge Base / Wiki**
- **Chatbot Interface (new layer over existing systems)**

## Design principles

1. **Single source of truth**
   - Each type of information has a “home” system (e.g. customer data in CRM, people data in employee registry).
2. **Stability over novelty**
   - The core systems are old but extremely stable. We minimise risky changes.
3. **Progressive modernisation**
   - New initiatives (like the chatbot) sit **on top of** existing systems rather than replacing them immediately.

## System roles and access

Every employee with system access has:

- A **user account** mapped to an internal employee ID.
- A **location** and **department** associated with their profile.
- One or more **system roles** (e.g. “SalesUser”, “R&DUser”, “HRAdmin”, “ITAdmin”).

Access is granted according to job needs and is centrally managed by IT in coordination with HR and managers.

## Relationship between systems

At a high level:

- The **CRM** stores customers and basic opportunities.
- The **project registry** tracks all major customer and internal projects.
- The **employee registry** stores employee profiles, including skills, wills, salary, department and location.
- The **time tracking** system records how employees spend their time across projects and internal activities.
- The **wiki** stores process documentation, guidelines, case studies and reference material.
- The **chatbot** reads from and writes to these systems via APIs and uses the wiki for context and explanations.

For detailed instructions on each system, refer to the dedicated pages in this section.
