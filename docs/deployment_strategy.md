# 发布策略与开关文档

**BSK-SC-035: 发布策略与开关**

## 文档概述

本文档定义了 BugSeek 平台的发布策略和 Feature Flags（功能开关）机制，支持按项目/环境灰度启用并可回滚，确保新功能的安全发布。

## Feature Flags 概述

Feature Flags 是一种软件工程技术，允许在不重新部署代码的情况下启用或禁用功能。它提供了以下好处：

1. **安全发布**: 逐步推出新功能，降低风险
2. **快速回滚**: 出现问题时立即禁用功能
3. **A/B 测试**: 对不同用户群体展示不同功能
4. **灰度发布**: 按比例逐步开放新功能
5. **环境隔离**: 不同环境使用不同的功能配置

## Feature Flags 设计

### 核心原则

1. **细粒度控制**: 支持全局、项目、环境级别的控制
2. **可观测性**: 记录功能开关的使用情况
3. **性能优先**: 功能开关不应影响系统性能
4. **简单易用**: 开发人员易于使用和维护
5. **可回滚**: 出现问题时能快速回滚

### 功能开关类型

#### 1. 布尔开关（Boolean Flag）

最简单的开关类型，只有开启和关闭两种状态。

**适用场景**:
- 功能的完全启用/禁用
- 新功能的灰度发布
- 实验性功能的控制

**示例**:
```python
if settings.SCENARIO_V2_ENABLED:
    # 使用新的场景功能
    return execute_scenario_v2(scenario_id)
else:
    # 使用旧的场景功能
    return execute_scenario_v1(scenario_id)
```

#### 2. 百分比开关（Percentage Flag）

按百分比控制功能的开放程度。

**适用场景**:
- 灰度发布（逐步开放）
- A/B 测试
- 负载均衡

**示例**:
```python
if is_user_in_percentage(user_id, settings.SCENARIO_V2_ROLLOUT_PERCENTAGE):
    # 用户在灰度范围内
    return execute_scenario_v2(scenario_id)
else:
    # 用户在灰度范围外
    return execute_scenario_v1(scenario_id)
```

#### 3. 白名单开关（Whitelist Flag）

只有在白名单中的用户/项目才能使用新功能。

**适用场景**:
- 内部测试
- 早期访问者
- 重要客户

**示例**:
```python
if project_id in settings.SCENARIO_V2_WHITELIST_PROJECTS:
    # 项目在白名单中
    return execute_scenario_v2(scenario_id)
else:
    # 项目不在白名单中
    return execute_scenario_v1(scenario_id)
```

#### 4. 环境开关（Environment Flag）

根据环境启用或禁用功能。

**适用场景**:
- 开发环境启用实验性功能
- 测试环境启用完整功能
- 生产环境启用稳定功能

**示例**:
```python
if settings.ENVIRONMENT == "development":
    # 开发环境：启用所有新功能
    return execute_scenario_v2(scenario_id)
elif settings.ENVIRONMENT == "production":
    # 生产环境：根据开关决定
    if settings.SCENARIO_V2_ENABLED:
        return execute_scenario_v2(scenario_id)
    else:
        return execute_scenario_v1(scenario_id)
```

## BugSeek Feature Flags

### 1. SCENARIO_V2_ENABLED

**描述**: 启用 V2.0 场景功能（DAG 执行、Context Bus、意图工作台等）

**类型**: Boolean

**默认值**: `false`

**级别**: 全局、项目、环境

**控制范围**:
- 场景执行引擎
- 意图工作台
- JIT 字段映射
- 场景报告

**配置示例**:
```bash
# .env 文件
SCENARIO_V2_ENABLED=true
SCENARIO_V2_ROLLOUT_PERCENTAGE=50
SCENARIO_V2_WHITELIST_PROJECTS=1,2,3
```

