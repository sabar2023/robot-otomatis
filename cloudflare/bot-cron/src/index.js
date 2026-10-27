const TARGETS = [
  { repo: "sabar2023/robot-otomatis", workflow: "cron-vst.yml" },
];

async function dispatch(env, { repo, workflow }) {
  const resp = await fetch(
    `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_PAT}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "bot-cron-worker",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );
  const body = resp.ok ? "" : (await resp.text()).slice(0, 200);
  return { repo, workflow, status: resp.status, ok: resp.ok, body };
}

async function notify(env, text) {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) return;
  try {
    await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: env.TELEGRAM_CHAT_ID,
        text,
        parse_mode: "HTML",
        disable_web_page_preview: true,
      }),
    });
  } catch (err) {
    console.log("notify failed:", String(err));
  }
}

async function runAll(env) {
  const results = await Promise.all(TARGETS.map((t) => dispatch(env, t)));
  const failed = results.filter((r) => !r.ok);
  if (failed.length) {
    const detail = failed
      .map((r) => `${r.repo}/${r.workflow}: HTTP ${r.status} ${r.body}`)
      .join("\n");
    await notify(env, `&#10060; <b>bot-cron: dispatch GitHub gagal</b>\n<code>${detail}</code>\nPeriksa secret <code>GITHUB_PAT</code> di Worker.`);
  }
  return results;
}

export default {
  async scheduled(event, env, ctx) {
    const results = await runAll(env);
    console.log(JSON.stringify(results));
  },
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/run" && url.searchParams.get("key") === env.TRIGGER_KEY) {
      const results = await runAll(env);
      return Response.json({ results });
    }
    return new Response("ok", { status: 200 });
  },
};