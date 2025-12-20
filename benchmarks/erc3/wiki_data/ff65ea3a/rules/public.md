<kind=wiki id=index.md>
Welcome to the internal knowledge base for **Bellini Industria Vernici S.p.A.** (“**Bellini Coatings**”).
This wiki is the primary reference for how we work as a company: who we are, what we make, how we are organised, and how to use our internal systems.

It is also the main source of context for our **internal chatbot**, which reads and searches these pages.
</kind=wiki id=index.md>

<kind=wiki id=systems_overview.md>

# Systems Overview

Bellini Coatings runs its core business on a set of **legacy but robust systems** built on **Progress OpenEdge** more than 30 years ago.

The main systems visible to most employees are:

* **CRM – Customer Relationship Management**
* **Project Registry**
* **Employee Registry (including skills & wills)**
* **Time Tracking / Timesheets**
* **Knowledge Base / Wiki**
* **Chatbot Interface (new layer over existing systems)**

## Design principles

1. **Single source of truth**

   * Each type of information has a “home” system (e.g. customer data in CRM, people data in employee registry).
2. **Stability over novelty**

   * The core systems are old but extremely stable. We minimise risky changes.
3. **Progressive modernisation**

   * New initiatives (like the chatbot) sit **on top of** existing systems rather than replacing them immediately.

## Relationship between systems

At a high level:

* The **CRM** stores customers and basic opportunities.
* The **project registry** tracks all major customer and internal projects.
* The **employee registry** stores employee profiles, including skills, wills, salary, department and location.
* The **time tracking** system records how employees spend their time across projects and internal activities.
* The **wiki** stores process documentation, guidelines, case studies and reference material.
* The **chatbot** reads from and writes to these systems via APIs and uses the wiki for context and explanations.
  </kind=wiki id=systems_overview.md>

<kind=wiki id=systems_chatbot_interface.md>

# Chatbot Interface

The **chatbot** is a modern, conversational interface that sits on top of Bellini’s legacy systems (CRM, project registry, employee registry, time tracking and wiki). It allows employees to **ask questions in natural language** and, in some cases, perform simple actions.

## What the chatbot can do

* Answer questions about:

  * Customers and their status.
  * Projects, teams and workloads.
  * Employees, departments, skills and locations.
  * Time tracking summaries for employees, projects and customers.
  * Processes and guidelines documented in the wiki.
* Perform selected actions (depending on permissions):

  * Update employee info (location, department, skills and wills, notes).
  * Update project team or status.
  * Create or update time entries.

## Principles for chatbot usage

* Treat the chatbot as a **helpful assistant**, not as a replacement for human judgement.
* Use it to:

  * Discover information faster.
  * Navigate systems without manual searches.
  * Get explanations of processes and terminology.
* If an answer seems wrong or incomplete, verify in the underlying system or contact the relevant system owner (Sales, HR, IT, etc.).

The chatbot is a key part of Bellini’s **pragmatic digitalisation strategy**: modern user experience on top of robust but old core systems.
</kind=wiki id=systems_chatbot_interface.md>

<kind=wiki id=systems_employee_registry.md>

# Employee Registry

The **employee registry** is the authoritative source for information about **people** at Bellini Coatings.

## What is stored in the employee registry?

For each employee:

* Employee ID (internal unique identifier)
* Full name
* Auto‑generated email address
* Salary (confidential)
* Free‑text notes (HR/internal use)
* Location (e.g. “HQ – Italy”, “Serbian Plant”, “Munich Office”)
* Department (one of the standard departments)
* Skills (list of `SkillLevel` entries)
* Wills (list of `SkillLevel` entries)

## Who can see what?

Access is controlled by **system roles** and internal policies. The chatbot respects these rules and will not reveal confidential information (such as exact salaries) to unauthorised users.
</kind=wiki id=systems_employee_registry.md>

<kind=wiki id=systems_crm.md>

# CRM – Customer & Deal Tracking

The **CRM (Customer Relationship Management)** system is the central repository for **customer master data** and **high‑level opportunity tracking**.

## What is stored in the CRM?

For each **customer company**:

