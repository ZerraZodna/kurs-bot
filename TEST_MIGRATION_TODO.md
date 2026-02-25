# Test Migration TODO

## Goal: Migrate tests to new framework structure

### Test Categories:
1. **Unit Tests** - tests/unit/
2. **Integration Tests** - tests/integration/
3. **E2E Tests** - tests/e2e/

## Progress: 46/66 files migrated (All duplicate source files deleted)

### Phase 1: Memory Tests (tests/unit/memory/)
- [x] tests/test_memory_manager.py → tests/unit/memory/test_memory_manager.py
- [x] tests/test_memory_model.py → tests/unit/memory/test_memory_model.py
- [x] tests/test_memory_extractor.py → tests/unit/memory/test_memory_extractor.py
- [x] (tests/test_semantic_search.py - file does not exist, was likely removed)
- [x] tests/test_semantic_search_reuse.py → tests/unit/memory/test_semantic_search_reuse.py
- [x] tests/test_search_threshold.py → tests/unit/memory/test_search_threshold.py

### Phase 2: Scheduler Tests (tests/unit/scheduler/)
- [x] tests/test_scheduler_service.py → tests/unit/scheduler/test_scheduler_service.py
- [x] tests/test_scheduler_manager.py → tests/unit/scheduler/test_scheduler_manager.py
- [x] tests/test_scheduler_domain.py → tests/unit/scheduler/test_scheduler_domain.py
- [x] tests/test_scheduler_jobs.py → tests/unit/scheduler/test_scheduler_jobs.py
- [x] tests/test_scheduler_characterization.py → tests/unit/scheduler/test_scheduler_characterization.py
- [x] tests/test_schedule_model.py → tests/unit/scheduler/test_schedule_model.py
- [x] tests/test_timezones.py → tests/unit/scheduler/test_timezones.py

### Phase 3: Onboarding Tests (tests/unit/onboarding/)
- [x] tests/test_onboarding.py → tests/unit/onboarding/test_onboarding.py
- [x] tests/test_onboarding_flow.py → tests/unit/onboarding/test_onboarding_flow.py
- [x] tests/test_onboarding_language.py → tests/unit/onboarding/test_onboarding_language.py
- [x] tests/test_onboarding_lesson_state.py → tests/unit/onboarding/test_onboarding_lesson_state.py
- [x] tests/test_onboarding_scheduling.py → tests/unit/onboarding/test_onboarding_scheduling.py
- [x] tests/test_onboarding_fact_extraction.py → tests/unit/onboarding/test_onboarding_fact_extraction.py
- [x] tests/test_onboarding_defers_lesson_request.py → tests/unit/onboarding/test_onboarding_defers_lesson_request.py
- [x] tests/test_onboarding_service_integration.py → tests/unit/onboarding/test_onboarding_service_integration.py

### Phase 4: Language/Detection Tests (tests/unit/language/)
- [x] tests/test_detect_language_hi.py → tests/unit/language/test_detect_language_hi.py
- [x] tests/test_detect_language_regression.py → tests/unit/language/test_detect_language_regression.py
- [x] tests/test_detect_language_regression_portuguese.py → tests/unit/language/test_detect_language_regression_portuguese.py
- [x] tests/test_language_detection_short_messages.py → tests/unit/language/test_language_detection_short_messages.py
- [x] tests/test_language_override_set_command.py → tests/unit/language/test_language_override_set_command.py
- [x] tests/test_lesson_query_detection.py → tests/unit/language/test_lesson_query_detection.py

### Phase 5: Trigger Tests (tests/unit/triggers/)
- [x] tests/test_trigger_matcher.py → tests/unit/triggers/test_trigger_matcher.py
- [x] tests/test_trigger_matching.py → tests/unit/triggers/test_trigger_matching.py
- [x] tests/test_trigger_dispatcher.py → tests/unit/triggers/test_trigger_dispatcher.py (MIGRATED)
- [x] tests/test_trigger_dispatcher_update.py → tests/unit/triggers/test_trigger_dispatcher_update.py (MIGRATED)
- [x] tests/test_trigger_admin_commands.py → tests/unit/triggers/test_trigger_admin_commands.py (MIGRATED)
- [x] tests/test_trigger_embeddings_seed.py → tests/unit/triggers/test_trigger_embeddings_seed.py (MIGRATED)
- [x] tests/test_trigger_observability.py → tests/unit/triggers/test_trigger_observability.py (MIGRATED)

