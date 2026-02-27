const PptxGenJS = require('pptxgenjs');
const fs = require('fs');

const pptx = new PptxGenJS();

pptx.layout = 'LAYOUT_16x9';

// Slide 1: 封面
const slide1 = pptx.addSlide();
slide1.background = { color: '181B24' };
slide1.addText('BugSeek', { x: 2.5, y: 2, fontSize: 48, color: 'FFFFFF', bold: true, align: 'center' });
slide1.addText('AI 驱动的测试质量平台', { x: 2.5, y: 3.5, fontSize: 24, color: '40695B', align: 'center' });
slide1.addText('从需求洞察到 CI/CD 集成的全流程测试解决方案', { x: 1.5, y: 5, fontSize: 16, color: 'A0AEC0', align: 'center' });

// Slide 2: 业务痛点与解决方案
const slide2 = pptx.addSlide();
slide2.background = { color: 'FFFFFF' };
slide2.addText('业务痛点与解决方案', { x: 1, y: 0.5, fontSize: 32, color: '181B24', bold: true });
slide2.addShape(pptx.ShapeType.line, { x: 1, y: 1.3, w: 8, h: 0, line: { color: 'B165FB', width: 3 } });

slide2.addText('传统测试的挑战', { x: 0.5, y: 1.6, fontSize: 16, color: 'FC8181', bold: true });
slide2.addText('• 测试用例维护成本高\n• 接口依赖关系复杂\n• 质量门禁难以落地\n• 回归测试耗时漫长', { x: 0.5, y: 2.0, fontSize: 12, color: '4A5568', bullet: true });
slide2.addShape(pptx.ShapeType.rect, { x: 0.5, y: 1.6, w: 4, h: 2.5, fill: { color: 'FFF5F5' }, line: { color: 'FC8181', width: 0 } });

slide2.addText('BugSeek 的价值', { x: 4.5, y: 1.6, fontSize: 16, color: '40695B', bold: true });
slide2.addText('• AI 智能分析接口依赖\n• 自动生成测试场景\n• 精准测试减少冗余\n• 全流程质量管控', { x: 4.5, y: 2.0, fontSize: 12, color: '4A5568', bullet: true });
slide2.addShape(pptx.ShapeType.rect, { x: 4.5, y: 1.6, w: 4, h: 2.5, fill: { color: 'F0FFF4' }, line: { color: '40695B', width: 0 } });

slide2.addText('核心优势', { x: 4.5, y: 4.5, fontSize: 16, color: '40695B', bold: true });
slide2.addText('• 效率提升 80%\n• 覆盖率提高 60%\n• 维护成本降低 70%', { x: 4.5, y: 4.9, fontSize: 12, color: '4A5568', bullet: true });
slide2.addShape(pptx.ShapeType.rect, { x: 4.5, y: 4.5, w: 4, h: 1.2, fill: { color: 'F0FFF4' }, line: { color: '40695B', width: 0 } });

// Slide 3: 核心功能模块
const slide3 = pptx.addSlide();
slide3.background = { color: 'FFFFFF' };
slide3.addText('核心功能模块', { x: 1, y: 0.5, fontSize: 32, color: '181B24', bold: true });
slide3.addShape(pptx.ShapeType.line, { x: 1, y: 1.3, w: 8, h: 0, line: { color: 'B165FB', width: 3 } });

const modules = [
  { icon: '📄', title: '接口文档管理', desc: '导入 Swagger/OpenAPI 文档，自动解析接口定义' },
  { icon: '🔗', title: '智能场景组装', desc: 'AI 分析接口依赖，自动生成业务场景' },
  { icon: '📊', title: '模块依赖分析', desc: '识别模块间依赖关系，优化测试策略' },
  { icon: '🔄', title: '字段映射管理', desc: '智能推荐字段映射，支持人工审核确认' },
  { icon: '🧪', title: '测试脚本管理', desc: '自动生成测试脚本，支持批量执行' },
  { icon: '📈', title: '测试报告分析', desc: '可视化测试报告，质量问题一目了然' }
];

modules.forEach((module, i) => {
  const x = 0.5 + (i % 3) * 2.5;
  const y = 1.8 + Math.floor(i / 3) * 2.2;
  slide3.addShape(pptx.ShapeType.rect, { x, y, w: 2.2, h: 1.8, fill: { color: 'F7FAFC' }, rectRadius: 0.15 });
  slide3.addText(module.icon, { x, y: y + 0.1, fontSize: 28, align: 'center' });
  slide3.addText(module.title, { x, y: y + 0.5, fontSize: 12, color: '181B24', bold: true, align: 'center' });
  slide3.addText(module.desc, { x, y: y + 0.9, fontSize: 9, color: '4A5568', align: 'center' });
});

