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

function md5(string) {
  function rotateLeft(lValue, iShiftBits) {
    return (lValue << iShiftBits) | (lValue >>> (32 - iShiftBits));
  }
  function addUnsigned(lX, lY) {
    const lX8 = lX & 0x80000000;
    const lY8 = lY & 0x80000000;
    const lX4 = lX & 0x40000000;
    const lY4 = lY & 0x40000000;
    const lResult = (lX & 0x3fffffff) + (lY & 0x3fffffff);
    if (lX4 & lY4) return lResult ^ 0x80000000 ^ lX8 ^ lY8;
    if (lX4 | lY4) {
      if (lResult & 0x40000000) return lResult ^ 0xc0000000 ^ lX8 ^ lY8;
      return lResult ^ 0x40000000 ^ lX8 ^ lY8;
    }
    return lResult ^ lX8 ^ lY8;
  }
  function FF(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned((b & c) | (~b & d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  }
  function GG(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned((b & d) | (c & ~d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  }
  function HH(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(b ^ c ^ d, x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  }
  function II(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(c ^ (b | ~d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  }
  function convertToWordArray(str) {
    const len = str.length;
    const wordCount = (((len + 8) >> 6) + 1) << 4;
    const arr = new Array(wordCount).fill(0);
    for (let i = 0; i < len; i++) arr[i >> 2] |= str.charCodeAt(i) << ((i % 4) * 8);
    arr[len >> 2] |= 0x80 << ((len % 4) * 8);
    arr[wordCount - 2] = len << 3;
    arr[wordCount - 1] = len >>> 29;
    return arr;
  }
  function wordToHex(lValue) {
    let out = "";
    for (let count = 0; count <= 3; count++) {
      const byte = (lValue >>> (count * 8)) & 255;
      out += ("0" + byte.toString(16)).slice(-2);
    }
    return out;
  }
  const x = convertToWordArray(string);
  let a = 0x67452301;
  let b = 0xefcdab89;
  let c = 0x98badcfe;
  let d = 0x10325476;
  for (let k = 0; k < x.length; k += 16) {
    const aa = a, bb = b, cc = c, dd = d;
    a = FF(a, b, c, d, x[k + 0], 7, 0xd76aa478);
    d = FF(d, a, b, c, x[k + 1], 12, 0xe8c7b756);
    c = FF(c, d, a, b, x[k + 2], 17, 0x242070db);
    b = FF(b, c, d, a, x[k + 3], 22, 0xc1bdceee);
    a = FF(a, b, c, d, x[k + 4], 7, 0xf57c0faf);
    d = FF(d, a, b, c, x[k + 5], 12, 0x4787c62a);
    c = FF(c, d, a, b, x[k + 6], 17, 0xa8304613);
    b = FF(b, c, d, a, x[k + 7], 22, 0xfd469501);
    a = FF(a, b, c, d, x[k + 8], 7, 0x698098d8);
    d = FF(d, a, b, c, x[k + 9], 12, 0x8b44f7af);
    c = FF(c, d, a, b, x[k + 10], 17, 0xffff5bb1);
    b = FF(b, c, d, a, x[k + 11], 22, 0x895cd7be);
    a = FF(a, b, c, d, x[k + 12], 7, 0x6b901122);
    d = FF(d, a, b, c, x[k + 13], 12, 0xfd987193);
    c = FF(c, d, a, b, x[k + 14], 17, 0xa679438e);
    b = FF(b, c, d, a, x[k + 15], 22, 0x49b40821);
    a = GG(a, b, c, d, x[k + 1], 5, 0xf61e2562);
    d = GG(d, a, b, c, x[k + 6], 9, 0xc040b340);
    c = GG(c, d, a, b, x[k + 11], 14, 0x265e5a51);
    b = GG(b, c, d, a, x[k + 0], 20, 0xe9b6c7aa);
    a = GG(a, b, c, d, x[k + 5], 5, 0xd62f105d);
    d = GG(d, a, b, c, x[k + 10], 9, 0x2441453);
    c = GG(c, d, a, b, x[k + 15], 14, 0xd8a1e681);
    b = GG(b, c, d, a, x[k + 4], 20, 0xe7d3fbc8);
    a = GG(a, b, c, d, x[k + 9], 5, 0x21e1cde6);
    d = GG(d, a, b, c, x[k + 14], 9, 0xc33707d6);
    c = GG(c, d, a, b, x[k + 3], 14, 0xf4d50d87);
    b = GG(b, c, d, a, x[k + 8], 20, 0x455a14ed);
    a = GG(a, b, c, d, x[k + 13], 5, 0xa9e3e905);
    d = GG(d, a, b, c, x[k + 2], 9, 0xfcefa3f8);
    c = GG(c, d, a, b, x[k + 7], 14, 0x676f02d9);
    b = GG(b, c, d, a, x[k + 12], 20, 0x8d2a4c8a);
    a = HH(a, b, c, d, x[k + 5], 4, 0xfffa3942);
    d = HH(d, a, b, c, x[k + 8], 11, 0x8771f681);
    c = HH(c, d, a, b, x[k + 11], 16, 0x6d9d6122);
    b = HH(b, c, d, a, x[k + 14], 23, 0xfde5380c);
    a = HH(a, b, c, d, x[k + 1], 4, 0xa4beea44);
    d = HH(d, a, b, c, x[k + 4], 11, 0x4bdecfa9);
    c = HH(c, d, a, b, x[k + 7], 16, 0xf6bb4b60);
    b = HH(b, c, d, a, x[k + 10], 23, 0xbebfbc70);
    a = HH(a, b, c, d, x[k + 13], 4, 0x289b7ec6);
    d = HH(d, a, b, c, x[k + 0], 11, 0xeaa127fa);
    c = HH(c, d, a, b, x[k + 3], 16, 0xd4ef3085);
    b = HH(b, c, d, a, x[k + 6], 23, 0x4881d05);
    a = HH(a, b, c, d, x[k + 9], 4, 0xd9d4d039);
    d = HH(d, a, b, c, x[k + 12], 11, 0xe6db99e5);
    c = HH(c, d, a, b, x[k + 15], 16, 0x1fa27cf8);
    b = HH(b, c, d, a, x[k + 2], 23, 0xc4ac5665);
    a = II(a, b, c, d, x[k + 0], 6, 0xf4292244);
    d = II(d, a, b, c, x[k + 7], 10, 0x432aff97);
    c = II(c, d, a, b, x[k + 14], 15, 0xab9423a7);
    b = II(b, c, d, a, x[k + 5], 21, 0xfc93a039);
    a = II(a, b, c, d, x[k + 12], 6, 0x655b59c3);
    d = II(d, a, b, c, x[k + 3], 10, 0x8f0ccc92);
    c = II(c, d, a, b, x[k + 10], 15, 0xffeff47d);
    b = II(b, c, d, a, x[k + 1], 21, 0x85845dd1);
    a = II(a, b, c, d, x[k + 8], 6, 0x6fa87e4f);
    d = II(d, a, b, c, x[k + 15], 10, 0xfe2ce6e0);
    c = II(c, d, a, b, x[k + 6], 15, 0xa3014314);
    b = II(b, c, d, a, x[k + 13], 21, 0x4e0811a1);
    a = II(a, b, c, d, x[k + 4], 6, 0xf7537e82);
    d = II(d, a, b, c, x[k + 11], 10, 0xbd3af235);
    c = II(c, d, a, b, x[k + 2], 15, 0x2ad7d2bb);
    b = II(b, c, d, a, x[k + 9], 21, 0xeb86d391);
    a = addUnsigned(a, aa);
    b = addUnsigned(b, bb);
    c = addUnsigned(c, cc);
    d = addUnsigned(d, dd);
  }
  return (wordToHex(a) + wordToHex(b) + wordToHex(c) + wordToHex(d)).toLowerCase();
}

function restHeaders(sk) {
  return {
    apikey: sk,
    Authorization: `Bearer ${sk}`,
    "Content-Type": "application/json",
    Prefer: "return=representation",
  };
}

async function getAuthUser(request) {
  const auth = request.headers.get("Authorization") || "";
  const token = auth.replace(/^Bearer\s+/i, "");
  if (!token) return null;
  const check = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    headers: { apikey: SUPABASE_ANON_KEY, Authorization: `Bearer ${token}` },
  });
  if (!check.ok) return null;
  return check.json();
}

async function requireAdmin(request, env) {
  const user = await getAuthUser(request);
  if (!user) return { ok: false, status: 401, body: { error: "unauthorized" } };
  const sk = env.SUPABASE_SERVICE_KEY;
  if (!sk) return { ok: false, status: 500, body: { error: "service_key_missing" } };
  const resp = await fetch(
    `${SUPABASE_URL}/rest/v1/users_profile?auth_id=eq.${user.id}&select=role`,
    { headers: restHeaders(sk) }
  );
  const rows = await resp.json();
  const prof = Array.isArray(rows) ? rows[0] : rows;
  if (!prof || prof.role !== "admin") {
    return { ok: false, status: 403, body: { error: "forbidden" } };
  }
  return { ok: true, user };
}

async function adminLoginAs(env, request) {
  const auth = await requireAdmin(request, env);
  if (!auth.ok) return { status: auth.status, body: auth.body };
  const sk = env.SUPABASE_SERVICE_KEY;
  let body = {};
  try {
    body = await request.json();
  } catch (e) {
    body = {};
  }
  const email = String(body.email || "").trim();
  if (!email) return { status: 400, body: { error: "email_required" } };
  const resp = await fetch(`${SUPABASE_URL}/auth/v1/admin/generate_link`, {
    method: "POST",
    headers: restHeaders(sk),
    body: JSON.stringify({ type: "magiclink", email }),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok || !data.action_link) {
    return {
      status: 502,
      body: { error: "generate_link_failed", message: String(data.msg || data.message || resp.status).slice(0, 200) },
    };
  }
  return { status: 200, body: { url: data.action_link } };
}

async function adminSetPassword(env, request) {
  const auth = await requireAdmin(request, env);
  if (!auth.ok) return { status: auth.status, body: auth.body };
  const sk = env.SUPABASE_SERVICE_KEY;
  let body = {};
  try {
    body = await request.json();
  } catch (e) {
    body = {};
  }
  const authId = String(body.auth_id || "").trim();
  const password = String(body.password || "");
  if (!authId || !password || password.length < 6) {
    return { status: 400, body: { error: "invalid_input", message: "auth_id dan password (min 6) wajib diisi." } };
  }
  const resp = await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${authId}`, {
    method: "PUT",
    headers: restHeaders(sk),
    body: JSON.stringify({ password }),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    return {
      status: 502,
      body: { error: "update_failed", message: String(data.msg || data.message || resp.status).slice(0, 200) },
    };
  }
  return { status: 200, body: { ok: true } };
}

async function createPayment(env, request) {
  const user = await getAuthUser(request);
  if (!user) return { status: 401, body: { error: "unauthorized" } };
  const uid = user.id;
  const email = user.email;
  const sk = env.SUPABASE_SERVICE_KEY;
  if (!sk) return { status: 500, body: { error: "service_key_missing" } };

  const profResp = await fetch(
    `${SUPABASE_URL}/rest/v1/users_profile?auth_id=eq.${uid}&select=id,plan,nama,no_hp`,
    { headers: restHeaders(sk) }
  );
  const profRows = await profResp.json();
  const prof = Array.isArray(profRows) ? profRows[0] : profRows;
  if (!prof) return { status: 404, body: { error: "profile_not_found" } };
  if ((prof.plan || "free_trial") === "premium") {
    return { status: 409, body: { error: "already_premium", message: "Paket sudah premium." } };
  }

  const merchantCode = env.DUITKU_MERCHANT_CODE;
  const apiKey = env.DUITKU_API_KEY;
  const envMode = (env.DUITKU_ENV || "sandbox").toLowerCase();
  if (!merchantCode || !apiKey) {
    return {
      status: 503,
      body: { error: "payment_gateway_not_configured", message: "Gateway pembayaran belum dikonfigurasi admin." },
    };
  }

  const amount = 500000;
  const merchantOrderId = "BB-" + Date.now() + "-" + prof.id.slice(0, 8);
  const origin = new URL(request.url).origin;
  const signature = md5(`${merchantCode}${merchantOrderId}${amount}${apiKey}`);
  const baseUrl =
    envMode === "production"
      ? "https://passport.duitku.com/webapi/api/merchant/v2/inquiry"
      : "https://sandbox.duitku.com/webapi/api/merchant/v2/inquiry";

  const inquiry = await fetch(baseUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      merchantCode,
      paymentAmount: amount,
      paymentMethod: "VC",
      merchantOrderId,
      productDetails: "Langganan Premium BrandBisnis V5.0 1 bulan",
      email: email || "",
      phoneNumber: prof.no_hp || "",
      customerVaName: prof.nama || email || "",
      callbackUrl: `${origin}/payment/callback`,
      returnUrl: `${origin}/payment/return`,
      signature,
    }),
  });
  const raw = await inquiry.text();
  let data = {};
  try {
    data = JSON.parse(raw);
  } catch (e) {
    data = {};
  }
  if (!inquiry.ok || !data.paymentUrl) {
    return {
      status: 502,
      body: { error: "duitku_error", message: (data.Message || data.message || raw || "").slice(0, 200) },
    };
  }

  await fetch(`${SUPABASE_URL}/rest/v1/payments`, {
    method: "POST",
    headers: restHeaders(sk),
    body: JSON.stringify({
      user_id: prof.id,
      provider: "duitku",
      reference: merchantOrderId,
      amount,
      status: "pending",
    }),
  });

  return {
    status: 200,
    body: { paymentUrl: data.paymentUrl, reference: data.reference || merchantOrderId },
  };
}

async function handlePaymentCallback(env, request) {
  const sk = env.SUPABASE_SERVICE_KEY;
  const apiKey = env.DUITKU_API_KEY;
  if (!sk || !apiKey) return new Response("not configured", { status: 503 });
  let params = {};
  try {
    params = Object.fromEntries(await request.formData());
  } catch (e) {
    try {
      params = await request.json();
    } catch (e2) {
      params = {};
    }
  }
  const amount = String(params.amount || "");
  const merchantOrderId = String(params.merchantOrderId || "");
  const merchantCode = String(params.merchantCode || "");
  const resultCode = String(params.resultCode || "");
  const signature = String(params.signature || "");
  const expected = md5(`${merchantCode}${amount}${merchantOrderId}${apiKey}`);
  if (!signature || signature.toLowerCase() !== expected.toLowerCase()) {
    return new Response("bad signature", { status: 400 });
  }
  if (resultCode !== "00") {
    return new Response("ok", { status: 200 });
  }
  const payResp = await fetch(
    `${SUPABASE_URL}/rest/v1/payments?reference=eq.${merchantOrderId}&select=id,user_id,status`,
    { headers: restHeaders(sk) }
  );
  const payRows = await payResp.json();
  const pay = Array.isArray(payRows) ? payRows[0] : payRows;
  if (!pay) return new Response("not found", { status: 404 });
  if ((pay.status || "") === "paid") return new Response("ok", { status: 200 });
  const now = new Date().toISOString();
  await fetch(`${SUPABASE_URL}/rest/v1/payments?id=eq.${pay.id}`, {
    method: "PATCH",
    headers: restHeaders(sk),
    body: JSON.stringify({ status: "paid", paid_at: now }),
  });
  await fetch(`${SUPABASE_URL}/rest/v1/users_profile?id=eq.${pay.user_id}`, {
    method: "PATCH",
    headers: restHeaders(sk),
    body: JSON.stringify({ plan: "premium" }),
  });
  const expiry = new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString();
  await fetch(`${SUPABASE_URL}/rest/v1/subscriptions`, {
    method: "POST",
    headers: restHeaders(sk),
    body: JSON.stringify({
      user_id: pay.user_id,
      plan: "premium",
      status: "active",
      started_at: now,
      expires_at: expiry,
    }),
  });
  return new Response("ok", { status: 200 });
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
    if (url.pathname === "/pay") {
      const result = await createPayment(env, request);
      return Response.json(result.body, { status: result.status, headers: cors });
    }
    if (url.pathname === "/admin/login-as" && request.method === "POST") {
      const result = await adminLoginAs(env, request);
      return Response.json(result.body, { status: result.status, headers: cors });
    }
    if (url.pathname === "/admin/set-password" && request.method === "POST") {
      const result = await adminSetPassword(env, request);
      return Response.json(result.body, { status: result.status, headers: cors });
    }
    if (url.pathname === "/payment/callback") {
      try {
        return await handlePaymentCallback(env, request);
      } catch (err) {
        return new Response(String(err), { status: 500 });
      }
    }
    if (url.pathname === "/payment/return") {
      return new Response(
        "<html><body style='font-family:sans-serif;padding:40px;text-align:center'><h2>Pembayaran diproses.</h2><p>Status paket akan aktif otomatis setelah pembayaran terverifikasi.</p></body></html>",
        { status: 200, headers: { "Content-Type": "text/html", ...cors } }
      );
    }
    return new Response("ok", { status: 200, headers: cors });
  },
};