# Phase 9 definition of done

Phase 9 is complete when all Phase 9 automated gates, PostgreSQL migration and
security checks, route audit, canonical dashboard navigation, and Chrome
desktop/mobile acceptance evidence pass. Category snapshot/required
enforcement remains deferred; Phase 10 is not started here.

For Step 9.10A, completion additionally requires authenticated desktop and
mobile smoke for selector navigation and assignment modal lifecycle; automated
gates alone do not satisfy that final acceptance condition.

The native-date and analytics portion is complete only after the full warning-
as-error test suite, JavaScript syntax/npm checks, dependency/security/migration
checks, and authenticated responsive smoke have been repeated. The smoke must
confirm native pickers, future-date rejection, analytics charts and accessible
summaries at desktop, 390×844, 430×932, and 768×1024.

For Step 9.10B, the same smoke additionally confirms the client-side Project
Update future-date feedback, Reports navigation order in the desktop sidebar
and mobile offcanvas, System tab order, and the responsive vertical contractor
active-project chart without console or CSP errors.
