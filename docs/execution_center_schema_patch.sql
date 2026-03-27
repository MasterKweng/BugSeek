ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS version_id INTEGER NULL REFERENCES versions(id);
ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS parent_execution_id INTEGER NULL REFERENCES test_executions(id);
ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS operator_user_id INTEGER NULL REFERENCES users(id);
ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS title VARCHAR(255) NULL;
ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS summary_json JSON NULL;
ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS result_status VARCHAR(20) NULL;
ALTER TABLE test_executions ADD COLUMN IF NOT EXISTS source_execution_id INTEGER NULL REFERENCES test_executions(id);

ALTER TABLE test_execution_results ADD COLUMN IF NOT EXISTS case_id INTEGER NULL REFERENCES api_cases(id);
ALTER TABLE test_execution_results ADD COLUMN IF NOT EXISTS definition_id INTEGER NULL REFERENCES api_definitions(id);
ALTER TABLE test_execution_results ADD COLUMN IF NOT EXISTS target_name VARCHAR(255) NULL;
ALTER TABLE test_execution_results ADD COLUMN IF NOT EXISTS request_headers JSON NULL;
ALTER TABLE test_execution_results ADD COLUMN IF NOT EXISTS response_headers JSON NULL;
ALTER TABLE test_execution_results ADD COLUMN IF NOT EXISTS request_display_type VARCHAR(20) NULL;
ALTER TABLE test_execution_results ADD COLUMN IF NOT EXISTS response_display_type VARCHAR(20) NULL;
ALTER TABLE test_execution_results ADD COLUMN IF NOT EXISTS assertion_passed_count INTEGER NULL DEFAULT 0;
ALTER TABLE test_execution_results ADD COLUMN IF NOT EXISTS assertion_total_count INTEGER NULL DEFAULT 0;
ALTER TABLE test_execution_results ADD COLUMN IF NOT EXISTS sort_order INTEGER NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_test_executions_version_id ON test_executions(version_id);
CREATE INDEX IF NOT EXISTS ix_test_executions_parent_execution_id ON test_executions(parent_execution_id);
CREATE INDEX IF NOT EXISTS ix_test_executions_operator_user_id ON test_executions(operator_user_id);
CREATE INDEX IF NOT EXISTS ix_test_executions_project_version_env ON test_executions(project_id, version_id, environment_id);
CREATE INDEX IF NOT EXISTS ix_test_execution_results_case_id ON test_execution_results(case_id);
CREATE INDEX IF NOT EXISTS ix_test_execution_results_definition_id ON test_execution_results(definition_id);
CREATE INDEX IF NOT EXISTS ix_test_execution_results_execution_status ON test_execution_results(execution_id, status);
