  您希望基本配置中的"鉴权类型"在选择 BASIC、BEARER、API_KEY、SESSION 这四种类型时，能够提供与登录接口鉴权类型一致的简化配置体验。

  当前情况分析

  登录接口鉴权类型：
   - 选择 BASIC/BEARER/API_KEY/SESSION 时，显示简化的参数映射界面
   - 这些参数用于调用登录接口获取 token

  基本配置中的鉴权类型：
   - 选择鉴权类型后，需要配置"注入目标"和"注入方式"
   - 这些配置用于将鉴权信息注入到目标接口

  改动方案

  方案思路
  当用户在基本配置中选择 BASIC、BEARER、API_KEY、SESSION 这四种鉴权类型时：

   1. 自动设置注入方式：
      - BASIC：自动设置注入目标为 HEADER，注入 key 为 Authorization，注入模板为 Basic {static_value}
      - BEARER：自动设置注入目标为 HEADER，注入 key 为 Authorization，注入模板为 Bearer {static_value}
      - API_KEY：显示配置界面，让用户选择添加到 Header 还是 Query，并输入 key 名称
      - SESSION：自动设置注入目标为 HEADER，注入 key 为 Cookie，注入模板为 {static_value}

   2. 来源模式处理：
      - 这四种类型应该自动切换为"静态模式"
      - 隐藏"动态模式"相关配置（登录接口 ID、参数映射、提取规则）
      - 只显示静态值输入框

   3. 界面展示：
      - 鉴权类型选择后，在"基本配置"卡片内显示对应的简化输入界面
      - BASIC：用户名 + 密码（自动拼接为 base64(username:password)）
      - Bearer：Token 输入框
      - API Key：Key 名称 + Value + 添加位置（Header/Query）
      - Session：Session ID + Cookie 名称

   4. 数据保存：
      - 前端将简化输入转换为标准的注入配置格式
      - BASIC 类型：static_value = base64(username:password)
      - 其他类型：直接使用用户输入的值

  具体改动点

  前端（AuthConfigForm.tsx）：
   1. 监听 auth_type 的变化
   2. 当选择 BASIC/BEARER/API_KEY/SESSION 时：
      - 自动设置 source_mode 为 STATIC
      - 自动设置注入目标的默认值
      - 显示对应的简化配置界面
   3. 修改 handleSubmit 函数，处理简化输入的转换

  后端：
   - 基本配置的注入逻辑已经支持这些类型，应该不需要修改
   - 前端传递的 injection 配置格式已经标准化

  特殊类型处理说明

   - NONE：不显示简化配置，保持原有的完整配置界面（静态/动态模式）
   - CUSTOM：不显示简化配置，保持原有的完整配置界面（静态/动态模式）

  这样的改动能让用户在配置基本鉴权时，与配置登录接口鉴权类型有类似的简化体验，降低配置复杂度。

本次修改不要修改其他内容，只修改基本鉴权