### Phase 6: Services Tests (tests/unit/services/)
- [x] tests/test_embedding_service.py → tests/unit/services/test_embedding_service.py (MIGRATED)
- [x] tests/test_prompt_builder.py → tests/unit/services/test_prompt_builder.py (MIGRATED)

### Phase 7: Integration Tests (tests/integration/)
- [x] tests/test_integration_memory.py → tests/integration/test_memory_integration.py (MIGRATED)
- [x] tests/test_memory_driven_scheduler_integration.py → tests/integration/test_memory_driven_scheduler_integration.py (MIGRATED)
- [x] tests/test_trigger_scheduler_integration.py → tests/integration/test_trigger_scheduler_integration.py (MIGRATED)

### Phase 8: E2E Tests (tests/e2e/)
- [x] tests/test_onboarding_e2e.py → tests/e2e/test_onboarding_e2e.py (MIGRATED)
- [x] tests/test_onboarding_flow_e2e.py → tests/e2e/test_onboarding_flow_e2e.py (MIGRATED)

### Phase 9: Regression Tests (keep in root)
- [ ] tests/test_regression_rag_one_time_flow.py
- [ ] tests/test_regressions_one_time_reminder.py

### Phase 10: Other Tests
- [ ] tests/test_api_app.py
- [ ] tests/test_gdpr.py
- [ ] tests/test_gdpr_api.py
- [ ] tests/test_gdpr_verification.py
- [x] tests/test_models.py (empty file - no migration needed)
- [x] tests/test_user_model.py → tests/unit/test_user_model.py (MIGRATED - source deleted)
- [x] tests/test_telegram_handler.py → tests/unit/integrations/test_telegram_handler.py (MIGRATED - source deleted)
- [x] tests/test_timezones.py → tests/unit/scheduler/test_timezones.py (already migrated)
- [x] tests/test_timezone_migration.py → tests/unit/scheduler/test_timezone_migration.py (MIGRATED - source deleted)
- [ ] tests/test_next_day_confirmation.py
- [ ] tests/test_one_time_does_not_modify_daily.py
- [ ] tests/test_process_message_creates_one_time.py
- [ ] tests/test_schedule_deletion_flow.py
- [ ] tests/test_schedule_query_handler.py
- [x] tests/test_lesson_short_circuit.py → tests/unit/lessons/test_lesson_short_circuit.py (MIGRATED - source deleted)
- [x] tests/test_lesson_trigger_order.py → tests/unit/lessons/test_lesson_trigger_order.py (MIGRATED - source deleted)
- [x] tests/test_lesson_embeddings.py (not a test file - it's a script - no migration needed)
- [x] tests/test_import_lesson_headers.py → tests/unit/lessons/test_import_lesson_headers.py (MIGRATED - source deleted)
- [ ] tests/test_rag_list_memories.py
- [ ] tests/test_remind_text_is_stored_and_sent.py
- [x] tests/test_norwegian_onboarding.py → tests/unit/onboarding/test_norwegian_onboarding.py (MIGRATED - source deleted)
- [x] tests/test_keyword_detector.py → tests/unit/language/test_keyword_detector.py (MIGRATED - source deleted)
- [x] tests/test_memory_integration.py → tests/integration/test_memory_integration.py (MIGRATED - source deleted)
- [x] tests/test_memory_driven_scheduler_integration.py → tests/integration/test_memory_driven_scheduler_integration.py (MIGRATED - source deleted)
- [x] tests/test_onboarding_e2e.py → tests/e2e/test_onboarding_e2e.py (MIGRATED - source deleted)
- [x] tests/test_onboarding_flow_e2e.py → tests/e2e/test_onboarding_flow_e2e.py (MIGRATED - source deleted)

---

## Migration Steps per file:
1. Read original test file
2. Update imports to use new fixtures
3. Apply Given-When-Then structure if missing
4. Move to appropriate directory
5. Verify tests still pass

