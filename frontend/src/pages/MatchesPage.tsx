import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  Empty,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import enUS from "antd/locale/en_US";
import zhCN from "antd/locale/zh_CN";
import { useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { submitClaim } from "../api/claims";
import { loadMatches } from "../api/matches";
import type { Category, ClaimResult, Color, DayPart, Item, PlaceCode } from "../api/types";

/**
 * C 组：候选与已找回。
 * 失主发布失物后，在这里查看候选拾获并标记「已找回」或「没找到」。
 * 仅通过 matches.ts 和 claims.ts 发请求，不各自实现 fetch。
 * Match 的完整形状在 types.ts 里是 unknown[]，这里与 notifications.ts 一样本地定义并断言。
 */

type Reason = {
  code: "category" | "color" | "place" | "time" | "brand" | "keyword";
  points: number;
  text: string;
};

type PublicItem = {
  item_id: string;
  type: "lost" | "found";
  category: Category | null;
  color: Color | null;
  place_code: PlaceCode | null;
  place_note: string | null;
  occurred_on: string | null;
  day_part: DayPart | null;
  image_id: string | null;
};

type Match = {
  id: string;
  lost_item_id: string;
  found_item_id: string;
  score: number;
  score_max: number;
  notify: boolean;
  reasons: Reason[];
  conflicts: Reason[];
  counterpart: PublicItem;
};

type ClaimedState = Record<string, ClaimResult>;
type Language = "zh" | "en";

type Props = {
  /** 失主已发布的失物记录。本页用它作为 lost_item_id 查询候选并提交找回。 */
  item: Item;
  /** 未登录时由集成页决定跳转，不在本页约定路由。 */
  onLoginRequired?: () => void;
};

const categoryLabels: Record<Language, Record<Category, string>> = {
  zh: {
    earphones: "耳机",
    campus_card: "校园卡",
    keys: "钥匙",
    bottle: "水杯",
    book: "书",
    clothing: "衣物",
    electronics: "电子产品",
    umbrella: "伞",
    bag: "包",
    other: "其他",
    unknown: "未知",
  },
  en: {
    earphones: "Earphones",
    campus_card: "Campus card",
    keys: "Keys",
    bottle: "Bottle",
    book: "Book",
    clothing: "Clothing",
    electronics: "Electronics",
    umbrella: "Umbrella",
    bag: "Bag",
    other: "Other",
    unknown: "Unknown",
  },
};

const colorLabels: Record<Language, Record<Color, string>> = {
  zh: {
    black: "黑色",
    white: "白色",
    gray: "灰色",
    red: "红色",
    orange: "橙色",
    yellow: "黄色",
    green: "绿色",
    blue: "蓝色",
    purple: "紫色",
    pink: "粉色",
    brown: "棕色",
    multi: "多色",
    unknown: "未知",
  },
  en: {
    black: "Black",
    white: "White",
    gray: "Gray",
    red: "Red",
    orange: "Orange",
    yellow: "Yellow",
    green: "Green",
    blue: "Blue",
    purple: "Purple",
    pink: "Pink",
    brown: "Brown",
    multi: "Multicolor",
    unknown: "Unknown",
  },
};

const placeLabels: Record<Language, Record<PlaceCode, string>> = {
  zh: {
    library: "图书馆",
    teaching_a: "教学楼A",
    teaching_b: "教学楼B",
    canteen_1: "一食堂",
    canteen_2: "二食堂",
    dorm: "宿舍区",
    gym: "体育馆",
    admin_building: "行政楼",
  },
  en: {
    library: "Library",
    teaching_a: "Teaching Building A",
    teaching_b: "Teaching Building B",
    canteen_1: "Canteen 1",
    canteen_2: "Canteen 2",
    dorm: "Dormitories",
    gym: "Gym",
    admin_building: "Administration Building",
  },
};

const dayPartLabels: Record<Language, Record<DayPart, string>> = {
  zh: { morning: "上午", afternoon: "下午", evening: "晚上" },
  en: { morning: "Morning", afternoon: "Afternoon", evening: "Evening" },
};

const resultLabels: Record<Language, Record<ClaimResult, string>> = {
  zh: { returned: "已找回", not_found: "没找到" },
  en: { returned: "Recovered", not_found: "Not found" },
};

/** 只翻译界面文案；枚举值始终使用接口约定的英文。 */
const english: Record<string, string> = {
  候选与已找回: "Matches and recovery",
  "为这条失物查看候选拾获，并标记是否已找回。":
    "Review candidate found items for this lost item, and mark whether it was recovered.",
  "候选加载失败，请稍后重试。": "Failed to load matches. Please try again later.",
  没有候选: "No matches yet",
  "正在加载候选…": "Loading matches...",
  为什么像: "Why it matches",
  冲突: "Conflicts",
  类别: "Category",
  颜色: "Color",
  地点: "Place",
  日期: "Date",
  时段: "Time of day",
  位置备注: "Location note",
  已找回: "Recovered",
  没找到: "Not found",
  "已提交：已找回。": "Submitted: recovered.",
  "已提交：未找到。": "Submitted: not found.",
  "该拾获已被标记为已找回。": "This found item has already been returned.",
  "操作失败，请稍后重试。": "The action failed. Please try again later.",
  "这条记录不是失物，无法查看候选。":
    "This record is not a lost item, so there are no matches to show.",
  "请先登录后再操作。": "Please sign in before continuing.",
  "匹配分数仅用于排序，不作为领回判定。":
    "The match score is for ordering only and is not proof of ownership.",
  界面语言: "Interface language",
};

function translate(text: string, language: Language): string {
  return language === "en" ? (english[text] ?? text) : text;
}

function scoreLabel(score: number, language: Language): string {
  return language === "en"
    ? `Match score ${score}/100, for ordering only`
    : `匹配分 ${score}/100，仅用于排序`;
}

function Thumbnail({ imageId }: { imageId: string | null }) {
  const [hidden, setHidden] = useState(false);
  if (imageId === null || hidden) return null;
  return (
    <img
      src={`/api/v1/files/${encodeURIComponent(imageId)}`}
      alt=""
      loading="lazy"
      onError={() => setHidden(true)}
      style={{ width: 96, height: 96, objectFit: "cover", borderRadius: 6, display: "block" }}
    />
  );
}

export default function MatchesPage({ item, onLoginRequired }: Props) {
  const [language, setLanguage] = useState<Language>("zh");
  const languageRef = useRef<Language>("zh");
  const [matches, setMatches] = useState<Match[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [claimed, setClaimed] = useState<ClaimedState>({});
  const [claiming, setClaiming] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const t = (text: string) => translate(text, languageRef.current);
  const isLost = item.type === "lost";

  function changeLanguage(next: Language) {
    languageRef.current = next;
    setLanguage(next);
  }

  useEffect(() => {
    if (!isLost) return;
    let cancelled = false;
    async function run() {
      setLoading(true);
      setLoadError(null);
      try {
        const list = await loadMatches(item.id);
        if (!cancelled) setMatches(list.matches as Match[]);
      } catch {
        if (!cancelled) setLoadError("候选加载失败，请稍后重试。");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void run();
    return () => {
      cancelled = true;
    };
  }, [item.id, isLost]);

  async function handleClaim(match: Match, result: ClaimResult) {
    setClaiming(match.found_item_id);
    setNotice(null);
    try {
      await submitClaim(item.id, match.found_item_id, result);
      setClaimed((prev) => ({ ...prev, [match.found_item_id]: result }));
      setNotice({
        type: "success",
        text: result === "returned" ? "已提交：已找回。" : "已提交：未找到。",
      });
    } catch (error) {
      if (error instanceof ApiError && error.code === "unauthenticated") {
        setNotice({ type: "error", text: "请先登录后再操作。" });
        onLoginRequired?.();
        return;
      }
      if (error instanceof ApiError && error.code === "found_already_returned") {
        setClaimed((prev) => ({ ...prev, [match.found_item_id]: "returned" }));
        setNotice({ type: "error", text: "该拾获已被标记为已找回。" });
        return;
      }
      setNotice({ type: "error", text: "操作失败，请稍后重试。" });
    } finally {
      setClaiming(null);
    }
  }

  return (
    <ConfigProvider locale={language === "zh" ? zhCN : enUS}>
      <section
        lang={language === "zh" ? "zh-CN" : "en"}
        style={{ maxWidth: 720, margin: "0 auto" }}
      >
        <Space style={{ marginBottom: 16 }}>
          <span>{t("界面语言")} / Language</span>
          <Select
            aria-label="界面语言 / Interface language"
            value={language}
            onChange={changeLanguage}
            options={[
              { label: "中文", value: "zh" },
              { label: "English", value: "en" },
            ]}
            style={{ minWidth: 120 }}
          />
        </Space>

        <Typography.Title level={2} style={{ marginTop: 0 }}>
          {t("候选与已找回")}
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          {t("为这条失物查看候选拾获，并标记是否已找回。")}
        </Typography.Paragraph>

        {notice && (
          <Alert
            type={notice.type}
            showIcon
            message={t(notice.text)}
            style={{ marginBottom: 16 }}
          />
        )}

        {!isLost ? (
          <Alert type="error" showIcon message={t("这条记录不是失物，无法查看候选。")} />
        ) : loading ? (
          <Spin tip={t("正在加载候选…")} style={{ display: "block", margin: "32px auto" }}>
            <div style={{ minHeight: 120 }} />
          </Spin>
        ) : loadError ? (
          <Alert type="error" showIcon message={t(loadError)} />
        ) : matches === null || matches.length === 0 ? (
          <Empty description={t("没有候选")} style={{ marginTop: 48 }} />
        ) : (
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            {matches.map((match) => {
              const counterpart = match.counterpart;
              const claimResult = claimed[match.found_item_id];
              return (
                <Card key={match.id} size="small">
                  <Space wrap style={{ justifyContent: "space-between", width: "100%" }}>
                    <Thumbnail imageId={counterpart.image_id} />
                    <Space direction="vertical" size={2}>
                      <Typography.Text strong>{scoreLabel(match.score, language)}</Typography.Text>
                      <Typography.Text type="secondary">
                        {t("类别")}:{" "}
                        {counterpart.category
                          ? categoryLabels[language][counterpart.category]
                          : "—"}
                      </Typography.Text>
                      <Typography.Text type="secondary">
                        {t("颜色")}:{" "}
                        {counterpart.color ? colorLabels[language][counterpart.color] : "—"}
                      </Typography.Text>
                    </Space>
                    <Space direction="vertical" size={2}>
                      <Typography.Text type="secondary">
                        {t("地点")}:{" "}
                        {counterpart.place_code
                          ? placeLabels[language][counterpart.place_code]
                          : "—"}
                      </Typography.Text>
                      {counterpart.place_note && (
                        <Typography.Text type="secondary">
                          {t("位置备注")}: {counterpart.place_note}
                        </Typography.Text>
                      )}
                      <Typography.Text type="secondary">
                        {t("日期")}: {counterpart.occurred_on ?? "—"}
                      </Typography.Text>
                      <Typography.Text type="secondary">
                        {t("时段")}:{" "}
                        {counterpart.day_part ? dayPartLabels[language][counterpart.day_part] : "—"}
                      </Typography.Text>
                    </Space>
                  </Space>

                  {match.reasons.length > 0 && (
                    <Space direction="vertical" size={2} style={{ marginTop: 12, width: "100%" }}>
                      <Typography.Text strong>{t("为什么像")}</Typography.Text>
                      {match.reasons.map((reason) => (
                        <Typography.Text key={`${reason.code}-${reason.text}`}>
                          {reason.points >= 0 ? `+${reason.points}` : reason.points} · {reason.text}
                        </Typography.Text>
                      ))}
                    </Space>
                  )}

                  {match.conflicts.length > 0 && (
                    <Space direction="vertical" size={2} style={{ marginTop: 12, width: "100%" }}>
                      <Typography.Text strong type="danger">
                        {t("冲突")}
                      </Typography.Text>
                      {match.conflicts.map((reason) => (
                        <Typography.Text type="danger" key={`${reason.code}-${reason.text}`}>
                          {reason.points} · {reason.text}
                        </Typography.Text>
                      ))}
                    </Space>
                  )}

                  <Space style={{ marginTop: 16 }}>
                    {claimResult ? (
                      <Tag color={claimResult === "returned" ? "green" : "default"}>
                        {resultLabels[language][claimResult]}
                      </Tag>
                    ) : (
                      <>
                        <Button
                          type="primary"
                          loading={claiming === match.found_item_id}
                          onClick={() => void handleClaim(match, "returned")}
                        >
                          {t("已找回")}
                        </Button>
                        <Button
                          loading={claiming === match.found_item_id}
                          onClick={() => void handleClaim(match, "not_found")}
                        >
                          {t("没找到")}
                        </Button>
                      </>
                    )}
                  </Space>
                </Card>
              );
            })}
          </Space>
        )}

        {isLost && (
          <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
            {t("匹配分数仅用于排序，不作为领回判定。")}
          </Typography.Paragraph>
        )}
      </section>
    </ConfigProvider>
  );
}
