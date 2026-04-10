# Telegram group/private routing hardening TODO

1. [ ] Add explicit same-chat routing policy helper (group stays group, private stays private)
2. [ ] Integrate routing helper in webhook path (`src/api/telegram_routes.py`)
3. [ ] Integrate routing helper in polling path (`src/integrations/telegram_polling.py`)
4. [ ] Add concise routing decision logs for transparency/maintainability
5. [ ] Add targeted tests:
   - [ ] group inbound => group outbound
   - [ ] private inbound => private outbound
   - [ ] webhook and polling parity
6. [ ] Run critical-path testing (A)
7. [ ] Fix issues found in A
8. [ ] Run thorough testing (B)
9. [ ] Fix issues found in B
10. [ ] Final verification summary
