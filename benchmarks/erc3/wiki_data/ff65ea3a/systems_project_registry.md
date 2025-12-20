# Project Registry

The **project registry** is the central place where Bellini tracks all significant **customer and internal work** as projects.

## What is a project?

A project is any substantial piece of work that:

- Requires coordinated effort across multiple people or departments, and/or
- Represents a distinct opportunity, development or contract.

Examples:

- Developing a new high‑temperature coating for a machinery OEM.
- Implementing a new floor coating system at a large warehouse.
- Internal R&D initiatives (e.g. new low‑VOC formulation series).
- Internal process or IT projects (e.g. chatbot pilot, warehouse re‑layout).
- Departmental initiatives (e.g. “HR – Training 2025”).

## Core project fields

Each project has:

- Project ID (internal)
- Name
- Linked customer (if applicable)
- Description / brief
- Status (aligned with deal phases):
  - `idea`
  - `exploring`
  - `active`
  - `paused`
  - `archived`
- Project manager (employee ID)
- Team and workloads:
  - Which employees are assigned
  - Their role (Lead, Engineer, Designer, QA, Ops, Other)
  - Their approximate time slice (fraction of an FTE)

## Why the project registry matters

- **Planning and workload**
  - Managers can see who is involved in which projects and at what intensity.
- **Visibility**
  - Sales, R&D, production and management can all see key projects and their status.
- **Reporting**
  - Combined with time tracking, the registry supports cost and effort analysis by project and customer.

## Project types

While the system uses a single “project” concept, we distinguish informally between:

- **Customer development projects**
  - New or adapted formulations, trials and approvals.
- **Customer supply projects**
  - Ongoing contracts where time is logged for support and technical visits.
- **Internal R&D projects**
  - Platform developments, testing programmes, regulatory updates.
- **Internal process / IT projects**
  - Improvements in production, logistics, quality, HR, IT and digitalisation.

## Workload

Employee workload in Bellini Coatings is determined by analysing **their allocated FTE slices across all active projects**. Each project stores, as part of its team definition, a list of `Workload` entries:

* `Employee` – the employee ID
* `TimeSlice` – the fraction of a full-time equivalent (FTE) that the employee is expected to contribute to that project (e.g. 0.1, 0.3, 0.5, 1.0)
* `Role` – the project role (Lead, Engineer, QA, Ops, Other)

These allocations are defined and maintained in the **project registry**, which is the system of record for planned workload assignments.

### How total workload is computed

1. **Collect all projects** where the employee appears in the team list, excluding archived projects unless explicitly included in reporting.
   Projects can be in phases such as `idea`, `exploring`, `active`, or `paused`. Only `active` (and sometimes `exploring`) projects are normally counted toward real workload.

2. **Extract each `TimeSlice` value** for the employee from every such project.
   For example, if an employee is allocated:

  * 0.5 FTE in Project A
  * 0.3 FTE in Project B
  * 0.2 FTE in Project C

   then their planned workload totals **1.0 FTE**.

3. **Sum all FTE slices** to determine the employee’s **aggregate planned workload**.
   This provides a quick view of whether someone is under-allocated, fully allocated, or overloaded.

4. **Compare allocations to actual time spent** (from time tracking) when needed.
   The time tracking system records real hours spent on each project and customer, which can be aggregated by employee. This allows managers to reconcile planned vs. actual workload.

### Why this method is used

* It aligns with the project-centric way Bellini plans work: projects define who is involved and at what intensity.
* It provides a **forward-looking view** of workload independent of time logs, which reflect past activity.
* It supports cross-department planning, since employees often contribute to multiple projects concurrently.

### How the workload data is used

* **Resource planning:** Department leads and project managers identify overload situations early.
* **Staffing decisions:** R&D, Sales, and Technical Service use workload figures to decide who can be assigned to new initiatives.
* **Chatbot queries:** The chatbot can answer questions such as “Who is overloaded?” or “What is Sara Romano’s workload across current projects?” by directly aggregating `TimeSlice` values from the project registry.

## Responsibilities

- **Project manager:**
  - Ensures the project is created correctly and linked to the right customer.
  - Keeps the **status** up to date as the project progresses.
  - Maintains a meaningful **description** that others can understand.
- **Team members:**
  - Log time against the correct project.
  - Flag missing or incorrect project data to their manager or the project manager.
- **Department leaders:**
  - Review project portfolios to avoid overload and to prioritise work.

## Chatbot examples

The chatbot can help by answering questions such as:

- “List all active projects for Customer FerroRail in Germany.”
- “Show the team and workloads for project P‑2025‑017.”
- “Which projects is E0221 (Sara Romano) currently assigned to as Lead?”

It does this by querying the project registry and linking results to employees and customers.
