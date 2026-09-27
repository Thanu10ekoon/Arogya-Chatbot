function Chat($msg, $role="admin", $uid=49) {
    $body = @{ messages = @(@{ role = "user"; content = $msg }); user_id = $uid; user_role = $role } | ConvertTo-Json -Depth 10
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:8091/chat" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 90
    return $r.reply
}

Write-Host "=== TEST: Create a clinic ===" -ForegroundColor Cyan
Chat "Create a new clinic named 'Test LLM Clinic' in Western province, Colombo district, at Townhall for tomorrow at 10:00 AM."

Write-Host "
=== TEST: RBAC Doctor creating clinic ===" -ForegroundColor Cyan
Chat "Create a new clinic named 'Doctor Secret Clinic'" "doctor" 50

