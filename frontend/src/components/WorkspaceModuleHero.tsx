import type { ReactNode } from 'react'
import { Space } from 'antd'

interface MetricItem {
  label: string
  value: ReactNode
}

interface WorkspaceModuleHeroProps {
  eyebrow?: string
  title: string
  description: string
  metrics?: MetricItem[]
  actions?: ReactNode
}

const WorkspaceModuleHero = (props: WorkspaceModuleHeroProps) => {
  const { metrics = [], actions } = props

  return (
    <section className="workspace-module-hero">
      {metrics.length > 0 ? (
        <div className="workspace-module-hero__metrics">
          {metrics.map((metric) => (
            <article key={metric.label} className="workspace-module-hero__metric">
              <span className="workspace-module-hero__metric-label">{metric.label}</span>
              <strong>{metric.value}</strong>
            </article>
          ))}
        </div>
      ) : null}

      {actions ? (
        <div className="workspace-module-hero__actions">
          <Space wrap>{actions}</Space>
        </div>
      ) : null}
    </section>
  )
}

export default WorkspaceModuleHero
