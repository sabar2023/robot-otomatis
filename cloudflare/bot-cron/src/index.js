const TARGETS = [
  { repo: "sabar2023/robot-trading", workflow: "cron.yml" },
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

async function runAll(env) {
  return Promise.all(TARGETS.map((t) => dispatch(env, t)));
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