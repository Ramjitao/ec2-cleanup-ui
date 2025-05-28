
async function fetchAndDisplayArtifact(url) {
  const tokenInput = document.getElementById('tokenInput');
  const resultsDiv = document.getElementById('results');
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${tokenInput.value}`
    }
  });

  const blob = await response.blob();
  const zip = await JSZip.loadAsync(blob);
  const file = zip.file("output.json");

  if (!file) {
    resultsDiv.innerHTML = "<p>❌ output.json not found in artifact.</p>";
    return;
  }

  const content = await file.async("string");
  const data = JSON.parse(content);

  resultsDiv.innerHTML = "";

  if (data.length === 0) {
    resultsDiv.innerHTML = "<p>✅ No unused AMIs or snapshots found.</p>";
    return;
  }

  data.forEach((entry, index) => {
    const div = document.createElement("div");
    div.style.marginBottom = "1.5em";
    div.style.border = "1px solid #ccc";
    div.style.padding = "1em";
    div.style.borderRadius = "5px";
    div.innerHTML = `
      <h4>🔍 AMI ${index + 1}</h4>
      <ul>
        <li><strong>AMI ID:</strong> ${entry.ami_id}</li>
        <li><strong>Created At:</strong> ${new Date(entry.created_at).toLocaleString()}</li>
        <li><strong>Snapshots:</strong> ${entry.snapshot_ids.join(', ')}</li>
        <li><strong>Volumes:</strong> ${entry.volumes.join(', ')}</li>
        <li><strong>Used by EC2:</strong> ${entry.in_use_by.ec2_instances.length > 0 ? entry.in_use_by.ec2_instances.join(', ') : '❌ No'}</li>
        <li><strong>Used by Auto Scaling Groups:</strong> ${entry.in_use_by.autoscaling_groups.length > 0 ? entry.in_use_by.autoscaling_groups.join(', ') : '❌ No'}</li>
      </ul>
    `;
    resultsDiv.appendChild(div);
  });
}
