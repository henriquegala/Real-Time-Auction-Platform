// Configurações Globais
const USE_MOCK = true; // Altere para 'false' quando Henrique e Arthur entregarem as APIs
const API_BASE_URL = "http://localhost:8000";
const WS_BASE_URL = "ws://localhost:8000";

let token = localStorage.getItem("token") || null;
let currentUsername = localStorage.getItem("username") || null;
let activeWebSocket = null;
let currentAuctionId = null;
let mockInterval = null; // Para simular lances automáticos de outros usuários

// Banco de dados simulado (Armazenado na memória do navegador)
let mockAuctions = [
    {
        id: 1,
        title: "Relógio Vintage de Ouro 18K",
        description: "Raro relógio suíço da década de 1960 em perfeito estado de conservação.",
        current_price: 1500.00,
        end_time: new Date(Date.now() + 3600000 * 2).toISOString(), // Termina em 2 horas
        bids: [
            { username: "Carlos", amount: 1200.00, timestamp: new Date(Date.now() - 600000).toISOString() },
            { username: "Maria", amount: 1350.00, timestamp: new Date(Date.now() - 300000).toISOString() },
            { username: "Carlos", amount: 1500.00, timestamp: new Date(Date.now() - 50000).toISOString() }
        ]
    },
    {
        id: 2,
        title: "Quadro 'Sol de Outono' - Óleo sobre Tela",
        description: "Obra de arte original pintada à mão, datada de 1995. Assinada pelo artista.",
        current_price: 450.00,
        end_time: new Date(Date.now() + 3600000 * 5).toISOString(), // Termina em 5 horas
        bids: []
    }
];

// Inicialização da página
document.addEventListener("DOMContentLoaded", () => {
    if (token) {
        showDashboard();
    } else {
        showSection("login-section");
    }
});

function showSection(sectionId) {
    document.getElementById("login-section").classList.add("hidden");
    document.getElementById("dashboard-section").classList.add("hidden");
    document.getElementById("detail-section").classList.add("hidden");
    document.getElementById(sectionId).classList.remove("hidden");
}

// ---------------- AUTENTICAÇÃO (MOCK / REAL) ----------------

async function handleLogin(event) {
    event.preventDefault();
    const usernameInput = document.getElementById("username").value;
    const passwordInput = document.getElementById("password").value;

    if (USE_MOCK) {
        // Simulação instantânea de login bem-sucedido
        token = "mock-jwt-token-123456";
        currentUsername = usernameInput;
        localStorage.setItem("token", token);
        localStorage.setItem("username", currentUsername);
        showDashboard();
        return;
    }

    // Integração Real (Henrique)
    const formData = new URLSearchParams();
    formData.append("username", usernameInput);
    formData.append("password", passwordInput);

    try {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: formData
        });
        if (!response.ok) throw new Error("Usuário ou senha incorretos.");
        const data = await response.json();
        token = data.access_token;
        currentUsername = usernameInput;
        localStorage.setItem("token", token);
        localStorage.setItem("username", currentUsername);
        showDashboard();
    } catch (error) {
        alert("Erro no login: " + error.message);
    }
}

function showDashboard() {
    document.getElementById("username-display").innerText = `Olá, ${currentUsername}`;
    document.getElementById("user-info").classList.remove("hidden");
    showSection("dashboard-section");
    fetchAuctions();
}

function logout() {
    token = null;
    currentUsername = null;
    localStorage.clear();
    stopMockWebSocket();
    if (activeWebSocket) activeWebSocket.close();
    document.getElementById("user-info").classList.add("hidden");
    showSection("login-section");
}

// ---------------- LEILÕES (MOCK / REAL) ----------------

async function fetchAuctions() {
    if (USE_MOCK) {
        renderAuctions(mockAuctions);
        return;
    }

    // Integração Real (Henrique)
    try {
        const response = await fetch(`${API_BASE_URL}/auctions`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!response.ok) throw new Error("Erro ao carregar leilões.");
        const auctions = await response.json();
        renderAuctions(auctions);
    } catch (error) {
        console.error(error);
    }
}

