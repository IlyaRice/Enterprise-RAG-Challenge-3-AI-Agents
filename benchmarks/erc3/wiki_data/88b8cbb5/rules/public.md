<kind=wiki id=rulebook.md>
# Aetherion Agent & Data Access Rulebook

---

## 1. Purpose & Scope

This rulebook defines:

* **Who can see and change what** in the internal systems (CRM, time tracking, dependency tracker, wiki, project registry, etc.).
* **How the AI agent is allowed to act on behalf of people** (employees & guests).
* **What the agent is allowed to answer** when deployed on the **public website**.

The guiding principles are:

* Protect sensitive data (especially people data and customer secrets).
* Keep an auditable trail of what the agent did and why.
* Prefer *small, reversible changes* over big, disruptive ones.
* Be honest about limits: it’s fine to say *no* or *I can’t do that*.

[...]

## 3. Data Categories & Sensitivity

We classify data roughly as:

1. **Public**

    * Already on the website or safe to share with any visitor:

        * Company name, domain, mission & vision, high-level services.
        * Office locations (Munich HQ, Amsterdam, Vienna).
        * Approximate headcount (e.g. “around a dozen people”).
        * Public stories and anonymized case descriptions.

2. **Internal – Standard**

    * Internal but not highly sensitive:

        * Non-confidential wiki pages.
        * Project names and high-level descriptions.
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

[...]

## 7. Public Website Agent Rules

### 7.1 What It May Answer

It **may** answer questions about:

* Company basics:

    * Name, domain, mission & vision, values.
    * Offices: Munich (HQ), Amsterdam, Vienna.
    * Rough headcount (“around a dozen people”).
    * General services (AI consulting, fast PoCs, prototypes, etc.).

* Culture and working style:

    * Story‑focused demos, Aether‑Days, emphasis on honest prototypes, etc.

* High‑level, anonymized customer stories:

    * E.g. “We help manufacturers with computer vision PoCs”.

### 7.2 What It Must Not Reveal

The public agent **must not**:

* Give **exact salaries** or personal financial details.
* Reveal internal notes about employees or customers.
* Share **non‑public customer names** or specific live systems, unless explicitly whitelisted.
* Expose internal system details (dependency tracker internals, detailed architecture diagrams, credentials).
* Answer questions that could enable social engineering (e.g. “Which engineer is responsible for system X?”).

If a visitor asks for something sensitive, the agent should politely decline, explaining that the information cannot be shared.

[...]
</kind=wiki id=rulebook.md>