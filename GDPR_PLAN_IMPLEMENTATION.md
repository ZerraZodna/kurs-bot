# GDPR Plan & Implementation Checklist

> Scope: All items are required for EU GDPR compliance for this application.
> Date: 2026-02-04

## 1) Governance & Accountability
- [ ] Appoint a Data Protection Officer (DPO) or document why not required (Art. 37–39).
- [ ] Maintain Records of Processing Activities (RoPA) (Art. 30).
- [ ] Establish a data protection policy and staff training.
- [ ] Perform and document a Data Protection Impact Assessment (DPIA) (Art. 35).
- [ ] Define roles: controller/processor and data processing agreements (DPAs) with vendors (Art. 28).

## 2) Lawful Basis & Consent
- [ ] Document lawful basis for each processing purpose (Art. 6).
- [ ] For consent-based processing: implement explicit, granular consent and audit trail (Art. 7).
- [x] Allow consent withdrawal and ensure it is as easy as giving consent.
- [ ] Implement age-gating and parental consent if children’s data may be processed (Art. 8).

## 3) Transparency & Notices
- [x] Provide a clear Privacy Notice (Art. 12–14) covering:
  - Identity and contact of controller/DPO
  - Purposes and lawful bases
  - Categories of personal data
  - Recipients and international transfers
  - Retention periods
  - Data subject rights
  - Right to lodge complaint with supervisory authority
  - Whether data is mandatory and consequences of refusal
  - Automated decision-making and logic (if applicable)

## 4) Data Subject Rights (DSR)
Implement and document processes + APIs for:
- [x] Right of access (Art. 15)
- [x] Right to rectification (Art. 16)
- [x] Right to erasure / “right to be forgotten” (Art. 17)
- [x] Right to restrict processing (Art. 18)
- [x] Right to data portability (Art. 20)
- [x] Right to object (Art. 21)
- [ ] Rights related to automated decision-making and profiling (Art. 22)
- [ ] Identity verification and response SLA (1 month) (Art. 12)
- [x] DSR logging/audit trail

## 5) Data Minimization & Purpose Limitation
- [ ] Collect only required data fields.
- [ ] Enforce purpose limitation in code and data access.
- [ ] Disable optional data collection by default.

## 6) Retention & Deletion
- [ ] Define retention schedule per data category (Art. 5(1)(e)).
- [ ] Implement automated deletion/anonymization jobs.
- [ ] Ensure backups follow retention & deletion policy.

## 7) Security of Processing
- [ ] Encryption in transit (TLS) and at rest.
- [ ] Secrets management; no secrets in code.
- [ ] Access control (least privilege) and audit logging.
- [ ] Pseudonymization/anonymization where feasible.
- [ ] Regular security testing and vulnerability management.

## 8) International Transfers
- [ ] Identify all data transfer destinations.
- [ ] Implement SCCs or ensure adequacy decisions.
- [ ] Document transfer impact assessments.

## 9) Incident & Breach Response
- [ ] Incident response plan.
- [ ] Breach notification within 72 hours (Art. 33).
- [ ] Communicate high-risk breaches to data subjects (Art. 34).

## 10) Vendor & Subprocessor Management
- [ ] Maintain vendor list and subprocessors.
- [ ] Ensure DPAs and security due diligence.
- [ ] Subprocessor change notifications.

## 11) Product Features to Implement (Code/DB)
- [ ] Data inventory: map all personal data fields and processing.
- [x] Consent storage table with timestamps, scope, and version.
- [x] DSR endpoints: export, delete, restrict, rectify.
- [ ] Admin tools for DSR handling and audit logs.
- [x] Retention job (scheduled) for anonymization/deletion.
- [x] Data portability export (JSON/CSV) with schema/version.
- [x] Privacy notice and terms endpoints.

## 12) Documentation & Evidence
- [ ] DPIA report.
- [ ] RoPA.
- [ ] Security policies and controls.
- [ ] Vendor DPAs.
- [ ] DSR request logs.
- [ ] Retention schedule.

