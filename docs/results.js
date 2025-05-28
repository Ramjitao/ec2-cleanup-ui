fetch('output/results.txt')
  .then(res => res.text())
  .then(text => {
    const tbody = document.querySelector('#results-table tbody');
    text.split('\n').forEach(line => {
      if (line.trim()) {
        const row = line.split('|').map(cell => `<td>${cell.trim()}</td>`).join('');
        tbody.innerHTML += `<tr>${row}</tr>`;
      }
    });
  });
