// 在浏览器控制台中运行此代码来检查 store 状态

// 获取 localStorage 中的数据
console.log('=== 检查 localStorage ===');
const authStorage = localStorage.getItem('auth-storage');
const projectStorage = localStorage.getItem('project-storage');

console.log('auth-storage:', authStorage ? JSON.parse(authStorage) : null);
console.log('project-storage:', projectStorage ? JSON.parse(projectStorage) : null);

// 检查 token
const token = localStorage.getItem('token');
console.log('token:', token ? token.substring(0, 20) + '...' : '无');

console.log('\n=== 预期结果 ===');
console.log('auth-storage.state.user: 应该有用户信息');
console.log('auth-storage.state.token: 应该有token');
console.log('auth-storage.state.isAuthenticated: 应该是 true');
console.log('project-storage.state.currentProject: 应该有当前项目');
console.log('project-storage.state.currentProject.id: 应该是 2');
console.log('project-storage.state.currentVersion: 应该有当前版本');
console.log('project-storage.state.currentVersion.id: 应该是 4');