document.getElementById('trigger-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const pat = document.getElementById('pat').value.trim();
  const owner = document.getElementById('owner').value.trim();
  const repo = document.getElementById('repo').value.trim();
  const region = document.getElementById('region').value.trim();
  const awsKey = document.getElementById('awsKey').value.trim();
  const awsSecret = document.getElementById('awsSecret').value.trim();
  const awsToken = document.getElementById('awsToken').value.trim();
  const action = document.getElementById('action').value;

  const statusEl = document.getElementById('status');
  const artifactLinkEl = document.getElementById('artifact-link');

  statusEl.innerText = '🚀 Triggering workflow...';
  artifactLinkEl.innerHTML = '';

  // Trigger the workflow dispatch
  const dispatchResp = await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/workflows/cleanup.yml/dispatches`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${pat}`,
      'Accept': 'application/vnd.github+json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      ref: 'main',
      inputs: {
        region,
        access_key_id: awsKey,
        secret_access_key: awsSecret,
        session_token: awsToken,
        action
      }
    })
  });

  if (!dispatchResp.ok) {
    statusEl.innerText = `❌ Failed to trigger workflow: ${await dispatchResp.text()}`;
    return;
  }

  statusEl.innerText = '⏳ Workflow triggered, waiting for run to appear...';

  // Poll to find the latest run triggered by this dispatch
  let runId = null;
  let runUrl = null;

  for (let i = 0; i < 20; i++) { // up to ~100 seconds wait for the run to appear
    await new Promise(res => setTimeout(res, 5000));

    const runsResp = await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/runs?branch=main&event=workflow_dispatch`, {
      headers: { Authorization: `Bearer ${pat}` }
    });

    if (!runsResp.ok) {
      statusEl.innerText = `❌ Failed to fetch workflow runs: ${await runsResp.text()}`;
      return;
    }

    const runsData = await runsResp.json();
    // Sort runs by creation date descending, find the most recent run triggered by dispatch
    const sortedRuns = runsData.workflow_runs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    if (sortedRuns.length > 0) {
      runId = sortedRuns[0].id;
      runUrl = sortedRuns[0].html_url;
      break;
    }
  }

  if (!runId) {
    statusEl.innerText = '❌ Could not find the workflow run triggered.';
    return;
  }

  // Now poll the exact run status
  statusEl.innerText = `⏳ Workflow run started: #${runId}. Monitoring status...`;

  while (true) {
    await new Promise(res => setTimeout(res, 5000));

    const runResp = await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/runs/${runId}`, {
      headers: { Authorization: `Bearer ${pat}` }
    });

    if (!runResp.ok) {
      statusEl.innerText = `❌ Failed to fetch run status: ${await runResp.text()}`;
      break;
    }

    const runData = await runResp.json();
    const { status, conclusion } = runData;

    statusEl.innerText = `Workflow run status: ${status}` + (status === 'completed' ? `, conclusion: ${conclusion}` : '');

    if (status === 'completed') {
      // Show artifact or results link if you have a known URL or page
      artifactLinkEl.innerHTML = `<a href="${runUrl}" target="_blank">📄 View Workflow Run on GitHub</a>`;
      break;
    }
  }
});
