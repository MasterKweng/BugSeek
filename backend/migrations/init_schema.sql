-- Full database initialization script generated from the live database schema.
--
-- Execution center note:
-- The baseline schema includes public.test_executions and
-- public.test_execution_results.
-- Scenario orchestration note:
-- The baseline should preserve scenario execution linkage and node
-- runtime control fields required by the current executor.

CREATE SCHEMA IF NOT EXISTS public;

CREATE TABLE public.users (
	id SERIAL NOT NULL, 
	username VARCHAR(50) NOT NULL, 
	email VARCHAR(100) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	nickname VARCHAR(50), 
	avatar VARCHAR(255), 
	is_active BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT users_pkey PRIMARY KEY (id)
);

CREATE TABLE public.api_scenarios (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	scenario_type VARCHAR(50) NOT NULL, 
	category VARCHAR(50), 
	endpoint_ids JSON DEFAULT '[]'::json NOT NULL, 
	execution_order JSON DEFAULT '[]'::json NOT NULL, 
	variables JSON, 
	timeout INTEGER, 
	retry_count INTEGER, 
	continue_on_failure BOOLEAN, 
	endpoint_count INTEGER, 
	status VARCHAR(20), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	source_type VARCHAR(50) DEFAULT 'manual'::character varying, 
	source_module_chain_id INTEGER, 
	version_id INTEGER, 
	environment_id INTEGER, 
	source_ref_id INTEGER, 
	context_init JSON, 
	execution_mode VARCHAR(20) DEFAULT 'sequential'::character varying, 
	timeout_seconds INTEGER DEFAULT 600, 
	created_by INTEGER, 
	updated_by INTEGER, 
	CONSTRAINT api_scenarios_pkey PRIMARY KEY (id)
);

CREATE TABLE public.api_module_chains (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	group_ids JSONB DEFAULT '[]'::jsonb NOT NULL, 
	chain_structure JSONB DEFAULT '[]'::jsonb NOT NULL, 
	endpoint_count INTEGER DEFAULT 0 NOT NULL, 
	group_count INTEGER DEFAULT 0 NOT NULL, 
	status VARCHAR(20) DEFAULT 'active'::character varying NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	chain_type VARCHAR(50) DEFAULT 'business'::character varying, 
	complexity_score INTEGER DEFAULT 1, 
	estimated_duration INTEGER, 
	related_scenario_id INTEGER, 
	CONSTRAINT api_module_chains_pkey PRIMARY KEY (id)
);

CREATE TABLE public.group_dependencies (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	source_group_id INTEGER NOT NULL, 
	target_group_id INTEGER NOT NULL, 
	dependency_strength DOUBLE PRECISION DEFAULT 1.0, 
	dependency_type VARCHAR(20) NOT NULL, 
	mapping_rule JSONB, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT group_dependencies_pkey PRIMARY KEY (id), 
	CONSTRAINT uq_group_source_target UNIQUE NULLS DISTINCT (source_group_id, target_group_id)
);

CREATE TABLE public.async_tasks (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	task_type VARCHAR(50) NOT NULL, 
	status VARCHAR(20) DEFAULT 'pending'::character varying, 
	task_params JSONB, 
	progress INTEGER DEFAULT 0, 
	progress_message TEXT, 
	error_message TEXT, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	group_id INTEGER, 
	celery_task_id VARCHAR(255), 
	priority INTEGER DEFAULT 5, 
	retry_count INTEGER DEFAULT 0, 
	max_retries INTEGER DEFAULT 3, 
	estimated_duration INTEGER, 
	current_stage VARCHAR(50), 
	stages JSON, 
	statistics JSON, 
	task_config JSON, 
	result JSON, 
	stage_results JSONB DEFAULT '{}'::jsonb, 
	CONSTRAINT async_tasks_pkey PRIMARY KEY (id)
);

CREATE TABLE public.api_project_auth_configs (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	enabled BOOLEAN DEFAULT false NOT NULL, 
	auth_type VARCHAR(50) DEFAULT 'bearer'::character varying NOT NULL, 
	login_url VARCHAR(500), 
	login_method VARCHAR(10) DEFAULT 'POST'::character varying, 
	login_body_template JSONB DEFAULT '{}'::jsonb, 
	token_extract_expression VARCHAR(500), 
	token_inject_header VARCHAR(100) DEFAULT 'Authorization'::character varying, 
	token_inject_template VARCHAR(200) DEFAULT 'Bearer {token}'::character varying, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	created_by INTEGER, 
	cached_token TEXT, 
	token_expire_time TIMESTAMP WITHOUT TIME ZONE, 
	last_login_time TIMESTAMP WITHOUT TIME ZONE, 
	login_status VARCHAR(20), 
	last_error_message TEXT, 
	basic_username VARCHAR(255), 
	basic_password VARCHAR(255), 
	bearer_token VARCHAR(500), 
	api_key_name VARCHAR(100), 
	api_key_value VARCHAR(500), 
	api_key_location VARCHAR(20), 
	custom_headers JSONB DEFAULT '{}'::jsonb, 
	oauth2_client_id VARCHAR(255), 
	oauth2_client_secret VARCHAR(255), 
	oauth2_grant_type VARCHAR(50), 
	oauth2_auth_url VARCHAR(500), 
	oauth2_token_url VARCHAR(500), 
	oauth2_scopes JSONB, 
	oauth2_callback_url VARCHAR(500), 
	cookie_auto_manage BOOLEAN, 
	csrf_header_name VARCHAR(100), 
	csrf_token_extract_expression VARCHAR(500), 
	digest_username VARCHAR(255), 
	digest_password VARCHAR(255), 
	digest_realm VARCHAR(255), 
	aws_access_key VARCHAR(255), 
	aws_secret_key VARCHAR(255), 
	aws_region VARCHAR(100), 
	aws_service VARCHAR(100), 
	source_mode VARCHAR(20) DEFAULT 'static'::character varying, 
	injection_config JSON, 
	acquisition_config JSON, 
	cache_ttl INTEGER DEFAULT 3600, 
	config_version VARCHAR(10) DEFAULT 'v1'::character varying, 
	CONSTRAINT api_project_auth_configs_pkey PRIMARY KEY (id), 
	CONSTRAINT uq_project_auth_config UNIQUE NULLS DISTINCT (project_id)
);

CREATE TABLE public.ai_memory (
	id SERIAL NOT NULL, 
	project_id INTEGER, 
	memory_type VARCHAR(50) NOT NULL, 
	context JSON, 
	result JSON, 
	embedding JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT ai_memory_pkey PRIMARY KEY (id)
);

CREATE TABLE public.scenario_nodes (
	id SERIAL NOT NULL, 
	scenario_id INTEGER NOT NULL, 
	node_key VARCHAR(64) NOT NULL, 
	node_name VARCHAR(255), 
	node_type VARCHAR(20) DEFAULT 'api_call'::character varying NOT NULL, 
	ref_type VARCHAR(20) DEFAULT 'api_case'::character varying NOT NULL, 
	ref_id INTEGER NOT NULL, 
	step_order INTEGER DEFAULT 0 NOT NULL, 
	depends_on JSON, 
	input_mapping JSON, 
	extract_rules JSON, 
	assertion_overrides JSON, 
	timeout_seconds INTEGER, 
	retry_count INTEGER DEFAULT 0 NOT NULL, 
	continue_on_failure BOOLEAN DEFAULT false NOT NULL, 
	is_enabled BOOLEAN DEFAULT true NOT NULL, 
	extra_config JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT scenario_nodes_pkey PRIMARY KEY (id)
);

CREATE TABLE public.api_execution_traces (
	id SERIAL NOT NULL, 
	execution_id VARCHAR(100) NOT NULL, 
	api_id INTEGER NOT NULL, 
	start_time TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	end_time TIMESTAMP WITHOUT TIME ZONE, 
	status VARCHAR(20) DEFAULT 'running'::character varying NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT api_execution_traces_pkey PRIMARY KEY (id)
);

CREATE TABLE public.sql_traces (
	id SERIAL NOT NULL, 
	trace_id VARCHAR(100) NOT NULL, 
	sql_text TEXT NOT NULL, 
	operation_type VARCHAR(10), 
	table_name VARCHAR(255), 
	timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT sql_traces_pkey PRIMARY KEY (id)
);

CREATE TABLE public.table_impacts (
	id SERIAL NOT NULL, 
	execution_id VARCHAR(100) NOT NULL, 
	api_id INTEGER NOT NULL, 
	table_name VARCHAR(255) NOT NULL, 
	operation VARCHAR(10), 
	row_count INTEGER DEFAULT 0, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT table_impacts_pkey PRIMARY KEY (id)
);