// Slide 4: 智能场景组装
const slide4 = pptx.addSlide();
slide4.background = { color: 'FFFFFF' };
slide4.addText('核心能力：智能场景组装', { x: 1, y: 0.5, fontSize: 32, color: '181B24', bold: true });
slide4.addShape(pptx.ShapeType.line, { x: 1, y: 1.3, w: 8, h: 0, line: { color: 'B165FB', width: 3 } });

const features = [
  { icon: '🧠', title: 'AI 驱动分析', desc: '自动识别接口依赖关系，生成完整业务链路' },
  { icon: '🎯', title: '精准场景生成', desc: '基于分组分析，生成高价值测试场景' },
  { icon: '🔄', title: '变量自动传递', desc: '接口间参数自动关联，无需手动配置' },
  { icon: '📊', title: '依赖图可视化', desc: '直观展示接口依赖关系，便于理解' }
];

features.forEach((feature, i) => {
  const y = 1.8 + i * 0.9;
  slide4.addShape(pptx.ShapeType.rect, { x: 0.5, y, w: 4, h: 0.8, fill: { color: 'EDF2F7' }, rectRadius: 0.1 });
  slide4.addText(feature.icon, { x: 0.6, y: y + 0.15, fontSize: 20 });
  slide4.addText(feature.title, { x: 1.2, y: y + 0.15, fontSize: 14, color: '181B24', bold: true });
  slide4.addText(feature.desc, { x: 1.2, y: y + 0.45, fontSize: 10, color: '4A5568' });
});

slide4.addShape(pptx.ShapeType.rect, { x: 4.8, y: 1.8, w: 3.5, h: 3.8, fill: { color: 'F7FAFC' }, rectRadius: 0.15 });
slide4.addText('效果提升', { x: 5, y: 2.1, fontSize: 18, color: 'B165FB', bold: true });
slide4.addText('• 接口依赖分析准确率达到 95%+\n• 场景生成效率提升 10 倍\n• 测试覆盖率提升 60%\n• 人工维护成本降低 80%', { x: 5, y: 2.6, fontSize: 11, color: '2D3748', bullet: true });

// Slide 5: 业务流程
const slide5 = pptx.addSlide();
slide5.background = { color: 'FFFFFF' };
slide5.addText('业务流程', { x: 1, y: 0.5, fontSize: 32, color: '181B24', bold: true });
slide5.addShape(pptx.ShapeType.line, { x: 1, y: 1.3, w: 8, h: 0, line: { color: 'B165FB', width: 3 } });

const processes = [
  '导入接口文档（Swagger/OpenAPI）',
  'AI 分析接口依赖关系',
  '自动生成测试场景',
  '配置测试数据和参数',
  '执行测试并生成报告'
];

processes.forEach((process, i) => {
  const y = 1.8 + i * 0.8;
  slide5.addShape(pptx.ShapeType.rect, { x: 0.5, y, w: 3.8, h: 0.6, fill: { color: 'F7FAFC' }, rectRadius: 0.08 });
  slide5.addShape(pptx.ShapeType.ellipse, { x: 0.6, y: y + 0.05, w: 0.4, h: 0.5, fill: { color: 'B165FB' } });
  slide5.addText((i + 1).toString(), { x: 0.65, y: y + 0.1, fontSize: 14, color: 'FFFFFF', bold: true, align: 'center' });
  slide5.addText(process, { x: 1.2, y: y + 0.15, fontSize: 12, color: '2D3748' });
});

slide5.addShape(pptx.ShapeType.rect, { x: 4.5, y: 1.8, w: 4, h: 3.8, fill: { color: '40695B' }, rectRadius: 0.15 });
slide5.addText('业务价值', { x: 4.7, y: 2.1, fontSize: 18, color: 'FFFFFF', bold: true });
slide5.addText('⚡ 测试准备时间缩短 70%\n🎯 测试用例覆盖率提升 60%\n🔍 缺陷发现率提升 45%\n💰 测试成本降低 50%', { x: 4.7, y: 2.6, fontSize: 12, color: 'FFFFFF' });

// Slide 6: 适用场景
const slide6 = pptx.addSlide();
slide6.background = { color: 'FFFFFF' };
slide6.addText('适用场景', { x: 1, y: 0.5, fontSize: 32, color: '181B24', bold: true });
slide6.addShape(pptx.ShapeType.line, { x: 1, y: 1.3, w: 8, h: 0, line: { color: 'B165FB', width: 3 } });

