<?php
declare(strict_types=1);
session_start();

$APP_NAME = 'Duplicator Installer';
$WORKDIR = __DIR__;
$STATE_FILE = $WORKDIR . '/.duplicator-installer-state.json';
$LOG_FILE = $WORKDIR . '/.duplicator-installer.log';
$ARCHIVE_NAME = '';
$EXTRACT_DIR = $WORKDIR . '/.duplicator-extract';

function h(string $s): string {
    return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function log_msg(string $msg): void {
    global $LOG_FILE;
    $line = '[' . date('c') . '] ' . $msg . "\n";
    @file_put_contents($LOG_FILE, $line, FILE_APPEND);
}

function read_state(): array {
    global $STATE_FILE;
    if (!is_file($STATE_FILE)) return [];
    $j = json_decode((string)@file_get_contents($STATE_FILE), true);
    return is_array($j) ? $j : [];
}

function write_state(array $state): void {
    global $STATE_FILE;
    @file_put_contents($STATE_FILE, json_encode($state, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
}

function csrf_token(): string {
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(16));
    }
    return $_SESSION['csrf'];
}

function csrf_check(): void {
    $ok = isset($_POST['csrf']) && hash_equals($_SESSION['csrf'] ?? '', (string)$_POST['csrf']);
    if (!$ok) {
        http_response_code(400);
        echo 'Invalid CSRF token';
        exit;
    }
}

function ensure_auth(): bool {
    $state = read_state();
    $hash = $state['installer_password_hash'] ?? '';
    if ($hash === '') return true; // first run: force set
    return !empty($_SESSION['installer_authed']);
}

function require_auth_or_render(): void {
    $state = read_state();
    $hash = $state['installer_password_hash'] ?? '';
    if ($hash === '') {
        render_set_password();
        exit;
    }
    if (empty($_SESSION['installer_authed'])) {
        render_login();
        exit;
    }
}

function render_header(string $title): void {
    global $APP_NAME;
    echo '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">';
    echo '<title>' . h($APP_NAME . ' - ' . $title) . '</title>';
    echo '<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0b1020;color:#e8ecf6;margin:0;padding:24px}';
    echo '.card{max-width:860px;margin:0 auto;background:#121a2f;border:1px solid #26314d;border-radius:12px;padding:24px}';
    echo 'h1,h2{margin:0 0 12px}p{color:#a9b4cc}label{display:block;margin:10px 0 4px;color:#c8d2e6}';
    echo 'input[type=text],input[type=password],input[type=file]{width:100%;padding:10px;border-radius:8px;border:1px solid #34415f;background:#0b1224;color:#e8ecf6;box-sizing:border-box}';
    echo 'button{background:#2dd4a8;color:#072016;border:0;padding:10px 16px;border-radius:8px;font-weight:700;cursor:pointer}';
    echo 'button:hover{filter:brightness(1.05)}.muted{color:#8ea0bf;font-size:13px}.err{background:#3a1820;color:#ffb4c0;padding:10px;border-radius:8px;margin:10px 0}';
    echo '.ok{background:#14352b;color:#aef0d6;padding:10px;border-radius:8px;margin:10px 0}pre{background:#0b1224;padding:12px;border-radius:8px;overflow:auto;max-height:360px}';
    echo '.steps{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}.step{padding:6px 10px;border-radius:999px;background:#1a2540;color:#93a3bf;font-size:12px}.step.active{background:#2dd4a8;color:#072016;font-weight:700}';
    echo 'table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #26314d;text-align:left;font-size:14px}';
    echo '</style></head><body><div class="card">';
    echo '<h1>' . h($APP_NAME) . '</h1>';
}

function render_footer(): void {
    echo '<p class="muted" style="margin-top:20px">Hapus installer.php dan file state setelah selesai restore.</p>';
    echo '</div></body></html>';
}

function render_steps(int $active): void {
    $steps = ['1. Password', '2. Upload', '3. Extract', '4. Supabase', '5. GitHub Secrets', '6. Deploy Worker', '7. Selesai'];
    echo '<div class="steps">';
    foreach ($steps as $i => $s) {
        $cls = ($i + 1) === $active ? 'step active' : 'step';
        echo '<span class="' . $cls . '">' . h($s) . '</span>';
    }
    echo '</div>';
}

function render_set_password(?string $err = null): void {
    render_header('Set Password');
    render_steps(1);
    echo '<h2>Buat Password Installer</h2><p>Password ini melindungi wizard restore. Simpan dengan aman.</p>';
    if ($err) echo '<div class="err">' . h($err) . '</div>';
    echo '<form method="post"><input type="hidden" name="action" value="set_password">';
    echo '<input type="hidden" name="csrf" value="' . h(csrf_token()) . '">';
    echo '<label>Password baru</label><input type="password" name="password" required minlength="8">';
    echo '<label>Konfirmasi password</label><input type="password" name="password2" required minlength="8">';
    echo '<div style="margin-top:14px"><button type="submit">Simpan & Lanjut</button></div></form>';
    render_footer();
}

function render_login(?string $err = null): void {
    render_header('Login');
    render_steps(1);
    echo '<h2>Login Installer</h2>';
    if ($err) echo '<div class="err">' . h($err) . '</div>';
    echo '<form method="post"><input type="hidden" name="action" value="login">';
    echo '<input type="hidden" name="csrf" value="' . h(csrf_token()) . '">';
    echo '<label>Password</label><input type="password" name="password" required>';
    echo '<div style="margin-top:14px"><button type="submit">Masuk</button></div></form>';
    render_footer();
}

function render_upload(?string $err = null, ?string $ok = null): void {
    $state = read_state();
    render_header('Upload');
    render_steps(2);
    echo '<h2>Upload Arsip Backup</h2><p>Upload file <code>duplicator-*.tar.gz</code>. Pastikan <code>post_max_size</code> dan <code>upload_max_filesize</code> PHP cukup besar.</p>';
    if ($err) echo '<div class="err">' . h($err) . '</div>';
    if ($ok) echo '<div class="ok">' . h($ok) . '</div>';
    if (!empty($state['archive_path']) && is_file($state['archive_path'])) {
        echo '<div class="ok">Arsip saat ini: ' . h(basename($state['archive_path'])) . ' (' . h((string)filesize($state['archive_path'])) . ' bytes)</div>';
    }
    echo '<form method="post" enctype="multipart/form-data"><input type="hidden" name="action" value="upload">';
    echo '<input type="hidden" name="csrf" value="' . h(csrf_token()) . '">';
    echo '<label>File arsip (.tar.gz)</label><input type="file" name="archive" accept=".gz,.tgz" required>';
    echo '<div style="margin-top:14px"><button type="submit">Upload & Extract</button></div></form>';
    render_footer();
}

function render_supabase_form(array $manifest, ?string $err = null): void {
    $state = read_state();
    $sup = $state['supabase'] ?? [];
    render_header('Supabase');
    render_steps(4);
    echo '<h2>Konfigurasi Supabase Target</h2><p>Masukkan kredensial project Supabase <strong>baru/kosong</strong>. Service role key tidak akan disimpan ke state file.</p>';
    if ($err) echo '<div class="err">' . h($err) . '</div>';
    $src = $manifest['source'] ?? [];
    echo '<p class="muted">Source: ' . h((string)($src['project_ref'] ?? '-')) . ' | dibuat: ' . h((string)($manifest['created_at'] ?? '-')) . '</p>';
    echo '<form method="post"><input type="hidden" name="action" value="restore_supabase">';
    echo '<input type="hidden" name="csrf" value="' . h(csrf_token()) . '">';
    $fields = [
        'project_ref' => 'Project Ref (baru)',
        'db_host' => 'DB Host',
        'db_port' => 'DB Port',
        'db_name' => 'DB Name',
        'db_user' => 'DB User',
    ];
    foreach ($fields as $k => $label) {
        $val = (string)($sup[$k] ?? ($k === 'db_port' ? '5432' : ($k === 'db_name' ? 'postgres' : '')));
        echo '<label>' . h($label) . '</label><input type="text" name="' . h($k) . '" value="' . h($val) . '" required>';
    }
    echo '<label>DB Password</label><input type="password" name="db_password" required>';
    echo '<label>Supabase Service Role Key (target)</label><input type="password" name="service_role_key" required>';
    echo '<div style="margin-top:14px"><button type="submit">Jalankan Restore Supabase</button></div></form>';
    render_footer();
}

function render_github_form(?string $err = null, ?string $ok = null): void {
    $state = read_state();
    render_header('GitHub Secrets');
    render_steps(5);
    echo '<h2>Set GitHub Secrets & Variables</h2><p>Masukkan GitHub PAT yang punya akses repo target. PAT tidak disimpan ke state.</p>';
    if ($err) echo '<div class="err">' . h($err) . '</div>';
    if ($ok) echo '<div class="ok">' . h($ok) . '</div>';
    $repo = (string)($state['github_repo'] ?? '');
    echo '<form method="post"><input type="hidden" name="action" value="set_github">';
    echo '<input type="hidden" name="csrf" value="' . h(csrf_token()) . '">';
    echo '<label>GitHub Repo (owner/repo)</label><input type="text" name="github_repo" value="' . h($repo) . '" placeholder="owner/repo" required>';
    echo '<label>GitHub PAT</label><input type="password" name="github_pat" required>';
    echo '<div style="margin-top:14px"><button type="submit">Set Secrets/Variables</button></div></form>';
    render_footer();
}

function render_worker_form(?string $err = null, ?string $ok = null): void {
    $state = read_state();
    render_header('Deploy Worker');
    render_steps(6);
    echo '<h2>Deploy Cloudflare Worker</h2><p>Gunakan Cloudflare API token yang punya izin Workers edit. Token tidak disimpan ke state.</p>';
    if ($err) echo '<div class="err">' . h($err) . '</div>';
    if ($ok) echo '<div class="ok">' . h($ok) . '</div>';
    $acct = (string)($state['cf_account_id'] ?? '');
    $wname = (string)($state['cf_worker_name'] ?? 'bot-cron');
    echo '<form method="post"><input type="hidden" name="action" value="deploy_worker">';
    echo '<input type="hidden" name="csrf" value="' . h(csrf_token()) . '">';
    echo '<label>Cloudflare Account ID</label><input type="text" name="cf_account_id" value="' . h($acct) . '" required>';
    echo '<label>Worker Name</label><input type="text" name="cf_worker_name" value="' . h($wname) . '" required>';
    echo '<label>Cloudflare API Token</label><input type="password" name="cf_api_token" required>';
    echo '<div style="margin-top:14px"><button type="submit">Deploy Worker</button></div></form>';
    render_footer();
}

function render_done(): void {
    $state = read_state();
    render_header('Selesai');
    render_steps(7);
    echo '<h2>Restore Selesai</h2>';
    echo '<div class="ok">Langkah restore yang dijalankan installer telah selesai. Periksa log di bawah.</div>';
    echo '<table><tr><th>Item</th><th>Status</th></tr>';
    foreach (['supabase' => 'Restore Supabase', 'github' => 'GitHub Secrets/Vars', 'worker' => 'Deploy Worker'] as $k => $label) {
        $st = !empty($state[$k . '_done']) ? 'OK' : 'Belum';
        echo '<tr><td>' . h($label) . '</td><td>' . h($st) . '</td></tr>';
    }
    echo '</table>';
    global $LOG_FILE;
    echo '<h3 style="margin-top:16px">Log</h3><pre>' . h((string)@file_get_contents($LOG_FILE)) . '</pre>';
    echo '<form method="post" style="margin-top:12px"><input type="hidden" name="action" value="cleanup"><input type="hidden" name="csrf" value="' . h(csrf_token()) . '">';
    echo '<button type="submit">Hapus file state &amp; extract</button></form>';
    render_footer();
}

function extract_archive(string $archivePath, string $extractDir): string {
    if (is_dir($extractDir)) {
        $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($extractDir, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $f) {
            $f->isDir() ? @rmdir($f->getPathname()) : @unlink($f->getPathname());
        }
        @rmdir($extractDir);
    }
    @mkdir($extractDir, 0755, true);
    // PharData can handle .tar.gz
    $phar = new PharData($archivePath);
    $phar->extractTo($extractDir, null, true);
    // find manifest.json
    $rootManifest = $extractDir . '/manifest.json';
    if (is_file($rootManifest)) return $extractDir;
    $items = scandir($extractDir) ?: [];
    foreach ($items as $it) {
        if ($it === '.' || $it === '..') continue;
        $p = $extractDir . '/' . $it;
        if (is_dir($p) && is_file($p . '/manifest.json')) return $p;
    }
    throw new RuntimeException('manifest.json tidak ditemukan di arsip');
}

function load_manifest(string $dir): array {
    $p = $dir . '/manifest.json';
    $j = json_decode((string)@file_get_contents($p), true);
    if (!is_array($j)) throw new RuntimeException('manifest.json tidak valid');
    return $j;
}

function run_cmd(string $cmd, ?array $env = null, ?string $stdin = null): array {
    $desc = [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
    $proc = proc_open($cmd, $desc, $pipes, null, $env);
    if (!is_resource($proc)) {
        return ['code' => 127, 'out' => '', 'err' => 'proc_open gagal'];
    }
    if ($stdin !== null) {
        fwrite($pipes[0], $stdin);
    }
    fclose($pipes[0]);
    $out = stream_get_contents($pipes[1]); fclose($pipes[1]);
    $err = stream_get_contents($pipes[2]); fclose($pipes[2]);
    $code = proc_close($proc);
    return ['code' => $code, 'out' => (string)$out, 'err' => (string)$err];
}

function psql_cmd(array $sup, string $sql, ?string $file = null): array {
    $env = $_ENV;
    $env['PGPASSWORD'] = $sup['db_password'];
    $host = $sup['db_host']; $port = $sup['db_port']; $user = $sup['db_user']; $db = $sup['db_name'];
    if ($file !== null) {
        $cmd = sprintf('psql -h %s -p %s -U %s -d %s -v ON_ERROR_STOP=1 -f %s',
            escapeshellarg($host), escapeshellarg($port), escapeshellarg($user), escapeshellarg($db), escapeshellarg($file));
        return run_cmd($cmd, $env);
    }
    $cmd = sprintf('psql -h %s -p %s -U %s -d %s -v ON_ERROR_STOP=1 -c %s',
        escapeshellarg($host), escapeshellarg($port), escapeshellarg($user), escapeshellarg($db), escapeshellarg($sql));
    return run_cmd($cmd, $env);
}

function supabase_restore(array $sup, string $payloadDir, array $manifest): void {
    // 1. schema
    $schema = $payloadDir . '/supabase/schema.sql';
    if (is_file($schema)) {
        log_msg('Restore schema.sql');
        $r = psql_cmd($sup, '', $schema);
        if ($r['code'] !== 0) throw new RuntimeException('schema restore gagal: ' . $r['err'] . $r['out']);
    }
    // 2. public data
    $publicSql = $payloadDir . '/supabase/data/public.sql';
    $publicDir = $payloadDir . '/supabase/data/public';
    if (is_file($publicSql)) {
        log_msg('Restore public.sql');
        $r = psql_cmd($sup, '', $publicSql);
        if ($r['code'] !== 0) throw new RuntimeException('public.sql restore gagal: ' . $r['err'] . $r['out']);
    } elseif (is_dir($publicDir)) {
        $tables = $manifest['supabase']['public_tables'] ?? [];
        if (!$tables) {
            // infer from csv
            foreach (glob($publicDir . '/*.csv') ?: [] as $f) $tables[] = basename($f, '.csv');
        }
        foreach ($tables as $t) {
            $csv = $publicDir . '/' . $t . '.csv';
            if (!is_file($csv)) continue;
            $colsLine = trim((string)fgets(fopen($csv, 'r')));
            $cols = str_getcsv($colsLine);
            $colList = implode(',', array_map(fn($c) => '"' . str_replace('"', '""', $c) . '"', $cols));
            log_msg('Import table ' . $t);
            $r = psql_cmd($sup, "\\copy public.\"$t\" ($colList) FROM '" . str_replace("'", "''", $csv) . "' WITH (FORMAT csv, HEADER true)");
            if ($r['code'] !== 0) throw new RuntimeException('copy ' . $t . ' gagal: ' . $r['err'] . $r['out']);
        }
    }
    // 3. auth users via Admin API
    $usersFile = $payloadDir . '/supabase/data/auth_users.json';
    $serviceKey = $sup['service_role_key'];
    $projectRef = $sup['project_ref'];
    $apiBase = 'https://' . $projectRef . '.supabase.co';
    if (is_file($usersFile)) {
        $users = json_decode((string)@file_get_contents($usersFile), true);
        if (is_array($users)) {
            foreach ($users as $u) {
                $payload = [
                    'email' => $u['email'] ?? null,
                    'email_confirm' => true,
                    'user_metadata' => $u['raw_user_meta_data'] ?? new stdClass(),
                    'app_metadata' => $u['raw_app_meta_data'] ?? new stdClass(),
                ];
                if (!empty($u['phone'])) $payload['phone'] = $u['phone'];
                if (!empty($u['phone_confirmed_at'])) $payload['phone_confirm'] = true;
                // idempotent: check if exists by email
                $email = (string)($u['email'] ?? '');
                $exists = false;
                if ($email !== '') {
                    $check = http_json('GET', $apiBase . '/auth/v1/admin/users?page=1&per_page=200', $serviceKey);
                    if ($check['code'] >= 200 && $check['code'] < 300) {
                        foreach (($check['body']['users'] ?? []) as $eu) {
                            if (strcasecmp((string)($eu['email'] ?? ''), $email) === 0) { $exists = true; break; }
                        }
                    }
                }
                if ($exists) { log_msg('Auth user exists: ' . $email); continue; }
                $res = http_json('POST', $apiBase . '/auth/v1/admin/users', $serviceKey, $payload);
                if ($res['code'] < 200 || $res['code'] >= 300) {
                    log_msg('Auth user create warn: ' . $email . ' ' . json_encode($res['body']));
                } else {
                    log_msg('Auth user created: ' . $email);
                }
            }
        }
    }
    // 4. storage buckets + objects
    $bucketsFile = $payloadDir . '/supabase/storage/buckets.json';
    $objectsDir = $payloadDir . '/supabase/storage/objects';
    if (is_file($bucketsFile)) {
        $buckets = json_decode((string)@file_get_contents($bucketsFile), true);
        if (is_array($buckets)) {
            foreach ($buckets as $b) {
                $name = (string)($b['name'] ?? $b['id'] ?? '');
                if ($name === '') continue;
                $res = http_json('POST', $apiBase . '/storage/v1/bucket', $serviceKey, [
                    'name' => $name,
                    'public' => (bool)($b['public'] ?? false),
                ]);
                if ($res['code'] >= 200 && $res['code'] < 300) log_msg('Bucket created: ' . $name);
                else log_msg('Bucket create skip/warn: ' . $name . ' ' . $res['code']);
            }
        }
    }
    if (is_dir($objectsDir)) {
        $rit = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($objectsDir, FilesystemIterator::SKIP_DOTS));
        foreach ($rit as $f) {
            if (!$f->isFile()) continue;
            $rel = ltrim(str_replace('\\', '/', substr($f->getPathname(), strlen($objectsDir))), '/');
            $parts = explode('/', $rel, 2);
            if (count($parts) !== 2) continue;
            [$bucket, $object] = $parts;
            $content = (string)@file_get_contents($f->getPathname());
            $url = $apiBase . '/storage/v1/object/' . rawurlencode($bucket) . '/' . implode('/', array_map('rawurlencode', explode('/', $object)));
            $ch = curl_init($url);
            curl_setopt_array($ch, [
                CURLOPT_POST => true,
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $serviceKey, 'apikey: ' . $serviceKey, 'x-upsert: true', 'Content-Type: application/octet-stream'],
                CURLOPT_POSTFIELDS => $content,
            ]);
            $body = curl_exec($ch);
            $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);
            if ($code >= 200 && $code < 300) log_msg('Storage upsert: ' . $bucket . '/' . $object);
            else log_msg('Storage warn: ' . $bucket . '/' . $object . ' ' . $code . ' ' . substr((string)$body, 0, 200));
        }
    }
}