CREATE TABLE public.snapshots (
	id SERIAL NOT NULL, 
	execution_id VARCHAR(100) NOT NULL, 
	table_name VARCHAR(255) NOT NULL, 
	data_json JSON NOT NULL, 
	snapshot_time TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT snapshots_pkey PRIMARY KEY (id)
);

CREATE TABLE public.api_table_impacts (
	id SERIAL NOT NULL, 
	api_id INTEGER NOT NULL, 
	table_name VARCHAR(255) NOT NULL, 
	confidence DOUBLE PRECISION DEFAULT 0.0, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT api_table_impacts_pkey PRIMARY KEY (id), 
	CONSTRAINT uq_api_table_impacts_api_table UNIQUE NULLS DISTINCT (api_id, table_name)
);

CREATE TABLE public.projects (
	id SERIAL NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	business_domain VARCHAR(50) NOT NULL, 
	logo_url VARCHAR(500), 
	backend_language VARCHAR(50), 
	backend_framework VARCHAR(100), 
	database VARCHAR(50), 
	frontend_framework VARCHAR(100), 
	asset_config JSON DEFAULT '{}'::json NOT NULL, 
	created_by INTEGER, 
	owner_id INTEGER, 
	is_deleted BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT projects_pkey PRIMARY KEY (id), 
	CONSTRAINT projects_owner_id_fkey FOREIGN KEY(owner_id) REFERENCES public.users (id)
);

CREATE TABLE public.api_chain_scenarios (
	id SERIAL NOT NULL, 
	chain_id INTEGER NOT NULL, 
	chain_type VARCHAR(20) NOT NULL, 
	scenario_id INTEGER NOT NULL, 
	is_primary BOOLEAN DEFAULT true, 
	mapping_config JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT api_chain_scenarios_pkey PRIMARY KEY (id), 
	CONSTRAINT api_chain_scenarios_scenario_id_fkey FOREIGN KEY(scenario_id) REFERENCES public.api_scenarios (id) ON DELETE CASCADE, 
	CONSTRAINT api_chain_scenarios_chain_id_chain_type_scenario_id_key UNIQUE NULLS DISTINCT (chain_id, chain_type, scenario_id)
);

CREATE TABLE public.field_mapping_stage_artifacts (
	id BIGSERIAL NOT NULL, 
	task_id INTEGER NOT NULL, 
	stage INTEGER NOT NULL, 
	artifact_type VARCHAR(50) NOT NULL, 
	artifact_key VARCHAR(255) DEFAULT 'default'::character varying NOT NULL, 
	payload_json JSON NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT field_mapping_stage_artifacts_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_field_mapping_stage_artifacts_task FOREIGN KEY(task_id) REFERENCES public.async_tasks (id) ON DELETE CASCADE, 
	CONSTRAINT uq_field_mapping_stage_artifact UNIQUE NULLS DISTINCT (task_id, stage, artifact_type, artifact_key)
);

CREATE TABLE public.field_impacts (
	id SERIAL NOT NULL, 
	table_impact_id INTEGER NOT NULL, 
	field_name VARCHAR(255) NOT NULL, 
	old_value JSON, 
	new_value JSON, 
	change_type VARCHAR(20), 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT field_impacts_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_field_impacts_table FOREIGN KEY(table_impact_id) REFERENCES public.table_impacts (id) ON DELETE CASCADE
);

CREATE TABLE public.versions (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	version_number VARCHAR(50) NOT NULL, 
	parent_version_id INTEGER, 
	status VARCHAR(20), 
	inherit_endpoints BOOLEAN, 
	inherit_test_cases BOOLEAN, 
	inherit_environments BOOLEAN, 
	change_summary TEXT, 
	requirement_doc TEXT, 
	test_scope JSON, 
	mapping_config JSON DEFAULT '{}'::json NOT NULL, 
	endpoints_count INTEGER, 
	test_cases_count INTEGER, 
	notification_url VARCHAR(500), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT versions_pkey PRIMARY KEY (id), 
	CONSTRAINT versions_parent_version_id_fkey FOREIGN KEY(parent_version_id) REFERENCES public.versions (id), 
	CONSTRAINT versions_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id)
);

CREATE TABLE public.environments (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	base_url VARCHAR(500) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	headers JSONB DEFAULT '{}'::jsonb, 
	variables JSONB DEFAULT '{}'::jsonb, 
	is_default BOOLEAN DEFAULT false, 
	CONSTRAINT environments_pkey PRIMARY KEY (id), 
	CONSTRAINT environments_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id)
);

CREATE TABLE public.database_configs (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	alias VARCHAR(50) NOT NULL, 
	connection_string TEXT, 
	db_type VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT database_configs_pkey PRIMARY KEY (id), 
	CONSTRAINT database_configs_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id)
);

CREATE TABLE public.api_endpoints (
	id SERIAL NOT NULL, 
	project_id INTEGER, 
	document_id INTEGER, 
	path VARCHAR(500) NOT NULL, 
	method VARCHAR(10) NOT NULL, 
	summary TEXT, 
	description TEXT, 
	request_schema JSON, 
	response_schema JSON, 
	tags JSON, 
	group_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_deleted BOOLEAN DEFAULT false, 
	CONSTRAINT api_endpoints_pkey PRIMARY KEY (id), 
	CONSTRAINT api_endpoints_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id)
);

CREATE TABLE public.api_endpoint_groups (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	sort_order INTEGER DEFAULT 0, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	analysis_status VARCHAR(20) DEFAULT 'pending'::character varying NOT NULL, 
	input_endpoints JSONB, 
	output_endpoints JSONB, 
	internal_chains JSONB, 
	CONSTRAINT api_endpoint_groups_pkey PRIMARY KEY (id), 
	CONSTRAINT api_endpoint_groups_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id)
);

CREATE TABLE public.test_types (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	description TEXT, 
	is_preset BOOLEAN, 
	is_active BOOLEAN, 
	sort_order INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT test_types_pkey PRIMARY KEY (id), 
	CONSTRAINT test_types_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id), 
	CONSTRAINT uq_project_type_code UNIQUE NULLS DISTINCT (project_id, code)
);

CREATE TABLE public.test_executions (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	version_id INTEGER, 
	execution_type VARCHAR(20) NOT NULL, 
	target_id INTEGER NOT NULL, 
	parent_execution_id INTEGER, 
	operator_user_id INTEGER, 
	title VARCHAR(255), 
	summary_json JSON, 
	result_status VARCHAR(20), 
	source_execution_id INTEGER, 
	environment_id INTEGER, 
	execution_mode VARCHAR(20), 
	triggered_by VARCHAR(50), 
	status VARCHAR(20), 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	duration INTEGER, 
	total INTEGER, 
	passed INTEGER, 
	failed INTEGER, 
	skipped INTEGER, 
	jenkins_job_name VARCHAR(100), 
	jenkins_build_number INTEGER, 
	jenkins_build_url VARCHAR(255), 
	webhook_url VARCHAR(255), 
	callback_status VARCHAR(20), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT test_executions_pkey PRIMARY KEY (id), 
	CONSTRAINT test_executions_environment_id_fkey FOREIGN KEY(environment_id) REFERENCES public.environments (id), 
	CONSTRAINT test_executions_operator_user_id_fkey FOREIGN KEY(operator_user_id) REFERENCES public.users (id), 
	CONSTRAINT test_executions_parent_execution_id_fkey FOREIGN KEY(parent_execution_id) REFERENCES public.test_executions (id), 
	CONSTRAINT test_executions_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id), 
	CONSTRAINT test_executions_source_execution_id_fkey FOREIGN KEY(source_execution_id) REFERENCES public.test_executions (id), 
	CONSTRAINT test_executions_version_id_fkey FOREIGN KEY(version_id) REFERENCES public.versions (id)
);

CREATE TABLE public.global_vars (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	environment_id INTEGER NOT NULL, 
	var_key VARCHAR(100) NOT NULL, 
	var_value TEXT, 
	is_sensitive BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT global_vars_pkey PRIMARY KEY (id), 
	CONSTRAINT global_vars_environment_id_fkey FOREIGN KEY(environment_id) REFERENCES public.environments (id), 
	CONSTRAINT global_vars_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id)
);

