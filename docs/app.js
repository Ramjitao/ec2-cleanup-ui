document.getElementById("triggerForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  clearUI();

  const pat = document.getElementById("pat").value.trim();
  const owner = document.getElementById("owner").value.trim();
  const repo = document.getElementById("repo").value.trim();
  const region = document.getElementById("region").value.trim() || "eu-west-1";
  const action = document.getElementById("action").value;
  const accessKeyId = document.getElementById("accessKeyId").value.trim();
  const secretAccessKey = document.getElementById("secretAccessKey").value.trim();
  const sessionToken = document.getElementById("sessionToken").value.trim();

  if (!pat || !owner || !repo || !accessKeyId || !secretAccessKey) {
    updateStatus("❌ Please fill all required fields.");
    return;
  }

  try {
    updateStatus("⏳ Triggering workflow...");

    // Trigger workflow_dispatch
    const dispatchResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/actions/workflows/cleanup.yml/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `token ${pat}`,
          Accept: "application/vnd.github+json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ref: "main", // Change if your default branch is different
          inputs: {
            region,
            action,
            access_key_id: accessKeyId,
            secret_access_key: secretAccessKey,
            session_token: sessionToken,
          },
        }),
      }
    );

    if (dispatchResponse.status !== 204) {
      const errorData = await dispatchResponse.json();
      throw new Error(`Failed to trigger workflow: ${JSON.stringify(errorData)}`);
    }

    updateStatus("✅ Workflow triggered. Fetching latest run...");

    // Get the latest run id for this workflow
    const runId = await waitForLatestRunId(owner, repo, pat, "cleanup.yml");

    if (!runId) {
      throw new Error("Could not find latest workflow run.");
    }

    updateStatus(`⏳ Monitoring workflow run ID: ${runId}`);

    // Poll the workflow run status
    await pollWorkflowRun(owner, repo, pat, runId);
  } catch (err) {
    updateStatus(`❌ Error: ${err.message}`);
  }
});

function updateStatus(message) {
  document.getElementById("status").textContent = message;
}

function clearUI() {
  updateStatus("");
  const artifactsDiv = document.getElementById("artifacts");
  artifactsDiv.innerHTML = "";
}

async function waitForLatestRunId(owner, repo, pat, workflowFileName) {
  // Poll the workflow runs API until we find the latest run that triggered after dispatch
  // Retry for up to ~30 seconds
  for (let i = 0; i < 6; i++) {
    const runsResponse = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflowFileName}/runs?per_page=5`,
      {
        headers: {
          Authorization: `token ${pat}`,
          Accept: "application/vnd.github+json",
        },
      }
    );
    const runsData = await runsResponse.json();

    if (runsData.workflow_runs && runsData.workflow_runs.length > 0) {
      // Assume latest run is first
      return runsData.workflow_runs[0].id;
    }
    // Wait before retrying
    await new Promise((res) => setTimeout(res, 5000));
  }
  return null;
}

async function pollWorkflowRun(owner, repo, pat, runId) {
  return new Promise((resolve) => {
    const interval = setInterval(async () => {
      const runResponse = await fetch(
        `https://api.github.com/repos/${owner}/${repo}/actions/runs/${runId}`,
        {
          headers: {
            Authorization: `token ${pat}`,
            Accept: "application/vnd.github+json",
          },
        }
      );
      const runData = await runResponse.json();

      if (runData.status === "completed") {
        clearInterval(interval);
        updateStatus(`✅ Workflow completed with conclusion: ${runData.conclusion}`);

        // Fetch and display artifacts
        await fetchArtifacts(owner, repo, pat, runId);
        resolve();
      } else {
        updateStatus(`⏳ Workflow status: ${runData.status} (${runData.conclusion || "N/A"})`);
      }
    }, 10000);
  });
}

async function fetchArtifacts(owner, repo, pat, runId) {
  const artifactsResponse = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/runs/${runId}/artifacts`,
    {
      headers: {
        Authorization: `token ${pat}`,
        Accept: "application/vnd.github+json",
      },
    }
  );

  const artifactsData = await artifactsResponse.json();
  const artifactsDiv = document.getElementById("artifacts");
  artifactsDiv.innerHTML = "";

  if (!artifactsData.artifacts || artifactsData.artifacts.length === 0) {
    artifactsDiv.textContent = "No artifacts found for this run.";
    return;
  }

  artifactsData.artifacts.forEach((artifact) => {
    const a = document.createElement("a");
    a.href = artifact.archive_download_url;
    a.textContent = `Download Artifact: ${artifact.name}`;
    a.target = "_blank";
    artifactsDiv.appendChild(a);
  });
}
