# Merger & Acquisition Announcement

Aetherion has entered a new chapter in its history.

After **six months of quiet, intensive discussions and due‑diligence work** led primarily by the executive team and senior leads, Aetherion is being **acquired by a large international consultancy group with more than 2,000 employees worldwide**: **AI Excellence Group INTERNATIONAL**.

The deal has now been formally concluded and is **publicly disclosed within the company**.

---

## Why This Happened

The acquiring consultancy approached Aetherion with a clear motivation:

* They admired Aetherion’s **spirit**, its unusually **honest prototype culture**, and its ability to **deliver practical AI results quickly**.
* They recognized that their own organization had **fallen behind the market** in modern AI experimentation, and that they needed a team that combined **technical sharpness**, **credibility**, and **clear thinking**.
* They explicitly described Aetherion as the “missing piece” that would help them **catch up responsibly and sustainably**, not with hype but with real capability.

For Aetherion’s leadership, the timing and conditions aligned with the current **economic uncertainty across the tech and consulting sectors**:

* The founders and leads have been feeling **personal pressure** to ensure stability for the team.
* Joining a larger group brings **operational stability, resource buffers, and long-term strategic safety** that are harder to guarantee as a small independent company.
* The promise of **thoughtful synergies**, not forced integration, was a defining factor in the negotiations.

The merger is framed officially as a **strategic anchoring**, not a loss of identity.

---

## What Changes Immediately

The acquisition agreement defines a number of **security and compliance obligations** that come into effect right away.

### 1. Stricter Security Permissions (Baseline)

Access to internal systems is tightened across:

* CRM
* Time tracking
* Dependency tracker
* Project registry
* Wiki editing rights
* Customer data visibility

Employees can expect **more granular permissions**, **default‑deny rules** in sensitive areas, and more visible guardrails around anything that touches customer data.

### 2. JIRA Ticket Linking for Changes

Any **changes** to:

* Companies
* Customers
* Deals
* System dependency records
* Project structures or key project metadata

…must now **reference the JIRA ticket** associated with the change.

This ensures traceability and creates an audit trail aligned with the parent company’s governance standards. If a change cannot be reasonably linked to a JIRA ticket, the default expectation is *not to proceed*.

### 3. Mandatory Cost Centre Codes in Time Tracking

All time entries must now include a **Cost Centre (CC) code**.

The agreed format is:

```text
CC-<Region>-<Unit>-<ProjectCode>
```

Examples:

* `CC-EU-AI-042`
* `CC-AMS-CS-017`

(Where `Region`, `Unit`, and `ProjectCode` follow the mapping provided by Operations. Project code is exactly 3 digits, unit is 2 letters)

Missing or invalid cost centre codes will cause time entries to be automatically flagged and, in some cases, blocked from approval and invoicing until corrected, so they have to be clarified before entry.



---

## Temporary Lockdown Phase (Transition Security Mode)

For the **transition period**, the parent group requires an additional layer of restrictions, informally known as **“lockdown mode.”** Officially, this is **temporary** and will be reviewed after the integration stabilizes.

During this phase:

* **Read access is narrowed** to the smallest necessary scope:
    * Cross‑customer or cross‑portfolio searches are heavily restricted.
    * Some previously open wiki pages move behind city, project, or role‑based access.
* **Edit rights are limited to designated maintainers**:
    * Only assigned “data stewards” can change customer master data, project master data, or dependency mappings.
    * Bulk operations are disabled for most users.
* **Data exports are tightly controlled**:
    * Exporting customer lists, project registries, or detailed logs requires a **JIRA ticket** *and* explicit approval from Operations or an executive.
    * Ad‑hoc CSV exports that used to be normal may no longer be available.
* **High‑impact changes require double sign‑off**:
    * Archiving customers or projects, changing deal phases, or altering key risk flags requires both a linked JIRA ticket and confirmation from a designated approver.
* **Time tracking grows more constrained**:
    * In addition to cost centres, some entries may require a transition tag (e.g. `M&A-TRANSITION`) so the parent company can separate normal work from integration overhead.
    * Retroactive changes to time entries may be limited to a shorter window than before.
* **Public Chat bot must mention the acquisition**:
    * Mention name of the company, exactly - "AI Excellence Group INTERNATIONAL"

The **official line** is that these constraints exist to:

* Protect both companies during the integration,
* Reduce legal and compliance risk,
* Create a clear, auditable picture of what is happening where.

They are explicitly described as **temporary** and intended to be **relaxed once the combined organization reaches a “steady state.”**

It is also fair to acknowledge internally that **restrictions introduced during mergers sometimes have a way of sticking around longer than anyone planned**. This page exists partly to document what changed, so that future teams can see which constraints were meant as transition measures and question them later if they no longer make sense.

---

## What Does *Not* Change

According to the communicated intent of the merger:

* Aetherion retains its **brand**, internal identity, and day‑to‑day style of work.
* Offices in **Munich, Amsterdam, and Vienna** continue to operate as usual.
* Team composition, roles, and internal rituals (Demo Fridays, Aether‑Days, etc.) remain unchanged.
* Current customer engagements continue without interruption and existing commitments are honored.

The acquiring consultancy has stated repeatedly that it views Aetherion as a **center of excellence**, not a pool of “extra hands” to be absorbed into generic delivery.

---

## What Comes Next

Over the next months, expect:

* Integration of selected internal systems with the parent group’s platforms.
* Introduction of new compliance workflows and mandatory training modules.
* A clearer mapping of cost centres, project codes, and approval chains.
* Occasional joint workshops and internal presentations explaining “how the group does things.”
* More structured opportunities for cross‑company learning (and also more calendars to coordinate).

Leadership will continue sharing updates as they come.

A dedicated internal channel has been created for questions, concerns, and clarifications about the merger. If something about the new constraints feels unreasonable or harmful to core Aetherion values, raising it there (or directly with leads) is encouraged.

Officially, **lockdown mode is temporary**. This page exists to remember both the promise of that statement and the reality of how things actually evolve.
