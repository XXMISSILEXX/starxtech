# Open questions

1. Can a Partner be restored while its Company remains archived? Recommendation:
   yes for history, but block assigning/changing to inactive Company.
2. Is any cascade archive desired? Recommendation: no Company → Partner cascade;
   preserve independent lifecycle and links.
3. Does Department require public archive/restore now, or is inactive-only
   sufficient for MVP? Confirm operator workflow and historical org chart need.
4. Is an archived Relationship UI needed immediately? Recommendation: no; keep
   active tree clean and support audited admin restore first.
5. Should restore have a separate permission? Recommendation: yes, `*.restore`.
6. Is hard delete ever permitted? Recommendation: never via application UI;
   exceptional retention/legal purge must be separately approved and audited.
7. Should archive reason and timestamp be stored on entity? AuditLog is enough
   for MVP; add fields only if reporting/retention requirements demand them.
8. Which legacy POST deactivate/delete aliases must be retained, and for how
   long? Inventory integrations before canonical route rollout.