function http_json(string $method, string $url, string $serviceKey, ?array $payload = null): array {
    $ch = curl_init($url);
    $headers = ['Authorization: Bearer ' . $serviceKey, 'apikey: ' . $serviceKey, 'Content-Type: application/json'];
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST => $method,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => $headers,
    ]);
    if ($payload !== null) curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
    $body = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err = curl_error($ch);
    curl_close($ch);
    $json = json_decode((string)$body, true);
    return ['code' => $code, 'body' => is_array($json) ? $json : ['raw' => (string)$body], 'err' => $err];
}

function github_put_secret(string $repo, string $pat, string $name, string $value): void {
    // get public key
    $ch = curl_init('https://api.github.com/repos/' . $repo . '/actions/secrets/public-key');
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_HTTPHEADER => [
        'Authorization: Bearer ' . $pat, 'Accept: application/vnd.github+json', 'User-Agent: duplicator-installer'
    ]]);
    $pkBody = curl_exec($ch); $pkCode = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE); curl_close($ch);
    if ($pkCode < 200 || $pkCode >= 300) throw new RuntimeException('Gagal ambil public key repo: ' . $pkCode . ' ' . substr((string)$pkBody,0,200));
    $pk = json_decode((string)$pkBody, true);
    $keyId = $pk['key_id'] ?? '';
    $key = $pk['key'] ?? '';
    if (!$keyId || !$key) throw new RuntimeException('public key tidak valid');
    if (!function_exists('sodium_crypto_box_seal')) throw new RuntimeException('Ekstensi sodium tidak tersedia untuk encrypt secret');
    $encrypted = sodium_crypto_box_seal($value, base64_decode($key));
    $encB64 = base64_encode($encrypted);
    $ch = curl_init('https://api.github.com/repos/' . $repo . '/actions/secrets/' . rawurlencode($name));
    curl_setopt_array($ch, [CURLOPT_CUSTOMREQUEST => 'PUT', CURLOPT_RETURNTRANSFER => true, CURLOPT_HTTPHEADER => [
        'Authorization: Bearer ' . $pat, 'Accept: application/vnd.github+json', 'User-Agent: duplicator-installer', 'Content-Type: application/json'
    ], CURLOPT_POSTFIELDS => json_encode(['encrypted_value' => $encB64, 'key_id' => $keyId])]);
    $body = curl_exec($ch); $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE); curl_close($ch);
    if ($code < 200 || $code >= 300) throw new RuntimeException('Set secret gagal: ' . $name . ' ' . $code . ' ' . substr((string)$body,0,200));
}

