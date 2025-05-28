document.getElementById('trigger-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const pat = document.getElementById('pat').value.trim();
  const owner = document.getElementById('owner').value.trim();
  const repo = document.getElementById('repo').value.trim();
  const region = document.getElementById('region').value.trim();
  const awsKey = document.getElementById('awsKey').value.trim();
  const awsSecret = document.getElementById('awsSecret').value.trim();
  const awsToken = document.getElementById('awsToken').value.trim();
  const action = document.getElementById('action').value.trim();

  const statusEl = document.getElementById('status');
  const artifactLinkEl = document.getElementById('artifact-link');

  statusEl.innerText = '✅ Triggering workflow...';
  artifactLinkEl.innerHTML = '';

  try {
    // Trigger workflow_dispatch event
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
      const errorText = await dispatchResp.text();
      statusEl.innerText = `❌ Failed to trigger workflow: ${errorText}`;
      return;
    }

    statusEl.innerText = '✅ Workflow triggered. Waiting for the run to start...';

    // Poll every 5 seconds for workflow run status
    const workflowName = "EC2 Cleanup Operation";
    const maxWaitTimeMs = 10 * 60 * 1000; // 10 minutes
    const pollIntervalMs = 5000;
    const startTime = Date.now();

    let runId = null;

    while (true) {
      if (Date.now() - startTime > maxWaitTimeMs) {
        statusEl.innerText = '⏰ Timeout waiting for workflow to complete.';
        break;
      }

      // Get latest workflow runs
      const runsResp = await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/runs?per_page=10`, {
        headers: {
          'Authorization': `Bearer ${pat}`,
          'Accept': 'application/vnd.github+json'
        }
      });

      if (!runsResp.ok) {
        statusEl.innerText = '❌ Failed to fetch workflow runs.';
        break;
      }

      const { workflow_runs } = await runsResp.json();
      // Find the latest run with matching workflow name
      const run = workflow_runs.find(r => r.name === workflowName);

      if (!run) {
        statusEl.innerText = '⚠️ No workflow run found yet, retrying...';
        await delay(pollIntervalMs);
        continue;
      }

      runId = run.id;

      statusEl.innerText = `Status: ${run.status.toUpperCase()}${run.conclusion ? ' - ' + run.conclusion.toUpperCase() : ''}`;

      if (run.status === 'completed') {
        if (run.conclusion === 'success') {
          // Fetch artifacts and show them
          await showArtifacts(owner, repo, runId, pat);
        } else {
          statusEl.innerText += ' (Failed or cancelled)';
          artifactLinkEl.innerHTML = '';
        }
        break;
      }

      // Wait before next poll
      await delay(pollIntervalMs);
    }

  } catch (error) {
    statusEl.innerText = `❌ Error: ${error.message}`;
  }
});

// Utility delay function
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Fetch artifacts for a given run and show links in UI
async function showArtifacts(owner, repo, runId, pat) {
  const artifactLinkEl = document.getElementById('artifact-link');
  artifactLinkEl.innerHTML = 'Fetching artifacts...';

  const artifactsResp = await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/runs/${runId}/artifacts`, {
    headers: {
      'Authorization': `Bearer ${pat}`,
      'Accept': 'application/vnd.github+json'
    }
  });

  if (!artifactsResp.ok) {
    artifactLinkEl.innerHTML = '❌ Failed to fetch artifacts.';
    return;
  }

  const data = await artifactsResp.json();

  if (data.total_count === 0) {
    artifactLinkEl.innerHTML = 'No artifacts found.';
    return;
  }

  // Show all artifact download links
  const links = data.artifacts.map(artifact => {
    return `<li><a href="${artifact.archive_download_url}" target="_blank" rel="noopener noreferrer">${artifact.name}</a> (${formatBytes(artifact.size_in_bytes)})</li>`;
  }).join('');

  artifactLinkEl.innerHTML = `<ul>${links}</ul>`;
}

// Utility to format bytes nicely
function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
