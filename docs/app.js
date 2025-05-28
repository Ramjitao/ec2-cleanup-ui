
document.getElementById("cleanupForm").addEventListener("submit", async function (e) {
  e.preventDefault();
  const pat = document.getElementById("pat").value.trim();
  const repo = document.getElementById("repo").value.trim();
  const region = document.getElementById("region").value.trim();
  const accessKeyId = document.getElementById("accessKeyId").value.trim();
  const secretAccessKey = document.getElementById("secretAccessKey").value.trim();
  const sessionToken = document.getElementById("sessionToken").value.trim();
  const action = document.querySelector("input[name='action']:checked").value;

  const inputs = {
    region,
    access_key_id: accessKeyId,
    secret_access_key: secretAccessKey,
    session_token: sessionToken,
    action
  };

  const res = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/cleanup.yml/dispatches`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${pat}`,
      "Accept": "application/vnd.github+json"
    },
    body: JSON.stringify({
      ref: "main",
      inputs: inputs
    })
  });

  const output = document.getElementById("output");
  if (res.ok) {
    output.textContent = "✅ Workflow triggered successfully.";
  } else {
    const data = await res.json();
    output.textContent = `❌ Failed to trigger: ${data.message}`;
  }
});
