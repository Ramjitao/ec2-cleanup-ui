document.getElementById("trigger-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const owner = document.getElementById("gh-owner").value.trim();
  const repo = document.getElementById("gh-repo").value.trim();
  const workflow = document.getElementById("gh-workflow").value.trim();
  const branch = document.getElementById("gh-branch").value.trim();
  const token = document.getElementById("pat-token").value.trim();

  const accessKey = document.getElementById("access-key").value.trim();
  const secretKey = document.getElementById("secret-key").value.trim();
  const sessionToken = document.getElementById("session-token").value.trim();
  const region = document.getElementById("region").value.trim();
  const autoConfirm = document.getElementById("auto-confirm").value;

  const resultDiv = document.getElementById("result");
  resultDiv.textContent = "⏳ Triggering...";

  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`;

  const payload = {
    ref: branch,
    inputs: {
      region,
      auto_confirm: autoConfirm,
      access_key_id: accessKey,
      secret_access_key: secretKey,
      session_token: sessionToken
    }
  };

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    if (response.status === 204) {
      resultDiv.textContent = "✅ Workflow triggered successfully.";
    } else {
      const err = await response.json();
      resultDiv.textContent = `❌ Failed to trigger: ${err.message}`;
      console.error(err);
    }
  } catch (error) {
    resultDiv.textContent = `❌ Network Error: ${error.message}`;
    console.error(error);
  }
});