**使用示例**:
```python
from app.config import settings

def execute_scenario(scenario_id: int, db: Session):
    if settings.SCENARIO_V2_ENABLED:
        # 使用 V2.0 场景执行引擎
        executor = ScenarioExecutorV2()
        return executor.execute(scenario_id, db)
    else:
        # 使用 V1.0 场景执行引擎
        executor = ScenarioExecutorV1()
        return executor.execute(scenario_id, db)
```

### 2. INTENT_WORKBENCH_ENABLED

**描述**: 启用意图工作台功能

**类型**: Boolean

**默认值**: `false`

**级别**: 全局、项目

**控制范围**:
- 意图生成场景
- API 检索
- AI 驱动的场景编排

**配置示例**:
```bash
# .env 文件
INTENT_WORKBENCH_ENABLED=true
INTENT_WORKBENCH_WHITELIST_PROJECTS=1,5,10
```

**使用示例**:
```python
from app.config import settings

@router.post("/intent-workbench/generate-scenario")
async def generate_scenario(request: IntentGenerateRequest):
    if not settings.INTENT_WORKBENCH_ENABLED:
        raise HTTPException(status_code=403, detail="意图工作台功能未启用")
    
    # 执行意图生成逻辑
    return await generate_scenario_from_intent(request)
```

### 3. JIT_MAPPING_ENABLED

**描述**: 启用 JIT 字段映射功能

**类型**: Boolean

**默认值**: `false`

**级别**: 全局、项目

**控制范围**:
- 场景级字段映射
- 子集映射处理
- 自动映射建议

**配置示例**:
```bash
# .env 文件
JIT_MAPPING_ENABLED=true
```

**使用示例**:
```python
from app.config import settings

def generate_field_mapping_suggestions(definition_ids: List[int], scenario_id: int):
    if settings.JIT_MAPPING_ENABLED:
        # 使用 JIT 映射
        processor = FieldMappingProcessor(definition_ids=definition_ids, scenario_id=scenario_id)
        return processor.process()
    else:
        # 使用全量映射
        processor = FieldMappingProcessor()
        return processor.process()
```

### 4. RCA_IN_REPORT_ENABLED

**描述**: 启用报告中的 AI RCA（根因分析）功能

**类型**: Boolean

**默认值**: `false`

**级别**: 全局

**控制范围**:
- 场景执行报告
- AI 根因分析
- 失败诊断

**配置示例**:
```bash
# .env 文件
RCA_IN_REPORT_ENABLED=true
```

**使用示例**:
```python
from app.config import settings

async def generate_report(execution_id: int, db: Session):
    report_data = aggregate_report_data(execution_id, db)
    
    if settings.RCA_IN_REPORT_ENABLED and report_data.has_failures:
        # 生成 RCA 分析
        rca_result = await generate_rca_analysis(report_data)
        report_data.rca = rca_result
    
    return report_data
```

### 5. CI_CD_INTEGRATION_ENABLED

**描述**: 启用 CI/CD 集成功能（Webhook、CLI 触发）

**类型**: Boolean

**默认值**: `true`

**级别**: 全局

**控制范围**:
- Webhook 触发
- CLI 脚本
- 执行结果回调

**配置示例**:
```bash
# .env 文件
CI_CD_INTEGRATION_ENABLED=true
```

**使用示例**:
```python
from app.config import settings

@router.post("/scenarios/{scenario_id}/trigger")
async def trigger_scenario(scenario_id: int, request: TriggerRequest):
    if not settings.CI_CD_INTEGRATION_ENABLED:
        raise HTTPException(status_code=403, detail="CI/CD 集成功能未启用")
    
    # 执行 CI/CD 触发逻辑
    return await trigger_scenario_execution(scenario_id, request)
```

## 配置文件更新

### backend/app/config.py