CREATE TABLE public.version_endpoints (
	id SERIAL NOT NULL, 
	version_id INTEGER NOT NULL, 
	endpoint_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT version_endpoints_pkey PRIMARY KEY (id), 
	CONSTRAINT version_endpoints_endpoint_id_fkey FOREIGN KEY(endpoint_id) REFERENCES public.api_endpoints (id), 
	CONSTRAINT version_endpoints_version_id_fkey FOREIGN KEY(version_id) REFERENCES public.versions (id)
);

CREATE TABLE public.api_documents (
	id SERIAL NOT NULL, 
	project_id INTEGER, 
	version_id INTEGER, 
	name VARCHAR(255) NOT NULL, 
	source_type VARCHAR(50) NOT NULL, 
	source_url VARCHAR(500), 
	content TEXT, 
	version VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_latest BOOLEAN DEFAULT true, 
	parent_id INTEGER, 
	CONSTRAINT api_documents_pkey PRIMARY KEY (id), 
	CONSTRAINT api_documents_parent_id_fkey FOREIGN KEY(parent_id) REFERENCES public.api_documents (id), 
	CONSTRAINT api_documents_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id), 
	CONSTRAINT api_documents_version_id_fkey FOREIGN KEY(version_id) REFERENCES public.versions (id)
);

CREATE TABLE public.api_test_scripts (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	endpoint_id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	script_content JSON NOT NULL, 
	test_type VARCHAR(50) NOT NULL, 
	generated_by VARCHAR(50) DEFAULT 'ai'::character varying, 
	status VARCHAR(20) DEFAULT 'active'::character varying, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT api_test_scripts_pkey PRIMARY KEY (id), 
	CONSTRAINT api_test_scripts_endpoint_id_fkey FOREIGN KEY(endpoint_id) REFERENCES public.api_endpoints (id), 
	CONSTRAINT api_test_scripts_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id)
);

CREATE TABLE public.api_definitions (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	group_id INTEGER, 
	method VARCHAR(10) NOT NULL, 
	path VARCHAR(500) NOT NULL, 
	summary VARCHAR(200), 
	description TEXT, 
	tags JSONB, 
	version_hash VARCHAR(64), 
	content_hash VARCHAR(64), 
	source_type VARCHAR(20), 
	source_url VARCHAR(500), 
	source_version VARCHAR(50), 
	schema_snapshot JSONB, 
	request_schema JSONB, 
	response_schema JSONB, 
	mock_data JSONB, 
	mock_rules JSONB, 
	status VARCHAR(20) DEFAULT 'active'::character varying, 
	sync_status VARCHAR(20) DEFAULT 'synced'::character varying, 
	lock_status VARCHAR(20) DEFAULT 'unlocked'::character varying, 
	last_sync_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	updated_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT api_definitions_pkey PRIMARY KEY (id), 
	CONSTRAINT api_definitions_created_by_fkey FOREIGN KEY(created_by) REFERENCES public.users (id) ON DELETE SET NULL, 
	CONSTRAINT api_definitions_group_id_fkey FOREIGN KEY(group_id) REFERENCES public.api_endpoint_groups (id) ON DELETE SET NULL, 
	CONSTRAINT api_definitions_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT api_definitions_updated_by_fkey FOREIGN KEY(updated_by) REFERENCES public.users (id) ON DELETE SET NULL, 
	CONSTRAINT uq_project_path_method UNIQUE NULLS DISTINCT (project_id, path, method)
);

CREATE TABLE public.user_contexts (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	current_project_id INTEGER, 
	current_version_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT user_contexts_pkey PRIMARY KEY (id), 
	CONSTRAINT user_contexts_current_project_id_fkey FOREIGN KEY(current_project_id) REFERENCES public.projects (id) ON DELETE SET NULL, 
	CONSTRAINT user_contexts_current_version_id_fkey FOREIGN KEY(current_version_id) REFERENCES public.versions (id) ON DELETE SET NULL, 
	CONSTRAINT user_contexts_user_id_fkey FOREIGN KEY(user_id) REFERENCES public.users (id) ON DELETE CASCADE, 
	CONSTRAINT user_contexts_user_id_key UNIQUE NULLS DISTINCT (user_id)
);

CREATE TABLE public.script_generations (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	endpoint_id INTEGER NOT NULL, 
	test_types JSON NOT NULL, 
	generated_count INTEGER, 
	status VARCHAR(20), 
	error_message TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT script_generations_pkey PRIMARY KEY (id), 
	CONSTRAINT script_generations_endpoint_id_fkey FOREIGN KEY(endpoint_id) REFERENCES public.api_endpoints (id), 
	CONSTRAINT script_generations_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id)
);

CREATE TABLE public.api_dependencies (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	source_endpoint_id INTEGER NOT NULL, 
	target_endpoint_id INTEGER NOT NULL, 
	mapping_rule JSON, 
	dependency_type VARCHAR(20) NOT NULL, 
	dependency_strength DOUBLE PRECISION, 
	discovery_method VARCHAR(50), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT api_dependencies_pkey PRIMARY KEY (id), 
	CONSTRAINT api_dependencies_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id), 
	CONSTRAINT api_dependencies_source_endpoint_id_fkey FOREIGN KEY(source_endpoint_id) REFERENCES public.api_endpoints (id), 
	CONSTRAINT api_dependencies_target_endpoint_id_fkey FOREIGN KEY(target_endpoint_id) REFERENCES public.api_endpoints (id), 
	CONSTRAINT uq_source_target UNIQUE NULLS DISTINCT (source_endpoint_id, target_endpoint_id)
);

CREATE TABLE public.scenario_endpoints (
	id SERIAL NOT NULL, 
	scenario_id INTEGER NOT NULL, 
	endpoint_id INTEGER NOT NULL, 
	step_order INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT scenario_endpoints_pkey PRIMARY KEY (id), 
	CONSTRAINT scenario_endpoints_endpoint_id_fkey FOREIGN KEY(endpoint_id) REFERENCES public.api_endpoints (id), 
	CONSTRAINT scenario_endpoints_scenario_id_fkey FOREIGN KEY(scenario_id) REFERENCES public.api_scenarios (id), 
	CONSTRAINT uq_scenario_endpoint UNIQUE NULLS DISTINCT (scenario_id, endpoint_id)
);

CREATE TABLE public.api_module_dependencies (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	source_group_id INTEGER NOT NULL, 
	target_group_id INTEGER NOT NULL, 
	endpoint_mappings JSONB DEFAULT '[]'::jsonb NOT NULL, 
	dependency_strength DOUBLE PRECISION DEFAULT 1.0 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	dependency_type VARCHAR(20) DEFAULT 'indirect'::character varying, 
	discovery_method VARCHAR(50) DEFAULT 'resource_context'::character varying, 
	discovery_details JSONB, 
	confidence_score DOUBLE PRECISION DEFAULT 1.0, 
	CONSTRAINT api_module_dependencies_pkey PRIMARY KEY (id), 
	CONSTRAINT api_module_dependencies_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT api_module_dependencies_source_group_id_fkey FOREIGN KEY(source_group_id) REFERENCES public.api_endpoint_groups (id) ON DELETE CASCADE, 
	CONSTRAINT api_module_dependencies_target_group_id_fkey FOREIGN KEY(target_group_id) REFERENCES public.api_endpoint_groups (id) ON DELETE CASCADE, 
	CONSTRAINT uq_module_source_target UNIQUE NULLS DISTINCT (source_group_id, target_group_id)
);

CREATE TABLE public.api_internal_chains (
	id SERIAL NOT NULL, 
	group_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	endpoint_ids JSON DEFAULT '[]'::json NOT NULL, 
	execution_order JSON DEFAULT '[]'::json NOT NULL, 
	chain_type VARCHAR(50) DEFAULT 'business'::character varying, 
	complexity_score INTEGER DEFAULT 1, 
	estimated_duration INTEGER, 
	auto_generated BOOLEAN DEFAULT true, 
	analysis_version VARCHAR(50), 
	status VARCHAR(20) DEFAULT 'active'::character varying, 
	endpoint_count INTEGER DEFAULT 0, 
	dependency_count INTEGER DEFAULT 0, 
	related_scenario_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT api_internal_chains_pkey PRIMARY KEY (id), 
	CONSTRAINT api_internal_chains_group_id_fkey FOREIGN KEY(group_id) REFERENCES public.api_endpoint_groups (id) ON DELETE CASCADE, 
	CONSTRAINT api_internal_chains_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT api_internal_chains_related_scenario_id_fkey FOREIGN KEY(related_scenario_id) REFERENCES public.api_scenarios (id) ON DELETE SET NULL, 
	CONSTRAINT uq_internal_chain UNIQUE NULLS DISTINCT (group_id, name)
);

