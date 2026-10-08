<?php
declare(strict_types=1);

$logFile = __DIR__ . '/.private/pca-contact.log';

function config_candidates(): array {
    return array_values(array_unique([
        __DIR__ . '/.private/pca-contact-config.json',
        dirname(__DIR__) . '/.private/pca-contact-config.json',
        dirname(__DIR__, 2) . '/.private/pca-contact-config.json',
    ]));
}

function find_config(): string {
    foreach (config_candidates() as $configFile) {
        if (is_file($configFile)) return $configFile;
    }
    throw new RuntimeException('Missing SMTP config. Checked: ' . implode(', ', config_candidates()));
}

function load_json_object(string $path, string $label): array {
    $raw = file_get_contents($path);
    if ($raw === false) throw new RuntimeException('Unable to read ' . $label . ': ' . $path);
    $data = json_decode($raw, true);
    if (json_last_error() !== JSON_ERROR_NONE || !is_array($data)) throw new RuntimeException($label . ' JSON is invalid');
    return $data;
}

function load_config(): array {
    global $logFile;
    $configPath = find_config();
    $logFile = dirname($configPath) . '/pca-contact.log';
    $config = load_json_object($configPath, 'SMTP config');
    foreach (['smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'from_email', 'from_name', 'to_email'] as $key) {
        if (!array_key_exists($key, $config) || trim((string)$config[$key]) === '') throw new RuntimeException('SMTP config missing key: ' . $key);
    }
    $config['smtp_port'] = (int)$config['smtp_port'];
    return $config;
}

function load_contact_locale(): array {
    $path = __DIR__ . '/.private/pca-contact-locale.json';
    $locale = load_json_object($path, 'Contact locale');
    foreach (['confirmation_subject', 'confirmation_body'] as $key) {
        if (!isset($locale[$key]) || trim((string)$locale[$key]) === '') throw new RuntimeException('Contact locale missing key: ' . $key);
    }
    return $locale;
}

function log_line(string $msg): void {
    global $logFile;
    $line = '[' . date('c') . '] ' . $msg . "\n";
    $targets = array_filter(array_unique([$logFile ?? null, __DIR__ . '/../.private/pca-contact.log', dirname(__DIR__, 2) . '/.private/pca-contact.log']));
    foreach ($targets as $target) {
        $dir = dirname($target);
        if (is_dir($dir) && (is_writable($dir) || (is_file($target) && is_writable($target))) && @file_put_contents($target, $line, FILE_APPEND | LOCK_EX) !== false) return;
    }
    error_log('PCA contact form: ' . $msg);
}

function clean_header(string $value): string { return trim(str_replace(["\r", "\n"], ' ', $value)); }
function encode_header(string $value): string { return '=?UTF-8?B?' . base64_encode($value) . '?='; }

function normalize_language(string $value): string {
    $lang = clean_header($value);
    return preg_match('/^[a-z]{2}(-[A-Z]{2})?$/', $lang) === 1 ? $lang : 'unknown';
}

function smtp_read($fp): array {
    $data = '';
    while (($line = fgets($fp, 515)) !== false) {
        $data .= $line;
        if (strlen($line) >= 4 && $line[3] === ' ') break;
    }
    return [(int)substr($data, 0, 3), $data];
}

function smtp_cmd($fp, string $cmd, array $expected): string {
    fwrite($fp, $cmd . "\r\n");
    [$code, $data] = smtp_read($fp);
    if (!in_array($code, $expected, true)) throw new RuntimeException("SMTP command failed: {$cmd}; response: {$data}");
    return $data;
}

function smtp_send_raw(array $cfg, string $mailFrom, string $rcptTo, string $raw): bool {
    $context = stream_context_create(['ssl' => ['verify_peer' => true, 'verify_peer_name' => true, 'allow_self_signed' => false]]);
    $fp = stream_socket_client('ssl://' . $cfg['smtp_host'] . ':' . (int)$cfg['smtp_port'], $errno, $errstr, 30, STREAM_CLIENT_CONNECT, $context);
    if (!$fp) throw new RuntimeException("SMTP connect failed: {$errno} {$errstr}");
    stream_set_timeout($fp, 30);
    try {
        [$code, $banner] = smtp_read($fp);
        if ($code !== 220) throw new RuntimeException("SMTP banner failed: {$banner}");
        smtp_cmd($fp, 'EHLO polandchildabduction.pl', [250]);
        smtp_cmd($fp, 'AUTH LOGIN', [334]);
        smtp_cmd($fp, base64_encode($cfg['smtp_user']), [334]);
        smtp_cmd($fp, base64_encode($cfg['smtp_pass']), [235]);
        smtp_cmd($fp, 'MAIL FROM:<' . $mailFrom . '>', [250]);
        smtp_cmd($fp, 'RCPT TO:<' . $rcptTo . '>', [250, 251]);
        smtp_cmd($fp, 'DATA', [354]);
        fwrite($fp, $raw . "\r\n.\r\n");
        [$code, $data] = smtp_read($fp);
        smtp_cmd($fp, 'QUIT', [221, 250]);
        if ($code !== 250) throw new RuntimeException("SMTP DATA failed: {$data}");
        return true;
    } finally {
        if (is_resource($fp)) fclose($fp);
    }
}

function normalize_raw_message(string $raw): string {
    $raw = str_replace(["\r\n", "\r"], "\n", $raw);
    $raw = str_replace("\n", "\r\n", $raw);
    return preg_replace('/^\./m', '..', $raw);
}

function send_smtp(array $cfg, string $replyEmail, string $name, string $lang, string $message): bool {
    $fromEmail = clean_header($cfg['from_email']);
    $fromName = clean_header($cfg['from_name']);
    $toEmail = clean_header($cfg['to_email']);
    $body = "Name: {$name}\nEmail: {$replyEmail}\nIP: " . ($_SERVER['REMOTE_ADDR'] ?? '') . "\nLanguage: {$lang}\n\n{$message}\n";
    $headers = ['Date: ' . date('r'), 'From: ' . encode_header($fromName) . ' <' . $fromEmail . '>', 'To: <' . $toEmail . '>', 'Reply-To: <' . clean_header($replyEmail) . '>', 'Subject: ' . encode_header('Contact form - Poland Child Abduction'), 'MIME-Version: 1.0', 'Content-Type: text/plain; charset=UTF-8', 'Content-Transfer-Encoding: 8bit'];
    return smtp_send_raw($cfg, $fromEmail, $toEmail, normalize_raw_message(implode("\r\n", $headers) . "\r\n\r\n" . $body));
}

function send_confirmation_smtp(array $cfg, array $locale, string $recipientEmail, string $name): bool {
    $fromEmail = clean_header($cfg['from_email']);
    $fromName = clean_header($cfg['from_name']);
    $replyToEmail = clean_header($cfg['reply_to_email'] ?? $cfg['from_email']);
    $recipientEmail = clean_header($recipientEmail);
    $subject = (string)$locale['confirmation_subject'];
    $body = str_replace('{name}', $name, (string)$locale['confirmation_body']);
    $headers = ['Date: ' . date('r'), 'From: ' . encode_header($fromName) . ' <' . $fromEmail . '>', 'To: <' . $recipientEmail . '>', 'Reply-To: <' . $replyToEmail . '>', 'Subject: ' . encode_header($subject), 'MIME-Version: 1.0', 'Content-Type: text/plain; charset=UTF-8', 'Content-Transfer-Encoding: 8bit'];
    return smtp_send_raw($cfg, $fromEmail, $recipientEmail, normalize_raw_message(implode("\r\n", $headers) . "\r\n\r\n" . $body));
}


function contact_guard(array $cfg, string $email): array {
    $dir = dirname(find_config());
    $file = $dir . '/pca-contact-limits.json';
    $fp = fopen($file, 'c+');
    if (!$fp || !flock($fp, LOCK_EX)) throw new RuntimeException('Contact protection unavailable');
    try {
        $raw = stream_get_contents($fp);
        $state = json_decode($raw ?: '{}', true);
        if (!is_array($state)) $state = [];
        $now = time();
        foreach ($state as $key => $expires) {
            if (!is_numeric($expires) || (int)$expires <= $now) unset($state[$key]);
        }
        $ip = (string)($_SERVER['REMOTE_ADDR'] ?? 'unknown');
        $secret = (string)($cfg['smtp_pass'] ?? '');
        $ipHash = hash_hmac('sha256', $ip, $secret);
        $emailHash = hash_hmac('sha256', strtolower($email), $secret);
        $ipCount = 0;
        $globalCount = 0;
        foreach ($state as $key => $expires) {
            if (str_starts_with($key, 'ip:' . $ipHash . ':')) $ipCount++;
            if (str_starts_with($key, 'global:')) $globalCount++;
        }
        if ($ipCount >= 5 || $globalCount >= 30) {
            log_line('Rate limit exceeded');
            http_response_code(429);
            throw new RuntimeException('Rate limit exceeded');
        }
        $confirmKey = 'confirmation:' . $emailHash;
        $allowConfirmation = !isset($state[$confirmKey]);
        $confirmationCount = 0;
        foreach ($state as $key => $expires) if (str_starts_with($key, 'confirm-global:')) $confirmationCount++;
        if ($confirmationCount >= 20) $allowConfirmation = false;
        $nonce = bin2hex(random_bytes(12));
        $state['ip:' . $ipHash . ':' . $nonce] = $now + 900;
        $state['global:' . $nonce] = $now + 3600;
        if ($allowConfirmation) {
            $state[$confirmKey] = $now + 86400;
            $state['confirm-global:' . $nonce] = $now + 3600;
        }
        rewind($fp);
        if (!ftruncate($fp, 0) || fwrite($fp, json_encode($state, JSON_THROW_ON_ERROR)) === false || !fflush($fp)) {
            throw new RuntimeException('Unable to save contact limits');
        }
        return ['confirmation' => $allowConfirmation];
    } finally {
        flock($fp, LOCK_UN);
        fclose($fp);
    }
}

function verify_turnstile(array $cfg): void {
    $secret = trim((string)($cfg['turnstile_secret_key'] ?? ''));
    if ($secret === '') return; // Enable only after configuring Cloudflare.
    $token = (string)($_POST['cf-turnstile-response'] ?? '');
    if ($token === '' || strlen($token) > 2048) throw new RuntimeException('Turnstile token missing');
    $payload = http_build_query([
        'secret' => $secret,
        'response' => $token,
        'remoteip' => (string)($_SERVER['REMOTE_ADDR'] ?? ''),
    ]);
    $context = stream_context_create(['http' => [
        'method' => 'POST',
        'header' => "Content-Type: application/x-www-form-urlencoded\r\n",
        'content' => $payload,
        'timeout' => 8,
        'ignore_errors' => true,
    ]]);
    $result = @file_get_contents('https://challenges.cloudflare.com/turnstile/v0/siteverify', false, $context);
    $data = $result === false ? null : json_decode($result, true);
    $hostname = strtolower((string)($data['hostname'] ?? ''));
    $allowedHosts = ['polandchildabduction.pl', 'www.polandchildabduction.pl', 'preview.polandchildabduction.pl'];
    if (!is_array($data) || ($data['success'] ?? false) !== true || !in_array($hostname, $allowedHosts, true) || (string)($data['action'] ?? '') !== 'contact') {
        throw new RuntimeException('Turnstile verification failed');
    }
}

function back_url(): string {
    $url = clean_header((string)($_POST['back_url'] ?? $_SERVER['HTTP_REFERER'] ?? '/'));
    if ($url === '') return '/';
    if (preg_match('~^https?://~i', $url)) {
        $parts = parse_url($url);
        $currentHost = strtolower((string)($_SERVER['HTTP_HOST'] ?? ''));
        $urlHost = strtolower((string)($parts['host'] ?? ''));
        if ($currentHost === '' || $urlHost === '' || $urlHost !== $currentHost) return '/';
        $url = ($parts['path'] ?? '/');
        if (isset($parts['query']) && $parts['query'] !== '') $url .= '?' . $parts['query'];
        if (isset($parts['fragment']) && $parts['fragment'] !== '') $url .= '#' . $parts['fragment'];
    }
    return $url[0] === '/' ? $url : '/';
}

function redirect_with_status(bool $ok): void {
    $url = back_url();
    $hash = '';
    $hashPos = strpos($url, '#');
    if ($hashPos !== false) { $hash = substr($url, $hashPos); $url = substr($url, 0, $hashPos); }
    $path = $url;
    $params = [];
    $queryPos = strpos($url, '?');
    if ($queryPos !== false) { $path = substr($url, 0, $queryPos); parse_str(substr($url, $queryPos + 1), $params); }
    unset($params['sent']);
    $params['sent'] = $ok ? '1' : '0';
    header('Location: ' . $path . '?' . http_build_query($params) . $hash, true, 303);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['turnstile_config'])) {
    header('Content-Type: application/json; charset=UTF-8');
    header('Cache-Control: no-store');
    try {
        $cfg = load_config();
        $sitekey = trim((string)($cfg['turnstile_site_key'] ?? '0x4AAAAAAFRJQ2Yq6MuQJNtH'));
        $enabled = trim((string)($cfg['turnstile_secret_key'] ?? '')) !== '';
        if ($enabled && $sitekey === '') throw new RuntimeException('Turnstile site key missing');
        echo json_encode(['enabled' => $enabled, 'sitekey' => $enabled ? $sitekey : '']);
    } catch (Throwable $e) {
        http_response_code(503);
        echo json_encode(['error' => 'Contact configuration unavailable']);
    }
    exit;
}
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    header('Content-Type: text/plain; charset=UTF-8');
    echo "This endpoint only handles contact form submissions.\n";
    exit;
}