function github_put_variable(string $repo, string $pat, string $name, string $value): void {
    // Try PATCH existing, then POST
    $url = 'https://api.github.com/repos/' . $repo . '/actions/variables/' . rawurlencode($name);
    $ch = curl_init($url);
    curl_setopt_array($ch, [CURLOPT_CUSTOMREQUEST => 'PATCH', CURLOPT_RETURNTRANSFER => true, CURLOPT_HTTPHEADER => [
        'Authorization: Bearer ' . $pat, 'Accept: application/vnd.github+json', 'User-Agent: duplicator-installer', 'Content-Type: application/json'
    ], CURLOPT_POSTFIELDS => json_encode(['name' => $name, 'value' => $value])]);
    $body = curl_exec($ch); $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE); curl_close($ch);
    if ($code === 404) {
        $ch = curl_init('https://api.github.com/repos/' . $repo . '/actions/variables');
        curl_setopt_array($ch, [CURLOPT_CUSTOMREQUEST => 'POST', CURLOPT_RETURNTRANSFER => true, CURLOPT_HTTPHEADER => [
            'Authorization: Bearer ' . $pat, 'Accept: application/vnd.github+json', 'User-Agent: duplicator-installer', 'Content-Type: application/json'
        ], CURLOPT_POSTFIELDS => json_encode(['name' => $name, 'value' => $value])]);
        $body = curl_exec($ch); $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE); curl_close($ch);
    }
    if ($code < 200 || $code >= 300) throw new RuntimeException('Set variable gagal: ' . $name . ' ' . $code . ' ' . substr((string)$body,0,200));
}

