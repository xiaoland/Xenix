import "./styles.css";
import { apiUrl } from "./lib/config";

type DownloadResponse =
  | { ok: true; downloadUrl: string; message: string }
  | { ok: false; message: string; code?: string };

const screenshots = [
  {
    src: "/images/xenix/PixPin_2026-06-11_21-36-46.png",
    alt: "Xenix 软件截图 1",
  },
  {
    src: "/images/xenix/PixPin_2026-06-11_21-37-43.png",
    alt: "Xenix 软件截图 2",
  },
  {
    src: "/images/xenix/PixPin_2026-06-11_21-38-12.png",
    alt: "Xenix 软件截图 3",
  },
];

const features = [
  {
    icon: "message",
    title: "自然语言提问",
    description: "直接用日常语言描述分析需求，不需要编写 SQL 或公式。",
  },
  {
    icon: "chart",
    title: "自动生成分析结果",
    description: "从数据中提取关键信息，并辅助生成更容易理解的图表与结论。",
  },
  {
    icon: "team",
    title: "面向非技术人员",
    description: "降低数据分析门槛，让业务、运营和管理场景也能快速使用 AI 分析数据。",
  },
];

const app = document.querySelector<HTMLDivElement>("#app");
if (!app) {
  throw new Error("Missing #app root");
}

app.innerHTML = `
  <article class="xenix-page">
    <header class="hero">
      <div class="hero-copy">
        <p class="eyebrow">Xenix Native</p>
        <h1>Xenix</h1>
        <p class="hero-lead">面向非技术人员的 AI 数据分析软件。</p>
      </div>
    </header>

    <section class="screenshot-panel" aria-label="Xenix 软件截图">
      <div class="carousel-frame">
        <div class="carousel-track">
          ${screenshots
            .map(
              (screenshot, index) => `
                <figure class="carousel-slide" aria-label="Xenix 软件截图 ${index + 1} / ${screenshots.length}">
                  <img
                    src="${screenshot.src}"
                    alt="${screenshot.alt}"
                    loading="${index === 0 ? "eager" : "lazy"}"
                    decoding="async"
                  />
                </figure>
              `,
            )
            .join("")}
        </div>
        <button class="carousel-control previous" type="button" aria-label="查看上一张截图">
          <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M15.5 5 8.5 12l7 7" /></svg>
        </button>
        <button class="carousel-control next" type="button" aria-label="查看下一张截图">
          <svg aria-hidden="true" viewBox="0 0 24 24"><path d="m8.5 5 7 7-7 7" /></svg>
        </button>
      </div>
      <div class="carousel-dots" aria-label="截图导航">
        ${screenshots
          .map(
            (_, index) => `
              <button class="carousel-dot" type="button" aria-label="查看第 ${index + 1} 张 Xenix 截图"></button>
            `,
          )
          .join("")}
      </div>
    </section>

    <section class="features" aria-labelledby="features-title">
      <div class="section-header">
        <p class="eyebrow">Features</p>
        <h2 id="features-title">为快速理解数据而设计</h2>
      </div>
      <ul class="feature-list">
        ${features
          .map(
            (feature) => `
              <li class="feature-item">
                <span class="feature-icon ${feature.icon}" aria-hidden="true"></span>
                <div>
                  <h3>${feature.title}</h3>
                  <p>${feature.description}</p>
                </div>
              </li>
            `,
          )
          .join("")}
      </ul>
    </section>

    <section class="download" aria-labelledby="download-title">
      <div class="download-copy">
        <h2 id="download-title">获取软件</h2>
        <p>目前仅支持 Windows。下载后解压并双击 xenix.exe 即可运行；初次启动较慢，请耐心等待。</p>
        <p>填写手机号或邮箱即可开始下载。</p>
      </div>

      <form class="download-form" novalidate>
        <label for="xenix-contact">邮箱或手机号</label>
        <div class="form-row">
          <input
            id="xenix-contact"
            name="contact"
            type="text"
            inputmode="email"
            autocomplete="email"
            placeholder="you@example.com / 13800000000"
            required
          />
          <button type="submit">获取</button>
        </div>
        <p class="form-status" aria-live="polite"></p>
      </form>
    </section>
  </article>
`;

const track = app.querySelector<HTMLDivElement>(".carousel-track");
const dots = Array.from(app.querySelectorAll<HTMLButtonElement>(".carousel-dot"));
const previousButton = app.querySelector<HTMLButtonElement>(".carousel-control.previous");
const nextButton = app.querySelector<HTMLButtonElement>(".carousel-control.next");
let activeScreenshot = 0;

function setActiveScreenshot(index: number): void {
  activeScreenshot = (index + screenshots.length) % screenshots.length;
  if (track) {
    track.style.transform = `translateX(-${activeScreenshot * 100}%)`;
  }
  dots.forEach((dot, dotIndex) => {
    dot.setAttribute("aria-current", String(dotIndex === activeScreenshot));
  });
}

previousButton?.addEventListener("click", () => {
  setActiveScreenshot(activeScreenshot - 1);
});

nextButton?.addEventListener("click", () => {
  setActiveScreenshot(activeScreenshot + 1);
});

dots.forEach((dot, index) => {
  dot.addEventListener("click", () => {
    setActiveScreenshot(index);
  });
});

setActiveScreenshot(0);

const form = app.querySelector<HTMLFormElement>(".download-form");
const contactInput = app.querySelector<HTMLInputElement>("#xenix-contact");
const status = app.querySelector<HTMLParagraphElement>(".form-status");

function showStatus(message: string, kind: "idle" | "success" | "error"): void {
  if (!status) {
    return;
  }
  status.textContent = message;
  status.dataset.kind = kind;
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const contact = contactInput?.value.trim() ?? "";
  if (!contact) {
    showStatus("请先填写邮箱或手机号。", "error");
    contactInput?.focus();
    return;
  }

  const submitButton = form.querySelector<HTMLButtonElement>('button[type="submit"]');
  submitButton?.setAttribute("disabled", "true");
  showStatus("正在准备下载...", "idle");

  try {
    const response = await fetch(apiUrl("/api/xenix/download"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contact }),
    });
    const payload = (await response.json()) as DownloadResponse;

    if (!response.ok || !payload.ok) {
      showStatus(payload.message || "暂时无法准备下载链接，请稍后再试。", "error");
      return;
    }

    showStatus(payload.message, "success");
    window.location.assign(payload.downloadUrl);
  } catch {
    showStatus("网络请求失败，请稍后再试。", "error");
  } finally {
    submitButton?.removeAttribute("disabled");
  }
});
