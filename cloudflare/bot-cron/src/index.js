const TARGETS = [
  { repo: "sabar2023/robot-otomatis", workflow: "cron-vst.yml" },
];

const SUPABASE_URL = "https://jklbczruvbxscpwxxfud.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_Jj5TIfWxCu2vbsaj9Uoneg_EZjYrkta";

async function dispatch(env, { repo, workflow, inputs }) {
  const body = { ref: "main" };
  if (inputs) body.inputs = inputs;
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
      body: JSON.stringify(body),
    }
  );
  const respBody = resp.ok ? "" : (await resp.text()).slice(0, 200);
  return { repo, workflow, status: resp.status, ok: resp.ok, body: respBody };
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

function corsHeaders(request) {
  const origin = request.headers.get("Origin") || "*";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

export default {
  async scheduled(event, env, ctx) {
    const results = await runAll(env);
    console.log(JSON.stringify(results));
  },
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders(request);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    if (url.pathname === "/run" && url.searchParams.get("key") === env.TRIGGER_KEY) {
      const results = await runAll(env);
      return Response.json({ results }, { headers: cors });
    }
    if (url.pathname === "/simulate") {
      const auth = request.headers.get("Authorization") || "";
      const token = auth.replace(/^Bearer\s+/i, "");
      if (!token) return Response.json({ error: "missing token" }, { status: 401, headers: cors });
      const check = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
        headers: { apikey: SUPABASE_ANON_KEY, Authorization: `Bearer ${token}` },
      });
      if (!check.ok) return Response.json({ error: "unauthorized" }, { status: 401, headers: cors });
      const profile = await check.json();
      const email = profile.email;
      if (!email) return Response.json({ error: "no email" }, { status: 400, headers: cors });
      const result = await dispatch(env, {
        repo: TARGETS[0].repo,
        workflow: TARGETS[0].workflow,
        inputs: { simulate_user: email },
      });
      return Response.json({ result }, { headers: cors });
    }
    return new Response("ok", { status: 200, headers: cors });
  },
};