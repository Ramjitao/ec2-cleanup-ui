async function triggerWorkflow() {
  const token = document.getElementById('pat').value;
  const owner = document.getElementById('owner').value;
  const repo = document.getElementById('repo').value;
  const workflowFileName = document.getElementById('workflow_file').value;
  const region = document.getElementById('region').value || 'eu-west-1';
  const action = document.querySelector('input[name="action"]:checked').value;
  const accessKey = document.getElementById('access_key').value;
  const secretKey = document.getElementById('secret_key').value;
  const sessionToken = document.getElementById('session_token').value;

  const inputs = {
    region,
    action,
    access_key_id: accessKey,
    secret_access_key: secretKey
  };

  if (sessionToken) {
    inputs.session_token = sessionToken;
  }

  try {
    const response = await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflowFileName}/dispatches`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github.v3+json'
      },
      body: JSON.stringify({
        ref: 'main',
        inputs
      })
    });

    if (response.ok) {
      alert("✅ Workflow triggered successfully.");
    } else {
      const error = await response.json();
      alert(`❌ Failed to trigger: ${error.message}`);
    }
  } catch (err) {
    console.error(err);
    alert("❌ Error triggering workflow. See console.");
  }
}
