# Migration notes

## Scope

- **Source:** HelpDocs site `docs.getthread.com` (account `pplv67kiu4`), read API.
- **Total articles in HelpDocs:** ~261 (incl. drafts/unpublished).
- **Migrated (in scope):** 151 — every published article, plus private articles
  created or updated on/after **2026-04-27** (last ~60 days). Drafts, unpublished
  articles, and older private articles were excluded.

## Information architecture

The HelpDocs category tree (55 categories, several duplicated/untitled) was
reorganized into 13 top-level sections. Mapping (HelpDocs categories → section):

| Section | Includes |
|---|---|
| Get Started | Getting Started |
| Thread Inbox | Thread Inbox, App Overview & Behavior, Getting Started w/ Inbox, Views & Insights, Flows, Planner, Snippets, Tips & Tricks, Admin Panel, Approvals |
| Assistive AI | Auto Prioritization, Auto Categorization, Auto Title, Recap Templates, Sentiment, + prompt/variable guides |
| AI Agents | Triage Agent, Voice AI, Reminder Agent, Contact/Client Intelligence |
| Super Magic | Super Magic + Super Magic Tools |
| Magic Analytics | Magic Analytics |
| Automagically | Automagically |
| Messenger | Messenger + Getting Started, Teams/Slack/Desktop/Web service apps, Messenger FAQ |
| Companion Apps | Teams & Slack companion apps for service teams |
| Integrations | PSA (ConnectWise, Autotask, Halo) + Other (Hudu, IT Glue, Rewst, Auvik, CloudRadial, etc.) |
| Notifications | Notifications for Customers / Team |
| Security & Billing | Security & Billing |
| Adoption | Customer Communication & Adoption |

Sub-categories render as nested groups inside their section in `docs.json`.

## Conversion

`scripts/migrate.py` converts HelpDocs WYSIWYG HTML to Mintlify MDX:
- headings, lists (nested), bold/italic, links, blockquotes, tables → GFM
- `tip-callout` / `note-callout` / `warning-callout` → `<Tip>` / `<Note>` / `<Warning>`
- Loom embeds → `<Frame><iframe></Frame>`
- `<pre>` → fenced code blocks; `{{variables}}` preserved inside code spans
- internal `/article/<id>` and `/category/<id>` links rewritten to new paths
- `<figure><img>` → markdown images pointing at local `/images/...`; original URLs
  recorded in `scripts/image-manifest.json` (385 images)
- MDX-hazardous characters (`{ } <`) escaped in body text

## Pages awaiting a live re-run (15)

These came back during the initial pull only as rate-limited or inline responses
that couldn't be cached, so they're currently placeholders ("Content for this
article is being migrated"). A single `HELPDOCS_API_KEY=… python3 scripts/migrate.py`
run fills them with real content (and downloads all images):

- ai-agents/approvals.mdx — Automate Approvals with Magic Agents
- ai-agents/custom-rules-beta-partner-guide.mdx — New Custom Rules — Triage Agent
- ai-agents/outbound-calling-lite.mdx — Outbound Calling
- ai-agents/setting-up-your-triage-agent-user-guide.mdx — Setting up your Triage Agent (User Guide)
- ai-agents/voice-ai-outbound-calling.mdx — Voice AI - Outbound Calling
- assistive-ai/how-to-set-up-auto-prioritization.mdx — Configuring Auto Prioritization
- assistive-ai/proactive-suggestions-in-ask-magic-partner-guide.mdx — Proactive Suggestions in Ask Magic
- get-started/thread-product-overview-your-guide-to-the-ai-powered-msp-service-desk.mdx — Thread Product Overview
- inbox/approvals-in-inbox.mdx — Approvals in Inbox
- inbox/inbox-teams.mdx — Inbox Teams
- inbox/planner-outlook-calendar-integration.mdx — Planner ↔ Outlook Calendar Integration
- integrations/microsoft-bookings-integration-for-psa-scheduling.mdx — Automated Scheduling w/ Microsoft Bookings
- integrations/pia-integration.mdx — Pia Integration
- super-magic/add-external-tools-to-super-magic-with-connectors-super-mcp.mdx — Add External Tools (Super MCP)
- super-magic/use-liongard-with-super-magic.mdx — Use Liongard with Super Magic

## Images

All 385 referenced images are catalogued in `scripts/image-manifest.json` with their
target local paths. They download on the next `migrate.py` run, or via
`python3 scripts/fetch_assets.py`.
