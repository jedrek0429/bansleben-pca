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
        if (is_file($configFile)) {
            return $configFile;
        }
    }

    throw new RuntimeException('Missing SMTP config. Checked: ' . implode(', ', config_candidates()));
}

function load_config(): array {
    global $logFile;

    $configPath = find_config();
    $logFile = dirname($configPath) . '/pca-contact.log';

    $rawConfig = file_get_contents($configPath);
    if ($rawConfig === false) {
        throw new RuntimeException('Unable to read SMTP config: ' . $configPath);
    }

    $config = json_decode($rawConfig, true);
    if (json_last_error() !== JSON_ERROR_NONE) {
        throw new RuntimeException('SMTP config JSON is invalid: ' . json_last_error_msg());
    }

    if (!is_array($config)) {
        throw new RuntimeException('SMTP config JSON must contain an object');
    }

    foreach (['smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'from_email', 'from_name', 'to_email'] as $key) {
        if (!array_key_exists($key, $config) || trim((string)$config[$key]) === '') {
            throw new RuntimeException('SMTP config missing key: ' . $key);
        }
    }

    $config['smtp_port'] = (int)$config['smtp_port'];

    return $config;
}

function log_line(string $msg): void {
    global $logFile;

    $line = '[' . date('c') . '] ' . $msg . "\n";
    $targets = array_filter(array_unique([
        $logFile ?? null,
        __DIR__ . '/../.private/pca-contact.log',
        dirname(__DIR__, 2) . '/.private/pca-contact.log',
    ]));

    foreach ($targets as $target) {
        $dir = dirname($target);
        if (is_dir($dir) && (is_writable($dir) || (is_file($target) && is_writable($target)))) {
            if (@file_put_contents($target, $line, FILE_APPEND | LOCK_EX) !== false) {
                return;
            }
        }
    }

    error_log('PCA contact form: ' . $msg);
}

function clean_header(string $value): string {
    return trim(str_replace(["\r", "\n"], ' ', $value));
}

function encode_header(string $value): string {
    return '=?UTF-8?B?' . base64_encode($value) . '?=';
}

function smtp_read($fp): array {
    $data = '';

    while (($line = fgets($fp, 515)) !== false) {
        $data .= $line;

        if (strlen($line) >= 4 && $line[3] === ' ') {
            break;
        }
    }

    $code = (int)substr($data, 0, 3);
    return [$code, $data];
}

function smtp_cmd($fp, string $cmd, array $expected): string {
    fwrite($fp, $cmd . "\r\n");
    [$code, $data] = smtp_read($fp);

    if (!in_array($code, $expected, true)) {
        throw new RuntimeException("SMTP command failed: {$cmd}; response: {$data}");
    }

    return $data;
}

function smtp_send_raw(array $cfg, string $mailFrom, string $rcptTo, string $raw): bool {
    $host = $cfg['smtp_host'];
    $port = (int)$cfg['smtp_port'];
    $user = $cfg['smtp_user'];
    $pass = $cfg['smtp_pass'];

    $context = stream_context_create([
        'ssl' => [
            'verify_peer' => true,
            'verify_peer_name' => true,
            'allow_self_signed' => false,
        ],
    ]);

    $fp = stream_socket_client(
        'ssl://' . $host . ':' . $port,
        $errno,
        $errstr,
        30,
        STREAM_CLIENT_CONNECT,
        $context
    );

    if (!$fp) {
        throw new RuntimeException("SMTP connect failed: {$errno} {$errstr}");
    }

    stream_set_timeout($fp, 30);

    try {
        [$code, $banner] = smtp_read($fp);
        if ($code !== 220) {
            throw new RuntimeException("SMTP banner failed: {$banner}");
        }

        smtp_cmd($fp, 'EHLO polandchildabduction.pl', [250]);
        smtp_cmd($fp, 'AUTH LOGIN', [334]);
        smtp_cmd($fp, base64_encode($user), [334]);
        smtp_cmd($fp, base64_encode($pass), [235]);
        smtp_cmd($fp, 'MAIL FROM:<' . $mailFrom . '>', [250]);
        smtp_cmd($fp, 'RCPT TO:<' . $rcptTo . '>', [250, 251]);
        smtp_cmd($fp, 'DATA', [354]);

        fwrite($fp, $raw . "\r\n.\r\n");
        [$code, $data] = smtp_read($fp);

        smtp_cmd($fp, 'QUIT', [221, 250]);

        if ($code !== 250) {
            throw new RuntimeException("SMTP DATA failed: {$data}");
        }

        return true;
    } finally {
        if (is_resource($fp)) {
            fclose($fp);
        }
    }
}

function normalize_raw_message(string $raw): string {
    $raw = str_replace(["\r\n", "\r"], "\n", $raw);
    $raw = str_replace("\n", "\r\n", $raw);
    return preg_replace('/^\./m', '..', $raw);
}

function send_smtp(array $cfg, string $replyEmail, string $name, string $message): bool {
    $fromEmail = clean_header($cfg['from_email']);
    $fromName = clean_header($cfg['from_name']);
    $toEmail = clean_header($cfg['to_email']);

    $subject = 'Contact form - Poland Child Abduction';

    $body =
        "Name: {$name}\n" .
        "Email: {$replyEmail}\n" .
        "IP: " . ($_SERVER['REMOTE_ADDR'] ?? '') . "\n" .
        "Page: " . clean_header((string)($_POST['page'] ?? ($_SERVER['HTTP_REFERER'] ?? ''))) . "\n\n" .
        $message . "\n";

    $headers = [
        'Date: ' . date('r'),
        'From: ' . encode_header($fromName) . ' <' . $fromEmail . '>',
        'To: <' . $toEmail . '>',
        'Reply-To: <' . clean_header($replyEmail) . '>',
        'Subject: ' . encode_header($subject),
        'MIME-Version: 1.0',
        'Content-Type: text/plain; charset=UTF-8',
        'Content-Transfer-Encoding: 8bit',
    ];

    $raw = normalize_raw_message(implode("\r\n", $headers) . "\r\n\r\n" . $body);

    return smtp_send_raw($cfg, $fromEmail, $toEmail, $raw);
}

function confirmation_subject(string $lang): string {
    switch ($lang) {
        case 'fr':
            return 'Nous avons reçu votre message';
        case 'hr':
            return 'Primili smo vašu poruku';
        default:
            return 'We received your message';
    }
}

function confirmation_body(string $lang, string $name): string {
    switch ($lang) {
        case 'fr':
            return "Bonjour {$name},\n\n" .
                   "Merci d’avoir contacté Poland Child Abduction. Nous avons bien reçu votre message et l’examinerons dès que possible.\n\n" .
                   "Ce message est une confirmation automatique. Il ne constitue pas un conseil juridique.\n\n" .
                   "Poland Child Abduction\n";
        case 'hr':
            return "Poštovani/a {$name},\n\n" .
                   "Hvala što ste kontaktirali Poland Child Abduction. Primili smo vašu poruku i pregledat ćemo je što je prije moguće.\n\n" .
                   "Ovo je automatska potvrda. Ova poruka ne predstavlja pravni savjet.\n\n" .
                   "Poland Child Abduction\n";
        default:
            return "Dear {$name},\n\n" .
                   "Thank you for contacting Poland Child Abduction. We have received your message and will review it as soon as possible.\n\n" .
                   "This is an automatic confirmation. Please do not rely on this message as legal advice.\n\n" .
                   "Poland Child Abduction\n";
    }
}

function send_confirmation_smtp(array $cfg, string $recipientEmail, string $name, string $lang): bool {
    $fromEmail = clean_header($cfg['from_email']);
    $fromName = clean_header($cfg['from_name']);
    $replyToEmail = clean_header($cfg['reply_to_email'] ?? $cfg['from_email']);
    $recipientEmail = clean_header($recipientEmail);

    if (!in_array($lang, ['en', 'fr', 'hr'], true)) {
        $lang = 'en';
    }

    $subject = confirmation_subject($lang);
    $body = confirmation_body($lang, $name);

    $headers = [
        'Date: ' . date('r'),
        'From: ' . encode_header($fromName) . ' <' . $fromEmail . '>',
        'To: <' . $recipientEmail . '>',
        'Reply-To: <' . $replyToEmail . '>',
        'Subject: ' . encode_header($subject),
        'MIME-Version: 1.0',
        'Content-Type: text/plain; charset=UTF-8',
        'Content-Transfer-Encoding: 8bit',
    ];

    $raw = normalize_raw_message(implode("\r\n", $headers) . "\r\n\r\n" . $body);

    return smtp_send_raw($cfg, $fromEmail, $recipientEmail, $raw);
}

function back_url(): string {
    $url = clean_header((string)($_POST['back_url'] ?? $_SERVER['HTTP_REFERER'] ?? '/'));

    if ($url === '') {
        return '/';
    }

    // Allow same-site absolute URLs, but convert them to path-only URLs.
    // Reject external URLs to avoid open redirects.
    if (preg_match('~^https?://~i', $url)) {
        $parts = parse_url($url);
        $currentHost = strtolower((string)($_SERVER['HTTP_HOST'] ?? ''));
        $urlHost = strtolower((string)($parts['host'] ?? ''));

        if ($currentHost === '' || $urlHost === '' || $urlHost !== $currentHost) {
            return '/';
        }

        $url = ($parts['path'] ?? '/');
        if (isset($parts['query']) && $parts['query'] !== '') {
            $url .= '?' . $parts['query'];
        }
        if (isset($parts['fragment']) && $parts['fragment'] !== '') {
            $url .= '#' . $parts['fragment'];
        }
    }

    if ($url[0] !== '/') {
        return '/';
    }

    return $url;
}

function redirect_with_status(bool $ok): void {
    $url = back_url();

    $hash = '';
    $hashPos = strpos($url, '#');

    if ($hashPos !== false) {
        $hash = substr($url, $hashPos);
        $url = substr($url, 0, $hashPos);
    }

    $path = $url;
    $params = [];
    $queryPos = strpos($url, '?');
    if ($queryPos !== false) {
        $path = substr($url, 0, $queryPos);
        parse_str(substr($url, $queryPos + 1), $params);
    }

    unset($params['sent']);
    $params['sent'] = $ok ? '1' : '0';

    $target = $path . '?' . http_build_query($params) . $hash;

    header('Location: ' . $target, true, 303);
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

    $lang = clean_header((string)($_POST['lang'] ?? 'en'));
    if (!in_array($lang, ['en', 'fr', 'hr'], true)) {
        $lang = 'en';
    }

    // Honeypot field: pretend success for bots, but do not send email.
    if (trim((string)($_POST['website'] ?? '')) !== '') {
        log_line('Honeypot triggered');
        redirect_with_status(true);
    }

    if ($name === '' || $email === '' || $message === '') {
        throw new RuntimeException('Missing required fields');
    }

    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        throw new RuntimeException('Invalid email address');
    }

    // Load config inside the try block so missing/broken config redirects back with sent=0.
    $config = load_config();

    log_line('Submitting form from email=' . $email . ' name=' . $name);

    send_smtp($config, $email, $name, $message);
    log_line('Notification OK');

    send_confirmation_smtp($config, $email, $name, $lang);
    log_line('Confirmation OK to=' . $email . ' lang=' . $lang);

    redirect_with_status(true);
} catch (Throwable $e) {
    log_line('ERROR: ' . $e->getMessage());
    redirect_with_status(false);
}