CREATE TABLE public.sync_tasks (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	version_id INTEGER, 
	name VARCHAR(255) NOT NULL, 
	source_type VARCHAR(20) NOT NULL, 
	source_url VARCHAR(500), 
	source_version VARCHAR(50), 
	task_id VARCHAR(100), 
	status VARCHAR(20) DEFAULT 'pending'::character varying, 
	progress INTEGER DEFAULT 0, 
	total_count INTEGER DEFAULT 0, 
	added_count INTEGER DEFAULT 0, 
	updated_count INTEGER DEFAULT 0, 
	deleted_count INTEGER DEFAULT 0, 
	conflict_count INTEGER DEFAULT 0, 
	error_message TEXT, 
	execution_log JSONB, 
	diff_data JSONB, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	impact_analysis JSON, 
	fix_data JSON, 
	celery_task_id VARCHAR(100), 
	CONSTRAINT sync_tasks_pkey PRIMARY KEY (id), 
	CONSTRAINT sync_tasks_created_by_fkey FOREIGN KEY(created_by) REFERENCES public.users (id) ON DELETE SET NULL, 
	CONSTRAINT sync_tasks_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT sync_tasks_version_id_fkey FOREIGN KEY(version_id) REFERENCES public.versions (id) ON DELETE SET NULL, 
	CONSTRAINT sync_tasks_task_id_key UNIQUE NULLS DISTINCT (task_id)
);

CREATE TABLE public.db_schema_versions (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	version_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	source_type VARCHAR(20) DEFAULT 'upload'::character varying, 
	source_version VARCHAR(50), 
	schema_snapshot JSONB NOT NULL, 
	created_by INTEGER, 
	updated_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT db_schema_versions_pkey PRIMARY KEY (id), 
	CONSTRAINT db_schema_versions_created_by_fkey FOREIGN KEY(created_by) REFERENCES public.users (id), 
	CONSTRAINT db_schema_versions_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id), 
	CONSTRAINT db_schema_versions_updated_by_fkey FOREIGN KEY(updated_by) REFERENCES public.users (id), 
	CONSTRAINT db_schema_versions_version_id_fkey FOREIGN KEY(version_id) REFERENCES public.versions (id)
);

CREATE TABLE public.script_executions (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	script_id INTEGER NOT NULL, 
	endpoint_id INTEGER NOT NULL, 
	environment_id INTEGER NOT NULL, 
	status VARCHAR(20), 
	duration_ms INTEGER, 
	request_url VARCHAR(500), 
	request_method VARCHAR(10), 
	request_body JSON, 
	response_status_code INTEGER, 
	response_body JSON, 
	response_time_ms INTEGER, 
	assertion_results JSON, 
	error_message TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	request_headers JSON, 
	response_headers JSON, 
	request_size INTEGER, 
	response_size INTEGER, 
	dns_time_ms INTEGER, 
	tcp_time_ms INTEGER, 
	tls_time_ms INTEGER, 
	transfer_time_ms INTEGER, 
	CONSTRAINT script_executions_pkey PRIMARY KEY (id), 
	CONSTRAINT script_executions_endpoint_id_fkey FOREIGN KEY(endpoint_id) REFERENCES public.api_endpoints (id), 
	CONSTRAINT script_executions_environment_id_fkey FOREIGN KEY(environment_id) REFERENCES public.environments (id), 
	CONSTRAINT script_executions_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id), 
	CONSTRAINT script_executions_script_id_fkey FOREIGN KEY(script_id) REFERENCES public.api_test_scripts (id)
);

CREATE TABLE public.api_cases (
	id SERIAL NOT NULL, 
	definition_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	priority VARCHAR(10) DEFAULT 'P2'::character varying, 
	case_type VARCHAR(20) DEFAULT 'business'::character varying, 
	request_data JSONB, 
	environment_id INTEGER, 
	assertion_rules JSONB, 
	extraction_rules JSONB, 
	pre_sql TEXT, 
	post_sql TEXT, 
	ai_generated BOOLEAN DEFAULT false, 
	ai_confidence NUMERIC(3, 2), 
	ai_suggestions JSONB, 
	status VARCHAR(20) DEFAULT 'active'::character varying, 
	fix_status VARCHAR(20) DEFAULT 'normal'::character varying, 
	created_by INTEGER, 
	updated_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT api_cases_pkey PRIMARY KEY (id), 
	CONSTRAINT api_cases_created_by_fkey FOREIGN KEY(created_by) REFERENCES public.users (id) ON DELETE SET NULL, 
	CONSTRAINT api_cases_definition_id_fkey FOREIGN KEY(definition_id) REFERENCES public.api_definitions (id) ON DELETE CASCADE, 
	CONSTRAINT api_cases_environment_id_fkey FOREIGN KEY(environment_id) REFERENCES public.environments (id) ON DELETE SET NULL, 
	CONSTRAINT api_cases_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT api_cases_updated_by_fkey FOREIGN KEY(updated_by) REFERENCES public.users (id) ON DELETE SET NULL
);

CREATE TABLE public.version_api_definitions (
	id SERIAL NOT NULL, 
	version_id INTEGER NOT NULL, 
	definition_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT version_api_definitions_pkey PRIMARY KEY (id), 
	CONSTRAINT version_api_definitions_definition_id_fkey FOREIGN KEY(definition_id) REFERENCES public.api_definitions (id) ON DELETE CASCADE, 
	CONSTRAINT version_api_definitions_version_id_fkey FOREIGN KEY(version_id) REFERENCES public.versions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_version_definition UNIQUE NULLS DISTINCT (version_id, definition_id)
);

CREATE TABLE public.version_snapshots (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	version_id INTEGER, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	snapshot_type VARCHAR(20) DEFAULT 'manual'::character varying, 
	definition_ids JSONB DEFAULT '[]'::jsonb NOT NULL, 
	snapshot_data JSONB, 
	total_count INTEGER DEFAULT 0, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	definition_id INTEGER, 
	version_hash VARCHAR(64), 
	version_tag VARCHAR(50), 
	source_version VARCHAR(50), 
	schema_snapshot JSON, 
	created_by INTEGER, 
	CONSTRAINT version_snapshots_pkey PRIMARY KEY (id), 
	CONSTRAINT version_snapshots_created_by_fkey FOREIGN KEY(created_by) REFERENCES public.users (id) ON DELETE SET NULL, 
	CONSTRAINT version_snapshots_definition_id_fkey FOREIGN KEY(definition_id) REFERENCES public.api_definitions (id) ON DELETE CASCADE, 
	CONSTRAINT version_snapshots_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT version_snapshots_version_id_fkey FOREIGN KEY(version_id) REFERENCES public.versions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_definition_version_hash UNIQUE NULLS DISTINCT (definition_id, version_hash)
);

CREATE TABLE public.project_auth_templates (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	enabled BOOLEAN DEFAULT false NOT NULL, 
	auth_type VARCHAR(50) NOT NULL, 
	injection_target VARCHAR(20) NOT NULL, 
	injection_key VARCHAR(100), 
	injection_template TEXT, 
	source_mode VARCHAR(20) NOT NULL, 
	static_value TEXT, 
	login_api_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	login_auth_type VARCHAR(50) DEFAULT 'none'::character varying, 
	CONSTRAINT project_auth_templates_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_project_auth_templates_login_api_id FOREIGN KEY(login_api_id) REFERENCES public.api_definitions (id) ON DELETE SET NULL, 
	CONSTRAINT fk_project_auth_templates_project_id FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT project_auth_templates_project_id_key UNIQUE NULLS DISTINCT (project_id)
);

CREATE TABLE public.auth_configs (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	enabled BOOLEAN DEFAULT false NOT NULL, 
	auth_type VARCHAR(50) NOT NULL, 
	injection_target VARCHAR(20) NOT NULL, 
	injection_key VARCHAR(100), 
	injection_template TEXT, 
	source_mode VARCHAR(20) NOT NULL, 
	static_value TEXT, 
	login_api_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	environment_id INTEGER, 
	inherit_from_project BOOLEAN DEFAULT false, 
	login_auth_type VARCHAR(50) DEFAULT 'none'::character varying, 
	CONSTRAINT auth_configs_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_auth_configs_environment_id FOREIGN KEY(environment_id) REFERENCES public.environments (id) ON DELETE CASCADE, 
	CONSTRAINT fk_auth_configs_login_api_id FOREIGN KEY(login_api_id) REFERENCES public.api_definitions (id) ON DELETE SET NULL, 
	CONSTRAINT fk_auth_configs_project_id FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE
);

