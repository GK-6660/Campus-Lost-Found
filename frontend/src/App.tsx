import { Alert, Button, Card, Spin, Typography } from "antd";
import { useCallback, useEffect, useState } from "react";

import { loadMe } from "./api/auth";
import { ApiError } from "./api/client";
import type { User } from "./api/types";
import LoginPage from "./pages/LoginPage";

type AppState =
  | { kind: "loading" }
  | { kind: "signed-out" }
  | { kind: "signed-in"; user: User }
  | { kind: "error"; message: string };

function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Unable to verify your sign-in status. Please try again.";
}

export default function App() {
  const [state, setState] = useState<AppState>({ kind: "loading" });

  const loadCurrentUser = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      setState({ kind: "signed-in", user: await loadMe() });
    } catch (error) {
      if (error instanceof ApiError && error.code === "unauthenticated") {
        setState({ kind: "signed-out" });
        return;
      }
      setState({ kind: "error", message: messageFor(error) });
    }
  }, []);

  useEffect(() => {
    void loadCurrentUser();
  }, [loadCurrentUser]);

  if (state.kind === "loading") {
    return <Spin fullscreen tip="Checking sign-in status..." />;
  }

  if (state.kind === "signed-out") {
    return <LoginPage onLoginSuccess={(user) => setState({ kind: "signed-in", user })} />;
  }

  if (state.kind === "error") {
    return (
      <Card title="Unable to start" style={{ margin: "48px auto", maxWidth: 480 }}>
        <Alert type="error" message={state.message} showIcon />
        <Button type="primary" onClick={() => void loadCurrentUser()} style={{ marginTop: 16 }}>
          Try again
        </Button>
      </Card>
    );
  }

  return (
    <Card title="Campus Lost and Found" style={{ margin: "48px auto", maxWidth: 640 }}>
      <Typography.Title level={2}>You are signed in</Typography.Title>
      <Typography.Paragraph>
        Signed in as {state.user.nickname} ({state.user.student_no}).
      </Typography.Paragraph>
    </Card>
  );
}
