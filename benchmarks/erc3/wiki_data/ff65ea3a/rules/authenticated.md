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
  </kind=wiki id=systems_chatbot_interface.md>

<kind=wiki id=systems_overview.md>

# Systems Overview

Bellini Coatings runs its core business on a set of **legacy but robust systems** built on **Progress OpenEdge** more than 30 years ago. These systems are centralised at HQ and accessed from Italy, Serbia and all EU branches.

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

## System roles and access

Every employee with system access has:

* A **user account** mapped to an internal employee ID.
* A **location** and **department** associated with their profile.
* One or more **system roles** (e.g. “SalesUser”, “R&DUser”, “HRAdmin”, “ITAdmin”).

Access is granted according to job needs and is centrally managed by IT in coordination with HR and managers.

## Relationship between systems

At a high level:

* The **CRM** stores customers and basic opportunities.
* The **project registry** tracks all major customer and internal projects.
* The **employee registry** stores employee profiles, including skills, wills, salary, department and location.
* The **time tracking** system records how employees spend their time across projects and internal activities.
* The **wiki** stores process documentation, guidelines, case studies and reference material.
* The **chatbot** reads from and writes to these systems via APIs and uses the wiki for context and explanations.

For detailed instructions on each system, refer to the dedicated pages in this section.
</kind=wiki id=systems_overview.md>

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

Skills and wills are documented in detail in [Skills & Wills Model](../hr/skills_and_wills_model.md).

## Who can see what?

* **All employees (via chatbot):**

  * Name, email, location, department and basic role.
  * Selected skill and will information, depending on context.
* **Managers and HR:**

  * Full profile, including notes and salary.
* **IT & system processes:**

  * Use employee IDs and department/location to enforce access and routing rules.

Access is controlled by **system roles** and internal policies. The chatbot respects these rules and will not reveal confidential information (such as exact salaries) to unauthorised users.

## How data gets into the registry

* When an employee is hired, HR creates a record with:

  * Initial notes
  * Location
  * Department
  * Salary
  * Initial skills and wills
* Updates happen through:

  * HR changes (e.g. promotions, relocations, salary adjustments).
  * Manager and employee updates during reviews (skills and wills).
  * System events (e.g. location updates based on site changes).

Each significant change is recorded with “changed by” information for auditing.

## Typical usage

* **HR and managers**

  * Look up reporting lines, salary ranges (where allowed), and skill distributions.
* **Project staffing**

  * Find people with specific skills at certain levels (e.g. “epoxy floor systems ≥ 7”).
* **Cross‑site collaboration**

  * Identify experts in other locations or departments.
* **Chatbot queries**

  * “Who is the plant manager in Serbia?”
  * “Which employees report to the R&D Director?”
  * “Show Sara Romano’s skills and current department.”

Accurate employee records are essential for planning, analytics and for the chatbot to be helpful.
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

## Who uses the CRM?

* **Sales & Customer Success**

  * Primary owners of customer records and deal phases.
* **Customer Service**

  * Updates contact details and practical information.
* **Management and Finance**

  * Use CRM data for pipeline reviews and account prioritisation.
* **Chatbot**

  * Answers questions like “Who is the account manager for Customer X?” or “Show all active customers in Germany in the rail segment.”

## Basic rules for using the CRM

1. **Every active customer must exist in CRM.**

   * No “shadow customers” known only via email or spreadsheets.
2. **Each customer must have a clear account manager.**

   * The account manager is responsible for keeping data up to date.
3. **Use concise and informative briefs.**

   * Explain who the customer is, what they do and why they matter.
4. **Maintain deal phases realistically.**

   * Reflect the true state of the commercial relationship, not wishful thinking.

## Linking to other systems

* **Project registry:**

  * Projects always reference a **customer ID** from the CRM (unless internal).
* **Time tracking:**

  * Time entries for customer work show both the **customer** and the **project**, enabling customer profitability and effort analysis.
* **Wiki and chatbot:**

  * Wiki pages may describe key accounts or reference successful case studies.
  * The chatbot provides quick overviews of customer status, contacts, projects and time summaries.

Keeping CRM data clean and current is critical for accurate reporting and for the chatbot to give trustworthy answers.
</kind=wiki id=systems_crm.md>

<kind=wiki id=systems_project_registry.md>

# Project Registry

The **project registry** is the central place where Bellini tracks all significant **customer and internal work** as projects.

## What is a project?

A project is any substantial piece of work that:

* Requires coordinated effort across multiple people or departments, and/or
* Represents a distinct opportunity, development or contract.

Examples:

