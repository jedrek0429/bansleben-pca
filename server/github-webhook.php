<?php
declare(strict_types=1);

function deploy_config_path(): string {
    $candidates = [
        __DIR__ . '/.private/pca-deploy-config.json',
        dirname(__DIR__) . '/.private/pca-deploy-config.json',
        __DIR__ . '/../public_html/.private/pca-deploy-config.json',
    ];

    foreach ($candidates as $path) {
        if (is_file($path)) {
            return $path;
        }
    }

    http_response_code(500);
    echo "Missing deploy config\n";
    exit;
}

function load_deploy_config(): array {
    $path = deploy_config_path();
    $raw = file_get_contents($path);
    $config = json_decode((string)$raw, true);

    if (!is_array($config)) {
        http_response_code(500);
        echo "Invalid deploy config\n";
        exit;
    }

    return $config;
}

function respond(int $status, array $data): void {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_SLASHES) . "\n";
    exit;
}

function require_signature(array $config, string $body): void {
    $secret = (string)($config['webhook_secret'] ?? '');
    $signature = (string)($_SERVER['HTTP_X_HUB_SIGNATURE_256'] ?? '');

    if ($secret === '' || $signature === '') {
        respond(401, ['ok' => false, 'error' => 'missing signature']);
    }

    $expected = 'sha256=' . hash_hmac('sha256', $body, $secret);

    if (!hash_equals($expected, $signature)) {
        respond(401, ['ok' => false, 'error' => 'invalid signature']);
    }
}

function queue_dir(array $config): string {
    $dir = (string)($config['queue_dir'] ?? (__DIR__ . '/.private/deploy-queue'));
    if (!is_dir($dir) && !mkdir($dir, 0750, true) && !is_dir($dir)) {
        respond(500, ['ok' => false, 'error' => 'cannot create queue dir']);
    }
    return $dir;
}

function enqueue_job(array $config, array $job): string {
    $dir = queue_dir($config);
    $delivery = preg_replace('/[^A-Za-z0-9_.-]/', '-', (string)($_SERVER['HTTP_X_GITHUB_DELIVERY'] ?? uniqid('', true)));
    $name = gmdate('YmdHis') . '-' . $delivery . '-' . bin2hex(random_bytes(4)) . '.json';
    $path = rtrim($dir, '/') . '/' . $name;

    $job['queued_at'] = gmdate('c');
    $job['delivery'] = $_SERVER['HTTP_X_GITHUB_DELIVERY'] ?? null;
    $job['event'] = $_SERVER['HTTP_X_GITHUB_EVENT'] ?? null;

    $json = json_encode($job, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
    if ($json === false || file_put_contents($path, $json . "\n", LOCK_EX) === false) {
        respond(500, ['ok' => false, 'error' => 'cannot write queue job']);
    }

    return $name;
}

function is_preview_comment(array $payload): bool {
    $body = (string)($payload['comment']['body'] ?? '');
    return isset($payload['issue']['pull_request']) && preg_match('/(^|\s)\/preview(\s|$)/', $body) === 1;
}

$config = load_deploy_config();
$body = file_get_contents('php://input') ?: '';
require_signature($config, $body);

$event = (string)($_SERVER['HTTP_X_GITHUB_EVENT'] ?? '');
$payload = json_decode($body, true);

if (!is_array($payload)) {
    respond(400, ['ok' => false, 'error' => 'invalid json']);
}

$repo = (string)($payload['repository']['full_name'] ?? '');
$expectedRepo = (string)($config['repository'] ?? '');

if ($expectedRepo !== '' && $repo !== $expectedRepo) {
    respond(202, ['ok' => true, 'queued' => false, 'reason' => 'repository ignored']);
}

if ($event === 'push') {
    if (($payload['ref'] ?? '') !== 'refs/heads/main') {
        respond(202, ['ok' => true, 'queued' => false, 'reason' => 'non-main push ignored']);
    }

    $job = [
        'type' => 'production',
        'repository' => $repo,
        'ref' => $payload['ref'],
        'sha' => $payload['after'] ?? null,
    ];
    $file = enqueue_job($config, $job);
    respond(202, ['ok' => true, 'queued' => true, 'job' => $file]);
}

if ($event === 'pull_request') {
    $action = (string)($payload['action'] ?? '');
    $pr = $payload['pull_request'] ?? [];
    $number = (int)($payload['number'] ?? 0);

    if (in_array($action, ['opened', 'synchronize', 'reopened'], true)) {
        $job = [
            'type' => 'preview',
            'repository' => $repo,
            'action' => $action,
            'pr_number' => $number,
            'sha' => $pr['head']['sha'] ?? null,
            'head_repo' => $pr['head']['repo']['full_name'] ?? null,
            'base_repo' => $pr['base']['repo']['full_name'] ?? null,
        ];
        $file = enqueue_job($config, $job);
        respond(202, ['ok' => true, 'queued' => true, 'job' => $file]);
    }

    if ($action === 'closed') {
        $job = [
            'type' => 'cleanup_preview',
            'repository' => $repo,
            'pr_number' => $number,
        ];
        $file = enqueue_job($config, $job);
        respond(202, ['ok' => true, 'queued' => true, 'job' => $file]);
    }

    respond(202, ['ok' => true, 'queued' => false, 'reason' => 'pull_request action ignored']);
}

if ($event === 'issue_comment') {
    if (($payload['action'] ?? '') !== 'created' || !is_preview_comment($payload)) {
        respond(202, ['ok' => true, 'queued' => false, 'reason' => 'comment ignored']);
    }

    $job = [
        'type' => 'preview_comment',
        'repository' => $repo,
        'pr_number' => (int)($payload['issue']['number'] ?? 0),
        'comment_id' => $payload['comment']['id'] ?? null,
        'comment_user' => $payload['comment']['user']['login'] ?? null,
    ];
    $file = enqueue_job($config, $job);
    respond(202, ['ok' => true, 'queued' => true, 'job' => $file]);
}

respond(202, ['ok' => true, 'queued' => false, 'reason' => 'event ignored']);
