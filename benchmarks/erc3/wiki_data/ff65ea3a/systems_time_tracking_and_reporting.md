# Time Tracking & Reporting

Bellini Coatings uses a central **time tracking system** to understand how employees spend their time across customers, projects and internal activities.

Most non‑production employees (and selected production roles) are required to log time regularly.

## Time entry structure

Each time entry contains:

- Employee (employee ID)
- Customer (optional, usually derived from project)
- Project (project ID, customer or internal)
- Date (YYYY‑MM‑DD)
- Hours (decimal, e.g. 1.0, 7.5)
- Work category (e.g. `customer_project`, `internal`, `support`, `admin`)
- Notes (short free text)
- Billable flag (billable vs non‑billable)
- Status:
  - `draft`
  - `submitted`
  - `approved`
  - `invoiced`
  - `voided`

## Lifecycle of time entries

1. **Draft**
   - Employee is still editing; corrections are allowed.
2. **Submitted**
   - Employee considers entries complete for the period (e.g. week, month).
3. **Approved**
   - Supervisor or operations has reviewed entries for consistency.
4. **Invoiced**
   - Entries have been used for billing or customer reporting; they are effectively locked.
5. **Voided**
   - Entry has been cancelled (e.g. wrong project). Usually paired with a correcting entry.

After approval, employees cannot change entries directly; corrections require specific processes to ensure an audit trail.

## Why we track time

- **Customer profitability**
  - Understand how much effort is invested in supporting each customer.
- **Project costing**
  - Analyse efforts spent on different project types and stages.
- **Workload monitoring**
  - Identify overloaded employees or teams.
- **Internal improvements**
  - Quantify time spent on non‑customer initiatives (e.g. training, digital projects).

## Usage expectations

- Employees should log time **at least weekly**, ideally daily.
- Use **projects** consistently:
  - Customer work → customer projects.
  - Internal initiatives → internal projects (e.g. “IT – Chatbot Pilot 2025”).
- Notes should be concise but informative (what was done, not just “meeting”).
- Project leads can log entries for the team members in draft mode. They are NOT allowed to submit entries for them.

## Reporting and summaries

The system can aggregate and summarise time in different ways:

- **By project and customer**
  - Hours, billable vs non‑billable, number of distinct employees.
- **By employee**
  - Total hours, distribution between customer work and internal activities.

The chatbot can answer questions like:

- “How many hours did we spend on Customer X last quarter?”
- “Show time spent by Sara Romano on project P‑2025‑017 this year.”
- “Which employees logged more than 45 hours in the past week?”

Correct and timely time logging is essential for good data and fair decisions.

## Workload estimation

Note, that when estimating workload (e.g. who is busiest or non-busiest), we rely on workload time slices via Project registry.