* Developing a new high‑temperature coating for a machinery OEM.
* Implementing a new floor coating system at a large warehouse.
* Internal R&D initiatives (e.g. new low‑VOC formulation series).
* Internal process or IT projects (e.g. chatbot pilot, warehouse re‑layout).
* Departmental initiatives (e.g. “HR – Training 2025”).

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

## Why the project registry matters

* **Planning and workload**

  * Managers can see who is involved in which projects and at what intensity.
* **Visibility**

  * Sales, R&D, production and management can all see key projects and their status.
* **Reporting**

  * Combined with time tracking, the registry supports cost and effort analysis by project and customer.

## Project types

While the system uses a single “project” concept, we distinguish informally between:

* **Customer development projects**

  * New or adapted formulations, trials and approvals.
* **Customer supply projects**

  * Ongoing contracts where time is logged for support and technical visits.
* **Internal R&D projects**

  * Platform developments, testing programmes, regulatory updates.
* **Internal process / IT projects**

  * Improvements in production, logistics, quality, HR, IT and digitalisation.

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

* **Project manager:**

  * Ensures the project is created correctly and linked to the right customer.
  * Keeps the **status** up to date as the project progresses.
  * Maintains a meaningful **description** that others can understand.
* **Team members:**

  * Log time against the correct project.
  * Flag missing or incorrect project data to their manager or the project manager.
* **Department leaders:**

  * Review project portfolios to avoid overload and to prioritise work.

## Chatbot examples

The chatbot can help by answering questions such as:

* “List all active projects for Customer FerroRail in Germany.”
* “Show the team and workloads for project P‑2025‑017.”
* “Which projects is E0221 (Sara Romano) currently assigned to as Lead?”

It does this by querying the project registry and linking results to employees and customers.
</kind=wiki id=systems_project_registry.md>

<kind=wiki id=systems_time_tracking_and_reporting.md>

# Time Tracking & Reporting

Bellini Coatings uses a central **time tracking system** to understand how employees spend their time across customers, projects and internal activities.

Most non‑production employees (and selected production roles) are required to log time regularly.

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

## Lifecycle of time entries

1. **Draft**

   * Employee is still editing; corrections are allowed.
2. **Submitted**

   * Employee considers entries complete for the period (e.g. week, month).
3. **Approved**

   * Supervisor or operations has reviewed entries for consistency.
4. **Invoiced**

   * Entries have been used for billing or customer reporting; they are effectively locked.
5. **Voided**

   * Entry has been cancelled (e.g. wrong project). Usually paired with a correcting entry.

After approval, employees cannot change entries directly; corrections require specific processes to ensure an audit trail.

## Why we track time

* **Customer profitability**

  * Understand how much effort is invested in supporting each customer.
* **Project costing**

  * Analyse efforts spent on different project types and stages.
* **Workload monitoring**

  * Identify overloaded employees or teams.
* **Internal improvements**

  * Quantify time spent on non‑customer initiatives (e.g. training, digital projects).

## Usage expectations

* Employees should log time **at least weekly**, ideally daily.
* Use **projects** consistently:

  * Customer work → customer projects.
  * Internal initiatives → internal projects (e.g. “IT – Chatbot Pilot 2025”).
* Notes should be concise but informative (what was done, not just “meeting”).
* Project leads can log entries for the team members in draft mode. They are NOT allowed to submit entries for them.

## Reporting and summaries

The system can aggregate and summarise time in different ways:

* **By project and customer**

  * Hours, billable vs non‑billable, number of distinct employees.
* **By employee**

  * Total hours, distribution between customer work and internal activities.

The chatbot can answer questions like:

* “How many hours did we spend on Customer X last quarter?”
* “Show time spent by Sara Romano on project P‑2025‑017 this year.”
* “Which employees logged more than 45 hours in the past week?”

Correct and timely time logging is essential for good data and fair decisions.

## Workload estimation

Note, that when estimating workload (e.g. who is busiest or non-busiest), we rely on workload time slices via Project registry.
</kind=wiki id=systems_time_tracking_and_reporting.md>

<kind=wiki id=systems_knowledge_base.md>

# Knowledge Base / Wiki

The **knowledge base** (this wiki) is the central place for **processes, guidelines, technical notes and reference information** at Bellini Coatings.

## Purpose

* Preserve and share **know‑how** across locations and generations.
* Provide clear **process descriptions** for onboarding and daily work.
* Document **approved solutions**, best practices and lessons learned.
* Serve as a key source of context for the **chatbot**.

## Content types

Typical content includes:

* Company information (history, mission, organisation).
* Market and customer insights.
* R&D guidelines, test methods and application notes.
* Production and quality procedures (at a conceptual level; detailed SOPs may be separate).
* System usage guides and tips.
* HR and people‑related information (skills & wills, roles, development programmes).

## Structure

Pages are organised in logical folders, for example:

