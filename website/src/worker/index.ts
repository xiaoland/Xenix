import { Hono } from "hono";
import { cors } from "hono/cors";

type Env = {
  DB: D1Database;
  XENIX_DOWNLOAD_URL?: string;
};

type DownloadContact =
  | { contact: string; contactType: "email" }
  | { contact: string; contactType: "phone" };

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const CHINA_MAINLAND_PHONE_PATTERN = /^1[3-9]\d{9}$/;

const app = new Hono<{ Bindings: Env }>().basePath("/api");

function parseContact(value: string): DownloadContact | null {
  const contact = value.trim();

  if (EMAIL_PATTERN.test(contact)) {
    return { contact: contact.toLowerCase(), contactType: "email" };
  }

  if (CHINA_MAINLAND_PHONE_PATTERN.test(contact)) {
    return { contact, contactType: "phone" };
  }

  return null;
}

function configuredDownloadUrl(env: Env): string | null {
  const value = env.XENIX_DOWNLOAD_URL?.trim();
  return value ? value : null;
}

function corsOrigin(origin: string): string {
  if (!origin) {
    return "*";
  }

  try {
    const url = new URL(origin);
    if (url.hostname === "localhost" || url.hostname === "127.0.0.1") {
      return origin;
    }
    if (url.hostname.endsWith(".pages.dev") || url.hostname.endsWith(".workers.dev")) {
      return origin;
    }
    return origin;
  } catch {
    return "*";
  }
}

async function readContact(request: Request): Promise<string | null> {
  const contentType = request.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const body = (await request.json().catch(() => null)) as { contact?: unknown } | null;
    return typeof body?.contact === "string" ? body.contact : null;
  }

  const form = await request.formData().catch(() => null);
  const contact = form?.get("contact");
  return typeof contact === "string" ? contact : null;
}

app.use(
  "*",
  cors({
    origin: corsOrigin,
    allowMethods: ["GET", "POST", "OPTIONS"],
    allowHeaders: ["Content-Type"],
  }),
);

app.get("/health", (c) => {
  const configured = configuredDownloadUrl(c.env) !== null;
  return c.json({
    ok: configured,
    service: "xenix-website-api",
    required: {
      XENIX_DOWNLOAD_URL: configured,
    },
  }, configured ? 200 : 500);
});

app.post("/xenix/download", async (c) => {
  const downloadUrl = configuredDownloadUrl(c.env);
  if (!downloadUrl) {
    return c.json(
      {
        ok: false,
        code: "missing_download_url",
        message: "XENIX_DOWNLOAD_URL 未配置，暂时无法准备下载链接。",
      },
      500,
    );
  }

  const contactValue = await readContact(c.req.raw);
  if (!contactValue || contactValue.trim().length === 0) {
    return c.json(
      { ok: false, code: "missing_contact", message: "请先填写邮箱或手机号。" },
      400,
    );
  }

  const parsedContact = parseContact(contactValue);
  if (!parsedContact) {
    return c.json(
      {
        ok: false,
        code: "invalid_contact",
        message: "请填写有效的邮箱或中国大陆手机号。",
      },
      400,
    );
  }

  try {
    await c.env.DB.prepare(
      `INSERT OR IGNORE INTO xenix_download_contacts
        (id, contact, contact_type, created_at, user_agent, cf_country)
       VALUES (?, ?, ?, ?, ?, ?)`,
    )
      .bind(
        crypto.randomUUID(),
        parsedContact.contact,
        parsedContact.contactType,
        new Date().toISOString(),
        c.req.header("user-agent") ?? null,
        c.req.raw.cf?.country ?? null,
      )
      .run();
  } catch (error) {
    console.warn("Failed to save Xenix download contact", error);
    return c.json(
      {
        ok: false,
        code: "download_contact_persist_failed",
        message: "暂时无法准备下载链接，请稍后再试。",
      },
      500,
    );
  }

  return c.json({
    ok: true,
    downloadUrl,
    message: "已获取下载地址，下载将自动开始。",
  });
});

export default app;
