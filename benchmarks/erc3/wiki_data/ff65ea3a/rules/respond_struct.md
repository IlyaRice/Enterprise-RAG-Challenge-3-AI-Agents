<kind=wiki id=systems_chatbot_interface.md>

# CATEGORY 1 - outcome_rules

## Outcome codes

Every response includes an `Outcome` value indicating what happened:

* `ok_answer`

  * The chatbot understood the request and produced a meaningful answer.
* `ok_not_found`

  * The request was understood but no matching data was found (e.g. unknown employee ID).
* `denied_security`

  * The request was understood but the user lacks permission (e.g. salary details of another department).
* `none_clarification_needed`

  * The chatbot needs more information (e.g. “Which project do you mean?”).
* `none_unsupported`

  * The chatbot cannot perform this type of request (out of scope).
* `error_internal`

  * Something went wrong internally; IT may need to investigate.

## Examples of interactions

* “Who is responsible for Customer FerroRail?”

  * Outcome: `ok_answer`
  * Links: customer (FerroRail), employee (account manager).

* “Show all active projects for Customer X in Germany.”

  * Outcome: `ok_answer`
  * Links: multiple projects and the customer.

* “How many hours did we spend on project P‑2025‑017 last quarter?”

  * Outcome: `ok_answer`
  * Links: project; optional link to time summary view.

* “What is Sara Romano’s salary?”

  * Outcome: `denied_security`
  * Message: explanation that salary data is restricted.

* “Change my location to Munich office.”

  * Outcome: `ok_answer` (if allowed) or `denied_security` (if policy requires HR approval).

---

# CATEGORY 2 - link_rules

## Links

Responses can include a list of **links** that point to specific entities:

* `employee` – an employee in the employee registry.
* `customer` – a company in the CRM.
* `project` – a project in the project registry.
* `wiki` – a wiki article (by path).
* `location` – a recognised location/site.

These links allow user interfaces (e.g. chat frontend, dashboards) to present quick navigation and context around the chatbot’s answer.

---

# CATEGORY 3 - message_formatting

* “What is Sara Romano’s salary?”

  * Message: explanation that salary data is restricted.

---

# CATEGORY 4 - general_constraints

The chatbot returns a **message**, an **outcome** code and a set of **links** to relevant entities.

## Principles for chatbot usage

* Treat the chatbot as a **helpful assistant**, not as a replacement for human judgement.
* Use it to:

  * Discover information faster.
  * Navigate systems without manual searches.
  * Get explanations of processes and terminology.
* If an answer seems wrong or incomplete, verify in the underlying system or contact the relevant system owner (Sales, HR, IT, etc.).
  </kind=wiki id=systems_chatbot_interface.md>

<kind=wiki id=systems_employee_registry.md>

# CATEGORY 2 - link_rules

## What is stored in the employee registry?

For each employee:

* Employee ID (internal unique identifier)

---

# CATEGORY 3 - message_formatting

## Who can see what?

* **All employees (via chatbot):**

  * Name, email, location, department and basic role.
  * Selected skill and will information, depending on context.
* **Managers and HR:**

  * Full profile, including notes and salary.
* **IT & system processes:**

  * Use employee IDs and department/location to enforce access and routing rules.

Access is controlled by **system roles** and internal policies. The chatbot respects these rules and will not reveal confidential information (such as exact salaries) to unauthorised users.
</kind=wiki id=systems_employee_registry.md>

<kind=wiki id=systems_crm.md>

# CATEGORY 2 - link_rules

## What is stored in the CRM?

For each **customer company**:

* Customer ID (internal)
  </kind=wiki id=systems_crm.md>

<kind=wiki id=systems_project_registry.md>

# CATEGORY 2 - link_rules

## Core project fields

Each project has:

* Project ID (internal)
  </kind=wiki id=systems_project_registry.md>

<kind=wiki id=systems_overview.md>

# CATEGORY 4 - general_constraints

## System roles and access

Every employee with system access has:

* A **user account** mapped to an internal employee ID.
* A **location** and **department** associated with their profile.
* One or more **system roles** (e.g. “SalesUser”, “R&DUser”, “HRAdmin”, “ITAdmin”).

Access is granted according to job needs and is centrally managed by IT in coordination with HR and managers.
</kind=wiki id=systems_overview.md>
