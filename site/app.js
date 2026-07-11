(function () {
  "use strict";

  const data = window.GITHUB_HOTSPOTS_DATA;
  const numberFormat = new Intl.NumberFormat("zh-CN", {
    notation: "compact",
    maximumFractionDigits: 1,
  });
  const exactNumberFormat = new Intl.NumberFormat("zh-CN");

  function select(selector, scope = document) {
    return scope.querySelector(selector);
  }

  function selectAll(selector, scope = document) {
    return Array.from(scope.querySelectorAll(selector));
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function setText(selector, value) {
    const node = select(selector);
    if (node) node.textContent = value;
  }

  function formatNumber(value) {
    return numberFormat.format(Number(value) || 0);
  }

  function formatExact(value) {
    return exactNumberFormat.format(Number(value) || 0);
  }

  function formatDelta(value) {
    const numeric = Number(value) || 0;
    return `${numeric >= 0 ? "+" : ""}${formatExact(numeric)}`;
  }

  function formatDate(value) {
    if (!value) return "日期未标注";
    const date = new Date(`${value}T00:00:00+08:00`);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("zh-CN", {
      year: "numeric",
      month: "long",
      day: "numeric",
      weekday: "short",
      timeZone: "Asia/Shanghai",
    }).format(date);
  }

  function formatTimestamp(value) {
    if (!value) return "时间未标注";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "Asia/Shanghai",
    }).format(date);
  }

  function repositoriesOf(value) {
    return Array.isArray(value) ? value : [];
  }

  function reportBoard(report, boardName) {
    const configured =
      report && report.boards && typeof report.boards[boardName] === "object"
        ? report.boards[boardName]
        : null;
    if (configured) {
      return {
        label:
          typeof configured.label === "string" && configured.label
            ? configured.label
            : boardName === "ai"
              ? "AI 专题榜"
              : "综合主榜",
        repositories: repositoriesOf(configured.repositories),
      };
    }
    return {
      label: boardName === "ai" ? "AI 专题榜" : "综合主榜",
      repositories:
        boardName === "comprehensive" ? repositoriesOf(report && report.repositories) : [],
    };
  }

  function formatBoardCount(comprehensiveCount, aiCount) {
    return `${String(comprehensiveCount).padStart(2, "0")} / ${String(aiCount).padStart(2, "0")}`;
  }

  function safeRepositoryUrl(value) {
    if (typeof value !== "string") return "";
    try {
      const url = new URL(value);
      return url.protocol === "https:" && url.hostname === "github.com" ? url.href.replace(/\/$/, "") : "";
    } catch (_error) {
      return "";
    }
  }

  function safePosterPath(value) {
    if (typeof value !== "string") return "";
    const path = value.trim();
    if (!path.startsWith("generated/") || path.includes("..") || path.includes("\\")) {
      return "";
    }
    return path.endsWith(".png") ? path : "";
  }

  function posterAction(repository, { preview = false } = {}) {
    const path = safePosterPath(repository.poster_path);
    if (!path) return null;
    const link = element("a", preview ? "poster-preview" : "poster-download");
    link.href = path;
    link.download = "";
    link.setAttribute("aria-label", `下载 ${repository.full_name} 的小红书配图`);
    if (preview) {
      const thumbnail = element("img", "poster-thumbnail");
      thumbnail.src = path;
      thumbnail.alt = `${repository.full_name} 的 3:4 项目配图预览`;
      thumbnail.loading = "lazy";
      const copy = element("span", "poster-preview-copy");
      copy.append(
        element("strong", "", "XHS POSTER / 3:4"),
        element("small", "", "查看或下载 1200×1600 PNG ↗")
      );
      link.append(thumbnail, copy);
    } else {
      link.textContent = "配图 PNG ↓";
    }
    return link;
  }

  function inferRepositoryUrl() {
    if (!window.location.hostname.endsWith(".github.io")) return "";
    const owner = window.location.hostname.split(".")[0];
    const project = window.location.pathname.split("/").filter(Boolean)[0] || `${owner}.github.io`;
    return `https://github.com/${owner}/${project}`;
  }

  function configureProjectLinks() {
    const repositoryUrl =
      safeRepositoryUrl(data.site && data.site.repository_url) || inferRepositoryUrl();
    if (!repositoryUrl) return;
    selectAll("[data-project-link]").forEach((link) => {
      link.href = repositoryUrl;
      link.target = "_blank";
      link.rel = "noreferrer";
    });
    const readme = select("#readme-link");
    const actions = select("#actions-link");
    readme.href = `${repositoryUrl}#readme`;
    actions.href = `${repositoryUrl}/actions`;
    [readme, actions].forEach((link) => {
      link.target = "_blank";
      link.rel = "noreferrer";
    });
    [
      ["#daily-source-link", data.daily && data.daily.source_path],
      ["#weekly-source-link", data.weekly && data.weekly.source_path],
      ["#ai-daily-source-link", data.daily && data.daily.source_path],
      ["#ai-weekly-source-link", data.weekly && data.weekly.source_path],
    ].forEach(([selector, path]) => {
      const link = select(selector);
      if (link && path) {
        link.href = `${repositoryUrl}/blob/main/${path}`;
        link.target = "_blank";
        link.rel = "noreferrer";
      }
    });
  }

  function repositoryLink(repository, className) {
    const link = element("a", className, repository.full_name);
    const safeUrl = safeRepositoryUrl(repository.html_url);
    if (safeUrl) {
      link.href = safeUrl;
      link.target = "_blank";
      link.rel = "noreferrer";
    }
    return link;
  }

  function stat(label, value, emphasized = false) {
    const item = element("span", "repo-stat");
    const strong = element("strong", emphasized ? "signal-value" : "", value);
    item.append(strong, document.createTextNode(` ${label}`));
    return item;
  }

  function emptyBoard(message) {
    const empty = element("div", "board-empty");
    empty.append(
      element("strong", "", "NO SIGNAL / 暂无数据"),
      element("p", "", message)
    );
    return empty;
  }

  function renderDaily(repositories) {
    const list = select("#daily-list");
    list.replaceChildren();
    if (!repositories.length) {
      list.append(emptyBoard("当前报告没有可展示的综合主榜项目。"));
      return;
    }
    repositories.forEach((repository, index) => {
      const card = element("article", `daily-card rank-${repository.rank} reveal`);
      card.style.setProperty("--delay", `${index * 80}ms`);

      const top = element("div", "daily-card-top");
      const rank = element("span", "rank-number", String(repository.rank).padStart(2, "0"));
      const source = element("span", "source-badge", repository.delta_label);
      top.append(rank, source);

      const title = element("h3");
      title.append(repositoryLink(repository, "repository-name"));
      const description = element("p", "repository-description", repository.one_line);

      const tags = element("div", "repo-tags");
      tags.append(element("span", "language-tag", repository.language));
      repository.topics.slice(0, 3).forEach((topic) => {
        tags.append(element("span", "topic-tag", `#${topic}`));
      });

      const stats = element("div", "repo-stats");
      stats.append(
        stat("本期 Star", formatDelta(repository.star_delta), true),
        stat("累计", formatNumber(repository.stars)),
        stat("评分", repository.score.toFixed(1))
      );

      const meter = element("div", "score-meter");
      meter.setAttribute("aria-label", `综合评分 ${repository.score.toFixed(1)}`);
      const meterFill = element("span");
      meterFill.style.setProperty("--score", `${Math.max(0, Math.min(100, repository.score))}%`);
      meter.append(meterFill);

      const footer = element("div", "card-footer");
      footer.append(element("span", "audience", `适合 / ${repository.audience}`));
      const arrow = repositoryLink(repository, "card-arrow");
      arrow.textContent = "OPEN ↗";
      arrow.setAttribute("aria-label", `打开 ${repository.full_name}`);
      footer.append(arrow);

      card.append(top, title, description, tags, stats, meter, footer);
      const poster = posterAction(repository, { preview: true });
      if (poster) card.append(poster);
      list.append(card);
    });
  }

  function renderWeekly(repositories) {
    const list = select("#weekly-list");
    list.replaceChildren();
    if (!repositories.length) {
      list.append(emptyBoard("当前报告没有可展示的综合周榜项目。"));
      return;
    }
    repositories.forEach((repository, index) => {
      const row = element("article", "weekly-row reveal");
      row.style.setProperty("--delay", `${index * 55}ms`);

      const rank = element("div", "weekly-rank", String(repository.rank).padStart(2, "0"));
      const main = element("div", "weekly-main");
      const title = element("h3");
      title.append(repositoryLink(repository, "weekly-name"));
      main.append(title, element("p", "weekly-description", repository.one_line));
      const poster = posterAction(repository);
      if (poster) main.append(poster);

      const meta = element("div", "weekly-signal");
      meta.append(
        element("strong", "weekly-delta", formatDelta(repository.star_delta)),
        element("span", "", `${repository.delta_label} · ${repository.language}`),
        element("span", "", `${formatNumber(repository.stars)} 累计 Star`)
      );

      const score = element("div", "weekly-score");
      score.append(
        element("strong", "", repository.score.toFixed(1)),
        element("span", "", "/ 100")
      );
      row.append(rank, main, meta, score);
      list.append(row);
    });
  }

  function renderAiBoard(repositories, selector, period) {
    const list = select(selector);
    list.replaceChildren();
    if (!repositories.length) {
      list.append(
        emptyBoard("本期暂无可展示的 AI 专题项目；综合主榜仍可正常浏览。")
      );
      return;
    }
    repositories.forEach((repository, index) => {
      const entry = element("article", `ai-entry ai-entry-${period} reveal`);
      entry.style.setProperty("--delay", `${index * 55}ms`);

      const rank = element(
        "span",
        "ai-entry-rank",
        String(repository.rank).padStart(2, "0")
      );
      rank.setAttribute("aria-label", `第 ${repository.rank} 名`);

      const main = element("div", "ai-entry-main");
      main.append(
        element("p", "ai-entry-kicker", `${repository.language} / ${repository.delta_label}`)
      );
      const title = element("h4");
      title.append(repositoryLink(repository, "ai-entry-name"));
      main.append(title, element("p", "ai-entry-description", repository.one_line));
      const poster = posterAction(repository);
      if (poster) main.append(poster);

      const signal = element("div", "ai-entry-signal");
      signal.setAttribute("aria-label", `综合评分 ${repository.score.toFixed(1)}`);
      signal.append(
        element("strong", "", repository.score.toFixed(1)),
        element("span", "ai-entry-delta", `${formatDelta(repository.star_delta)} STAR`),
        element("span", "", `${formatNumber(repository.stars)} TOTAL`)
      );
      entry.append(rank, main, signal);
      list.append(entry);
    });
  }

  function renderMethodology(methodology) {
    setText("#method-summary", methodology.summary || "本期暂无方法说明。");
    setText("#method-quality", methodology.quality || "数据质量未标注");

    const warnings = select("#method-warnings");
    warnings.replaceChildren();
    (methodology.warnings || []).forEach((warning) => {
      warnings.append(element("li", "", warning));
    });
    if (!warnings.children.length) {
      warnings.append(element("li", "", "本期没有额外数据警告。"));
    }

    const metrics = select("#metrics-list");
    metrics.replaceChildren();
    (methodology.metrics || []).forEach((metric, index) => {
      const card = element("article", "metric-card reveal");
      card.style.setProperty("--delay", `${index * 45}ms`);
      const head = element("div", "metric-head");
      head.append(
        element("span", "metric-code", metric.code),
        element("strong", "metric-weight", metric.weight)
      );
      card.append(
        head,
        element("h3", "", metric.name),
        element("p", "", metric.detail)
      );
      metrics.append(card);
    });
  }

  function renderPipeline(pipeline) {
    const list = select("#pipeline-list");
    list.replaceChildren();
    (pipeline || []).forEach((item, index) => {
      const node = element("li", "pipeline-step reveal");
      node.style.setProperty("--delay", `${index * 65}ms`);
      node.append(
        element("span", "pipeline-number", item.step),
        element("h3", "", item.name),
        element("p", "", item.detail)
      );
      list.append(node);
    });
  }

  function render() {
    if (!data || !data.daily || !data.weekly) {
      document.body.classList.add("data-error");
      setText("#data-status", "■ DATA FEED UNAVAILABLE");
      setText("#quality-label", "构建数据缺失");
      return;
    }

    const dailyComprehensive = reportBoard(data.daily, "comprehensive");
    const weeklyComprehensive = reportBoard(data.weekly, "comprehensive");
    const dailyAi = reportBoard(data.daily, "ai");
    const weeklyAi = reportBoard(data.weekly, "ai");

    document.title = `${data.site.title} / ${data.daily.run_date}`;
    setText("#issue-date", `ISSUE / ${data.daily.run_date}`);
    setText(
      "#daily-count",
      formatBoardCount(dailyComprehensive.repositories.length, dailyAi.repositories.length)
    );
    setText(
      "#weekly-count",
      formatBoardCount(weeklyComprehensive.repositories.length, weeklyAi.repositories.length)
    );
    setText("#generated-at", formatTimestamp(data.generated_at));
    setText("#quality-label", data.methodology.quality);
    setText("#data-status", "■ DATA FEED READY");
    setText("#daily-board-label", dailyComprehensive.label);
    setText("#weekly-board-label", weeklyComprehensive.label);
    setText("#ai-board-label", dailyAi.label || weeklyAi.label);
    setText("#daily-window", `${formatDate(data.daily.run_date)} · 日榜`);
    setText("#weekly-window", `${data.weekly.window_label} · 周榜`);
    setText("#ai-daily-count", `TOP ${String(dailyAi.repositories.length).padStart(2, "0")}`);
    setText("#ai-weekly-count", `TOP ${String(weeklyAi.repositories.length).padStart(2, "0")}`);
    setText("#ai-daily-window", formatDate(data.daily.run_date));
    setText("#ai-weekly-window", data.weekly.window_label);

    renderDaily(dailyComprehensive.repositories);
    renderWeekly(weeklyComprehensive.repositories);
    renderAiBoard(dailyAi.repositories, "#ai-daily-list", "daily");
    renderAiBoard(weeklyAi.repositories, "#ai-weekly-list", "weekly");
    renderMethodology(data.methodology);
    renderPipeline(data.pipeline);
    configureProjectLinks();
    document.body.classList.add("data-ready");
  }

  render();
})();
