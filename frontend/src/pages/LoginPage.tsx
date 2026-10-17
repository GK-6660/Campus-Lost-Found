import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { useState } from "react";

import { login } from "../api/auth";
import { ApiError } from "../api/client";
import type { User } from "../api/types";

type LoginValues = {
  studentNo: string;
  password: string;
};

type Props = {
  onLoginSuccess: (user: User) => void;
};

function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Unable to sign in. Please try again.";
}

export default function LoginPage({ onLoginSuccess }: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function submit(values: LoginValues) {
    setSubmitting(true);
    setMessage(null);
    try {
      onLoginSuccess(await login(values.studentNo.trim(), values.password));
    } catch (error) {
      setMessage(messageFor(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card title="Sign in" style={{ margin: "48px auto", maxWidth: 400 }}>
      <Typography.Paragraph>
        Please sign in to access the campus lost-and-found service.
      </Typography.Paragraph>
      {message && <Alert type="error" message={message} showIcon style={{ marginBottom: 16 }} />}
      <Form<LoginValues> layout="vertical" onFinish={(values) => void submit(values)}>
        <Form.Item
          label="Student number"
          name="studentNo"
          rules={[{ required: true, message: "Student number is required." }]}
        >
          <Input autoComplete="username" />
        </Form.Item>
        <Form.Item
          label="Password"
          name="password"
          rules={[{ required: true, message: "Password is required." }]}
        >
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Button block type="primary" htmlType="submit" loading={submitting}>
          Sign in
        </Button>
      </Form>
    </Card>
  );
}