CREATE TABLE public.api_field_mappings (
	id SERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	version_id INTEGER NOT NULL, 
	definition_id INTEGER NOT NULL, 
	api_field_path VARCHAR(255) NOT NULL, 
	db_table VARCHAR(100) NOT NULL, 
	db_column VARCHAR(100) NOT NULL, 
	relation_type VARCHAR(20) DEFAULT 'direct'::character varying, 
	confidence DOUBLE PRECISION, 
	source VARCHAR(20) DEFAULT 'manual'::character varying, 
	created_by INTEGER, 
	updated_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	status VARCHAR(20) DEFAULT 'confirmed'::character varying, 
	CONSTRAINT api_field_mappings_pkey PRIMARY KEY (id), 
	CONSTRAINT api_field_mappings_created_by_fkey FOREIGN KEY(created_by) REFERENCES public.users (id), 
	CONSTRAINT api_field_mappings_definition_id_fkey FOREIGN KEY(definition_id) REFERENCES public.api_definitions (id), 
	CONSTRAINT api_field_mappings_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id), 
	CONSTRAINT api_field_mappings_updated_by_fkey FOREIGN KEY(updated_by) REFERENCES public.users (id), 
	CONSTRAINT api_field_mappings_version_id_fkey FOREIGN KEY(version_id) REFERENCES public.versions (id), 
	CONSTRAINT uq_field_mapping UNIQUE NULLS DISTINCT (project_id, version_id, definition_id, api_field_path, db_table, db_column)
);

CREATE TABLE public.field_mapping_traces (
	id BIGSERIAL NOT NULL, 
	task_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	definition_id INTEGER NOT NULL, 
	trace_id VARCHAR(100), 
	field_key VARCHAR(255) NOT NULL, 
	candidate VARCHAR(255) NOT NULL, 
	stage VARCHAR(50) NOT NULL, 
	decision_source VARCHAR(20) NOT NULL, 
	in_allowed_tables BOOLEAN, 
	is_anchor_table BOOLEAN, 
	s_vector DOUBLE PRECISION, 
	s_exact DOUBLE PRECISION, 
	s_graph DOUBLE PRECISION, 
	final_score DOUBLE PRECISION, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT field_mapping_traces_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_field_mapping_traces_definition FOREIGN KEY(definition_id) REFERENCES public.api_definitions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_field_mapping_traces_project FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_field_mapping_traces_task FOREIGN KEY(task_id) REFERENCES public.async_tasks (id) ON DELETE CASCADE
);

CREATE TABLE public.field_mapping_runtime_evidence (
	id BIGSERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	version_id INTEGER, 
	task_id INTEGER, 
	definition_id INTEGER NOT NULL, 
	api_field_path VARCHAR(255) NOT NULL, 
	evidence_type VARCHAR(50) NOT NULL, 
	evidence_key VARCHAR(255) NOT NULL, 
	source VARCHAR(50) DEFAULT 'field_mapping_engine'::character varying NOT NULL, 
	confidence DOUBLE PRECISION, 
	payload_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT field_mapping_runtime_evidence_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_field_mapping_runtime_evidence_definition FOREIGN KEY(definition_id) REFERENCES public.api_definitions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_field_mapping_runtime_evidence_project FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_field_mapping_runtime_evidence_task FOREIGN KEY(task_id) REFERENCES public.async_tasks (id) ON DELETE CASCADE, 
	CONSTRAINT fk_field_mapping_runtime_evidence_user FOREIGN KEY(created_by) REFERENCES public.users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_field_mapping_runtime_evidence_version FOREIGN KEY(version_id) REFERENCES public.versions (id) ON DELETE CASCADE
);

CREATE TABLE public.sql_lineage_edges (
	id BIGSERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	version_id INTEGER, 
	definition_id INTEGER NOT NULL, 
	api_field_path VARCHAR(255) NOT NULL, 
	source_table VARCHAR(255) NOT NULL, 
	source_column VARCHAR(255) NOT NULL, 
	projection_alias VARCHAR(255), 
	expression_type VARCHAR(50), 
	join_hit BOOLEAN DEFAULT false NOT NULL, 
	join_path JSON, 
	confidence DOUBLE PRECISION, 
	payload_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT sql_lineage_edges_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_sql_lineage_edges_definition FOREIGN KEY(definition_id) REFERENCES public.api_definitions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_sql_lineage_edges_project FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_sql_lineage_edges_user FOREIGN KEY(created_by) REFERENCES public.users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_sql_lineage_edges_version FOREIGN KEY(version_id) REFERENCES public.versions (id) ON DELETE CASCADE
);

CREATE TABLE public.code_lineage_edges (
	id BIGSERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	version_id INTEGER, 
	definition_id INTEGER NOT NULL, 
	api_field_path VARCHAR(255) NOT NULL, 
	target_field VARCHAR(255) NOT NULL, 
	target_object VARCHAR(255), 
	source_field VARCHAR(255) NOT NULL, 
	source_object VARCHAR(255), 
	db_table VARCHAR(255), 
	db_column VARCHAR(255), 
	evidence_type VARCHAR(50) DEFAULT 'code_assignment'::character varying NOT NULL, 
	chain_depth INTEGER, 
	confidence DOUBLE PRECISION, 
	payload_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT code_lineage_edges_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_code_lineage_edges_definition FOREIGN KEY(definition_id) REFERENCES public.api_definitions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_code_lineage_edges_project FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_code_lineage_edges_user FOREIGN KEY(created_by) REFERENCES public.users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_code_lineage_edges_version FOREIGN KEY(version_id) REFERENCES public.versions (id) ON DELETE CASCADE
);

CREATE TABLE public.test_execution_results (
	id SERIAL NOT NULL, 
	execution_id INTEGER NOT NULL, 
	target_type VARCHAR(20), 
	target_id INTEGER, 
	case_id INTEGER, 
	definition_id INTEGER, 
	target_name VARCHAR(255), 
	status VARCHAR(20), 
	response_time INTEGER, 
	response_code INTEGER, 
	response_body JSON, 
	request_body JSON, 
	response_headers JSON, 
	request_headers JSON, 
	request_display_type VARCHAR(20), 
	response_display_type VARCHAR(20), 
	assertion_results JSON, 
	assertion_passed_count INTEGER, 
	assertion_total_count INTEGER, 
	extracted_variables JSON, 
	error_message TEXT, 
	sort_order INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	CONSTRAINT test_execution_results_pkey PRIMARY KEY (id), 
	CONSTRAINT test_execution_results_case_id_fkey FOREIGN KEY(case_id) REFERENCES public.api_cases (id), 
	CONSTRAINT test_execution_results_definition_id_fkey FOREIGN KEY(definition_id) REFERENCES public.api_definitions (id), 
	CONSTRAINT test_execution_results_execution_id_fkey FOREIGN KEY(execution_id) REFERENCES public.test_executions (id)
);

CREATE TABLE public.auth_input_mappings (
	id SERIAL NOT NULL, 
	auth_config_id INTEGER NOT NULL, 
	param_location VARCHAR(20) NOT NULL, 
	param_key VARCHAR(100) NOT NULL, 
	param_value TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT auth_input_mappings_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_auth_input_mappings_auth_config_id FOREIGN KEY(auth_config_id) REFERENCES public.auth_configs (id) ON DELETE CASCADE
);

CREATE TABLE public.auth_extract_rules (
	id SERIAL NOT NULL, 
	auth_config_id INTEGER NOT NULL, 
	rule_name VARCHAR(50) NOT NULL, 
	extract_source VARCHAR(20) NOT NULL, 
	extract_expression TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT auth_extract_rules_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_auth_extract_rules_auth_config_id FOREIGN KEY(auth_config_id) REFERENCES public.auth_configs (id) ON DELETE CASCADE
);

CREATE TABLE public.project_auth_template_mappings (
	id SERIAL NOT NULL, 
	template_id INTEGER NOT NULL, 
	param_location VARCHAR(20) NOT NULL, 
	param_key VARCHAR(100) NOT NULL, 
	param_value TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT project_auth_template_mappings_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_project_auth_template_mappings_template_id FOREIGN KEY(template_id) REFERENCES public.project_auth_templates (id) ON DELETE CASCADE
);

