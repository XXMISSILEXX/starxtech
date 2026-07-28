# Phase 10 Step 7 — PoC selection

The ranked candidates below exclude the five root causes already covered by the
existing critical PoCs. “Effective severity” reflects executable reachability
in the isolated Flask test fixture, not a change to the original finding.

| Rank | Finding ID | Original severity | Effective severity | Reachable actor | Impact | Existing PoC duplicate? | Selected? | Reason |
|---:|---|---|---|---|---|---|---|---|
| 1 | REPORTS-001 | High | High | Reporter with `can_create_reports` on one project | Cancelling an owned session deletes pending uploads from another project | No | Yes | Deterministic cross-project destructive cleanup through a registered POST route. |
| 2 | CUSTOMER-001 | High | High | Custom `customers.edit` holder with read access to only one source project | Re-parents a project without management authority over its source customer | No | Yes | Deterministic cross-customer write; empty target makes the weak target check reachable. |
| 3 | CONTRACTOR-001 | High | High | Custom contractor-assignment manager with read scope on target project | Inserts an inaccessible contractor into that project and expands contractor visibility | No | Yes | Direct cross-project IDOR by client-supplied contractor ID. |
| 4 | AI-002 | Medium | High | Project document viewer without `project_document_files.download` | Receives a usable original-file signed URL | No | Yes | Independently confirmed: the download predicate uses `can_view_documents`, not the catalogue download permission. |
| 5 | ISSUE-002 | Medium | Medium | Project issue editor lacking `issues.delete` | Soft-deletes an issue through edit capability | No | Yes | Deterministic destructive-action/RBAC mismatch on a real POST route. |
| 6 | CM-001 | High | High | Company Media viewer without file-download permission | Mints original video URL through preview | Yes — same view-vs-download capability root cause as AI-002 | No | Kept as corroboration, not a second PoC for the same authorization-drift root cause. |
| 7 | PD-001 | High | High | Restricted-folder share ACL holder | Rewrites own ACL with unrelated capabilities | Yes — same self-ACL-escalation family as critical PoC 05 | No | Existing Company Media PoC already proves the share-only self-escalation root cause. |
| 8 | UPLOAD-001 | High | Medium | Authorized direct uploader | Format-confused bytes reach image processing | No | No | Safe byte-level reproduction would not establish exploit impact without risky processing/CVE assumptions. |
| 9 | DASHBOARD-004 | Medium | Medium | Contractor dashboard viewer with issue access only on another linked project | Reads issue titles/statuses for a project lacking issue-view capability | No | No | Valuable IDOR, but ranked below the selected direct destructive and signed-download routes. |
| 10 | REPORTS-004 | Medium | Medium | Report editor lacking `report_attachments.delete` | Deletes attachment with edit capability | No | No | Distinct finding, but lower priority than ISSUE-002’s directly destructive global permission mismatch. |
| 11 | DASHBOARD-001 | Medium | Medium | Project dashboard reader without `can_view_reports` | Sees report history and dashboard report data | No | No | Read-only capability drift; selected routes above have greater direct impact. |
| 12 | ISSUE-001 | Medium | Medium | User with issue capability on one project | Global list includes issues from readable-project scope lacking issue-view capability | No | No | Read-only scope drift; below cross-project writes/deletes. |
| 13 | REPORTS-002 | Medium | Medium | `reports.today.view` holder without `can_view_reports` | “Today” exposes report data | No | No | Read-only capability drift; below selected writes/destructive operations. |
| 14 | DASHBOARD-003 | Medium | Medium | Project dashboard viewer without project issue access | Learns issue totals/status aggregates | No | No | Aggregate disclosure only. |
| 15 | PROJECT-OPS-001 | Medium | Medium | Project-update creator probing foreign assignment IDs | Error page discloses contractor identity | No | No | Bounded identity disclosure; no unauthorized write occurs. |

Selected root causes are distinct: global cleanup scope, source-object write
authorization, cross-project identifier authorization, signed-download
capability enforcement, and destructive permission enforcement.
