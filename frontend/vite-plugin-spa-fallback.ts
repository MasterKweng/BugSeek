import { Plugin } from 'vite'
import fs from 'fs'
import path from 'path'

export function spaFallback(): Plugin {
  return {
    name: 'vite-plugin-spa-fallback',
    configureServer(server) {
      return () => {
        server.middlewares.use((req, res, next) => {
          // 如果是真正的 API 请求（/api/v1），跳过
          if (req.url?.startsWith('/api/v1')) {
            return next()
          }

          // 如果是静态资源请求，跳过
          if (req.url?.includes('.')) {
            return next()
          }

          // 对于其他请求，返回 index.html
          const indexPath = path.resolve(process.cwd(), 'index.html')
          if (fs.existsSync(indexPath)) {
            res.setHeader('Content-Type', 'text/html')
            res.end(fs.readFileSync(indexPath, 'utf-8'))
          } else {
            next()
          }
        })
      }
    },
  }
}