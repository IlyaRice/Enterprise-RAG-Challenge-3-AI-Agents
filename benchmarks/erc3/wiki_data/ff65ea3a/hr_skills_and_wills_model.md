# Skills & Wills Model

The **skills & wills** model describes what employees **can do** and what they **want to do**. It is implemented in the **employee registry** and is accessible to HR, managers, the chatbot and selected systems.

## Definitions

- **Skill**
  - A capability the employee has (e.g. “Solventborne formulation”, “German language”, “Project management”).
  - Stored as a `SkillLevel` with fields `name` and `level`.

- **Will**
  - An aspiration, interest or preference of the employee (e.g. “Interest in people management”, “Willingness to travel”, “Interest in automation projects”).
  - Also stored as a `SkillLevel`, but interpreted as motivation rather than demonstrated ability.

Both skills and wills are represented as **lists of `SkillLevel` objects** in the employee registry and are always stored **sorted alphabetically by name**.

## Rating scale

Bellini uses a **1–10 scale** for both skills and wills:

- **1–2:** Very low – limited exposure or interest.
- **3–4:** Basic – some experience or mild interest.
- **5–6:** Solid – can perform reliably / clear and stable interest.
- **7–8:** Strong – recognised expertise / strong motivation.
- **9–10:** Exceptional – go‑to person / very strong drive.

The maximum skill level configured in our systems is **10**.

## Principles for keeping profiles up to date

- **Employees and managers** update skills and wills during annual reviews and as needed after major changes (new responsibilities, training, relocations).
- Employees are encouraged to update their skills and wills outside of reviews as well, as a part of **SkillWillReflect update**.
- HR encourages **realistic ratings**: it is acceptable to have some high scores, but profiles should reflect reality, not wishful thinking.
- Wills are particularly important for:
  - Identifying candidates for **succession planning** and promotions.
  - Finding volunteers for **projects**, pilots or training.
  - Understanding who is open to **travel, relocation or cross‑functional work**.

## Use cases

- **Staffing projects:**
  - R&D and Sales leaders search for employees with specific skills above a threshold (e.g. “epoxy floor systems ≥ 7”).
- **Career development:**
  - Managers and HR use wills to propose training or role changes aligned with interests.
- **Chatbot queries:**
  - Employees can ask “Who in Serbia has strong skills in corrosion testing?” or “Who is interested in leading digitalisation projects?”.
- **Workload and succession:**
  - Combined with time tracking and project registry data, skills & wills help avoid single points of failure and distribute work fairly.

Keeping skills and wills profiles accurate is a **shared responsibility** between employees, managers and HR.