* `company/` – About Bellini as a company.
* `business/` – Markets, customers, marketing and sales approach.
* `operations/` – Factories, production and logistics concepts.
* `hr/` – People, departments, skills and example profiles.
* `systems/` – Systems overview and usage guidelines.

This structure is reflected in file paths (e.g. `systems/project_registry.md`).

## Editing and ownership

* Each section of the wiki has **content owners** (e.g. HR for HR pages, IT for systems pages, R&D for technical guidelines).
* Updates are coordinated via these owners to ensure consistency (top execs have full control).
* To delete a page - zero out its content. To rename - transfer content to new location and zero out old page.
* The IT & Digital team maintains the **technical infrastructure** and integrates the wiki with the chatbot.

## Relation to other systems

* The wiki is **not** a replacement for transactional data (e.g. CRM entries, project records, time logs).
* Instead, it documents:

  * How to use systems.
  * Why certain processes exist.
  * What standards and best practices apply.

The chatbot can search the wiki to answer “how” and “why” questions, and it can link directly to articles when relevant.

## Good practices

* Keep pages **short, focused and up to date**.
* Use clear headings and bullet points.
* Add **links** to related pages and systems where helpful.
* Avoid storing sensitive information (e.g. individual salaries) in the wiki.
  </kind=wiki id=systems_knowledge_base.md>

<kind=wiki id=business_markets_and_customers.md>

## Customer lifecycle in our systems

1. **Lead / idea**

   * Customer contact identified (trade fair, referral, inbound request).
   * Added to the CRM and represented as a `Company` record.
   * Deal phase in systems: `idea`.

2. **Exploring**

   * First visits, basic technical discussions.
   * Early lab suggestions or product recommendations.
   * Deal phase: `exploring`.

3. **Active**

   * Formal projects opened in the **project registry** for trials, custom formulations or supply schemes.
   * Significant internal time logged to the customer and related projects.
   * Deal phase: `active`.

4. **Paused or archived**

   * Projects may be `paused` (no current activity) or `archived` (closed).
   * Customer remains in CRM with a high‑level status (e.g. “Curious but cautious”, “Key account”, “Dormant”).

Our systems use these phases mainly for **visibility and prioritisation**. The exact phase is maintained by the **account manager**, typically after pipeline review meetings.
</kind=wiki id=business_markets_and_customers.md>

<kind=wiki id=business_marketing_and_sales_approach.md>

## CRM usage principles

Even though our CRM and project systems are built on **legacy technology**, they are the **single source of truth** for:

* Customer master data.
* Key contacts and roles.
* Active and recent projects.
* High‑level status of opportunities.

Account managers are expected to keep **deal phases** and **briefs** reasonably up to date, and to link projects correctly to customers. This is essential for meaningful reports and for the chatbot to give accurate answers.
</kind=wiki id=business_marketing_and_sales_approach.md>

<kind=wiki id=hr_people_and_roles.md>

## Main departments

The following department names are used consistently in the **employee registry**, time tracking and reporting:

* **Corporate Leadership**
* **Sales & Customer Success**
* **R&D and Technical Service**
* **Production – Italy**
* **Production – Serbia**
* **Logistics & Supply Chain**
* **Quality & HSE**
* **IT & Digital**
* **Human Resources (HR)**
* **Finance & Administration**

Each employee has exactly one **home department**, even if they collaborate with others.

## Reporting and responsibilities

Each role comes with responsibilities for:

* Keeping data up to date (e.g. CRM, project registry, time tracking).
* Supporting cross‑functional collaboration (e.g. Sales ↔ R&D ↔ Production).
* Maintaining and improving documentation in the internal wiki.

The **skills & wills** model is used in development discussions: employees and managers jointly maintain profiles to reflect strengths and ambitions.
</kind=wiki id=hr_people_and_roles.md>

<kind=wiki id=hr_skills_and_wills_model.md>

# Skills & Wills Model

The **skills & wills** model describes what employees **can do** and what they **want to do**. It is implemented in the **employee registry** and is accessible to HR, managers, the chatbot and selected systems.

## Definitions

* **Skill**

  * A capability the employee has (e.g. “Solventborne formulation”, “German language”, “Project management”).
  * Stored as a `SkillLevel` with fields `name` and `level`.

* **Will**

  * An aspiration, interest or preference of the employee (e.g. “Interest in people management”, “Willingness to travel”, “Interest in automation projects”).
  * Also stored as a `SkillLevel`, but interpreted as motivation rather than demonstrated ability.

Both skills and wills are represented as **lists of `SkillLevel` objects** in the employee registry and are always stored **sorted alphabetically by name**.

## Rating scale

Bellini uses a **1–10 scale** for both skills and wills:

