# CRM – Customer & Deal Tracking

The **CRM (Customer Relationship Management)** system is the central repository for **customer master data** and **high‑level opportunity tracking**.

## What is stored in the CRM?

For each **customer company**:

- Customer ID (internal)
- Name and legal form
- Main address and country
- Industry segment (e.g. Rail, Food & Beverage, General Industry)
- Primary contact name and email
- Assigned account manager (employee ID)
- Short descriptive **brief**
- Current overall **deal phase**
- High‑level status (e.g. “Key account”, “Curious but cautious”, “Dormant”)

For each **opportunity / relationship** (at company level):

- The **deal phase**:
  - `idea` – new lead, early conversation.
  - `exploring` – deeper exploration, early trials.
  - `active` – ongoing projects, regular business.
  - `paused` – no current activity, but not lost.
  - `archived` – relationship closed or no realistic future business.
- Optional descriptive notes and tags.

## Who uses the CRM?

- **Sales & Customer Success**
  - Primary owners of customer records and deal phases.
- **Customer Service**
  - Updates contact details and practical information.
- **Management and Finance**
  - Use CRM data for pipeline reviews and account prioritisation.
- **Chatbot**
  - Answers questions like “Who is the account manager for Customer X?” or “Show all active customers in Germany in the rail segment.”

## Basic rules for using the CRM

1. **Every active customer must exist in CRM.**
   - No “shadow customers” known only via email or spreadsheets.
2. **Each customer must have a clear account manager.**
   - The account manager is responsible for keeping data up to date.
3. **Use concise and informative briefs.**
   - Explain who the customer is, what they do and why they matter.
4. **Maintain deal phases realistically.**
   - Reflect the true state of the commercial relationship, not wishful thinking.

## Linking to other systems

- **Project registry:**
  - Projects always reference a **customer ID** from the CRM (unless internal).
- **Time tracking:**
  - Time entries for customer work show both the **customer** and the **project**, enabling customer profitability and effort analysis.
- **Wiki and chatbot:**
  - Wiki pages may describe key accounts or reference successful case studies.
  - The chatbot provides quick overviews of customer status, contacts, projects and time summaries.

Keeping CRM data clean and current is critical for accurate reporting and for the chatbot to give trustworthy answers.
