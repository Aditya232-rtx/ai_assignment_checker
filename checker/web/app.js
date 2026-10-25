const $ = (id) => document.getElementById(id);
const form = $('run-form');
let latestReportPath = '';

const revealObserver = 'IntersectionObserver' in window
  ? new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 })
  : null;
document.querySelectorAll('.reveal').forEach((element) => {
  if (revealObserver) revealObserver.observe(element);
  else element.classList.add('is-visible');
});

const modeInput = $('no-grade');
const modeBadge = document.querySelector('.mode-badge');
modeInput.addEventListener('change', () => {
  modeBadge.textContent = modeInput.checked ? 'ON' : 'OFF';
});

function values() {
  return {
    folder: $('folder').value.trim(),
    attendance: $('attendance').value.trim(),
    rubric: $('rubric').value.trim(),
    assignments: Number($('assignments').value || 11),
    no_grade: $('no-grade').checked,
  };
}

function setNote(message, error = false) {
  const note = $('form-note');
  note.textContent = message;
  note.classList.toggle('error', error);
}

function renderInspect(data) {
  $('empty-state').hidden = true;
  $('stats').hidden = false;
  $('mapped').textContent = data.mapped_submissions;
  $('students').textContent = data.students;
  $('attendance-rows').textContent = data.attendance_rows;
  $('unmapped').textContent = data.unmapped_files;
  $('mapped-stat').textContent = data.mapped_submissions;
  $('students-stat').textContent = data.students;
  $('attendance-stat').textContent = data.attendance_rows;
  $('unmapped-stat').textContent = data.unmapped_files;
  const list = $('unmapped-list');
  list.innerHTML = data.unmapped?.length ? data.unmapped.map(item => `<div>${escapeHtml(item)}</div>`).join('') : '<div>No files were skipped.</div>';
  list.hidden = false;
}

function renderResults(data) {
  $('results').hidden = false;
  latestReportPath = data.report;
  $('marks-tab').click();
  $('results').classList.remove('result-enter');
  requestAnimationFrame(() => $('results').classList.add('result-enter'));
  $('result-students').textContent = data.students;
  $('result-total').textContent = Number(data.total_marks).toFixed(2);
  $('result-output').textContent = data.output;
  $('report-link').href = `/api/file?path=${encodeURIComponent(data.report)}`;
  const columns = data.rows.length ? Object.keys(data.rows[0]) : ['rollno', 'Total'];
  $('table-head').innerHTML = `<tr>${columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr>`;
  $('table-body').innerHTML = data.rows.map(row => `<tr>${columns.map(c => `<td>${escapeHtml(String(row[c] ?? ''))}</td>`).join('')}</tr>`).join('');
  $('results').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function openReportInDashboard() {
  if (!latestReportPath) return;
  const reportView = $('report-content');
  reportView.textContent = 'Loading reasoning report…';
  $('marks-view').hidden = true;
  $('report-view').hidden = false;
  $('marks-tab').classList.remove('active');
  $('marks-tab').setAttribute('aria-selected', 'false');
  $('report-tab').classList.add('active');
  $('report-tab').setAttribute('aria-selected', 'true');
  try {
    const response = await fetch(`/api/file?path=${encodeURIComponent(latestReportPath)}`);
    if (!response.ok) throw new Error('Could not load report');
    reportView.textContent = await response.text();
  } catch (error) {
    reportView.textContent = error.message;
  }
}

function openMarksInDashboard() {
  $('marks-view').hidden = false;
  $('report-view').hidden = true;
  $('marks-tab').classList.add('active');
  $('marks-tab').setAttribute('aria-selected', 'true');
  $('report-tab').classList.remove('active');
  $('report-tab').setAttribute('aria-selected', 'false');
}

function escapeHtml(value) {
  return value.replace(/[&<>'"]/g, (char) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[char]));
}

async function inspect() {
  setNote('Inspecting folder…');
  $('inspect-btn').disabled = true;
  $('inspect-btn').classList.add('is-loading');
  try {
    const query = new URLSearchParams(values()).toString();
    const response = await fetch(`/api/inspect?${query}`);
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Inspection failed');
    renderInspect(data);
    setNote(`${data.mapped_submissions} mapped files found.`);
  } catch (error) { setNote(error.message, true); }
  finally { $('inspect-btn').disabled = false; $('inspect-btn').classList.remove('is-loading'); }
}

$('inspect-btn').addEventListener('click', inspect);
$('marks-tab').addEventListener('click', openMarksInDashboard);
$('report-tab').addEventListener('click', openReportInDashboard);
$('report-link').addEventListener('click', (event) => {
  event.preventDefault();
  openReportInDashboard();
});
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = $('run-btn');
  button.disabled = true;
  button.classList.add('is-loading');
  button.querySelector('span:first-child').textContent = 'Running…';
  setNote('Scanning, grading, and writing the workbook…');
  try {
    const response = await fetch('/api/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values()) });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || 'Run failed');
    renderResults(data);
    setNote(`Finished. ${data.students} students written to the marksheet.`);
    await inspect();
  } catch (error) { setNote(error.message, true); }
  finally { button.disabled = false; button.classList.remove('is-loading'); button.querySelector('span:first-child').textContent = 'Run marking'; }
});

fetch('/api/defaults').then(response => response.json()).then(data => {
  $('folder').value = data.folder || '';
  $('attendance').value = data.attendance || '';
  $('rubric').value = data.rubric || '';
  $('assignments').value = data.assignments || 11;
}).catch(() => setNote('Could not load defaults. Enter the paths manually.', true));
