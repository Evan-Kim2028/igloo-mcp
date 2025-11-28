"""System tests for end-to-end workflow validation.

System tests verify complete user workflows and production scenarios
without mocking core components. They ensure that all parts of the
system work together correctly.

Organization:
- test_user_workflows.py: Complete analyst journeys (Phase 1)
- test_production_scenarios.py: Scale, concurrency, recovery (Phase 2)
- test_advanced_scenarios.py: Cross-database, validation (Phase 3)
"""
