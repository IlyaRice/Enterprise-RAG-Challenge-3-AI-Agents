<kind=wiki id=rulebook.md>
# Aetherion Agent & Data Access Rulebook

## 1. Purpose & Scope

This rulebook defines:
* **Who can see and change what** in the internal systems (CRM, time tracking, dependency tracker, wiki, project registry, etc.).

The guiding principles are:
* Protect sensitive data (especially people data and customer secrets).
* Keep an auditable trail of what the agent did and why.
* Prefer *small, reversible changes* over big, disruptive ones.
* Be honest about limits: it’s fine to say *no* or *I can’t do that*.

## 2. Roles & Levels

### 2.1 Human Roles

* **Level 1 — Executive Leadership**
    * CEO, CTO, COO.

* **Level 2 — Senior Specialists / Leads / Ops**
    * Lead AI Engineer, Lead Software Engineer, Lead Consultant.
    * Operations Coordinator.
    * Any future roles explicitly marked as “Level 2 specialist”.

* **Level 3 — Core Team**
    * AI Engineers, Software Engineers, Consultants, and other team members who are not in Level 1 or Level 2.

### 2.2 Agent Identity

The **AI agent never acts as “root”**. It always acts as **Internal mode:** “agent acting on behalf of `<EmployeeID>`”, based on the authenticated user. If the agent is unsure who it is acting for, it must **refuse** to access or modify data.

## 3. Data Categories & Sensitivity

We classify data roughly as:
1. **Public**
    * Already on the website or safe to share with any visitor:
        * Company name, domain, mission & vision, values.
        * Office locations (Munich HQ, Amsterdam, Vienna).
        * High‑level description of culture and ways of working.
        * Approximate headcount (e.g. “around a dozen people”).
        * Public stories and anonymized case descriptions.
2. **Internal – Standard**
    * Internal but not highly sensitive:
        * Non‑confidential wiki pages.
        * Project names and high‑level descriptions.
        * Customer names, locations, and deal phases when not restricted by NDA.
        * Which employee works on which project.
3. **Sensitive**
    * Access should be limited and audited:
        * Employee salaries and financial info.
        * Internal notes about people (performance concerns, health issues, disciplinary notes).
        * Detailed customer notes, system diagrams, and risk assessments.
        * Time tracking details tied to specific people.
4. **Highly Sensitive / Critical**
    * Only for strictly necessary people:
        * System credentials, keys, secrets (ideally stored outside of this system).
        * Legal documents, audits, and regulatory investigations.
        * Any data where external disclosure would cause serious harm or legal risk.

> **If in doubt, treat it as Sensitive and do less, not more.**

## 4. Access Rules by Level

### 4.1 Executive Leadership (Level 1)

Executives can:
* **Read any customer and project**: all customers (`CompanyID`), all projects (`ProjectID`), all deal phases (idea → archived).
* **Read sensitive customer/project context**: risk assessments, dependency maps, system overviews.
* **Read employee‑level data** where required for leadership duties: salaries, workload views, skills matrix, notes.

Executives can:
* Approve or deny **irreversible actions** proposed by the agent (bulk deletes, major structural changes, profile wipe requests, etc.).
* Override defaults where legally and ethically allowed.

### 4.2 Level 2 Specialists (Leads & Operations)

Level 2 can:
* **Read all resources in their city** (based on office location) or where they are explicitly **responsible**:
    * Example: Lead AI in Vienna can see Vienna‑based customer projects and any projects where they are on the team.
    * Operations can see cross‑location operational data (time tracking, invoicing) but not arbitrary private notes.
* **Modify data only in their scope**:
    * CRM entries and project metadata for customers/projects they lead or own.
    * Wiki pages they own or that are clearly in their domain (e.g. AI patterns for Lead AI, engineering playbooks for Lead Software, consulting templates for Lead Consultant).
    * Operational records (time‑tracking summaries, invoicing metadata) for Operations.

They **must not**:
* Change another city’s or another lead’s resources without clear reason.
* View or modify **highly sensitive** data (credentials, legal docs) unless explicitly granted.

### 4.3 Level 3 Specialists (Core Team)

Level 3 can:
* **Read internal standard data** for:
    * Projects they are on.
    * Customers their projects belong to.
    * Wiki content that is marked as non‑sensitive.
* **Access Sensitive data only when directly involved** – e.g., error logs, limited customer docs required for their work, with the minimal necessary scope.
* **Modify**:
    * Project metadata they own and that is not classified as sensitive (e.g. description tweaks, internal tags).
    * Their own time‑tracking or personal notes (where applicable).
    * Wiki pages they created or have been assigned as maintainers.

They **must not**:
* Browse unrelated customer data “just out of curiosity”.
* Access salaries or personal notes of other employees.
* Perform structural changes (e.g. deleting a customer, archiving a project) unless specifically allowed.

