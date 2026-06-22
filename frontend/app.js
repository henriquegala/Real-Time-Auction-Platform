// Detecta se está rodando local ou dentro do Docker
const isLocalFile = window.location.protocol === 'file:';

// Configurações Globais
const USE_MOCK = false; 
const API_BASE_URL = isLocalFile ? "http://localhost:8000" : `${window.location.origin}/api`;
const WS_BASE_URL = isLocalFile ? "ws://localhost:8000" : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;

let token = localStorage.getItem("token") || null;
let currentUsername = localStorage.getItem("username") || null;
let activeWebSocket = null;
let currentAuctionId = null;
let pingInterval = null;

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

// ---------------- AUTENTICAÇÃO (MÉTODO JSON CORRETO) ----------------

async function handleRegister(event) {
    event.preventDefault();
    const usernameInput = document.getElementById("reg-username").value;
    const passwordInput = document.getElementById("reg-password").value;

    try {
        // Envia JSON bruto para o backend (Alinhado com schemas.UserRegister do Henrique)
        const response = await fetch(`${API_BASE_URL}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                username: usernameInput, 
                password: passwordInput 
            })
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Erro no cadastro.");
        }

        alert("Conta criada com sucesso! Faça login na aba ao lado.");
        toggleAuthMode('login');
        document.getElementById("username").value = usernameInput;
    } catch (error) {
        alert("Erro no cadastro: " + error.message);
    }
}

async function handleLogin(event) {
    event.preventDefault();
    const usernameInput = document.getElementById("username").value;
    const passwordInput = document.getElementById("password").value;

    try {
        // Envia JSON bruto para o login (Alinhado com schemas.UserLogin do Henrique)
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                username: usernameInput, 
                password: passwordInput 
            })
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Nome de utilizador ou palavra-passe incorretos.");
        }

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
    cleanupConnection();
    document.getElementById("user-info").classList.add("hidden");
    showSection("login-section");
}

function toggleAuthMode(mode) {
    const loginForm = document.getElementById("login-form");
    const registerForm = document.getElementById("register-form");
    const tabLogin = document.getElementById("tab-login");
    const tabRegister = document.getElementById("tab-register");

    if (mode === 'login') {
        loginForm.classList.remove("hidden");
        registerForm.classList.add("hidden");
        tabLogin.className = "w-1/2 pb-2 text-center font-bold border-b-2 border-blue-600 text-blue-600";
        tabRegister.className = "w-1/2 pb-2 text-center font-bold border-b-2 border-transparent text-gray-500 hover:text-gray-700";
    } else {
        loginForm.classList.add("hidden");
        registerForm.classList.remove("hidden");
        tabLogin.className = "w-1/2 pb-2 text-center font-bold border-b-2 border-transparent text-gray-500 hover:text-gray-700";
        tabRegister.className = "w-1/2 pb-2 text-center font-bold border-b-2 border-green-600 text-green-600";
    }
}

// ---------------- LEILÕES (JSON CORRETO) ----------------

async function fetchAuctions() {
    try {
        const response = await fetch(`${API_BASE_URL}/auctions`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!response.ok) throw new Error("Erro ao buscar leilões ativos.");
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
        // Alinhado com Henrique: Usa starting_price e title
        const itemTitle = auction.title || "Item sem título";
        const currentPrice = parseFloat(auction.starting_price).toFixed(2);
        
        listContainer.innerHTML += `
            <div class="bg-white p-4 rounded-lg shadow hover:shadow-md transition border border-gray-200">
                <h3 class="text-lg font-bold text-gray-800">${itemTitle}</h3>
                <p class="text-sm text-gray-600 mb-3">${auction.description || 'Sem descrição.'}</p>
                <div class="flex justify-between items-center">
                    <div>
                        <span class="text-xs text-gray-400">Preço Atual</span>
                        <p class="text-lg font-bold text-green-600">R$ ${currentPrice}</p>
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
    const startingPrice = parseFloat(document.getElementById("new-price").value);
    const endTime = document.getElementById("new-endtime").value;

    try {
        // Envia campos compatíveis com schemas.AuctionCreate do Henrique
        const response = await fetch(`${API_BASE_URL}/auctions`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ 
                title: title, 
                description: description,
                starting_price: startingPrice, 
                end_time: new Date(endTime).toISOString() 
            })
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Não foi possível criar o leilão.");
        }

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

// ---------------- TEMPO REAL & WEBSOCKET (CONECTOR INTEGRADO) ----------------

async function enterAuction(auctionId) {
    currentAuctionId = auctionId;
    showSection("detail-section");

    document.getElementById("bid-amount").disabled = false;
    document.getElementById("bid-form").querySelector("button").disabled = false;
    document.getElementById("bids-log").innerHTML = "";

    try {
        // Carrega o estado atual via REST (Henrique)
        const response = await fetch(`${API_BASE_URL}/auctions/${auctionId}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const auction = await response.json();
        
        document.getElementById("auction-title").innerText = auction.title;
        document.getElementById("auction-desc").innerText = auction.description || "Sem descrição.";
        document.getElementById("auction-current-price").innerText = `R$ ${parseFloat(auction.starting_price).toFixed(2)}`;
        document.getElementById("auction-time").innerText = new Date(auction.end_time).toLocaleString();
        
        connectWebSocket(auctionId);
    } catch (error) {
        alert("Erro ao carregar detalhes do leilão.");
        backToDashboard();
    }
}

function connectWebSocket(auctionId) {
    cleanupConnection();

    // WebSocket em tempo real (rota da camada realtime do Arthur). O token JWT
    // é obrigatório e vai na query string — o servidor fecha com 4401 sem ele.
    const wsUrl = `${WS_BASE_URL}/ws/auctions/${auctionId}?token=${encodeURIComponent(token)}`;
    activeWebSocket = new WebSocket(wsUrl);

    activeWebSocket.onopen = () => {
        console.log("Conectado ao canal de tempo real do leilão.");
        // Envia ping preventivo a cada 30 segundos (timeout de inatividade = 60s)
        pingInterval = setInterval(() => {
            if (activeWebSocket.readyState === WebSocket.OPEN) {
                activeWebSocket.send(JSON.stringify({ type: "ping" }));
            }
        }, 30000);
    };

    activeWebSocket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        const eventType = msg.type;
        const priceEl = document.getElementById("auction-current-price");

        if (eventType === "auction_state") {
            // Primeiro frame: estado inicial do leilão.
            priceEl.innerText = `R$ ${parseFloat(msg.current_bid).toFixed(2)}`;
        } else if (eventType === "bid_accepted") {
            const acceptedAmount = parseFloat(msg.amount);
            priceEl.innerText = `R$ ${acceptedAmount.toFixed(2)}`;
            addBidToLog(msg.bidder_name || "Participante", acceptedAmount, msg.at || new Date().toISOString());
        } else if (eventType === "bid_rejected") {
            const reasons = {
                too_low: "O seu lance tem de ser superior ao valor atual.",
                auction_closed: "Este leilão já se encontra encerrado.",
                self_bid: "Não pode licitar no seu próprio leilão.",
                not_authenticated: "Sessão inválida. Faça login novamente."
            };
            alert(reasons[msg.reason] || "Lance rejeitado.");
        } else if (eventType === "auction_closed") {
            handleAuctionFinished(msg.winner_id, msg.winning_amount);
        }
        // "pong" é ignorado (apenas mantém a ligação viva).
    };

    activeWebSocket.onclose = (event) => {
        cleanupConnection();
        if (event.code === 4401) {
            alert("Sessão inválida ou expirada. Faça login novamente.");
            logout();
        } else if (event.code === 4404) {
            alert("Leilão não encontrado.");
            backToDashboard();
        } else if (event.code === 4408) {
            console.warn("Ligação encerrada por inatividade.");
        }
    };
}

function handlePlaceBid(event) {
    event.preventDefault();
    const amountInput = document.getElementById("bid-amount");
    const amount = parseFloat(amountInput.value);

    if (isNaN(amount) || amount <= 0) return;

    if (!activeWebSocket || activeWebSocket.readyState !== WebSocket.OPEN) {
        alert("Ligação em tempo real indisponível. Tente reentrar no leilão.");
        return;
    }

    // O lance é enviado pelo WebSocket. O servidor valida atomicamente (Lua),
    // persiste em SQL e difunde via Redis Pub/Sub. Enviamos como string para
    // evitar imprecisão de vírgula flutuante (ver NOTES_FOR_LORENZO.md).
    activeWebSocket.send(JSON.stringify({ type: "place_bid", amount: String(amount) }));
    amountInput.value = "";
}

function handleAuctionFinished(winnerId, winningAmount) {
    document.getElementById("bid-amount").disabled = true;
    document.getElementById("bid-form").querySelector("button").disabled = true;

    if (winnerId) {
        const finalValue = parseFloat(winningAmount).toFixed(2);
        alert(`O Leilão encerrou! Vencedor: Usuário #${winnerId} com lance de R$ ${finalValue}`);
        document.getElementById("auction-current-price").innerText = `Encerrado - Vencedor: #${winnerId} (R$ ${finalValue})`;
    } else {
        alert("O leilão terminou sem ofertas válidas.");
        document.getElementById("auction-current-price").innerText = "Encerrado - Sem Vencedor";
    }
}

function cleanupConnection() {
    if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
    }
}

function backToDashboard() {
    if (activeWebSocket) activeWebSocket.close();
    cleanupConnection();
    currentAuctionId = null;
    showDashboard();
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