CREATE TABLE public.project_auth_template_rules (
	id SERIAL NOT NULL, 
	template_id INTEGER NOT NULL, 
	rule_name VARCHAR(50) NOT NULL, 
	extract_source VARCHAR(20) NOT NULL, 
	extract_expression TEXT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	CONSTRAINT project_auth_template_rules_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_project_auth_template_rules_template_id FOREIGN KEY(template_id) REFERENCES public.project_auth_templates (id) ON DELETE CASCADE
);

CREATE TABLE public.field_mapping_suggestions (
	id BIGSERIAL NOT NULL, 
	task_id INTEGER NOT NULL, 
	project_id INTEGER NOT NULL, 
	definition_id INTEGER NOT NULL, 
	api_field_path VARCHAR(255) NOT NULL, 
	candidates JSONB NOT NULL, 
	status VARCHAR(50) DEFAULT 'pending'::character varying NOT NULL, 
	mapping_id BIGINT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	decision_trace JSON, 
	CONSTRAINT field_mapping_suggestions_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_field_mapping_suggestions_definition FOREIGN KEY(definition_id) REFERENCES public.api_definitions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_field_mapping_suggestions_mapping FOREIGN KEY(mapping_id) REFERENCES public.api_field_mappings (id) ON DELETE SET NULL, 
	CONSTRAINT fk_field_mapping_suggestions_project FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_field_mapping_suggestions_task FOREIGN KEY(task_id) REFERENCES public.async_tasks (id) ON DELETE CASCADE
);

CREATE TABLE public.field_mapping_feedback (
	id BIGSERIAL NOT NULL, 
	project_id INTEGER NOT NULL, 
	version_id INTEGER, 
	suggestion_id BIGINT, 
	mapping_id BIGINT, 
	definition_id INTEGER NOT NULL, 
	api_field_path VARCHAR(255) NOT NULL, 
	feedback_type VARCHAR(50) NOT NULL, 
	chosen_db_table VARCHAR(255), 
	chosen_db_column VARCHAR(255), 
	relation_type VARCHAR(50), 
	decision_source VARCHAR(50), 
	confidence DOUBLE PRECISION, 
	reason TEXT, 
	payload_json JSON, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	CONSTRAINT field_mapping_feedback_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_field_mapping_feedback_definition FOREIGN KEY(definition_id) REFERENCES public.api_definitions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_field_mapping_feedback_mapping FOREIGN KEY(mapping_id) REFERENCES public.api_field_mappings (id) ON DELETE SET NULL, 
	CONSTRAINT fk_field_mapping_feedback_project FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE, 
	CONSTRAINT fk_field_mapping_feedback_suggestion FOREIGN KEY(suggestion_id) REFERENCES public.field_mapping_suggestions (id) ON DELETE SET NULL, 
	CONSTRAINT fk_field_mapping_feedback_user FOREIGN KEY(created_by) REFERENCES public.users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_field_mapping_feedback_version FOREIGN KEY(version_id) REFERENCES public.versions (id) ON DELETE CASCADE
);

ALTER TABLE public.api_scenarios ADD CONSTRAINT api_scenarios_source_module_chain_id_fkey FOREIGN KEY(source_module_chain_id) REFERENCES public.api_module_chains (id);

ALTER TABLE public.api_scenarios ADD CONSTRAINT api_scenarios_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id);

ALTER TABLE public.api_scenarios ADD CONSTRAINT api_scenarios_version_id_fkey FOREIGN KEY(version_id) REFERENCES public.versions (id) ON DELETE SET NULL;

ALTER TABLE public.api_scenarios ADD CONSTRAINT api_scenarios_environment_id_fkey FOREIGN KEY(environment_id) REFERENCES public.environments (id) ON DELETE SET NULL;

ALTER TABLE public.api_scenarios ADD CONSTRAINT api_scenarios_created_by_fkey FOREIGN KEY(created_by) REFERENCES public.users (id) ON DELETE SET NULL;

ALTER TABLE public.api_scenarios ADD CONSTRAINT api_scenarios_updated_by_fkey FOREIGN KEY(updated_by) REFERENCES public.users (id) ON DELETE SET NULL;

ALTER TABLE public.api_scenarios ALTER COLUMN source_type SET DEFAULT 'manual';

ALTER TABLE public.api_scenarios ALTER COLUMN execution_mode SET DEFAULT 'sequential';

ALTER TABLE public.api_scenarios ALTER COLUMN timeout_seconds SET DEFAULT 600;

ALTER TABLE public.api_scenarios ALTER COLUMN retry_count SET DEFAULT 0;

ALTER TABLE public.api_scenarios ALTER COLUMN continue_on_failure SET DEFAULT false;

ALTER TABLE public.api_scenarios ALTER COLUMN source_type SET NOT NULL;

ALTER TABLE public.api_scenarios ALTER COLUMN execution_mode SET NOT NULL;

ALTER TABLE public.api_scenarios ALTER COLUMN timeout_seconds SET NOT NULL;

ALTER TABLE public.api_scenarios ALTER COLUMN retry_count SET NOT NULL;

ALTER TABLE public.api_scenarios ALTER COLUMN continue_on_failure SET NOT NULL;

ALTER TABLE public.scenario_nodes ADD CONSTRAINT scenario_nodes_scenario_id_fkey FOREIGN KEY(scenario_id) REFERENCES public.api_scenarios (id) ON DELETE CASCADE;

ALTER TABLE public.api_module_chains ADD CONSTRAINT api_module_chains_related_scenario_id_fkey FOREIGN KEY(related_scenario_id) REFERENCES public.api_scenarios (id) ON DELETE SET NULL;

ALTER TABLE public.api_module_chains ADD CONSTRAINT api_module_chains_project_id_fkey FOREIGN KEY(project_id) REFERENCES public.projects (id) ON DELETE CASCADE;

CREATE UNIQUE INDEX ix_users_email ON public.users (email);

CREATE INDEX ix_users_id ON public.users (id);

CREATE UNIQUE INDEX ix_users_username ON public.users (username);

CREATE INDEX ix_projects_business_domain ON public.projects (business_domain);

CREATE INDEX ix_projects_created_by ON public.projects (created_by);

CREATE INDEX ix_projects_id ON public.projects (id);

CREATE INDEX ix_versions_id ON public.versions (id);

CREATE INDEX ix_versions_parent_version_id ON public.versions (parent_version_id);

CREATE INDEX ix_versions_project_id ON public.versions (project_id);

CREATE INDEX ix_versions_status ON public.versions (status);

CREATE INDEX ix_test_executions_execution_type ON public.test_executions (execution_type);

CREATE INDEX ix_test_executions_id ON public.test_executions (id);

CREATE INDEX ix_test_executions_operator_user_id ON public.test_executions (operator_user_id);

CREATE INDEX ix_test_executions_parent_execution_id ON public.test_executions (parent_execution_id);

CREATE INDEX ix_test_executions_project_version_env ON public.test_executions (project_id, version_id, environment_id);

CREATE INDEX ix_test_executions_result_status ON public.test_executions (result_status);

CREATE INDEX ix_test_executions_status ON public.test_executions (status);

CREATE INDEX ix_test_executions_target_id ON public.test_executions (target_id);

CREATE INDEX ix_test_executions_triggered_by ON public.test_executions (triggered_by);

CREATE INDEX ix_test_executions_version_id ON public.test_executions (version_id);

CREATE INDEX ix_environments_id ON public.environments (id);

CREATE INDEX ix_environments_name ON public.environments (name);

CREATE INDEX ix_environments_project_id ON public.environments (project_id);

CREATE INDEX ix_database_configs_id ON public.database_configs (id);

CREATE INDEX ix_database_configs_project_id ON public.database_configs (project_id);

CREATE UNIQUE INDEX uq_project_alias ON public.database_configs (project_id, alias);

CREATE INDEX ix_api_endpoints_document_id ON public.api_endpoints (document_id);

CREATE INDEX ix_api_endpoints_group_id ON public.api_endpoints (group_id);

CREATE INDEX ix_api_endpoints_id ON public.api_endpoints (id);

CREATE INDEX ix_api_endpoints_is_deleted ON public.api_endpoints (is_deleted);

CREATE INDEX ix_api_endpoints_path_method ON public.api_endpoints (path, method);

CREATE INDEX ix_api_endpoints_project_id ON public.api_endpoints (project_id);

CREATE INDEX ix_global_vars_environment_id ON public.global_vars (environment_id);

CREATE INDEX ix_global_vars_id ON public.global_vars (id);

CREATE INDEX ix_global_vars_project_id ON public.global_vars (project_id);