```python
from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    # 项目配置
    PROJECT_NAME: str = "BugSeek"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    
    # 环境配置
    ENVIRONMENT: str = "development"  # development, staging, production

    # ========== Feature Flags ==========
    
    # V2.0 场景功能开关
    SCENARIO_V2_ENABLED: bool = False
    SCENARIO_V2_ROLLOUT_PERCENTAGE: int = 0  # 0-100，灰度发布百分比
    SCENARIO_V2_WHITELIST_PROJECTS: str = ""  # 逗号分隔的项目ID列表，如 "1,2,3"
    
    # 意图工作台开关
    INTENT_WORKBENCH_ENABLED: bool = False
    INTENT_WORKBENCH_WHITELIST_PROJECTS: str = ""
    
    # JIT 字段映射开关
    JIT_MAPPING_ENABLED: bool = False
    
    # 报告 RCA 开关
    RCA_IN_REPORT_ENABLED: bool = False
    
    # CI/CD 集成开关
    CI_CD_INTEGRATION_ENABLED: bool = True

    # 数据库配置
    DATABASE_URL: str = "postgresql://bugseek:bugseek@localhost:5432/bugseek"

    # 数据库连接池配置
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 60
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True
    DB_POOL_EXPIRE: int = 30
    DB_MAX_IDLE: int = 10

    # JWT 配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # 文件上传配置
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024

    # 日志配置
    LOG_DIR: str = "./logs"
    LOG_LEVEL: str = "INFO"

    # AI 配置
    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    OPENAI_BASE_URL: str = "https://api.siliconflow.cn/v1"

    # Hugging Face 配置
    HF_ENDPOINT: str = "https://hf-mirror.com"

    def get_scenario_v2_whitelist_projects(self) -> List[int]:
        """获取 V2.0 场景白名单项目ID列表"""
        if not self.SCENARIO_V2_WHITELIST_PROJECTS:
            return []
        return [int(pid.strip()) for pid in self.SCENARIO_V2_WHITELIST_PROJECTS.split(",")]

    def get_intent_workbench_whitelist_projects(self) -> List[int]:
        """获取意图工作台白名单项目ID列表"""
        if not self.INTENT_WORKBENCH_WHITELIST_PROJECTS:
            return []
        return [int(pid.strip()) for pid in self.INTENT_WORKBENCH_WHITELIST_PROJECTS.split(",")]

    def is_project_in_scenario_v2_whitelist(self, project_id: int) -> bool:
        """检查项目是否在 V2.0 场景白名单中"""
        return project_id in self.get_scenario_v2_whitelist_projects()

    def is_project_in_intent_workbench_whitelist(self, project_id: int) -> bool:
        """检查项目是否在意图工作台白名单中"""
        return project_id in self.get_intent_workbench_whitelist_projects()

    def is_user_in_scenario_v2_rollout(self, user_id: int) -> bool:
        """检查用户是否在 V2.0 场景灰度范围内"""
        if self.SCENARIO_V2_ROLLOUT_PERCENTAGE == 0:
            return False
        if self.SCENARIO_V2_ROLLOUT_PERCENTAGE == 100:
            return True
        # 使用用户ID的最后两位数字作为随机种子
        return (user_id % 100) < self.SCENARIO_V2_ROLLOUT_PERCENTAGE

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
```

### frontend/src/constants/featureFlags.ts

```typescript
/**
 * Feature Flags 常量定义
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
```

## 环境变量配置

### backend/.env.example

```bash
# ========== 环境配置 ==========
ENVIRONMENT=development  # development, staging, production

# ========== Feature Flags ==========

# V2.0 场景功能
SCENARIO_V2_ENABLED=false
SCENARIO_V2_ROLLOUT_PERCENTAGE=0
SCENARIO_V2_WHITELIST_PROJECTS=

# 意图工作台
INTENT_WORKBENCH_ENABLED=false
INTENT_WORKBENCH_WHITELIST_PROJECTS=

# JIT 字段映射
JIT_MAPPING_ENABLED=false

# 报告 RCA
RCA_IN_REPORT_ENABLED=false

# CI/CD 集成
CI_CD_INTEGRATION_ENABLED=true
```