try {
    $name = trim((string)($_POST['name'] ?? ''));
    $email = trim((string)($_POST['email'] ?? ''));
    $message = trim((string)($_POST['message'] ?? ''));
    $lang = normalize_language((string)($_POST['lang'] ?? 'en'));
    if (trim((string)($_POST['website'] ?? '')) !== '') { log_line('Honeypot triggered'); redirect_with_status(true); }
    if ($name === '' || $email === '' || $message === '') throw new RuntimeException('Missing required fields');
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) throw new RuntimeException('Invalid email address');
    if (strlen($name) > 200 || strlen($email) > 254 || strlen($message) > 20000) throw new RuntimeException('Form input too long');
    $config = load_config();
    verify_turnstile($config);
    // Preview-only verification test. No rate-limit state changes or SMTP traffic.
    $host = strtolower((string)($_SERVER['HTTP_HOST'] ?? ''));
    if ($host === 'preview.polandchildabduction.pl' && ($config['turnstile_test_mode'] ?? false) === true) {
        header('Content-Type: text/plain; charset=UTF-8');
        header('Cache-Control: no-store');
        log_line('Turnstile preview verification OK (SMTP skipped)');
        echo "Turnstile verification OK; no email sent.\n";
        exit;
    }
    $guard = contact_guard($config, $email);
    $locale = load_contact_locale();
    log_line('Submitting form from email=' . $email . ' name=' . $name);
    send_smtp($config, $email, $name, $lang, $message);
    log_line('Notification OK');
    if ($guard['confirmation']) {
        try {
            send_confirmation_smtp($config, $locale, $email, $name);
            log_line('Confirmation OK to=' . $email . ' lang=' . $lang);
        } catch (Throwable $confirmationError) {
            log_line('Confirmation failed: ' . $confirmationError->getMessage());
        }
    } else {
        log_line('Confirmation suppressed by limits');
    }
    redirect_with_status(true);
} catch (Throwable $e) {
    log_line('ERROR: ' . $e->getMessage());
    redirect_with_status(false);
}
