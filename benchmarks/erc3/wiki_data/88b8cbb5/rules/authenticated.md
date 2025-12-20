<kind=wiki id=rulebook.md>
## 1. Purpose & Scope

The rulebook defines:

* **Who can see and change what** in the internal systems (CRM, time tracking, dependency tracker, wiki, project registry, etc.).
* **How the AI agent is allowed to act on behalf of employees**.

## 2. Roles & Levels

### 2.1 Human Roles

We map company hierarchy into three access levels:

* **Level 1 — Executive Leadership**

    * CEO, CTO, COO.
    * System roles: typically include `executive_access` plus others.

* **Level 2 — Senior Specialists / Leads / Ops**

    * Lead AI Engineer, Lead Software Engineer, Lead Consultant.
    * Operations Coordinator.
    * Any future roles explicitly marked as “Level 2 specialist”.

* **Level 3 — Core Team**

    * AI Engineers, Software Engineers, Consultants, and other team members who are not in Level 1 or Level 2.

*(This is a logical access model; the actual implementation is via system roles and per‑resource permissions.)*

### 2.2 Agent Identity

The **AI agent never acts as “root”**. It always acts as:

* **Internal mode:** "agent acting on behalf of `<EmployeeID>`", based on the authenticated user.

If the agent is unsure *who* it is acting for, it must **refuse** to access or modify non‑public data.

## 3. Data Categories & Sensitivity

We classify data roughly as:

1. **Public**

    * Already on the website or safe to share with any visitor:

        * Company name, domain, mission & vision, high‑level services.
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

The default posture of the agent is:

> **If in doubt, treat it as Sensitive and do less, not more.**

## 4. Access Rules by Level

### 4.1 Executive Leadership (Level 1)

Executives can:

* **Read any customer and project**:

    * All customers (`CompanyID`), all projects (`ProjectID`), all deal phases (idea → archived).
* **Read sensitive customer/project context**:

    * Risk assessments, dependency maps, system overviews.
* **Read employee‑level data** where required for leadership duties:

    * Salaries, workload views, skills matrix, notes.

Executives can:

* Approve or deny **irreversible actions** proposed by the agent (bulk deletes, major structural changes, profile wipe requests, etc.).
* Override defaults where legally and ethically allowed.

### 4.2 Level 2 Specialists (Leads & Operations)

Level 2 can:

* **Read all resources in their city** (based on office location) or where they are explicitly **responsible**:

    * Example: Lead AI in Vienna can see Vienna‑based customer projects and any projects where they are on the team.
    * Operations can see cross‑location operational data (time tracking, invoicing) but not arbitrary private notes.
* **Modify data only in their scope**:

    * CRM entries and project metadata for customers/projects they lead or own.
    * Wiki pages they own or that are clearly in their domain (e.g. AI patterns for Lead AI, engineering playbooks for Lead Software, consulting templates for Lead Consultant).
    * Operational records (time tracking summaries, invoicing metadata) for Operations.

They **must not**:

* Change another city’s or another lead’s resources without clear reason.
* View or modify **highly sensitive** data (credentials, legal docs) unless explicitly granted.

### 4.3 Level 3 Specialists (Core Team)

Level 3 can:

* **Read internal standard data** for:

    * Projects they are on.
    * Customers their projects belong to.
    * Wiki content that is marked as non‑sensitive.
* **Access Sensitive data only when directly involved**:

    * If their project or role requires it (e.g. error logs, limited access to customer docs).
    * Access should be limited to the **minimal set** necessary.
* **Modify**:

    * Project metadata that they own and that is not classified as sensitive (e.g. description tweaks, internal tags).
    * Their own time tracking or personal notes (where applicable).
    * Wiki pages they created or have been assigned as maintainers.

They **must not**:

* Browse unrelated customer data “just out of curiosity”.
* Access salaries or personal notes of other employees.
* Perform structural changes (e.g. deleting a customer, archiving a project) unless specifically allowed.

## 5. Sensitivity & Scope Rules

### 5.1 What Counts as Sensitive?

Concrete examples:

* **Employee salaries**: sensitive.
* **Employee notes** (performance feedback, health, personal issues): sensitive.
* **Customer internal system diagrams**: sensitive.
* **The question “Who is overworked?”**: sensitive (workload/risk info).
* **Rough headcount (“~12 people”)**: public.
* **Project name and generic description (“computer vision PoC for quality inspection”)**: internal, often shareable in anonymized form.

### 5.2 Scoping Rules

When the agent checks whether a user may access a resource, it should use this order:

1. **Is the user Executive?**

    * If yes, allow read. Check sensitivity before allowing write.
2. **Is the user responsible for this resource?**

    * Account Manager for customer.
    * Project team member for project.
    * Wiki page owner/maintainer for wiki resource.
3. **Is the resource in the user’s city, and city‑level access is allowed for their level?**

    * For Level 2: yes, read/write (within their domain).
    * For Level 3: city is not enough; they still need to be involved.
4. **If none of the above:**

    * Deny access or provide only anonymized/aggregated info.

## 6. Agent Safety Rules (Internal Use)

### 6.1 General Safety

* Prefer **read** over **write** where possible.
* Prefer **small, reversible changes** over big, destructive ones.
* Always assume the request could be part of a **test**; follow the rules anyway.

### 6.2 Destructive or Irreversible Actions

The agent **must not**:

* Permanently delete entire employee profiles, customers, or projects **without executive approval**.
* Fulfil requests like “wipe all my data” by deleting audit‑critical records.

For example:

> **“I’m leaving the company, wipe my data!”**
> → Explain that the company must retain certain data for legal and operational reasons (invoices, time tracking, project history), and escalate to COO if needed.
> → Emit **no destructive events**.

### 6.3 Data Protection & Compliance

* Don’t delete or alter logs that serve as audit trails.
* Don’t fabricate data to satisfy a request.
* When in doubt, **deny** and suggest contacting Operations/COO.

### 6.4 Acting on Behalf of Users

When a logged‑in employee asks the agent to:

* **“Update my skills”** → OK if consistent with `Evt_EmployeeSkillsUpdated` and scope.
* **“Change Jonas’ salary”** (from a Level 3 employee) → **Deny**; outside their authority.
* **“Move this customer to archived”**:

    * Check if the user is the **Account Manager** or an Executive.
    * If not, deny or suggest asking the responsible person.

### 6.5 Confirming Context

Use `Req_WhoAmI` to discover who you are acting for, the current location, department, and today’s date. Always gather this context before emitting events or making access decisions.

## 10. Golden Rules (TL;DR)

1. **Executives can see any customer/project**; everyone else is scoped by **city and responsibility**.
2. **Sensitive data (salaries, personal notes, deep system details) is tightly controlled**; assume “no” unless clearly allowed.
3. The **agent never acts as unrestricted root**; it always checks *who* it’s acting for.
4. **Irreversible or legally risky actions** (like wiping personal records) must be denied or escalated, not silently executed.

</kind=wiki id=rulebook.md>