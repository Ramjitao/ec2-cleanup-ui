document.getElementById('trigger').addEventListener('click', async () => {
  const accessKeyId = document.getElementById('accessKeyId').value;
  const secretAccessKey = document.getElementById('secretAccessKey').value;
  const sessionToken = document.getElementById('sessionToken').value;
  const region = document.getElementById('region').value;
  const autoConfirm = document.getElementById('autoConfirm').value;
  const githubToken = document.getElementById('githubToken').value;

  const statusDiv = document.getElementById('status');
  statusDiv.innerHTML = "⏳ Triggering workflow...";

  if (!accessKeyId || !secretAccessKey || !githubToken) {
    statusDiv.innerHTML = "❌ Please provide required AWS and GitHub credentials.";
    return;
  }

  const repoOwner = "your-github-username"; // 🔁 Replace with your username
  const repoName = "your-repo-name";        // 🔁 Replace with your repo

  const apiUrl = `https://api.github.com/repos/${repoOwner}/${repoName}/actions/workflows/cleanup.yml/dispatches`;

  const payload = {
    ref: "main",
    inputs: {
      region,
      auto_confirm: autoConfirm,
      access_key_id: accessKeyId,
      secret_access_key: secretAccessKey,
      session_token: sessionToken
    }
  };

  try {
    const res = await fetch(apiUrl, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${githubToken}`,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    if (res.status === 204) {
      statusDiv.innerHTML = "✅ Workflow triggered successfully!";
    } else {
      const error = await res.json();
      statusDiv.innerHTML = `❌ Failed to trigger: ${error.message || 'Unknown error'}`;
    }
  } catch (err) {
    statusDiv.innerHTML = `❌ Error: ${err.message}`;
  }
});