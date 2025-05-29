import boto3
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def get_ami_dependencies(region='eu-west-1'):
    ec2 = boto3.client('ec2', region_name=region)
    asg = boto3.client('autoscaling', region_name=region)

    print("🔍 Fetching AMIs...")
    amis = ec2.describe_images(Owners=['self'])['Images']

    print("🔍 Fetching EC2 instance usage...")
    ec2_images_in_use = set()
    reservations = ec2.describe_instances()['Reservations']
    for res in reservations:
        for inst in res['Instances']:
            ec2_images_in_use.add(inst['ImageId'])

    print("🔍 Fetching ASG usage...")
    asg_images_in_use = set()
    asgs = asg.describe_auto_scaling_groups()['AutoScalingGroups']
    for group in asgs:
        if 'LaunchTemplate' in group:
            lt_id = group['LaunchTemplate']['LaunchTemplateId']
            try:
                lt_versions = ec2.describe_launch_template_versions(
                    LaunchTemplateId=lt_id
                )['LaunchTemplateVersions']
                for version in lt_versions:
                    image_id = version['LaunchTemplateData'].get('ImageId')
                    if image_id:
                        asg_images_in_use.add(image_id)
            except Exception:
                continue
        elif 'LaunchConfigurationName' in group:
            lc_name = group['LaunchConfigurationName']
            try:
                lcs = asg.describe_launch_configurations(
                    LaunchConfigurationNames=[lc_name]
                )['LaunchConfigurations']
                for lc in lcs:
                    asg_images_in_use.add(lc.get('ImageId'))
            except Exception:
                continue

    print("🔍 Fetching EBS volumes...")
    volumes_by_snapshot = defaultdict(list)
    paginator = ec2.get_paginator('describe_volumes')
    for page in paginator.paginate():
        for volume in page['Volumes']:
            if volume['State'] == 'available' and 'SnapshotId' in volume:
                volumes_by_snapshot[volume['SnapshotId']].append(volume)

    print("✅ Analysis complete.")
    results = []

    for ami in amis:
        ami_id = ami['ImageId']
        snapshot_ids = []
        volume_count = 0

        for mapping in ami.get('BlockDeviceMappings', []):
            ebs = mapping.get('Ebs')
            if ebs and ebs.get('SnapshotId'):
                snapshot_id = ebs['SnapshotId']
                snapshot_ids.append(snapshot_id)
                volume_count += len(volumes_by_snapshot.get(snapshot_id, []))

        used_by_ec2 = ami_id in ec2_images_in_use
        used_by_asg = ami_id in asg_images_in_use
        safe_to_delete = not used_by_ec2 and not used_by_asg

        results.append({
            'ami_id': ami_id,
            'name': ami.get('Name', ''),
            'creation_date': ami.get('CreationDate', ''),
            'snapshots': snapshot_ids,
            'volume_count': volume_count,
            'used_by_ec2': used_by_ec2,
            'used_by_asg': used_by_asg,
            'safe_to_delete': safe_to_delete
        })

    return results

def generate_html(results):
    rows = ""
    for r in results:
        snapshot_ids = ", ".join(r['snapshots']) if r['snapshots'] else "-"
        used_ec2 = "✅" if r['used_by_ec2'] else "❌"
        used_asg = "✅" if r['used_by_asg'] else "❌"
        safe_class = "yes" if r['safe_to_delete'] else "no"
        safe_label = "✔️ Yes" if r['safe_to_delete'] else "❌ No"

        rows += f"""
        <tr>
            <td>{r['ami_id']}</td>
            <td>{r['name']}</td>
            <td>{r['creation_date']}</td>
            <td>{snapshot_ids}</td>
            <td>{used_ec2}</td>
            <td>{used_asg}</td>
            <td class="{safe_class}">{safe_label}</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>🌄 AMI Dependency Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; color: #333; }}
            table {{ border-collapse: collapse; width: 100%; background-color: #fff; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            th, td {{ border: 1px solid #ccc; padding: 10px; text-align: left; vertical-align: top; }}
            th {{ background-color: #f2f2f2; cursor: pointer; }}
            tr:hover {{ background-color: #f5f5f5; }}
            .yes {{ color: green; font-weight: bold; }}
            .no {{ color: red; font-weight: bold; }}
            .warn {{ color: orange; font-weight: bold; }}
            .center {{ text-align: center; }}
            .actions {{ margin: 10px 0; }}
            input[type="text"] {{ width: 300px; padding: 6px; margin-right: 10px; }}
        </style>
    </head>
    <body>
        <h2>🌄 AMI Dependency Dashboard</h2>
        <p><strong>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</strong></p>

        <div class="actions">
            <input type="text" id="searchInput" placeholder="🔎 Filter AMIs..." onkeyup="filterTable()" />
            <button onclick="exportTableToCSV('ami_dependencies.csv')">📥 Export CSV</button>
        </div>

        <table id="amiTable" data-sort-dir="asc">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">AMI ID</th>
                    <th onclick="sortTable(1)">Name</th>
                    <th onclick="sortTable(2)">Creation Date</th>
                    <th onclick="sortTable(3)">Snapshot IDs</th>
                    <th onclick="sortTable(4)">Used by EC2</th>
                    <th onclick="sortTable(5)">Used by ASG</th>
                    <th onclick="sortTable(6)">Safe to Delete</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>

        <script>
        function sortTable(n) {{
            var table = document.getElementById("amiTable");
            var rows = Array.from(table.rows).slice(1);
            var asc = table.getAttribute("data-sort-dir") !== "asc";
            rows.sort((a, b) => {{
                let x = a.cells[n].innerText;
                let y = b.cells[n].innerText;
                return asc ? x.localeCompare(y, undefined, {{numeric: true}}) : y.localeCompare(x, undefined, {{numeric: true}});
            }});
            rows.forEach(row => table.appendChild(row));
            table.setAttribute("data-sort-dir", asc ? "asc" : "desc");
        }}

        function filterTable() {{
            const filter = document.getElementById("searchInput").value.toUpperCase();
            const rows = document.getElementById("amiTable").rows;
            for (let i = 1; i < rows.length; i++) {{
                rows[i].style.display = Array.from(rows[i].cells).some(
                    function(td) {{ return td.innerText.toUpperCase().includes(filter); }}
                ) ? "" : "none";
            }}
        }}

        function exportTableToCSV(filename) {{
            const rows = document.querySelectorAll("table tr");
            const csv = Array.from(rows).map(function(row) {{
                return Array.from(row.cells).map(function(c) {{
                    return '"' + c.innerText + '"';
                }}).join(",");
            }}).join("\\n");

            const blob = new Blob([csv], {{ type: "text/csv" }});
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            a.click();
        }}
        </script>
    </body>
    </html>
    """

    Path("output").mkdir(parents=True, exist_ok=True)
    Path("output/results.html").write_text(html)
    print("✅ Saved: output/results.html")


# --------- MAIN ------------------
if __name__ == "__main__":
    region = 'eu-west-1'
    results = get_ami_dependencies(region)
    generate_html(results)
