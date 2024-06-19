async function fetchMessages() {
    const response = await fetch('/messages_from_MPESA');
    const results = await response.json();
    return results;
}

async function fetchCheckedMessages() {
    const response = await fetch('/checked_messages');
    const data = await response.json();
    displayTotalAmount(data.total_amount);
    return data.messages;
}

function displayTotalAmount(amount) {
    const resultsContainer = document.getElementById('results');
    const totalElement = document.createElement('div');
    totalElement.innerHTML = `<strong>Total Amount Checked: KSH ${amount.toFixed(2)}</strong>`;
    resultsContainer.appendChild(totalElement);
}

function displayMessage(sender, content, timestamp, id, checkedBy = null) {
    const resultsContainer = document.getElementById('results');
    const li = document.createElement('li');
    const words = content.split(' ').slice(0, 12).join(' ') + (content.split(' ').length > 12 ? '...' : '');

    li.innerHTML = `
        <strong>From:</strong> ${sender}<br>
        <span class="message-snippet">${words}</span>
        <br><strong>Timestamp:</strong> ${timestamp}
        ${checkedBy ? `<br><strong>Checked by:</strong> ${checkedBy} <br><button onclick="uncheckMessage(${id})">Uncheck</button>` : `<br><button onclick="checkMessage(${id})">Check</button>`}
    `;
    li.dataset.timestamp = timestamp;

    resultsContainer.appendChild(li);
}

async function loadMessages() {
    document.getElementById('results').innerHTML = '';
    const messages = await fetchMessages();
    messages.forEach(msg => displayMessage(msg[0], msg[1], msg[2], msg[3]));
}

async function loadCheckedMessages() {
    document.getElementById('results').innerHTML = '';
    const messages = await fetchCheckedMessages();
    messages.forEach(msg => displayMessage(msg[0], msg[1], msg[2], msg[4], msg[3]));
}

async function checkMessage(id) {
    const response = await fetch('/check_message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id }),
    });

    if (response.ok) {
        loadMessages();
        loadCheckedMessages();
    }
}

async function uncheckMessage(id) {
    const response = await fetch('/uncheck_message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id }),
    });

    if (response.ok) {
        loadMessages();
        loadCheckedMessages();
    }
}

function toggleView() {
    viewingChecked = !viewingChecked;
    const toggleViewBtn = document.getElementById('toggle-view-btn');
    const messageHeading = document.getElementById('message-heading');
    const searchBox = document.getElementById('search-box');
    const checkedSearchBox = document.getElementById('checked-search-box');

    if (viewingChecked) {
        toggleViewBtn.innerText = 'View Unchecked Messages';
        messageHeading.innerText = 'Checked Messages';
        searchBox.style.display = 'none';
        checkedSearchBox.style.display = 'flex';
        loadCheckedMessages();
    } else {
        toggleViewBtn.innerText = 'View Checked Messages';
        messageHeading.innerText = 'Messages from MPESA';
        searchBox.style.display = 'flex';
        checkedSearchBox.style.display = 'none';
        loadMessages();
    }
}

window.onload = () => {
    loadMessages();
    loadCheckedMessages();
};
