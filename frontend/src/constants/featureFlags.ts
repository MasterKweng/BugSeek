/**
 * Feature Flags 常量定义
 * 
 * BSK-SC-035: 发布策略与开关
 */

export interface FeatureFlags {
  // V2.0 场景功能
  scenarioV2Enabled: boolean;
  scenarioV2RolloutPercentage: number;
  scenarioV2WhitelistProjects: number[];
  
  // 意图工作台
  intentWorkbenchEnabled: boolean;
  intentWorkbenchWhitelistProjects: number[];
  
  // JIT 字段映射
  jitMappingEnabled: boolean;
  
  // 报告 RCA
  rcaInReportEnabled: boolean;
  
  // CI/CD 集成
  ciCdIntegrationEnabled: boolean;
}

/**
 * 默认 Feature Flags 配置
 */
export const DEFAULT_FEATURE_FLAGS: FeatureFlags = {
  scenarioV2Enabled: false,
  scenarioV2RolloutPercentage: 0,
  scenarioV2WhitelistProjects: [],
  intentWorkbenchEnabled: false,
  intentWorkbenchWhitelistProjects: [],
  jitMappingEnabled: false,
  rcaInReportEnabled: false,
  ciCdIntegrationEnabled: true,
};

/**
 * 从环境变量加载 Feature Flags
 */
export function loadFeatureFlagsFromEnv(): FeatureFlags {
  return {
    scenarioV2Enabled: import.meta.env.VITE_SCENARIO_V2_ENABLED === 'true',
    scenarioV2RolloutPercentage: parseInt(import.meta.env.VITE_SCENARIO_V2_ROLLOUT_PERCENTAGE || '0'),
    scenarioV2WhitelistProjects: import.meta.env.VITE_SCENARIO_V2_WHITELIST_PROJECTS
      ? import.meta.env.VITE_SCENARIO_V2_WHITELIST_PROJECTS.split(',').map(Number)
      : [],
    intentWorkbenchEnabled: import.meta.env.VITE_INTENT_WORKBENCH_ENABLED === 'true',
    intentWorkbenchWhitelistProjects: import.meta.env.VITE_INTENT_WORKBENCH_WHITELIST_PROJECTS
      ? import.meta.env.VITE_INTENT_WORKBENCH_WHITELIST_PROJECTS.split(',').map(Number)
      : [],
    jitMappingEnabled: import.meta.env.VITE_JIT_MAPPING_ENABLED === 'true',
    rcaInReportEnabled: import.meta.env.VITE_RCA_IN_REPORT_ENABLED === 'true',
    ciCdIntegrationEnabled: import.meta.env.VITE_CI_CD_INTEGRATION_ENABLED !== 'false',
  };
}

/**
 * 从后端 API 加载 Feature Flags
 */
export async function loadFeatureFlagsFromAPI(): Promise<FeatureFlags> {
  try {
    const response = await fetch('/api/v1/feature-flags');
    const data = await response.json();
    return data.data;
  } catch (error) {
    console.error('Failed to load feature flags from API:', error);
    return DEFAULT_FEATURE_FLAGS;
  }
}

/**
 * 检查项目是否在白名单中
 */
export function isProjectInWhitelist(
  projectId: number,
  whitelistProjects: number[]
): boolean {
  return whitelistProjects.includes(projectId);
}

/**
 * 检查用户是否在灰度范围内
 */
export function isUserInRollout(
  userId: number,
  rolloutPercentage: number
): boolean {
  if (rolloutPercentage === 0) return false;
  if (rolloutPercentage === 100) return true;
  return (userId % 100) < rolloutPercentage;
}

/**
 * 获取当前 Feature Flags
 */
let currentFeatureFlags: FeatureFlags = DEFAULT_FEATURE_FLAGS;

export function getFeatureFlags(): FeatureFlags {
  return currentFeatureFlags;
}

export function setFeatureFlags(flags: FeatureFlags): void {
  currentFeatureFlags = flags;
}

/**
 * 初始化 Feature Flags
 */
export async function initializeFeatureFlags(): Promise<void> {
  try {
    // 优先从 API 加载
    const apiFlags = await loadFeatureFlagsFromAPI();
    setFeatureFlags(apiFlags);
  } catch (error) {
    console.error('Failed to load feature flags from API, falling back to env vars:', error);
    // 回退到环境变量
    const envFlags = loadFeatureFlagsFromEnv();
    setFeatureFlags(envFlags);
  }
}