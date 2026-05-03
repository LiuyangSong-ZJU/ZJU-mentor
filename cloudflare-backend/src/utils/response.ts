import type { AppErrorLike } from "../types";

export class AppError extends Error implements AppErrorLike {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "AppError";
    this.status = status;
  }
}

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-Admin-Token, Authorization",
};

export function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders,
    },
  });
}

export function empty(status = 204): Response {
  return new Response(null, {
    status,
    headers: corsHeaders,
  });
}

export function handleOptions(): Response {
  return json({ ok: true }, 200);
}

export async function readJson<T>(request: Request): Promise<T> {
  const text = await request.text();
  if (!text) {
    return {} as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch (error) {
    throw new AppError(400, `请求体不是合法 JSON: ${String(error)}`);
  }
}

export function errorResponse(error: unknown): Response {
  if (error instanceof AppError) {
    return json({ message: error.message }, error.status);
  }

  const appError = error as AppErrorLike;
  if (typeof appError?.status === "number" && appError.message) {
    return json({ message: appError.message }, appError.status);
  }

  return json({ message: `服务器内部错误: ${String(error)}` }, 500);
}
