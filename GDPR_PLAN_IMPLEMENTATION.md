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
- [ ] Allow consent withdrawal and ensure it is as easy as giving consent.
- [ ] Implement age-gating and parental consent if children’s data may be processed (Art. 8).

## 3) Transparency & Notices
- [ ] Provide a clear Privacy Notice (Art. 12–14) covering:
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
- [ ] Right of access (Art. 15)
- [ ] Right to rectification (Art. 16)
- [ ] Right to erasure / “right to be forgotten” (Art. 17)
- [ ] Right to restrict processing (Art. 18)
- [ ] Right to data portability (Art. 20)
- [ ] Right to object (Art. 21)
- [ ] Rights related to automated decision-making and profiling (Art. 22)
- [ ] Identity verification and response SLA (1 month) (Art. 12)
- [ ] DSR logging/audit trail

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
- [ ] Consent storage table with timestamps, scope, and version.
- [ ] DSR endpoints: export, delete, restrict, rectify.
- [ ] Admin tools for DSR handling and audit logs.
- [ ] Retention job (scheduled) for anonymization/deletion.
- [ ] Data portability export (JSON/CSV) with schema/version.
- [ ] Privacy notice and terms endpoints.

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
- [ ] Identify personal data in DB models, logs, and integrations.
- [ ] Update [ARCHITECTURE.md](ARCHITECTURE.md) with data flows.

## B) Database & Models
- [ ] Add consent table/model.
- [ ] Add deletion/anonymization flags.
- [ ] Add audit log table/model for DSR actions.

## C) API Endpoints
- [ ] `GET /gdpr/export` (data portability)
- [ ] `POST /gdpr/erase`
- [ ] `POST /gdpr/restrict`
- [ ] `POST /gdpr/rectify`
- [ ] `GET /gdpr/privacy-notice`

## D) Services
- [ ] DSR service to orchestrate requests.
- [ ] Retention scheduler.
- [ ] Consent verification middleware.

## E) Tests
- [ ] Unit tests for DSR service.
- [ ] API tests for GDPR endpoints.
- [ ] Retention job tests.

## F) Ops & Security
- [ ] Secrets management verification.
- [ ] Logging redaction for personal data.
- [ ] Access control review.

---

## Status Tracking
- Owner:
- Target release:
- Risk assessment:
- Notes:
