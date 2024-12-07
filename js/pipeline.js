const form = document.getElementById('projectForm');
const tableBody = document.getElementById('projectTableBody');
let projects = JSON.parse(localStorage.getItem('projects')) || [];

function renderTable() {
    tableBody.innerHTML = '';
    projects.forEach((project, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${project.name}</td>
            <td>${project.description}</td>
            <td>${project.client}</td>
            <td>${project.amount}</td>
            <td>${project.probability}</td>
            <td>${project.startDate}</td>
            <td>${project.endDate}</td>
            <td>${project.status}</td>
            <td>${project.manager}</td>
            <td><span class="delete-btn" data-index="${index}">Διαγραφή</span></td>
        `;
        tableBody.appendChild(row);
    });
}

form.addEventListener('submit', (e) => {
    e.preventDefault();
    const name = document.getElementById('projectName').value;
    const description = document.getElementById('projectDescription').value;
    const client = document.getElementById('projectClient').value;
    const amount = document.getElementById('projectAmount').value;
    const probability = document.getElementById('projectProbability').value;
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    const status = document.getElementById('status').value;
    const manager = document.getElementById('projectManager').value;

    projects.push({ name, description, client, amount, probability, startDate, endDate, status, manager });
    localStorage.setItem('projects', JSON.stringify(projects));
    renderTable();
    form.reset();
});

tableBody.addEventListener('click', (e) => {
    if (e.target.classList.contains('delete-btn')) {
        const index = e.target.getAttribute('data-index');
        projects.splice(index, 1);
        localStorage.setItem('projects', JSON.stringify(projects));
        renderTable();
    }
});

renderTable();
