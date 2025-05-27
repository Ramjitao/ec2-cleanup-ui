
document.getElementById("cleanupForm").addEventListener("submit", async function (e) {
  e.preventDefault();
  const accessKey = document.getElementById("accessKey").value;
  const secretKey = document.getElementById("secretKey").value;
  const sessionToken = document.getElementById("sessionToken").value;
  const region = document.getElementById("region").value;
  const ghToken = prompt("Enter your GitHub PAT (repo + workflow scope):");
  const confirmDelete = confirm("❓ Confirm deletion?");

  const body = {
    ref: "main",
    inputs: {
      access_key_id: accessKey,
      secret_access_key: secretKey,
      session_token: sessionToken,
      region,
      confirm_delete: confirmDelete.toString()
    }
  };

  const res = await fetch("https://api.github.com/repos/YOUR_USERNAME/ec2-volume-cleanup/actions/workflows/cleanup.yml/dispatches", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${ghToken}`,
      "Accept": "application/vnd.github.v3+json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });

  const resultDiv = document.getElementById("results");
  if (res.status === 204) {
    resultDiv.innerText = "✅ Workflow triggered. Monitor progress on GitHub Actions.";
  } else {
    const data = await res.json();
    resultDiv.innerText = `❌ Failed to trigger: ${data.message}`;
  }
});
