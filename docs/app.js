async function triggerWorkflow() {
  const awsAccessKeyId = document.getElementById('awsAccessKeyId').value;
  const awsSecretAccessKey = document.getElementById('awsSecretAccessKey').value;
  const awsSessionToken = document.getElementById('awsSessionToken').value;
  const region = document.getElementById('region').value;

  const githubToken = document.getElementById('githubToken').value;
  const owner = document.getElementById('repoOwner').value;
  const repo = document.getElementById('repoName').value;
  const workflowFileName = document.getElementById('workflowFileName').value;
  const action = document.getElementById('action').value;

  const statusBox = document.getElementById('statusBox');
  statusBox.textContent = "⏳ Triggering workflow...";

  const dispatchUrl = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflowFileName}/dispatches`;

  const payload = {
    ref: "main",  // Update if default branch is different
    inputs: {
      access_key_id: awsAccessKeyId,
      secret_access_key: awsSecretAccessKey,
      session_token: awsSessionToken || '',
      region: region || 'eu-west-1',
      action: action
    }
  };

  const triggerResponse = await fetch(dispatchUrl, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${githubToken}`,
      "Accept": "application/vnd.github+json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!triggerResponse.ok) {
    statusBox.textContent = `❌ Failed to trigger workflow: ${triggerResponse.statusText}`;
    return;
  }

  statusBox.textContent = "✅ Workflow triggered. Monitoring run...";

  // Poll for run status
  const runsUrl = `https://api.github.com/repos/${owner}/${repo}/actions/runs`;
  let runId = null;
  for (let i = 0; i < 20; i++) {
    const runsResponse = await fetch(runsUrl, {
      headers: { Authorization: `Bearer ${githubToken}` }
    });
    const data = await runsResponse.json();
    const latestRun = data.workflow_runs.find(r => r.name === "EC2 Cleanup" && r.head_branch === "main");

    if (latestRun) {
      runId = latestRun.id;
      if (latestRun.status === "completed") {
        statusBox.textContent = `✅ Run completed: ${latestRun.conclusion}`;
        const artifactsUrl = latestRun.artifacts_url;
        const artifactsResponse = await fetch(artifactsUrl, {
          headers: { Authorization: `Bearer ${githubToken}` }
        });
        const artifactsData = await artifactsResponse.json();
        if (artifactsData.artifacts.length > 0) {
          const downloadLink = artifactsData.artifacts[0].archive_download_url;
          statusBox.textContent += `\n📦 Artifact: ${downloadLink}`;
        } else {
          statusBox.textContent += "\n📭 No artifacts found.";
        }
        return;
      } else {
        statusBox.textContent = `⏳ Still running... (${latestRun.status})`;
      }
    }

    await new Promise(res => setTimeout(res, 10000)); // 10 sec wait
  }

  statusBox.textContent = "⚠️ Timed out waiting for run to complete.";
}
