import argparse
import boto3
import html
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

def create_clients(region: str):
    ec2 = boto3.client('ec2', region_name=region)
    asg = boto3.client('autoscaling', region_name=region)
    return ec2, asg

def fetch_amis(ec2) -> List[Dict[str, Any]]:
    log.info("Fetching AMIs...")
    return ec2.describe_images(Owners=['self'])['Images']

def fetch_ec2_images_in_use(ec2) -> set:
    log.info("Fetching EC2 instance usage...")
    images_in_use = set()
    paginator = ec2.get_paginator('describe_instances')
    for page in paginator.paginate():
        for res in page['Reservations']:
            for inst in res['Instances']:
                images_in_use.add(inst['ImageId'])
    return images_in_use

def fetch_asg_images_in_use(asg, ec2) -> set:
    log.info("Fetching AutoScaling Group usage...")
    images_in_use = set()
    asgs = asg.describe_auto_scaling_groups()['AutoScalingGroups']
    for group in asgs:
        if 'LaunchTemplate' in group:
            lt_id = group['LaunchTemplate']['LaunchTemplateId']
            try:
                lt_versions = ec2.describe_launch_template_versions(LaunchTemplateId=lt_id)['LaunchTemplateVersions']
                for version in lt_versions:
                    image_id = version['LaunchTemplateData'].get('ImageId')
                    if image_id:
                        images_in_use.add(image_id)
            except Exception as e:
                log.warning(f"Error retrieving launch template {lt_id}: {e}")
        elif 'LaunchConfigurationName' in group:
            lc_name = group['LaunchConfigurationName']
            try:
                lcs = asg.describe_launch_configurations(LaunchConfigurationNames=[lc_name])['LaunchConfigurations']
                for lc in lcs:
                    if lc.get('ImageId'):
                        images_in_use.add(lc['ImageId'])
            except Exception as e:
                log.warning(f"Error retrieving launch configuration {lc_name}: {e}")
    return images_in_use

def fetch_volumes_by_snapshot(ec2) -> Dict[str, List[Dict[str, str]]]:
    log.info("Fetching EBS volumes...")
    volumes_by_snapshot = defaultdict(list)
    paginator = ec2.get_paginator('describe_volumes')
    for page in paginator.paginate():
        for volume in page['Volumes']:
            snapshot_id = volume.get('SnapshotId')
            if snapshot_id:
                volumes_by_snapshot[snapshot_id].append({
                    'VolumeId': volume['VolumeId'],
                    'State': volume['State']
                })
    return volumes_by_snapshot

def analyze_amis(
    amis: List[Dict[str, Any]],
    ec2_images_in_use: set,
    asg_images_in_use: set,
    volumes_by_snapshot: Dict[str, List[Dict[str, str]]]
) -> List[Dict[str, Any]]:
    log.info("Analyzing AMI dependencies...")
    results = []

    for ami in amis:
        ami_id = ami['ImageId']
        snapshot_details = []

        for mapping in ami.get('BlockDeviceMappings', []):
            ebs = mapping.get('Ebs')
            if ebs:
                snapshot_id = ebs.get('SnapshotId')
                if snapshot_id:
                    volumes = volumes_by_snapshot.get(snapshot_id, [])
                    snapshot_details.append({
                        'snapshot_id': snapshot_id,
                        'volumes': volumes
                    })

        used_by_ec2 = ami_id in ec2_images_in_use
        used_by_asg = ami_id in asg_images_in_use

        # ✅ New fix: check if any volume is in-use
        has_attached_volumes = any(
            v['State'] == 'in-use'
            for snap in snapshot_details
            for v in snap['volumes']
        )

        safe_to_delete = not used_by_ec2 and not used_by_asg and not has_attached_volumes

        results.append({
            'ami_id': ami_id,
            'name': ami.get('Name', ''),
            'creation_date': ami.get('CreationDate', ''),
            'snapshots': snapshot_details,
            'used_by_ec2': used_by_ec2,
            'used_by_asg': used_by_asg,
            'safe_to_delete': safe_to_delete,
            'has_attached_volumes': has_attached_volumes
        })

    results.sort(key=lambda x: x['creation_date'], reverse=True)
    return results