### frontend/.env.example

```bash
# ========== Feature Flags ==========

# V2.0 场景功能
VITE_SCENARIO_V2_ENABLED=false
VITE_SCENARIO_V2_ROLLOUT_PERCENTAGE=0
VITE_SCENARIO_V2_WHITELIST_PROJECTS=

# 意图工作台
VITE_INTENT_WORKBENCH_ENABLED=false
VITE_INTENT_WORKBENCH_WHITELIST_PROJECTS=

# JIT 字段映射
VITE_JIT_MAPPING_ENABLED=false

# 报告 RCA
VITE_RCA_IN_REPORT_ENABLED=false

# CI/CD 集成
VITE_CI_CD_INTEGRATION_ENABLED=true
```

## 发布策略

### 阶段 1: 内部可见（1-2 周）

**目标**: 在内部环境验证新功能

**配置**:
```bash
# 开发环境
ENVIRONMENT=development
SCENARIO_V2_ENABLED=true
INTENT_WORKBENCH_ENABLED=true
JIT_MAPPING_ENABLED=true
RCA_IN_REPORT_ENABLED=true
CI_CD_INTEGRATION_ENABLED=true
```

**验证项**:
- 所有新功能正常工作
- 无明显的性能问题
- 日志和监控正常
- 回滚方案可用

### 阶段 2: 灰度项目（2-4 周）

**目标**: 对少数项目开放新功能

**配置**:
```bash
# 测试环境
ENVIRONMENT=staging
SCENARIO_V2_ENABLED=true
SCENARIO_V2_WHITELIST_PROJECTS=1,5,10
INTENT_WORKBENCH_ENABLED=true
INTENT_WORKBENCH_WHITELIST_PROJECTS=1,5,10
JIT_MAPPING_ENABLED=true
RCA_IN_REPORT_ENABLED=true
CI_CD_INTEGRATION_ENABLED=true
```

**验证项**:
- 灰度项目反馈良好
- 无重大 Bug
- 性能指标正常
- 用户接受度高

### 阶段 3: 灰度发布（4-6 周）

**目标**: 逐步扩大新功能的开放范围

**配置**:
```bash
# 生产环境 - 第一阶段（10%）
ENVIRONMENT=production
SCENARIO_V2_ENABLED=true
SCENARIO_V2_ROLLOUT_PERCENTAGE=10
INTENT_WORKBENCH_ENABLED=true
INTENT_WORKBENCH_ROLLOUT_PERCENTAGE=10
JIT_MAPPING_ENABLED=true
RCA_IN_REPORT_ENABLED=false  # 暂不启用 RCA
CI_CD_INTEGRATION_ENABLED=true
```

**第二阶段（30%）**:
```bash
SCENARIO_V2_ROLLOUT_PERCENTAGE=30
INTENT_WORKBENCH_ROLLOUT_PERCENTAGE=30
RCA_IN_REPORT_ENABLED=false
```

**第三阶段（60%）**:
```bash
SCENARIO_V2_ROLLOUT_PERCENTAGE=60
INTENT_WORKBENCH_ROLLOUT_PERCENTAGE=60
RCA_IN_REPORT_ENABLED=true
```

**第四阶段（100%）**:
```bash
SCENARIO_V2_ROLLOUT_PERCENTAGE=100
INTENT_WORKBENCH_ROLLOUT_PERCENTAGE=100
```

**验证项**:
- 监控错误率和性能指标
- 收集用户反馈
- 逐步增加开放比例
- 准备好回滚

### 阶段 4: 全量发布（1-2 周）

**目标**: 所有用户都能使用新功能

