/**
 * 统一的 API 请求服务
 * 封装 fetch 请求，添加超时设置和错误处理
 */

// API 基础路径
const BASE_URL = '/api/v1';

// 请求超时配置（毫秒）
export const REQUEST_TIMEOUT = {
  NORMAL: 10000,    // 普通接口 10s
  FILE: 30000,      // 文件类 30s
  LONG_POLLING: 60000, // 长轮询 60s
};

/**
 * 带超时的 fetch 封装
 * @param url 请求地址
 * @param options fetch 选项
 * @param timeout 超时时间（毫秒）
 * @returns Promise<Response>
 */
export async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeout: number = REQUEST_TIMEOUT.NORMAL
): Promise<Response> {
  // 获取 token
  const token = localStorage.getItem('token');

  // 设置默认 headers
  const headers = new Headers(options.headers ?? undefined);

  if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // 创建超时控制器
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    return response;
  } catch (error: any) {
    clearTimeout(timeoutId);

    // 处理超时错误
    if (error.name === 'AbortError') {
      throw new Error('请求超时，请检查网络后重试');
    }

    // 处理网络错误
    if (!error.response) {
      throw new Error('网络连接失败，请检查网络');
    }

    throw error;
  }
}

/**
 * GET 请求
 */
export async function get<T = any>(
  url: string,
  params?: Record<string, any>,
  timeout: number = REQUEST_TIMEOUT.NORMAL
): Promise<T> {
  let requestUrl = `${BASE_URL}${url}`;

  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    requestUrl += `?${searchParams.toString()}`;
  }

  const response = await fetchWithTimeout(requestUrl, { method: 'GET' }, timeout);
  return await handleResponse<T>(response);
}

/**
 * POST 请求
 */
export async function post<T = any>(
  url: string,
  data?: any,
  timeout: number = REQUEST_TIMEOUT.NORMAL
): Promise<T> {
  const response = await fetchWithTimeout(
    `${BASE_URL}${url}`,
    {
      method: 'POST',
      body: data instanceof FormData ? data : data ? JSON.stringify(data) : undefined,
    },
    timeout
  );
  return await handleResponse<T>(response);
}

/**
 * PUT 请求
 */
export async function put<T = any>(
  url: string,
  data?: any,
  timeout: number = REQUEST_TIMEOUT.NORMAL
): Promise<T> {
  const response = await fetchWithTimeout(
    `${BASE_URL}${url}`,
    {
      method: 'PUT',
      body: data instanceof FormData ? data : data ? JSON.stringify(data) : undefined,
    },
    timeout
  );
  return await handleResponse<T>(response);
}

/**
 * DELETE 请求
 */
export async function del<T = any>(
  url: string,
  timeout: number = REQUEST_TIMEOUT.NORMAL
): Promise<T> {
  const response = await fetchWithTimeout(`${BASE_URL}${url}`, { method: 'DELETE' }, timeout);
  return await handleResponse<T>(response);
}

/**
 * 处理响应
 */
async function handleResponse<T>(response: Response): Promise<T> {
  // 检查响应的 Content-Type
  const contentType = response.headers.get('content-type');

  // 如果不是 JSON 响应，可能是 HTML 错误页面
  if (!contentType || !contentType.includes('application/json')) {
    const text = await response.text();
    console.error('非 JSON 响应:', response.status, text.substring(0, 200));

    // 401 未授权，静默跳转登录
    if (response.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
      throw new Error('登录已过期，请重新登录');
    }

    // 404 未找到
    if (response.status === 404) {
      throw new Error('接口不存在，请检查请求路径');
    }

    // 其他错误
    throw new Error(`服务器返回错误 (${response.status})，请稍后重试`);
  }

  const result = await response.json();

  // 401 未授权，静默跳转登录
  if (response.status === 401) {
    localStorage.removeItem('token');
    window.location.href = '/login';
    throw new Error('登录已过期，请重新登录');
  }

  // 409 冲突
  if (response.status === 409) {
    throw new Error(result.detail || result.message || '数据冲突');
  }

  // 500 服务器错误
  if (response.status >= 500) {
    throw new Error(result.message || '服务开小差了，请稍后重试');
  }

  // 业务错误
  if (result.code !== 0) {
    throw new Error(result.message || '请求失败');
  }

  return result.data;
}