* **1–2:** Very low – limited exposure or interest.
* **3–4:** Basic – some experience or mild interest.
* **5–6:** Solid – can perform reliably / clear and stable interest.
* **7–8:** Strong – recognised expertise / strong motivation.
* **9–10:** Exceptional – go‑to person / very strong drive.

The maximum skill level configured in our systems is **10**.

## Principles for keeping profiles up to date

* **Employees and managers** update skills and wills during annual reviews and as needed after major changes (new responsibilities, training, relocations).
* Employees are encouraged to update their skills and wills outside of reviews as well, as a part of **SkillWillReflect update**.
* HR encourages **realistic ratings**: it is acceptable to have some high scores, but profiles should reflect reality, not wishful thinking.
* Wills are particularly important for:

  * Identifying candidates for **succession planning** and promotions.
  * Finding volunteers for **projects**, pilots or training.
  * Understanding who is open to **travel, relocation or cross‑functional work**.

## Use cases

* **Staffing projects:**

  * R&D and Sales leaders search for employees with specific skills above a threshold (e.g. “epoxy floor systems ≥ 7”).
* **Career development:**

  * Managers and HR use wills to propose training or role changes aligned with interests.
* **Chatbot queries:**

  * Employees can ask “Who in Serbia has strong skills in corrosion testing?” or “Who is interested in leading digitalisation projects?”.
* **Workload and succession:**

  * Combined with time tracking and project registry data, skills & wills help avoid single points of failure and distribute work fairly.

Keeping skills and wills profiles accurate is a **shared responsibility** between employees, managers and HR.
</kind=wiki id=hr_skills_and_wills_model.md>

<kind=wiki id=company_locations_and_sites.md>

## Sales branches

Bellini maintains small sales and technical support offices in several European hubs. Typical size: **2–6 people**.

Current branches include:

* **Munich (Germany)**

  * Focus: machinery, automotive suppliers, industrial equipment.
  * Staff: regional sales manager, key account managers, technical sales engineer.

* **Paris (France)**

  * Focus: architectural metalwork, food processing, rail.
  * Staff: account manager(s), technical sales or application specialist, shared customer service.

* **Rotterdam (Netherlands)**

  * Focus: logistics infrastructure, marine‑adjacent industry, warehousing floors.
  * Staff: account manager, technical sales, inside sales.

* **Barcelona (Spain)**

  * Focus: regional OEMs and construction‑related applications.
  * Staff: account manager, technical sales, part‑time customer service.

* **Vienna (Austria)**

  * Focus: DACH and Central/Eastern Europe smaller accounts.
  * Staff: regional sales manager (also covering neighbouring countries), sales support.

All branches access the same **central CRM, project registry, employee registry and time tracking** systems via terminal or thin client, and rely heavily on email, Excel and the internal wiki.

## Remote and hybrid work

While production and lab roles are site‑bound, many roles in sales, IT, finance and HR have **hybrid arrangements**, combining days on site with home office. Regardless of location, employees are expected to:

* Use the central systems (CRM, project registry, time logging) as the **system of record**.
* Keep their **location field** in the employee registry up to date.
* Log where they spend their time to support fair workload and cost reporting.
  </kind=wiki id=company_locations_and_sites.md>

<kind=wiki id=company_organization_and_hierarchy.md>

## Reporting relationships

Every employee in the employee registry has a single **direct manager** recorded via the `reports_to` field (internally stored as an employee ID). This supports:

* Organisational charts and headcount analysis.
* Approvals for travel, training and salary changes.
* Reporting lines used by the chatbot when answering “who does X report to?” type questions.

**Team leads and supervisors** (e.g. lab team leaders, production supervisors, regional sales managers) are responsible for:

* Ensuring that **projects** in their area have clear owners.
* Checking that **time tracking** for their team is complete and reasonable.
* Encouraging team members to keep their **skills and wills** profiles updated.

The hierarchy is respected, but day‑to‑day collaboration is informal and often cross‑functional, especially between **Sales, R&D and Operations** on customer projects.
</kind=wiki id=company_organization_and_hierarchy.md>

<kind=wiki id=operations_factories_and_production.md>

## Production and systems

Both plants rely on the central Progress‑based systems for:

* **Production orders and recipes** (derived from project outcomes and product master data).
* **Time logging** for supervisors and selected roles (especially for support, rework and improvement projects).
* **Non‑conformity and deviation tracking** (often supplemented with Excel and paper forms).

Production supervisors are encouraged to:

* Ensure all improvement or troubleshooting efforts are linked to **projects** (internal or customer) where appropriate.
* Log their own time to give visibility into the effort required for support activities.
* Use the internal wiki to access **application notes** and **standard operating procedures** for production.
  </kind=wiki id=operations_factories_and_production.md>