**配置**:
```bash
# 生产环境
ENVIRONMENT=production
SCENARIO_V2_ENABLED=true
SCENARIO_V2_ROLLOUT_PERCENTAGE=100
INTENT_WORKBENCH_ENABLED=true
INTENT_WORKBENCH_ROLLOUT_PERCENTAGE=100
JIT_MAPPING_ENABLED=true
RCA_IN_REPORT_ENABLED=true
CI_CD_INTEGRATION_ENABLED=true
```

**验证项**:
- 系统稳定运行
- 用户满意度高
- 性能指标达标
- 无重大问题

## 回滚策略

### 触发条件

1. **错误率**: ERROR 日志数量超过基线的 200%
2. **响应时间**: API 响应时间 P99 超过基线的 150%
3. **可用性**: 服务可用性低于 99.5%
4. **用户反馈**: 大量用户投诉或负面反馈
5. **严重 Bug**: 发现严重的安全或功能 Bug

### 回滚步骤

1. **紧急回滚**（5 分钟内）:
   ```bash
   # 修改环境变量
   SCENARIO_V2_ENABLED=false
   INTENT_WORKBENCH_ENABLED=false
   JIT_MAPPING_ENABLED=false
   
   # 重启服务
   # 对于支持热加载的配置，可能不需要重启
   ```

2. **监控回滚**（15 分钟内）:
   - 监控错误率是否下降
   - 监控响应时间是否恢复
   - 确认系统恢复正常

3. **问题分析**（1-2 小时内）:
   - 收集日志和监控数据
   - 分析问题根因
   - 制定修复方案

4. **重新发布**（1-2 天内）:
   - 修复问题
   - 重新测试
   - 从小范围灰度开始

### 回滚验证清单

- [ ] 错误率恢复正常
- [ ] 响应时间恢复正常
- [ ] 系统可用性 > 99.5%
- [ ] 用户反馈正常
- [ ] 无新的问题出现

## 监控和告警

### 关键指标

1. **功能使用率**: 新功能的使用比例
2. **错误率**: 新功能的错误率
3. **性能指标**: 响应时间、吞吐量
4. **用户反馈**: 用户满意度、投诉率

### 告警规则

1. **功能使用率告警**: 新功能使用率突然下降
2. **错误率告警**: 新功能错误率超过阈值
3. **性能告警**: 新功能响应时间超过阈值
4. **用户反馈告警**: 负面反馈数量增加

## 最佳实践

### 1. 开发阶段

- 所有新功能都应该有功能开关
- 在开发环境默认启用所有功能开关
- 在生产环境默认禁用所有功能开关

### 2. 测试阶段

- 在测试环境测试各种开关组合
- 验证开关切换的正确性
- 确保回滚方案的可行性

### 3. 发布阶段

- 遵循渐进式发布策略
- 从小范围开始，逐步扩大
- 持续监控关键指标
- 准备好快速回滚

### 4. 运维阶段

- 定期审查功能开关的使用情况
- 清理不再需要的功能开关
- 保持功能开关的简洁性
- 记录功能开关的变更历史

## 附录

### A. Feature Flags 检查清单

- [ ] 所有新功能都有功能开关
- [ ] 功能开关有清晰的文档
- [ ] 功能开关有合理的默认值
- [ ] 功能开关有监控和告警
- [ ] 功能开关有回滚方案
- [ ] 功能开关有版本控制
- [ ] 功能开关有使用记录

### B. 发布检查清单

- [ ] 所有功能开关配置正确
- [ ] 环境变量配置正确
- [ ] 灰度策略已定义
- [ ] 监控和告警已配置
- [ ] 回滚方案已准备
- [ ] 用户通知已发送
- [ ] 文档已更新

### C. 回滚检查清单

- [ ] 回滚触发条件已明确
- [ ] 回滚步骤已文档化
- [ ] 回滚验证清单已准备
- [ ] 相关人员已通知
- [ ] 问题分析流程已定义
- [ ] 重新发布计划已准备

---

**文档版本**: 1.0
**创建日期**: 2026-03-10
**最后更新**: 2026-03-10
**维护者**: DevOps Team