import { Card, Row, Col, Statistic } from 'antd'
import { UserOutlined, FileTextOutlined, ApiOutlined } from '@ant-design/icons'

const Dashboard: React.FC = () => {
  return (
    <div style={{ padding: '24px' }}>
      <h1>仪表盘</h1>
      <Row gutter={16}>
        <Col span={8}>
          <Card>
            <Statistic
              title="用户数"
              value={1}
              prefix={<UserOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="接口文档数"
              value={0}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="接口定义数"
              value={0}
              prefix={<ApiOutlined />}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default Dashboard