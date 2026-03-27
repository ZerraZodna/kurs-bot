# DSR Identity Verification & SLA

**Last updated:** 2024-10-01

## Verification Policy
- Require requestor to prove control of the account or contact channel.
- Acceptable methods:
  - Email verification link
  - One-time code via SMS/Telegram
  - Signed-in session (if applicable)

## Telegram One-Time Code Flow
1. User sends a GDPR request in Telegram (e.g., \"gdpr export\").
2. System generates a 6-digit code and stores a hash + expiry in the DB.
3. Bot replies with the code and asks the user to send \"verify <code>\".
4. System verifies hash + expiry + attempt limit, then executes the request.

## SLA
- Response deadline: 30 days from verified request.
- Extensions: document reason and notify the user if extended.

## Logging
- Log request date, verification method, and completion date.
- Store logs in gdpr_requests and gdpr_audit_logs.