def generate_html(results: List[Dict[str, Any]], output_path: Path) -> None:
    log.info(f"Generating HTML report at {output_path} ...")
    rows = ""
    for r in results:
        snapshot_info = ""
        for snap in r['snapshots']:
            if snap['volumes']:
                vol_lines = "<ul class='volumes-list'>" + "".join(
                    f"<li>{html.escape(v['VolumeId'])} ({html.escape(v['State'])})</li>" for v in snap['volumes']
                ) + "</ul>"
            else:
                vol_lines = "Volumes: -"
            snapshot_info += f"<strong>{html.escape(snap['snapshot_id'])}</strong><br/>{vol_lines}<br/>"

        used_ec2 = "✅" if r['used_by_ec2'] else "❌"
        used_asg = "✅" if r['used_by_asg'] else "❌"
        safe_class = "yes" if r['safe_to_delete'] else "no"
        safe_label = "✔️ Yes" if r['safe_to_delete'] else "❌ No"
        vol_warn = "⚠️ Volumes attached" if r['has_attached_volumes'] else ""

        rows += f"""
        <tr>
            <td>{html.escape(r['ami_id'])}</td>
            <td>{html.escape(r['name'])}</td>
            <td>{html.escape(r['creation_date'])}</td>
            <td>{snapshot_info} {vol_warn}</td>
            <td>{used_ec2}</td>
            <td>{used_asg}</td>
            <td class="{safe_class}">{safe_label}</td>
        </tr>
        """

    total_amis = len(results)
    total_unused = sum(1 for r in results if r['safe_to_delete'])

    html_content = f"""
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
        .volumes-list {{ margin: 0; padding-left: 20px; list-style-type: disc; }}
        .actions {{ margin: 10px 0; }}
        input[type="text"] {{ width: 300px; padding: 6px; margin-right: 10px; }}
        @media (max-width: 800px) {{
            table, thead, tbody, th, td, tr {{ display: block; }}
            th {{ position: sticky; top: 0; background: #f2f2f2; }}
            tr {{ margin-bottom: 1em; }}
            td {{ border: none; position: relative; padding-left: 50%; }}
            td::before {{
                position: absolute;
                top: 10px;
                left: 10px;
                width: 45%;
                white-space: nowrap;
                font-weight: bold;
            }}
            td:nth-of-type(1)::before {{ content: "AMI ID"; }}
            td:nth-of-type(2)::before {{ content: "Name"; }}
            td:nth-of-type(3)::before {{ content: "Creation Date"; }}
            td:nth-of-type(4)::before {{ content: "Snapshots & Volumes"; }}
            td:nth-of-type(5)::before {{ content: "Used by EC2"; }}
            td:nth-of-type(6)::before {{ content: "Used by ASG"; }}
            td:nth-of-type(7)::before {{ content: "Safe to Delete"; }}
        }}
    </style>
    </head>
    <body>
    <h2>🌄 AMI Dependency Dashboard</h2>
    <p><strong>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</strong></p>
    <p>Total AMIs: <strong>{total_amis}</strong> | Safe to delete: <strong>{total_unused}</strong></p>

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
                <th onclick="sortTable(3)">Snapshots & Volumes</th>
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
                td => td.innerText.toUpperCase().includes(filter)
            ) ? "" : "none";
        }}
    }}

    function exportTableToCSV(filename) {{
        const rows = document.querySelectorAll("table tr");
        const csv = Array.from(rows).map(row => 
            Array.from(row.cells).map(c => '"' + c.innerText + '"').join(",")
        ).join("\\n");

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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding='utf-8')
    log.info(f"✅ Saved: {output_path}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AMI dependency dashboard")
    parser.add_argument("--region", default="eu-west-1", help="AWS region")
    parser.add_argument("--output", default="output/results.html", help="Output HTML file path")
    args = parser.parse_args()

    ec2, asg = create_clients(args.region)

    amis = fetch_amis(ec2)
    ec2_images_in_use = fetch_ec2_images_in_use(ec2)
    asg_images_in_use = fetch_asg_images_in_use(asg, ec2)
    volumes_by_snapshot = fetch_volumes_by_snapshot(ec2)

    results = analyze_amis(amis, ec2_images_in_use, asg_images_in_use, volumes_by_snapshot)
    generate_html(results, Path(args.output))

if __name__ == "__main__":
    main()