function renderAuctions(auctions) {
    const listContainer = document.getElementById("auctions-list");
    listContainer.innerHTML = "";
    auctions.forEach(auction => {
        listContainer.innerHTML += `
            <div class="bg-white p-4 rounded-lg shadow hover:shadow-md transition border border-gray-200">
                <h3 class="text-lg font-bold text-gray-800">${auction.title}</h3>
                <p class="text-sm text-gray-600 mb-3">${auction.description}</p>
                <div class="flex justify-between items-center">
                    <div>
                        <span class="text-xs text-gray-400">Lance Atual</span>
                        <p class="text-lg font-bold text-green-600">R$ ${parseFloat(auction.current_price).toFixed(2)}</p>
                    </div>
                    <button onclick="enterAuction(${auction.id})" class="bg-blue-600 hover:bg-blue-700 text-white text-sm py-2 px-4 rounded transition">
                        Participar
                    </button>
                </div>
            </div>
        `;
    });
}

async function handleCreateAuction(event) {
    event.preventDefault();
    const title = document.getElementById("new-title").value;
    const description = document.getElementById("new-desc").value;
    const startPrice = parseFloat(document.getElementById("new-price").value);
    const endTime = document.getElementById("new-endtime").value;

    if (USE_MOCK) {
        const newAuction = {
            id: mockAuctions.length + 1,
            title,
            description,
            current_price: startPrice,
            end_time: new Date(endTime).toISOString(),
            bids: []
        };
        mockAuctions.push(newAuction);
        toggleModal(false);
        document.getElementById("create-auction-form").reset();
        fetchAuctions();
        return;
    }

    // Integração Real (Henrique)
    try {
        const response = await fetch(`${API_BASE_URL}/auctions`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ title, description, start_price: startPrice, end_time: endTime })
        });
        if (!response.ok) throw new Error("Erro ao criar leilão");
        toggleModal(false);
        document.getElementById("create-auction-form").reset();
        fetchAuctions();
    } catch (error) {
        alert(error.message);
    }
}

function toggleModal(show) {
    const modal = document.getElementById("create-modal");
    if (show) modal.classList.remove("hidden");
    else modal.classList.add("hidden");
}

// ---------------- TEMPO REAL / LANCES (MOCK / REAL) ----------------

