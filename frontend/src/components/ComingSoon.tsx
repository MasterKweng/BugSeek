import React from 'react';
import { Result, Button } from 'antd';
import { useNavigate } from 'react-router-dom';

const ComingSoon: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div style={{ padding: '50px', textAlign: 'center' }}>
      <Result
        status="info"
        title="功能开发中"
        subTitle="该功能正在开发中，敬请期待"
        extra={[
          <Button type="primary" key="dashboard" onClick={() => navigate('/dashboard')}>
            返回首页
          </Button>,
        ]}
      />
    </div>
  );
};

export default ComingSoon;