CREATE UNIQUE INDEX uq_project_env_var ON public.global_vars (project_id, environment_id, var_key);

CREATE INDEX ix_version_endpoints_endpoint_id ON public.version_endpoints (endpoint_id);

CREATE INDEX ix_version_endpoints_id ON public.version_endpoints (id);

CREATE INDEX ix_version_endpoints_version_id ON public.version_endpoints (version_id);

CREATE UNIQUE INDEX uq_version_endpoint ON public.version_endpoints (version_id, endpoint_id);

CREATE INDEX ix_api_documents_id ON public.api_documents (id);

CREATE INDEX ix_api_documents_is_latest ON public.api_documents (is_latest);

CREATE INDEX ix_api_documents_parent_id ON public.api_documents (parent_id);

CREATE INDEX ix_api_documents_project_id ON public.api_documents (project_id);

CREATE INDEX ix_api_documents_version_id ON public.api_documents (version_id);

CREATE INDEX ix_api_test_scripts_endpoint_id ON public.api_test_scripts (endpoint_id);

CREATE INDEX ix_api_test_scripts_project_id ON public.api_test_scripts (project_id);

CREATE INDEX ix_api_test_scripts_test_type ON public.api_test_scripts (test_type);

CREATE INDEX ix_script_executions_endpoint_id ON public.script_executions (endpoint_id);

CREATE INDEX ix_script_executions_environment_id ON public.script_executions (environment_id);

CREATE INDEX ix_script_executions_id ON public.script_executions (id);

CREATE INDEX ix_script_executions_project_id ON public.script_executions (project_id);

CREATE INDEX ix_script_executions_script_id ON public.script_executions (script_id);

CREATE INDEX ix_test_execution_results_case_id ON public.test_execution_results (case_id);

CREATE INDEX ix_test_execution_results_definition_id ON public.test_execution_results (definition_id);

CREATE INDEX ix_test_execution_results_execution_id ON public.test_execution_results (execution_id);

CREATE INDEX ix_test_execution_results_execution_status ON public.test_execution_results (execution_id, status);

CREATE INDEX ix_test_execution_results_id ON public.test_execution_results (id);

CREATE INDEX ix_test_execution_results_status ON public.test_execution_results (status);

CREATE INDEX ix_test_execution_results_target_id ON public.test_execution_results (target_id);

CREATE INDEX ix_test_execution_results_target_type ON public.test_execution_results (target_type);

CREATE INDEX ix_api_cases_ai_generated ON public.api_cases (ai_generated);

CREATE INDEX ix_api_cases_definition_id ON public.api_cases (definition_id);

CREATE INDEX ix_api_cases_environment_id ON public.api_cases (environment_id);

CREATE INDEX ix_api_cases_priority ON public.api_cases (priority);

CREATE INDEX ix_api_cases_project_id ON public.api_cases (project_id);

CREATE INDEX ix_api_cases_status ON public.api_cases (status);

CREATE INDEX ix_api_definitions_content_hash ON public.api_definitions (content_hash);

CREATE INDEX ix_api_definitions_group_id ON public.api_definitions (group_id);

CREATE INDEX ix_api_definitions_lock_status ON public.api_definitions (lock_status);

CREATE INDEX ix_api_definitions_path_method ON public.api_definitions (path, method);

CREATE INDEX ix_api_definitions_project_id ON public.api_definitions (project_id);

CREATE INDEX ix_api_definitions_status ON public.api_definitions (status);

CREATE INDEX ix_api_definitions_sync_status ON public.api_definitions (sync_status);

CREATE INDEX ix_api_endpoint_groups_project_id ON public.api_endpoint_groups (project_id);

CREATE UNIQUE INDEX uq_project_group_name ON public.api_endpoint_groups (project_id, name);

CREATE INDEX ix_user_contexts_current_project_id ON public.user_contexts (current_project_id);

CREATE INDEX ix_user_contexts_current_version_id ON public.user_contexts (current_version_id);

CREATE INDEX ix_user_contexts_user_id ON public.user_contexts (user_id);

CREATE INDEX ix_test_types_id ON public.test_types (id);

CREATE INDEX ix_test_types_project_id ON public.test_types (project_id);

CREATE INDEX ix_script_generations_endpoint_id ON public.script_generations (endpoint_id);

CREATE INDEX ix_script_generations_id ON public.script_generations (id);

CREATE INDEX ix_script_generations_project_id ON public.script_generations (project_id);

CREATE INDEX ix_api_dependencies_dependency_type ON public.api_dependencies (dependency_type);

CREATE INDEX ix_api_dependencies_id ON public.api_dependencies (id);

CREATE INDEX ix_api_dependencies_project_id ON public.api_dependencies (project_id);

CREATE INDEX ix_api_dependencies_source_endpoint_id ON public.api_dependencies (source_endpoint_id);

CREATE INDEX ix_api_dependencies_target_endpoint_id ON public.api_dependencies (target_endpoint_id);

CREATE INDEX ix_scenario_endpoints_endpoint_id ON public.scenario_endpoints (endpoint_id);

CREATE INDEX ix_scenario_endpoints_id ON public.scenario_endpoints (id);

CREATE INDEX ix_scenario_endpoints_scenario_id ON public.scenario_endpoints (scenario_id);

CREATE INDEX ix_scenario_endpoints_step_order ON public.scenario_endpoints (step_order);

CREATE INDEX ix_api_scenarios_category ON public.api_scenarios (category);

CREATE INDEX ix_api_scenarios_environment_id ON public.api_scenarios (environment_id);

CREATE INDEX ix_api_scenarios_id ON public.api_scenarios (id);

CREATE INDEX ix_api_scenarios_project_id ON public.api_scenarios (project_id);

CREATE INDEX ix_api_scenarios_project_status ON public.api_scenarios (project_id, status);

CREATE INDEX ix_api_scenarios_scenario_type ON public.api_scenarios (scenario_type);

CREATE INDEX ix_api_scenarios_source_module_chain_id ON public.api_scenarios (source_module_chain_id);

CREATE INDEX ix_api_scenarios_source_type ON public.api_scenarios (source_type);

CREATE INDEX ix_api_scenarios_status ON public.api_scenarios (status);

CREATE INDEX ix_api_scenarios_updated_at ON public.api_scenarios (updated_at);

CREATE INDEX ix_api_scenarios_version_id ON public.api_scenarios (version_id);

CREATE INDEX ix_api_module_chains_project_id ON public.api_module_chains (project_id);

CREATE INDEX ix_api_module_chains_status ON public.api_module_chains (status);

CREATE INDEX ix_module_chains_status ON public.api_module_chains (status);

CREATE INDEX ix_group_dependencies_project_id ON public.group_dependencies (project_id);

CREATE INDEX ix_group_dependencies_source_group_id ON public.group_dependencies (source_group_id);

CREATE INDEX ix_group_dependencies_target_group_id ON public.group_dependencies (target_group_id);

CREATE INDEX ix_api_module_dependencies_dependency_type ON public.api_module_dependencies (dependency_type);

CREATE INDEX ix_api_module_dependencies_discovery_method ON public.api_module_dependencies (discovery_method);

CREATE INDEX ix_api_module_dependencies_project_id ON public.api_module_dependencies (project_id);

CREATE INDEX ix_api_module_dependencies_source_group_id ON public.api_module_dependencies (source_group_id);

CREATE INDEX ix_api_module_dependencies_target_group_id ON public.api_module_dependencies (target_group_id);

CREATE INDEX ix_internal_chains_auto_generated ON public.api_internal_chains (auto_generated);

CREATE INDEX ix_internal_chains_group_id ON public.api_internal_chains (group_id);

CREATE INDEX ix_internal_chains_project_id ON public.api_internal_chains (project_id);

CREATE INDEX ix_internal_chains_status ON public.api_internal_chains (status);

CREATE INDEX ix_async_tasks_celery_task_id ON public.async_tasks (celery_task_id);

CREATE INDEX ix_async_tasks_group_id ON public.async_tasks (group_id);

CREATE INDEX ix_async_tasks_project_id ON public.async_tasks (project_id);

CREATE INDEX ix_async_tasks_status ON public.async_tasks (status);

CREATE INDEX ix_async_tasks_task_type ON public.async_tasks (task_type);

CREATE INDEX ix_async_tasks_user_id ON public.async_tasks (user_id);

CREATE INDEX ix_chain_scenarios_chain_id ON public.api_chain_scenarios (chain_id, chain_type);