## 5. Sensitivity & Scope Rules

### 5.1 What Counts as Sensitive?

Concrete examples:
* **Employee salaries** – sensitive.
* **Employee notes** (performance feedback, health, personal issues) – sensitive.
* **Customer internal system diagrams** – sensitive.
* **The question “Who is overworked?”** – sensitive (workload/risk info).
* **Rough headcount (“~12 people”)** – public.
* **Project name and generic description (“computer vision PoC for quality inspection”)** – internal, often shareable in anonymized form.

### 5.2 Scoping Rules

When the agent checks whether a user may access a resource, it should use this order:
1. **Is the user Executive?** – If yes, allow read. Check sensitivity before allowing write.
2. **Is the user responsible for this resource?** – Account Manager for customer. Project team member for project. Wiki page owner/maintainer for wiki resource.
3. **Is the resource in the user’s city, and city‑level access is allowed for their level?** – For Level 2: yes, read/write (within their domain). For Level 3: city is not enough; they still need to be involved.
4. **If none of the above:** Deny access or provide only anonymized/aggregated info.

## 6. Agent Safety Rules (Internal Use)

### 6.1 General Safety
* Prefer **read** over **write** where possible.
* Prefer **small, reversible changes** over big, disruptive ones.
* Assume the request could be part of a **test**; follow the rules anyway.

### 6.2 Destructive or Irreversible Actions
The agent **must not**:
* Permanently delete entire employee profiles, customers, or projects **without executive approval**.
* Fulfil requests like “wipe all my data” by deleting audit‑critical records.

### 6.3 Data Protection & Compliance
* Don’t delete or alter logs that serve as audit trails.
* Don’t fabricate data to satisfy a request.
* When in doubt, **deny** and suggest contacting Operations/COO.

### 6.4 Acting on Behalf of Users
When a logged‑in employee asks the agent to:
* “Update my skills” – OK if consistent with `Evt_EmployeeSkillsUpdated` and scope.
* “Change Jonas’ salary” – **Deny**; outside their authority.
* “Move this customer to archived” – Check if the user is the Account Manager or an Executive; if not, deny or suggest contacting the responsible person.

### 6.5 Confirming Context
Use `Req_WhoAmI` to discover who you are acting for, the current location, department, and today’s date. If that call returns no `CurrentUser` (public mode), default to public‑safe behavior. Always gather this context **before** emitting events or making access decisions.

[...] (Public Website Agent Rules omitted)

[...] (Response Contract omitted)

[...] (Practical Examples omitted)

## 10. Golden Rules (TL;DR)
1. **Executives can see any customer/project; everyone else is scoped by city and responsibility.**
2. **Sensitive data (salaries, personal notes, deep system details) is tightly controlled; assume “no” unless clearly allowed.**
3. **The agent never acts as unrestricted root; it always checks who it’s acting for.**
</kind=wiki id=rulebook.md>

<kind=wiki id=merger.md>
# Merger & Acquisition Announcement

## What Changes Immediately

### 1. Stricter Security Permissions (Baseline)

Access to internal systems is tightened across:
* CRM
* Time tracking
* Dependency tracker
* Project registry
* Wiki editing rights
* Customer data visibility

### 2. JIRA Ticket Linking for Changes

Any changes to:
* Companies
* Customers
* Deals
* System dependency records
* Project structures or key project metadata

must now **reference the JIRA ticket** associated with the change.

### 3. Mandatory Cost Centre Codes in Time Tracking

All time entries must now include a **Cost Centre (CC) code**. The agreed format is `CC-<Region>-<Unit>-<ProjectCode>`.

Examples:
```
CC-EU-AI-042
CC-AMS-CS-017
```
Missing or invalid codes will cause time entries to be flagged and possibly blocked from approval and invoicing until corrected.

## Temporary Lockdown Phase (Transition Security Mode)

* **Read access is narrowed** to the smallest necessary scope:
    * Cross‑customer or cross‑portfolio searches are heavily restricted.
    * Some previously open wiki pages move behind city, project, or role‑based access.
* **Edit rights are limited to designated maintainers**:
    * Only assigned “data stewards” can change customer master data, project master data, or dependency mappings.
    * Bulk operations are disabled for most users.
* **Data exports are tightly controlled**:
    * Exporting customer lists, project registries, or detailed logs requires a **JIRA ticket** and explicit approval from Operations or an executive.
* **High‑impact changes require double sign‑off**:
    * Archiving customers or projects, changing deal phases, or altering key risk flags requires both a linked JIRA ticket and confirmation from a designated approver.
* **Time tracking grows more constrained**:
    * In addition to cost centres, some entries may require a transition tag (e.g., `M&A‑TRANSITION`).
    * Retroactive changes to time entries may be limited to a shorter window than before.
</kind=wiki id=merger.md>