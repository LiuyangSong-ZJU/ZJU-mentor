export const METRIC_FIELDS = [
  { key: "ethics", label: "师德品行", shortLabel: "师德", column: "score_ethics" },
  { key: "academic", label: "学术能力", shortLabel: "学术", column: "score_academic" },
  { key: "wlb", label: "WLB", shortLabel: "WLB", column: "score_wlb" },
  { key: "funding", label: "经费与津贴", shortLabel: "经费", column: "score_funding" },
  { key: "outcome", label: "出路与毕业难度", shortLabel: "出路", column: "score_outcome" },
] as const;

export async function d1All<T>(
  db: D1Database,
  sql: string,
  binds: unknown[] = [],
): Promise<T[]> {
  const result = await db.prepare(sql).bind(...binds).all<T>();
  return result.results || [];
}

export async function d1First<T>(
  db: D1Database,
  sql: string,
  binds: unknown[] = [],
): Promise<T | null> {
  const row = await db.prepare(sql).bind(...binds).first<T>();
  return row ?? null;
}

export async function d1Run(
  db: D1Database,
  sql: string,
  binds: unknown[] = [],
): Promise<D1Result<unknown>> {
  return db.prepare(sql).bind(...binds).run();
}