CREATE INDEX ix_chain_scenarios_scenario_id ON public.api_chain_scenarios (scenario_id);

CREATE INDEX ix_sync_tasks_celery_task_id ON public.sync_tasks (celery_task_id);

CREATE INDEX ix_sync_tasks_project_id ON public.sync_tasks (project_id);

CREATE INDEX ix_sync_tasks_status ON public.sync_tasks (status);

CREATE INDEX ix_sync_tasks_task_id ON public.sync_tasks (task_id);

CREATE INDEX ix_sync_tasks_version_id ON public.sync_tasks (version_id);

CREATE INDEX ix_version_api_definitions_definition_id ON public.version_api_definitions (definition_id);

CREATE INDEX ix_version_api_definitions_version_id ON public.version_api_definitions (version_id);

CREATE INDEX ix_version_snapshots_definition ON public.version_snapshots (definition_id);

CREATE INDEX ix_version_snapshots_hash ON public.version_snapshots (version_hash);

CREATE INDEX ix_version_snapshots_project_id ON public.version_snapshots (project_id);

CREATE INDEX ix_version_snapshots_type ON public.version_snapshots (snapshot_type);

CREATE INDEX ix_version_snapshots_version_id ON public.version_snapshots (version_id);

CREATE INDEX idx_api_project_auth_configs_auth_type ON public.api_project_auth_configs (auth_type);

CREATE INDEX idx_api_project_auth_configs_project_id ON public.api_project_auth_configs (project_id);

CREATE INDEX ix_api_project_auth_configs_config_version ON public.api_project_auth_configs (config_version);

CREATE INDEX ix_api_project_auth_configs_source_mode ON public.api_project_auth_configs (source_mode);

CREATE INDEX ix_project_auth_templates_auth_type ON public.project_auth_templates (auth_type);

CREATE INDEX ix_project_auth_templates_project_id ON public.project_auth_templates (project_id);

CREATE INDEX ix_project_auth_templates_source_mode ON public.project_auth_templates (source_mode);

CREATE INDEX ix_auth_configs_auth_type ON public.auth_configs (auth_type);

CREATE INDEX ix_auth_configs_inherit_from_project ON public.auth_configs (inherit_from_project);

CREATE INDEX ix_auth_configs_login_api_id ON public.auth_configs (login_api_id);

CREATE INDEX ix_auth_configs_project_id ON public.auth_configs (project_id);

CREATE INDEX ix_auth_configs_source_mode ON public.auth_configs (source_mode);

CREATE UNIQUE INDEX uq_auth_configs_environment_id ON public.auth_configs (environment_id);

CREATE INDEX ix_auth_input_mappings_auth_config_id ON public.auth_input_mappings (auth_config_id);

CREATE INDEX ix_auth_input_mappings_param_location ON public.auth_input_mappings (param_location);

CREATE INDEX ix_auth_extract_rules_auth_config_id ON public.auth_extract_rules (auth_config_id);

CREATE INDEX ix_auth_extract_rules_extract_source ON public.auth_extract_rules (extract_source);

CREATE INDEX ix_auth_extract_rules_rule_name ON public.auth_extract_rules (rule_name);

CREATE INDEX ix_project_auth_template_mappings_param_location ON public.project_auth_template_mappings (param_location);

CREATE INDEX ix_project_auth_template_mappings_template_id ON public.project_auth_template_mappings (template_id);

CREATE INDEX ix_project_auth_template_rules_extract_source ON public.project_auth_template_rules (extract_source);

CREATE INDEX ix_project_auth_template_rules_rule_name ON public.project_auth_template_rules (rule_name);

CREATE INDEX ix_project_auth_template_rules_template_id ON public.project_auth_template_rules (template_id);

CREATE INDEX ix_db_schema_versions_project_id ON public.db_schema_versions (project_id);

CREATE INDEX ix_db_schema_versions_source_type ON public.db_schema_versions (source_type);

CREATE INDEX ix_db_schema_versions_version_id ON public.db_schema_versions (version_id);

CREATE INDEX ix_api_field_mappings_definition_id ON public.api_field_mappings (definition_id);

CREATE INDEX ix_api_field_mappings_project_id ON public.api_field_mappings (project_id);

CREATE INDEX ix_api_field_mappings_status ON public.api_field_mappings (status);

CREATE INDEX ix_api_field_mappings_version_id ON public.api_field_mappings (version_id);

CREATE INDEX ix_field_mapping_suggestions_api_field_path ON public.field_mapping_suggestions (api_field_path);

CREATE INDEX ix_field_mapping_suggestions_definition_id ON public.field_mapping_suggestions (definition_id);

CREATE INDEX ix_field_mapping_suggestions_project_definition_field ON public.field_mapping_suggestions (project_id, definition_id, api_field_path);

CREATE INDEX ix_field_mapping_suggestions_project_id ON public.field_mapping_suggestions (project_id);

CREATE INDEX ix_field_mapping_suggestions_status ON public.field_mapping_suggestions (status);

CREATE INDEX ix_field_mapping_suggestions_task_id ON public.field_mapping_suggestions (task_id);

CREATE INDEX ix_field_mapping_suggestions_task_status ON public.field_mapping_suggestions (task_id, status);

CREATE UNIQUE INDEX uq_suggestion_task_definition_field ON public.field_mapping_suggestions (task_id, definition_id, api_field_path);

CREATE INDEX ix_field_mapping_traces_decision_source ON public.field_mapping_traces (decision_source);

CREATE INDEX ix_field_mapping_traces_field_key ON public.field_mapping_traces (field_key);

CREATE INDEX ix_field_mapping_traces_stage_source ON public.field_mapping_traces (stage, decision_source);

CREATE INDEX ix_field_mapping_traces_task_field ON public.field_mapping_traces (task_id, field_key);

CREATE INDEX ix_field_mapping_traces_task_id ON public.field_mapping_traces (task_id);

CREATE INDEX ix_ai_memory_memory_type ON public.ai_memory (memory_type);

CREATE INDEX ix_ai_memory_project_id ON public.ai_memory (project_id);

CREATE INDEX ix_ai_memory_project_type ON public.ai_memory (project_id, memory_type);

CREATE INDEX ix_scenario_nodes_ref_type_ref_id ON public.scenario_nodes (ref_type, ref_id);

CREATE INDEX ix_scenario_nodes_scenario_id ON public.scenario_nodes (scenario_id);

CREATE INDEX ix_scenario_nodes_scenario_step ON public.scenario_nodes (scenario_id, step_order);

CREATE UNIQUE INDEX uq_scenario_node_key ON public.scenario_nodes (scenario_id, node_key);

CREATE INDEX ix_field_mapping_stage_artifacts_artifact_type ON public.field_mapping_stage_artifacts (artifact_type);

CREATE INDEX ix_field_mapping_stage_artifacts_task_stage ON public.field_mapping_stage_artifacts (task_id, stage);

CREATE INDEX ix_api_execution_traces_execution_id ON public.api_execution_traces (execution_id);

CREATE INDEX ix_sql_traces_table_name ON public.sql_traces (table_name);

CREATE INDEX ix_sql_traces_trace_id ON public.sql_traces (trace_id);

CREATE INDEX ix_field_mapping_runtime_evidence_task_field ON public.field_mapping_runtime_evidence (task_id, definition_id, api_field_path);

CREATE INDEX ix_field_mapping_runtime_evidence_type_source ON public.field_mapping_runtime_evidence (evidence_type, source);

CREATE INDEX ix_sql_lineage_edges_definition_field ON public.sql_lineage_edges (definition_id, api_field_path);

CREATE INDEX ix_sql_lineage_edges_source ON public.sql_lineage_edges (source_table, source_column);

CREATE INDEX ix_code_lineage_edges_definition_field ON public.code_lineage_edges (definition_id, api_field_path);

CREATE INDEX ix_code_lineage_edges_source ON public.code_lineage_edges (db_table, db_column);

CREATE INDEX ix_table_impacts_execution_id ON public.table_impacts (execution_id);

CREATE INDEX ix_field_impacts_table_impact_id ON public.field_impacts (table_impact_id);

CREATE INDEX ix_snapshots_execution_id ON public.snapshots (execution_id);

CREATE INDEX ix_api_table_impacts_api_id ON public.api_table_impacts (api_id);

CREATE INDEX ix_field_mapping_feedback_project_field ON public.field_mapping_feedback (project_id, definition_id, api_field_path);

CREATE INDEX ix_field_mapping_feedback_type_created ON public.field_mapping_feedback (feedback_type, created_at);
