# Retention Schedule (GDPR)

**Last updated:** 2026-02-04

## Purpose
Define how long each data category is retained and the deletion/anonymization method.

## Retention Table

| Data Category | System/Location | Retention Period | Deletion Method | Notes |
|---|---|---|---|---|
| User profile (Users) | users table | Until account deletion + 30 days | Anonymize + delete | Remove name/email/phone, mark deleted |
| Conversation logs (MessageLog) | message_logs table | 30 days (configurable) | Hard delete | Controlled by MESSAGE_LOG_RETENTION_DAYS |
| Memories (active) | memories table | While active | Archive then purge | Archived records purged after 365 days |
| Memories (archived) | memories table | 365 days | Hard delete | Controlled by MEMORY_ARCHIVE_RETENTION_DAYS |
| Schedules | schedules table | Until user deletion | Hard delete | Deleted on erase |
| Consent logs | consent_logs table | 6 years (example) | Retain | Adjust for legal requirements |
| GDPR requests | gdpr_requests table | 6 years (example) | Retain | Compliance evidence |
| GDPR audit logs | gdpr_audit_logs table | 6 years (example) | Retain | Compliance evidence |
| Unsubscribes | unsubscribes table | 6 years (example) | Retain | Compliance evidence |

## Configurable Settings
- MESSAGE_LOG_RETENTION_DAYS
- MEMORY_ARCHIVE_RETENTION_DAYS

## Backup Retention
- Backups must be purged according to the same maximum retention period.
- Document backup schedule and deletion process here.
