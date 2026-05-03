import { pinyin } from "pinyin-pro";

export const UNASSIGNED_UNIT_NAME = "其他单位";

const BIG_UNIT_ORDER = [
  "人文学部",
  "社会科学学部",
  "理学部",
  "工学部",
  "信息学部",
  "农业生命环境学部",
  "医药学部",
  "国际校区",
  "其他单位",
];

const BIG_UNIT_ORDER_INDEX = new Map(BIG_UNIT_ORDER.map((name, index) => [name, index]));

export function normalizeText(value: string): string {
  return (value || "").normalize("NFKC").trim().toLowerCase();
}

export function compactText(value: string): string {
  return normalizeText(value).replace(/\s+/g, "");
}

export function getTeacherInitial(name: string): string {
  const trimmed = (name || "").trim();
  if (!trimmed) {
    return "#";
  }

  const first = trimmed[0];
  if (/^[A-Za-z]$/.test(first)) {
    return first.toUpperCase();
  }

  const initial = pinyin(first, {
    pattern: "first",
    toneType: "none",
    type: "array",
  })[0];

  if (initial && /^[A-Za-z]$/.test(initial)) {
    return initial.toUpperCase();
  }

  return "#";
}

export function teacherPinyin(name: string): { full: string; initials: string } {
  const source = name || "";
  const full = pinyin(source, {
    toneType: "none",
    type: "array",
  }).join("");
  const initials = pinyin(source, {
    pattern: "first",
    toneType: "none",
    type: "array",
  }).join("");

  return {
    full: compactText(full),
    initials: compactText(initials),
  };
}

export function bigUnitSortKey(name: string): [number, string] {
  if (name === UNASSIGNED_UNIT_NAME) {
    return [10000, name];
  }

  const index = BIG_UNIT_ORDER_INDEX.get(name);
  if (typeof index === "number") {
    return [index, name];
  }

  return [9000, name];
}

export function coerceScore(value: unknown): number | null {
  if (value === null || value === undefined || value === "" || value === 0) {
    return null;
  }

  const score = Number(value);
  if (!Number.isFinite(score)) {
    throw new Error("评分必须是数字。");
  }

  if (score < 0 || score > 5) {
    throw new Error("评分必须在 0 到 5 之间。");
  }

  return Math.round(score * 100) / 100;
}
