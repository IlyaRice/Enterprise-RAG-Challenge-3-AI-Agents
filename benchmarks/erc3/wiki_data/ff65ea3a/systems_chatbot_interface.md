# Chatbot Interface

The **chatbot** is a modern, conversational interface that sits on top of Bellini’s legacy systems (CRM, project registry, employee registry, time tracking and wiki). It allows employees to **ask questions in natural language** and, in some cases, perform simple actions.

## What the chatbot can do

- Answer questions about:
  - Customers and their status.
  - Projects, teams and workloads.
  - Employees, departments, skills and locations.
  - Time tracking summaries for employees, projects and customers.
  - Processes and guidelines documented in the wiki.
- Perform selected actions (depending on permissions):
  - Update employee info (location, department, skills and wills, notes).
  - Update project team or status.
  - Create or update time entries.

The chatbot returns a **message**, an **outcome** code and a set of **links** to relevant entities.

## Outcome codes

Every response includes an `Outcome` value indicating what happened:

- `ok_answer`
  - The chatbot understood the request and produced a meaningful answer.
- `ok_not_found`
  - The request was understood but no matching data was found (e.g. unknown employee ID).
- `denied_security`
  - The request was understood but the user lacks permission (e.g. salary details of another department).
- `none_clarification_needed`
  - The chatbot needs more information (e.g. “Which project do you mean?”).
- `none_unsupported`
  - The chatbot cannot perform this type of request (out of scope).
- `error_internal`
  - Something went wrong internally; IT may need to investigate.

## Links

Responses can include a list of **links** that point to specific entities:

- `employee` – an employee in the employee registry.
- `customer` – a company in the CRM.
- `project` – a project in the project registry.
- `wiki` – a wiki article (by path).
- `location` – a recognised location/site.
- `skill_id` or `will_id` - skills/wills.

These links allow user interfaces (e.g. chat frontend, dashboards) to present quick navigation and context around the chatbot’s answer.

## Examples of interactions

- “Who is responsible for Customer FerroRail?”  
  - Outcome: `ok_answer`  
  - Links: customer (FerroRail), employee (account manager).

- “Show all active projects for Customer X in Germany.”  
  - Outcome: `ok_answer`  
  - Links: multiple projects and the customer.

- “How many hours did we spend on project P‑2025‑017 last quarter?”  
  - Outcome: `ok_answer`  
  - Links: project; optional link to time summary view.

- “What is Sara Romano’s salary?”  
  - Outcome: `denied_security`  
  - Message: explanation that salary data is restricted.

- “Change my location to Munich office.”  
  - Outcome: `ok_answer` (if allowed) or `denied_security` (if policy requires HR approval).  
  - Action: system updates employee location and emits an event.

## Principles for chatbot usage

- Treat the chatbot as a **helpful assistant**, not as a replacement for human judgement.
- Use it to:
  - Discover information faster.
  - Navigate systems without manual searches.
  - Get explanations of processes and terminology.
- If an answer seems wrong or incomplete, verify in the underlying system or contact the relevant system owner (Sales, HR, IT, etc.).

The chatbot is a key part of Bellini’s **pragmatic digitalisation strategy**: modern user experience on top of robust but old core systems.
