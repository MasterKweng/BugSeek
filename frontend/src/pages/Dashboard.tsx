import { Card, Col, Row, Statistic } from 'antd'
import { ApiOutlined, FileTextOutlined, UserOutlined } from '@ant-design/icons'

const Dashboard: React.FC = () => {
  return (
    <div className="workspace-page">
      <Row gutter={16}>
        <Col span={8}>
          <Card className="workspace-table-card" bordered={false}>
            <Statistic title="用户数" value={1} prefix={<UserOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card className="workspace-table-card" bordered={false}>
            <Statistic title="接口文档数" value={0} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card className="workspace-table-card" bordered={false}>
            <Statistic title="接口定义数" value={0} prefix={<ApiOutlined />} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default Dashboard
