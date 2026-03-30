/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SCENARIO_V2_ENABLED?: string
  readonly VITE_SCENARIO_V2_ROLLOUT_PERCENTAGE?: string
  readonly VITE_SCENARIO_V2_WHITELIST_PROJECTS?: string
  readonly VITE_INTENT_WORKBENCH_ENABLED?: string
  readonly VITE_INTENT_WORKBENCH_WHITELIST_PROJECTS?: string
  readonly VITE_JIT_MAPPING_ENABLED?: string
  readonly VITE_RCA_IN_REPORT_ENABLED?: string
  readonly VITE_CI_CD_INTEGRATION_ENABLED?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.md?raw' {
  const content: string
  export default content
}