const useCases = [
  { title: '🏢 企业级应用', desc: '复杂业务系统，接口众多，依赖关系复杂' },
  { title: '🛒 电商平台', desc: '订单、商品、用户等模块深度耦合' },
  { title: '📱 移动应用', desc: '前后端分离，API 接口密集' },
  { title: '🔧 微服务架构', desc: '服务间调用复杂，需要跨服务测试' }
];

useCases.forEach((useCase, i) => {
  const y = 1.8 + i * 0.9;
  slide6.addShape(pptx.ShapeType.rect, { x: 0.5, y, w: 3.8, h: 0.8, fill: { color: 'FFFFFF' }, line: { color: 'E2E8F0', width: 2 }, rectRadius: 0.08 });
  slide6.addText(useCase.title, { x: 0.7, y: y + 0.1, fontSize: 14, color: '181B24', bold: true });
  slide6.addText(useCase.desc, { x: 0.7, y: y + 0.4, fontSize: 11, color: '4A5568' });
});

slide6.addText('目标用户', { x: 4.7, y: 1.8, fontSize: 18, color: 'B165FB', bold: true });
const users = [
  '• 软件测试团队 • QA 工程师 • 测试开发工程师',
  '• 软件开发团队 • 后端开发工程师 • API 开发工程师',
  '• 技术负责人 • 质量负责人 • 项目经理'
];
users.forEach((user, i) => {
  const y = 2.3 + i * 0.7;
  slide6.addShape(pptx.ShapeType.rect, { x: 4.5, y, w: 4, h: 0.6, fill: { color: 'FFFFFF' }, line: { color: 'E2E8F0', width: 0 }, rectRadius: 0.08 });
  slide6.addShape(pptx.ShapeType.rect, { x: 4.5, y, w: 0.1, h: 0.6, fill: { color: '40695B' }, rectRadius: 0.08 });
  slide6.addText(user, { x: 4.7, y: y + 0.15, fontSize: 12, color: '2D3748' });
});

// Slide 7: 产品特色
const slide7 = pptx.addSlide();
slide7.background = { color: 'FFFFFF' };
slide7.addText('产品特色', { x: 1, y: 0.5, fontSize: 32, color: '181B24', bold: true });
slide7.addShape(pptx.ShapeType.line, { x: 1, y: 1.3, w: 8, h: 0, line: { color: 'B165FB', width: 3 } });

const featuresList = [
  { title: '智能化', items: ['AI 驱动的接口依赖分析', '自动生成测试场景', '智能推荐字段映射', '自适应测试策略'] },
  { title: '易用性', items: ['一键导入接口文档', '可视化依赖图展示', '拖拽式场景编排', '实时执行反馈'] },
  { title: '可靠性', items: ['支持 PostgreSQL 数据库', '完整的任务状态追踪', '详细的执行日志', '数据安全保障'] }
];

featuresList.forEach((feature, i) => {
  const x = 0.5 + (i % 2) * 4;
  const y = 1.8 + Math.floor(i / 2) * 2.3;
  slide7.addText(feature.title, { x, y, fontSize: 16, color: 'B165FB', bold: true });
  slide7.addText(feature.items.map(item => '▸ ' + item).join('\n'), { x, y: y + 0.4, fontSize: 11, color: '2D3748' });
});

slide7.addShape(pptx.ShapeType.rect, { x: 0.5, y: 4.5, w: 8, h: 1.3, fill: { color: 'F7FAFC' }, rectRadius: 0.1 });
slide7.addText('技术架构', { x: 0.7, y: 4.7, fontSize: 16, color: '181B24', bold: true });
slide7.addText('前端：React + TypeScript | 后端：FastAPI + Python | 数据库：PostgreSQL + pgvector | 异步任务：Celery + Redis', { x: 0.7, y: 5.1, fontSize: 11, color: '2D3748' });

// Slide 8: 结束页
const slide8 = pptx.addSlide();
slide8.background = { color: '181B24' };
slide8.addText('感谢聆听', { x: 2.5, y: 1.5, fontSize: 42, color: 'FFFFFF', bold: true, align: 'center' });
slide8.addShape(pptx.ShapeType.line, { x: 2.8, y: 3, w: 3.4, h: 0, line: { color: '40695B', width: 4 } });
slide8.addText('让测试更智能', { x: 2.5, y: 3.5, fontSize: 28, color: 'B165FB', bold: true, align: 'center' });
slide8.addText('BugSeek - AI 驱动的测试质量平台', { x: 1.5, y: 5, fontSize: 18, color: 'A0AEC0', align: 'center' });
slide8.addText('如需了解更多信息，请联系我们', { x: 2.5, y: 5.5, fontSize: 14, color: 'FFFFFF', align: 'center' });

pptx.writeFile({ fileName: 'BugSeek_项目介绍.pptx' });
console.log('PPT created successfully!');