* Customer ID (internal)
* Name and legal form
* Main address and country
* Industry segment (e.g. Rail, Food & Beverage, General Industry)
* Primary contact name and email
* Assigned account manager (employee ID)
* Short descriptive **brief**
* Current overall **deal phase**
* High‑level status (e.g. “Key account”, “Curious but cautious”, “Dormant”)

For each **opportunity / relationship** (at company level):

* The **deal phase**:

  * `idea` – new lead, early conversation.
  * `exploring` – deeper exploration, early trials.
  * `active` – ongoing projects, regular business.
  * `paused` – no current activity, but not lost.
  * `archived` – relationship closed or no realistic future business.
* Optional descriptive notes and tags.

## Linking to other systems

* **Project registry:**

  * Projects always reference a **customer ID** from the CRM (unless internal).
* **Time tracking:**

  * Time entries for customer work show both the **customer** and the **project**, enabling customer profitability and effort analysis.
* **Wiki and chatbot:**

  * Wiki pages may describe key accounts or reference successful case studies.
  * The chatbot provides quick overviews of customer status, contacts, projects and time summaries.
    </kind=wiki id=systems_crm.md>

<kind=wiki id=systems_project_registry.md>

# Project Registry

The **project registry** is the central place where Bellini tracks all significant **customer and internal work** as projects.

## What is a project?

A project is any substantial piece of work that:

* Requires coordinated effort across multiple people or departments, and/or
* Represents a distinct opportunity, development or contract.

## Core project fields

Each project has:

* Project ID (internal)
* Name
* Linked customer (if applicable)
* Description / brief
* Status (aligned with deal phases):

  * `idea`
  * `exploring`
  * `active`
  * `paused`
  * `archived`
* Project manager (employee ID)
* Team and workloads:

  * Which employees are assigned
  * Their role (Lead, Engineer, Designer, QA, Ops, Other)
  * Their approximate time slice (fraction of an FTE)

## Workload

Employee workload in Bellini Coatings is determined by analysing **their allocated FTE slices across all active projects**. Each project stores, as part of its team definition, a list of `Workload` entries:

* `Employee` – the employee ID
* `TimeSlice` – the fraction of a full-time equivalent (FTE) that the employee is expected to contribute to that project (e.g. 0.1, 0.3, 0.5, 1.0)
* `Role` – the project role (Lead, Engineer, QA, Ops, Other)

These allocations are defined and maintained in the **project registry**, which is the system of record for planned workload assignments.
</kind=wiki id=systems_project_registry.md>

<kind=wiki id=systems_time_tracking_and_reporting.md>

# Time Tracking & Reporting

Bellini Coatings uses a central **time tracking system** to understand how employees spend their time across customers, projects and internal activities.

## Time entry structure

Each time entry contains:

* Employee (employee ID)
* Customer (optional, usually derived from project)
* Project (project ID, customer or internal)
* Date (YYYY‑MM‑DD)
* Hours (decimal, e.g. 1.0, 7.5)
* Work category (e.g. `customer_project`, `internal`, `support`, `admin`)
* Notes (short free text)
* Billable flag (billable vs non‑billable)
* Status:

  * `draft`
  * `submitted`
  * `approved`
  * `invoiced`
  * `voided`

## Why we track time

* **Customer profitability**

  * Understand how much effort is invested in supporting each customer.
* **Project costing**

  * Analyse efforts spent on different project types and stages.
* **Workload monitoring**

  * Identify overloaded employees or teams.
* **Internal improvements**

  * Quantify time spent on non‑customer initiatives (e.g. training, digital projects).
    </kind=wiki id=systems_time_tracking_and_reporting.md>

<kind=wiki id=systems_knowledge_base.md>

# Knowledge Base / Wiki

The **knowledge base** (this wiki) is the central place for **processes, guidelines, technical notes and reference information** at Bellini Coatings.

## Relation to other systems

* The wiki is **not** a replacement for transactional data (e.g. CRM entries, project records, time logs).
* Instead, it documents:

  * How to use systems.
  * Why certain processes exist.
  * What standards and best practices apply.

## Good practices

* Keep pages **short, focused and up to date**.
* Use clear headings and bullet points.
* Add links to related pages and systems where helpful.
* Avoid storing sensitive information (e.g. individual salaries) in the wiki.
  </kind=wiki id=systems_knowledge_base.md>
