param(
  [string]$PaperTitle = "Demo Paper",
  [string]$Abstract = "This paper proposes ...",
  [string]$Concept = "Core Idea",
  [string[]]$Claims = @("Claim A","Claim B"),
  [string[]]$Goals = @("Clarity","Engagement"),
  [int]$Duration = 6,
  [string]$Style = "educational",
  [int]$Fps = 24,
  [int]$Width = 720
)

$Body = [pscustomobject]@{
  paper_title = $PaperTitle
  abstract = $Abstract
  concept_name = $Concept
  key_claims = $Claims
  scene_goals = $Goals
  duration_sec = $Duration
  style = $Style
  fps = $Fps
  width = $Width
}

$Json = $Body | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/director/generate-from-paper" -Method Post -ContentType 'application/json' -Body $Json