function deploy_worker(string $accountId, string $workerName, string $apiToken, string $script, array $bindings): void {
    $url = 'https://api.cloudflare.com/client/v4/accounts/' . rawurlencode($accountId) . '/workers/scripts/' . rawurlencode($workerName);
    $metadata = ['main_module' => 'index.js', 'bindings' => $bindings];
    $boundary = '----duplicator' . bin2hex(random_bytes(8));
    $body = '';
    $body .= "--$boundary\r\nContent-Disposition: form-data; name=\"metadata\"; filename=\"metadata.json\"\r\nContent-Type: application/json\r\n\r\n" . json_encode($metadata) . "\r\n";
    $body .= "--$boundary\r\nContent-Disposition: form-data; name=\"index.js\"; filename=\"index.js\"\r\nContent-Type: application/javascript+module\r\n\r\n" . $script . "\r\n";
    $body .= "--$boundary--\r\n";
    $ch = curl_init($url);
    curl_setopt_array($ch, [CURLOPT_CUSTOMREQUEST => 'PUT', CURLOPT_RETURNTRANSFER => true, CURLOPT_HTTPHEADER => [
        'Authorization: Bearer ' . $apiToken, 'Content-Type: multipart/form-data; boundary=' . $boundary
    ], CURLOPT_POSTFIELDS => $body]);
    $resp = curl_exec($ch); $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE); curl_close($ch);
    if ($code < 200 || $code >= 300) throw new RuntimeException('Deploy worker gagal: ' . $code . ' ' . substr((string)$resp, 0, 300));
}