async function enterAuction(auctionId) {
    currentAuctionId = auctionId;
    showSection("detail-section");

    if (USE_MOCK) {
        const auction = mockAuctions.find(a => a.id === auctionId);
        if (!auction) return;
        
        document.getElementById("auction-title").innerText = auction.title;
        document.getElementById("auction-desc").innerText = auction.description;
        document.getElementById("auction-current-price").innerText = `R$ ${auction.current_price.toFixed(2)}`;
        document.getElementById("auction-time").innerText = new Date(auction.end_time).toLocaleString();
        
        loadBidsHistory(auction.bids);
        startMockWebSocket(); // Inicia lances simulados de robôs
        return;
    }

    // Integração Real (Henrique & Arthur)
    try {
        const response = await fetch(`${API_BASE_URL}/auctions/${auctionId}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const auction = await response.json();
        
        document.getElementById("auction-title").innerText = auction.title;
        document.getElementById("auction-desc").innerText = auction.description;
        document.getElementById("auction-current-price").innerText = `R$ ${auction.current_price.toFixed(2)}`;
        document.getElementById("auction-time").innerText = new Date(auction.end_time).toLocaleString();
        
        loadBidsHistory(auction.bids || []);
        connectWebSocket(auctionId);
    } catch (error) {
        console.error(error);
    }
}

function connectWebSocket(auctionId) {
    if (activeWebSocket) activeWebSocket.close();
    activeWebSocket = new WebSocket(`${WS_BASE_URL}/ws/auction/${auctionId}?token=${token}`);

    activeWebSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "new_bid") {
            document.getElementById("auction-current-price").innerText = `R$ ${data.payload.amount.toFixed(2)}`;
            addBidToLog(data.payload.username, data.payload.amount, data.payload.timestamp);
        }
    };
}

// Enviar lance do próprio usuário
async function handlePlaceBid(event) {
    event.preventDefault();
    const amountInput = document.getElementById("bid-amount");
    const amount = parseFloat(amountInput.value);

    // Validação local rápida
    const currentPriceText = document.getElementById("auction-current-price").innerText;
    const currentPrice = parseFloat(currentPriceText.replace("R$", "").trim());

    if (amount <= currentPrice) {
        alert("O lance deve ser maior do que o preço atual.");
        return;
    }

    if (USE_MOCK) {
        const auction = mockAuctions.find(a => a.id === currentAuctionId);
        if (auction) {
            auction.current_price = amount;
            const newBid = { username: currentUsername, amount, timestamp: new Date().toISOString() };
            auction.bids.push(newBid);
            
            // Simula o recebimento do sinal que o websocket do Arthur enviaria
            document.getElementById("auction-current-price").innerText = `R$ ${amount.toFixed(2)}`;
            addBidToLog(newBid.username, newBid.amount, newBid.timestamp);
        }
        amountInput.value = "";
        return;
    }

    // Integração Real (Arthur/Henrique)
    try {
        const response = await fetch(`${API_BASE_URL}/auctions/${currentAuctionId}/bids`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ amount })
        });
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Falha ao enviar lance");
        }
        amountInput.value = "";
    } catch (error) {
        alert(error.message);
    }
}

// ---------------- SIMULADOR DE LANCES ALHEIOS (ROBÔS) ----------------

function startMockWebSocket() {
    stopMockWebSocket();
    const botNames = ["Lucas", "Camila", "Rodrigo", "Juliana", "Felipe"];

    // A cada 7 a 15 segundos, simula que outro usuário deu um lance
    const triggerMockBid = () => {
        const currentPriceText = document.getElementById("auction-current-price").innerText;
        const currentPrice = parseFloat(currentPriceText.replace("R$", "").trim());
        const increase = Math.floor(Math.random() * 50) + 10; // Aumento entre 10 e 60 reais
        const newAmount = currentPrice + increase;

        const randomBot = botNames[Math.floor(Math.random() * botNames.length)];
        const timestamp = new Date().toISOString();

        // Atualiza banco de dados mockado
        const auction = mockAuctions.find(a => a.id === currentAuctionId);
        if (auction) {
            auction.current_price = newAmount;
            auction.bids.push({ username: randomBot, amount: newAmount, timestamp });
        }

        // Atualiza a tela
        document.getElementById("auction-current-price").innerText = `R$ ${newAmount.toFixed(2)}`;
        addBidToLog(randomBot, newAmount, timestamp);

        // Agenda o próximo lance aleatoriamente
        const nextTime = Math.floor(Math.random() * 8000) + 7000;
        mockInterval = setTimeout(triggerMockBid, nextTime);
    };

    mockInterval = setTimeout(triggerMockBid, 5000); // Começa 5s após abrir a tela
}

function stopMockWebSocket() {
    if (mockInterval) {
        clearTimeout(mockInterval);
        mockInterval = null;
    }
}

// ---------------- HISTÓRICO E COMPONENTIZAÇÃO DE TELA ----------------

function loadBidsHistory(bids) {
    const log = document.getElementById("bids-log");
    log.innerHTML = "";
    // Copia e ordena os lances do mais recente para o mais antigo para a visualização
    const sortedBids = [...bids].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    sortedBids.forEach(bid => {
        addBidToLog(bid.username, bid.amount, bid.timestamp);
    });
}

function addBidToLog(username, amount, timestamp) {
    const log = document.getElementById("bids-log");
    const formattedTime = new Date(timestamp).toLocaleTimeString();
    
    const bidItem = document.createElement("div");
    bidItem.className = "bg-white p-2 rounded shadow-sm border-l-4 border-blue-500 flex justify-between";
    bidItem.innerHTML = `
        <span><strong>${username}</strong> deu lance de R$ ${amount.toFixed(2)}</span>
        <span class="text-gray-400 text-xs">${formattedTime}</span>
    `;
    
    log.prepend(bidItem);
}

function backToDashboard() {
    stopMockWebSocket();
    if (activeWebSocket) activeWebSocket.close();
    currentAuctionId = null;
    showDashboard();
}