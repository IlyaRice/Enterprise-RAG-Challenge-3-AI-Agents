# Employee Registry

The **employee registry** is the authoritative source for information about **people** at Bellini Coatings.

## What is stored in the employee registry?

For each employee:

- Employee ID (internal unique identifier)
- Full name
- Auto‑generated email address
- Salary (confidential)
- Free‑text notes (HR/internal use)
- Location (e.g. “HQ – Italy”, “Serbian Plant”, “Munich Office”)
- Department (one of the standard departments)
- Skills (list of `SkillLevel` entries)
- Wills (list of `SkillLevel` entries)

Skills and wills are documented in detail in [Skills & Wills Model](../hr/skills_and_wills_model.md).

## Who can see what?

- **All employees (via chatbot):**
  - Name, email, location, department and basic role.
  - Selected skill and will information, depending on context.
- **Managers and HR:**
  - Full profile, including notes and salary.
- **IT & system processes:**
  - Use employee IDs and department/location to enforce access and routing rules.

Access is controlled by **system roles** and internal policies. The chatbot respects these rules and will not reveal confidential information (such as exact salaries) to unauthorised users.

## How data gets into the registry

- When an employee is hired, HR creates a record with:
  - Initial notes
  - Location
  - Department
  - Salary
  - Initial skills and wills
- Updates happen through:
  - HR changes (e.g. promotions, relocations, salary adjustments).
  - Manager and employee updates during reviews (skills and wills).
  - System events (e.g. location updates based on site changes).

Each significant change is recorded with “changed by” information for auditing.

## Typical usage

- **HR and managers**
  - Look up reporting lines, salary ranges (where allowed), and skill distributions.
- **Project staffing**
  - Find people with specific skills at certain levels (e.g. “epoxy floor systems ≥ 7”).
- **Cross‑site collaboration**
  - Identify experts in other locations or departments.
- **Chatbot queries**
  - “Who is the plant manager in Serbia?”
  - “Which employees report to the R&D Director?”
  - “Show Sara Romano’s skills and current department.”

Accurate employee records are essential for planning, analytics and for the chatbot to be helpful.
