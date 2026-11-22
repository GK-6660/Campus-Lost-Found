import { useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Empty, Input, Modal, Space, Spin, Typography } from "antd";
import { loadReports, takedown } from "../api/admin";
import { loadMe } from "../api/auth";
import { ApiError, request } from "../api/client";
import type { Item } from "../api/types";

type Report = {
  id: string;
  item_id: string;
  reason: string;
  created_at: string;
  status: "open" | "closed";
};

function isReport(value: unknown): value is Report {
  if (typeof value !== "object" || value === null) return false;
  const r = value as Record<string, unknown>;
  return (
    ["id", "item_id", "reason", "created_at"].every((key) => typeof r[key] === "string") &&
    (r.status === "open" || r.status === "closed")
  );
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : "Unable to connect. Please try again.";
}

/** D: standalone admin page; the integration owner mounts it in the shared app. */
export default function AdminPage() {
  const [access, setAccess] = useState<"checking" | "admin" | "denied" | "error">("checking");
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [selected, setSelected] = useState<Report | null>(null);
  const [item, setItem] = useState<Item | null>(null);
  const [reason, setReason] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [mustReload, setMustReload] = useState(false);
  const sending = useRef(false);
  const selection = useRef(0);
  const generation = useRef(0);

  function checkAccess(error: unknown) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      setAccess("denied");
      setReports([]);
      setSelected(null);
      setItem(null);
      return true;
    }
    return false;
  }

  async function refreshReports() {
    setLoading(true);
    setError(null);
    try {
      const result = await loadReports();
      if (!Array.isArray(result.items) || !result.items.every(isReport)) {
        throw new Error("Invalid report response");
      }
      setReports(result.items.filter((report) => report.status === "open"));
    } catch (error) {
      if (!checkAccess(error)) setError(errorText(error));
    } finally {
      setLoading(false);
    }
  }

  async function start() {
    const current = ++generation.current;
    setAccess("checking");
    setError(null);
    try {
      const user = await loadMe();
      if (current !== generation.current) return;
      if (user.role !== "admin") {
        setAccess("denied");
        return;
      }
      setAccess("admin");
      await refreshReports();
    } catch (error) {
      if (current !== generation.current) return;
      if (!checkAccess(error)) {
        setAccess("error");
        setError(errorText(error));
      }
    }
  }

  useEffect(() => {
    void start();
    return () => {
      generation.current++;
      selection.current++;
    };
    // Initial authentication runs once per mount, including React StrictMode remount checks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function readItem(report: Report) {
    const current = ++selection.current;
    setItem(null);
    setDetailLoading(true);
    setDetailError(null);
    setMustReload(false);
    try {
      // Reports contain no version; read the current item rather than guessing one.
      const latest = await request<Item>("/items/" + encodeURIComponent(report.item_id));
      if (current !== selection.current) return;
      if (latest.id !== report.item_id || !Number.isInteger(latest.version)) {
        throw new Error("Invalid item response");
      }
      setItem(latest);
      if (latest.status === "closed")
        setDetailError("This item is already closed. Refresh the report list.");
    } catch (error) {
      if (current !== selection.current) return;
      if (!checkAccess(error)) setDetailError(errorText(error));
    } finally {
      if (current === selection.current) setDetailLoading(false);
    }
  }

  function closeDialog() {
    if (sending.current) return;
    selection.current++;
    setSelected(null);
    setItem(null);
    setReason("");
  }

  async function submit() {
    const trimmed = reason.trim();
    if (sending.current || !selected || !item || mustReload || item.status === "closed") return;
    if (!trimmed || Array.from(trimmed).length > 200) {
      setDetailError("Enter a takedown reason of 1–200 characters.");
      return;
    }
    sending.current = true;
    setBusy(true);
    setDetailError(null);
    try {
      await takedown(item.id, item.version, trimmed);
      // One takedown closes all open reports about the same item.
      setReports((previous) => previous.filter((report) => report.item_id !== item.id));
      setSelected(null);
      setItem(null);
      setReason("");
      setSuccess("Item taken down. All open reports for this item have been closed.");
    } catch (error) {
      if (!checkAccess(error)) {
        // admin.ts creates a fresh request ID on every call. Do not automatically retry an uncertain write.
        setMustReload(true);
        setDetailError(
          error instanceof ApiError
            ? errorText(error) + " Reload the item and review before submitting again."
            : "The result could not be confirmed. Reload the item to check its state before submitting again.",
        );
      }
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }

  if (access === "checking")
    return (
      <Spin tip="Checking administrator access...">
        <div style={{ minHeight: 120 }} />
      </Spin>
    );
  if (access === "denied")
    return (
      <Alert
        type="warning"
        showIcon
        message="Administrator access required"
        description="Sign in with an administrator account to manage reports."
      />
    );
  if (access === "error")
    return (
      <Space direction="vertical">
        <Alert type="error" message={error} />
        <Button onClick={() => void start()}>Retry access check</Button>
      </Space>
    );

  return (
    <section style={{ maxWidth: 960, margin: "24px auto", padding: 16 }}>
      <Typography.Title level={2}>Report management</Typography.Title>
      <Typography.Paragraph>
        Review reported content and take down inappropriate items. Administrators do not determine
        ownership or hold physical items.
      </Typography.Paragraph>
      <Space direction="vertical" size="middle" style={{ width: "100%" }}>
        {success && <Alert type="success" showIcon message={success} />}
        {error && <Alert type="error" showIcon message={error} />}
        <Button loading={loading} disabled={busy} onClick={() => void refreshReports()}>
          Refresh reports
        </Button>
        <Spin spinning={loading}>
          {!loading && !error && reports.length === 0 && <Empty description="No pending reports" />}
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            {reports.map((report) => (
              <Card key={report.id} title="Pending report" size="small">
                <Typography.Paragraph style={{ overflowWrap: "anywhere" }}>
                  Report: {report.id}
                  <br />
                  Item: {report.item_id}
                </Typography.Paragraph>
                <Typography.Paragraph style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                  Reason: {report.reason}
                </Typography.Paragraph>
                <Typography.Paragraph>Reported: {report.created_at}</Typography.Paragraph>
                <Button
                  danger
                  disabled={loading || !!error || busy}
                  onClick={() => {
                    setSelected(report);
                    setReason("");
                    setSuccess(null);
                    void readItem(report);
                  }}
                >
                  Review takedown
                </Button>
              </Card>
            ))}
          </Space>
        </Spin>
      </Space>
      <Modal
        title="Review item takedown"
        open={selected !== null}
        onCancel={closeDialog}
        onOk={() => void submit()}
        okText="Take down item"
        confirmLoading={busy}
        okButtonProps={{
          danger: true,
          disabled:
            !item ||
            detailLoading ||
            mustReload ||
            item.status === "closed" ||
            !reason.trim() ||
            Array.from(reason.trim()).length > 200,
        }}
        cancelButtonProps={{ disabled: busy }}
        closable={!busy}
        maskClosable={!busy}
        keyboard={!busy}
      >
        {selected && (
          <Typography.Paragraph style={{ overflowWrap: "anywhere" }}>
            Item: {selected.item_id}
            <br />
            Report reason: {selected.reason}
          </Typography.Paragraph>
        )}
        {detailError && (
          <Alert type="error" showIcon message={detailError} style={{ marginBottom: 16 }} />
        )}
        <Spin spinning={detailLoading}>
          {item && (
            <Typography.Paragraph style={{ overflowWrap: "anywhere" }}>
              Category: {item.category ?? "Unknown"}
              <br />
              Description: {item.description ?? "Not provided"}
              <br />
              Status: {item.status} · Version: {item.version}
            </Typography.Paragraph>
          )}
        </Spin>
        {selected && (
          <Button
            disabled={busy || detailLoading}
            onClick={() => void readItem(selected)}
            style={{ marginBottom: 16 }}
          >
            Reload item
          </Button>
        )}
        <label htmlFor="takedown-reason">Takedown reason (required, 1–200 characters)</label>
        <Input.TextArea
          id="takedown-reason"
          value={reason}
          disabled={busy}
          rows={4}
          showCount
          maxLength={200}
          onChange={(event) => setReason(event.target.value)}
        />
        <Typography.Paragraph type="secondary">
          This closes the item and its open reports, and notifies its owner.
        </Typography.Paragraph>
      </Modal>
    </section>
  );
}