---

# Implementation Plan for This Repository

## A) Data Inventory
- [x] Identify personal data in DB models, logs, and integrations.
- [x] Update [ARCHITECTURE.md](ARCHITECTURE.md) with data flows.

## B) Database & Models
- [x] Add consent table/model.
- [x] Add deletion/anonymization flags.
- [x] Add audit log table/model for DSR actions.

## C) API Endpoints
- [x] `GET /gdpr/export` (data portability)
- [x] `POST /gdpr/erase`
- [x] `POST /gdpr/restrict`
- [x] `POST /gdpr/rectify`
- [x] `GET /gdpr/privacy-notice`

## D) Services
- [x] DSR service to orchestrate requests.
- [x] Retention scheduler.
- [x] Consent verification middleware.

## E) Tests
- [x] Unit tests for DSR service.
- [x] API tests for GDPR endpoints.
- [x] Retention job tests.

## F) Ops & Security
- [x] Secrets management verification.
- [x] Logging redaction for personal data.
- [x] Access control review.

---

## Status Tracking
- Owner:
- Target release:
- Risk assessment:
- Notes:

---

# Execution Plan (What to do & how)

## 1) Governance & Accountability
**What:** Decide if a DPO is required; create RoPA; run DPIA; define controller/processor roles; execute DPAs.
**How:**
- Appoint DPO or document exemption criteria.
- Create RoPA: list processing purposes, categories, recipients, retention, transfers.
- Run DPIA: identify risks, mitigations, residual risk acceptance.
- Map vendors to controller/processor roles and sign DPAs.

## 2) Lawful Basis & Consent
**What:** Document lawful basis per purpose; implement consent withdrawal; age-gating if applicable.
**How:**
- Add a “lawful basis” table in docs (purpose → basis).
- Add consent withdrawal flow (API/UI) and log to ConsentLog.
- If children may use the app: implement age-gate + parental consent record.

## 3) Data Subject Rights (remaining)
**What:** Right to object, Art. 22 protections, identity verification + SLA.
**How:**
- Add `/gdpr/object` endpoint to set processing_restricted + record request.
- Document automated decision-making logic and offer human review if needed.
- Add identity verification policy (email/phone confirmation) and DSR SLA tracking.

## 4) Data Minimization & Purpose Limitation
**What:** Ensure only required fields collected; enforce purpose limits.
**How:**
- Review all stored fields and remove optional defaults.
- Add explicit per-purpose flags in code paths (e.g., memory storage only after consent).

## 5) Retention & Deletion
**What:** Define retention schedule and enforce deletion/anonymization.
**How:**
- Create a retention policy table in docs (per data category + max duration).
- Align scheduled jobs with policy; document backup purge procedure.

## 6) Security of Processing (Ops & Security)
**What:** TLS/at-rest encryption, secrets verification, logging redaction, access control review.
**How:**
- Verify TLS on all endpoints and enable DB/storage encryption.
- Audit secrets in repo; ensure all secrets come from env/secret store.
- Add log redaction for email/phone/message content.
- Review roles/permissions for API and DB; enforce least privilege.

## 7) International Transfers & Vendors
**What:** Identify transfer destinations and ensure safeguards.
**How:**
- List all vendors + regions in RoPA.
- Attach SCCs or adequacy decisions; document TIAs.

## 8) Incident & Breach Response
**What:** Create response plan and notification workflow.
**How:**
- Write an incident runbook (72-hour notification process).
- Define severity levels, contact list, and communication templates.

## 9) Documentation & Evidence
**What:** DPIA, RoPA, policies, DSR logs, retention schedule.
**How:**
- Store documents in docs/ with versioning.
- Add release checklist to confirm compliance artifacts are updated.

Artifacts created:
- docs/RETENTION_SCHEDULE.md
- docs/ROPA.md
- docs/DPIA.md
- docs/INCIDENT_RESPONSE_PLAN.md
- docs/VENDOR_SUBPROCESSORS.md
- docs/DSR_ID_VERIFICATION.md
