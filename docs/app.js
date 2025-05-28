document.getElementById('trigger-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const pat = document.getElementById('pat').value;
  const owner = document.getElementById('owner').value;
  const repo = document.getElementById('repo').value;
  const region = document.getElementById('region').value;
  const awsKey = document.getElementById('awsKey').value;
  const awsSecret = document.getElementById('awsSecret').value;
  const awsToken = document.getElementById('awsToken').value;
  const action = document.getElementById('action').value;

  document.getElementById('status').innerText = '✅ Workflow triggered. Monitoring run...';

  const dispatchResp = await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/workflows/cleanup.yml/dispatches`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${pat}`,
      'Accept': 'application/vnd.github+json'
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
    document.getElementById('status').innerText = `❌ Failed to trigger workflow: ${await dispatchResp.text()}`;
    return;
  }

  // Poll for completion and show results
  let runId;
  while (true) {
    const runsResp = await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/runs`, {
      headers: { Authorization: `Bearer ${pat}` }
    });
    const { workflow_runs } = await runsResp.json();
    const run = workflow_runs.find(r => r.name === "EC2 Cleanup Operation");

    if (run && run.status === 'completed') {
      document.getElementById('status').innerText = `✅ Workflow completed: ${run.conclusion}`;
      document.getElementById('artifact-link').innerHTML = `<a href="results.html" target="_blank">📄 View Results</a>`;
      break;
    }

    await new Promise(res => setTimeout(res, 5000));
  }
});
