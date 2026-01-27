/** 脚本相关常量 */

/** 执行状态 */
export const ExecutionStatus = {
  PENDING: 'pending',
  RUNNING: 'running',
  SUCCESS: 'success',
  FAILED: 'failed',
} as const;

/** 测试类型 */
export const TestType = {
  POSITIVE: 'positive',
  NEGATIVE: 'negative',
  BOUNDARY: 'boundary',
  EXCEPTION: 'exception',
} as const;