function step_from_state(array $state): int {
    if (empty($state['installer_password_hash'])) return 1;
    if (empty($_SESSION['installer_authed'])) return 1;
    if (empty($state['archive_path']) || !is_file((string)$state['archive_path'])) return 2;
    if (empty($state['extract_dir']) || !is_dir((string)$state['extract_dir'])) return 3;
    if (empty($state['supabase_done'])) return 4;
    if (empty($state['github_done'])) return 5;
    if (empty($state['worker_done'])) return 6;
    return 7;
}

// ---- actions ----
$action = $_POST['action'] ?? $_GET['action'] ?? '';
$state = read_state();

try {
    if ($action === 'set_password') {
        csrf_check();
        $p1 = (string)($_POST['password'] ?? '');
        $p2 = (string)($_POST['password2'] ?? '');
        if (strlen($p1) < 8) { render_set_password('Password minimal 8 karakter.'); exit; }
        if ($p1 !== $p2) { render_set_password('Password tidak sama.'); exit; }
        $state['installer_password_hash'] = password_hash($p1, PASSWORD_DEFAULT);
        write_state($state);
        $_SESSION['installer_authed'] = true;
        log_msg('Installer password set');
        header('Location: installer.php'); exit;
    }

    if ($action === 'login') {
        csrf_check();
        $p = (string)($_POST['password'] ?? '');
        $hash = (string)($state['installer_password_hash'] ?? '');
        if ($hash === '' || !password_verify($p, $hash)) { render_login('Password salah.'); exit; }
        $_SESSION['installer_authed'] = true;
        header('Location: installer.php'); exit;
    }

    if ($action === 'logout') {
        $_SESSION['installer_authed'] = false;
        header('Location: installer.php'); exit;
    }

    require_auth_or_render();

    if ($action === 'upload') {
        csrf_check();
        if (empty($_FILES['archive']['tmp_name']) || !is_uploaded_file($_FILES['archive']['tmp_name'])) {
            render_upload('File upload tidak valid.'); exit;
        }
        $name = basename((string)$_FILES['archive']['name']);
        if (!preg_match('/\.tar\.gz$/i', $name)) { render_upload('File harus .tar.gz'); exit; }
        $dest = $WORKDIR . '/' . preg_replace('/[^A-Za-z0-9._-]/', '_', $name);
        if (!move_uploaded_file($_FILES['archive']['tmp_name'], $dest)) {
            render_upload('Gagal menyimpan file.'); exit;
        }
        $state['archive_path'] = $dest;
        write_state($state);
        log_msg('Archive uploaded: ' . $dest);
        try {
            $extractDir = $WORKDIR . '/.duplicator-extract';
            $payloadDir = extract_archive($dest, $extractDir);
            $state['extract_dir'] = $payloadDir;
            $state['manifest'] = load_manifest($payloadDir);
            write_state($state);
            log_msg('Archive extracted: ' . $payloadDir);
        } catch (Throwable $e) {
            log_msg('Extract error: ' . $e->getMessage());
            render_upload('Extract gagal: ' . $e->getMessage()); exit;
        }
        header('Location: installer.php'); exit;
    }

    if ($action === 'restore_supabase') {
        csrf_check();
        $sup = [
            'project_ref' => trim((string)($_POST['project_ref'] ?? '')),
            'db_host' => trim((string)($_POST['db_host'] ?? '')),
            'db_port' => trim((string)($_POST['db_port'] ?? '5432')),
            'db_name' => trim((string)($_POST['db_name'] ?? 'postgres')),
            'db_user' => trim((string)($_POST['db_user'] ?? 'postgres')),
            'db_password' => (string)($_POST['db_password'] ?? ''),
            'service_role_key' => (string)($_POST['service_role_key'] ?? ''),
        ];
        foreach (['project_ref','db_host','db_port','db_name','db_user','db_password','service_role_key'] as $k) {
            if ($sup[$k] === '') { render_supabase_form($state['manifest'] ?? [], 'Field wajib: ' . $k); exit; }
        }
        try {
            supabase_restore($sup, (string)$state['extract_dir'], $state['manifest'] ?? []);
            $saved = $sup; unset($saved['db_password'], $saved['service_role_key']);
            $state['supabase'] = $saved;
            $state['supabase_done'] = true;
            write_state($state);
            log_msg('Supabase restore done');
        } catch (Throwable $e) {
            log_msg('Supabase restore error: ' . $e->getMessage());
            render_supabase_form($state['manifest'] ?? [], $e->getMessage()); exit;
        }
        header('Location: installer.php'); exit;
    }

    if ($action === 'set_github') {
        csrf_check();
        $repo = trim((string)($_POST['github_repo'] ?? ''));
        $pat = (string)($_POST['github_pat'] ?? '');
        if (!preg_match('#^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$#', $repo)) { render_github_form('Format repo harus owner/repo'); exit; }
        if ($pat === '') { render_github_form('PAT wajib diisi'); exit; }
        $payloadDir = (string)($state['extract_dir'] ?? '');
        $manifest = $state['manifest'] ?? [];
        $gh = $manifest['github'] ?? [];
        $secrets = $gh['secrets'] ?? [];
        $variables = $gh['variables'] ?? [];
        $envFile = $payloadDir . '/env/.env.sanitized';
        $envMap = [];
        if (is_file($envFile)) {
            foreach (file($envFile) ?: [] as $line) {
                if (strpos($line, '=') === false) continue;
                [$k,$v] = explode('=', $line, 2);
                $envMap[trim($k)] = trim($v);
            }
        }
        try {
            foreach ($secrets as $s) {
                $name = (string)($s['name'] ?? '');
                if ($name === '') continue;
                $val = $envMap[$name] ?? '';
                if ($val === '') { log_msg('Secret skip (no value in env): ' . $name); continue; }
                github_put_secret($repo, $pat, $name, $val);
                log_msg('Secret set: ' . $name);
            }
            foreach ($variables as $v) {
                $name = (string)($v['name'] ?? '');
                $val = (string)($v['value'] ?? ($envMap[$name] ?? ''));
                if ($name === '') continue;
                github_put_variable($repo, $pat, $name, $val);
                log_msg('Variable set: ' . $name);
            }
            $state['github_repo'] = $repo;
            $state['github_done'] = true;
            write_state($state);
        } catch (Throwable $e) {
            log_msg('GitHub set error: ' . $e->getMessage());
            render_github_form($e->getMessage()); exit;
        }
        header('Location: installer.php'); exit;
    }

    if ($action === 'deploy_worker') {
        csrf_check();
        $accountId = trim((string)($_POST['cf_account_id'] ?? ''));
        $workerName = trim((string)($_POST['cf_worker_name'] ?? 'bot-cron'));
        $apiToken = (string)($_POST['cf_api_token'] ?? '');
        if ($accountId === '' || $workerName === '' || $apiToken === '') { render_worker_form('Semua field wajib.'); exit; }
        $payloadDir = (string)($state['extract_dir'] ?? '');
        $scriptFile = $payloadDir . '/cloudflare/worker/src/index.js';
        $secretsFile = $payloadDir . '/cloudflare/worker/secrets.json';
        if (!is_file($scriptFile)) { render_worker_form('worker script tidak ditemukan di arsip.'); exit; }
        $script = (string)@file_get_contents($scriptFile);
        $bindings = [];
        if (is_file($secretsFile)) {
            $sec = json_decode((string)@file_get_contents($secretsFile), true);
            if (is_array($sec)) {
                foreach ($sec as $k => $v) {
                    if (!is_string($k) || $k === '') continue;
                    $bindings[] = ['type' => 'secret_text', 'name' => $k, 'text' => (string)$v];
                }
            }
        }
        try {
            deploy_worker($accountId, $workerName, $apiToken, $script, $bindings);
            $state['cf_account_id'] = $accountId;
            $state['cf_worker_name'] = $workerName;
            $state['worker_done'] = true;
            write_state($state);
            log_msg('Worker deployed: ' . $workerName);
        } catch (Throwable $e) {
            log_msg('Worker deploy error: ' . $e->getMessage());
            render_worker_form($e->getMessage()); exit;
        }
        header('Location: installer.php'); exit;
    }

    if ($action === 'cleanup') {
        csrf_check();
        $extractDir = $WORKDIR . '/.duplicator-extract';
        if (is_dir($extractDir)) {
            $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($extractDir, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::CHILD_FIRST);
            foreach ($it as $f) { $f->isDir() ? @rmdir($f->getPathname()) : @unlink($f->getPathname()); }
            @rmdir($extractDir);
        }
        @unlink($STATE_FILE);
        @unlink($LOG_FILE);
        $_SESSION['installer_authed'] = false;
        render_header('Cleanup');
        echo '<div class="ok">State dan extract dibersihkan. Hapus installer.php secara manual dari server.</div>';
        render_footer();
        exit;
    }

} catch (Throwable $e) {
    log_msg('Unhandled: ' . $e->getMessage());
    http_response_code(500);
    render_header('Error');
    echo '<div class="err">' . h($e->getMessage()) . '</div>';
    echo '<p><a href="installer.php" style="color:#2dd4a8">Kembali</a></p>';
    render_footer();
    exit;
}

// ---- routing ----
$state = read_state();
if (empty($state['installer_password_hash'])) { render_set_password(); exit; }
if (empty($_SESSION['installer_authed'])) { render_login(); exit; }
$step = step_from_state($state);
if ($step === 2) { render_upload(); exit; }
if ($step === 3) { render_upload(null, 'Extract belum lengkap. Upload ulang.'); exit; }
if ($step === 4) { render_supabase_form($state['manifest'] ?? []); exit; }
if ($step === 5) { render_github_form(); exit; }
if ($step === 6) { render_worker_form(); exit; }
render_done();
