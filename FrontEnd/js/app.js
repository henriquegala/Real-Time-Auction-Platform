// js/app.js

// --- 1. VARIÁVEIS GLOBAIS ---
let leilaoAtivo = null; 
let saldoJogador = 2500; 
let indiceFantasmaSelecionado = null;
let intervaloTypewriter = null;

// --- 2. ELEMENTOS DO DOM ---
const displaySaldo = document.getElementById('saldo-jogador');
const ecraCemiterio = document.getElementById('ecra-cemiterio');
const ecraDialogo = document.getElementById('ecra-dialogo');
const ecraLeilao = document.getElementById('ecra-leilao');
const textoChat = document.getElementById('texto-fantasma-chat');

const btnIniciar = document.getElementById('btn-iniciar');
const btnLicitar = document.getElementById('btn-licitar');
const btnIrLeilao = document.getElementById('btn-ir-leilao');

// Elementos do Menu e Áudio (Que estavam em falta!)
const menuInicial = document.getElementById('menu-inicial');
const conteudoJogo = document.getElementById('conteudo-jogo');
const btnEntrar = document.getElementById('btn-entrar');
const musicaFundo = document.getElementById('musica-fundo');

// --- 3. LÓGICA DO MENU INICIAL E ÁUDIO ---
if (btnEntrar) {
    btnEntrar.addEventListener('click', () => {
        // Inicia a música
        if (musicaFundo) {
            musicaFundo.volume = 0.5;
            musicaFundo.play().catch(erro => console.log("Áudio bloqueado:", erro));
        }
        // Transita do Menu para o Jogo (Cemitério)
        if (menuInicial) menuInicial.style.display = 'none';
        if (conteudoJogo) conteudoJogo.style.display = 'block';
    });
}

// Efeito dramático de áudio quando o Bot licita
window.efeitoSustoBot = function() {
    if (musicaFundo) {
        musicaFundo.volume = 0.15; // Baixa o volume
        
        // Pisca o preço a vermelho
        const precoElement = document.getElementById('preco-atual');
        if (precoElement) precoElement.style.color = "#D32F2F";
        
        setTimeout(() => {
            if (precoElement) precoElement.style.color = "var(--ink-black)";
        }, 500);

        setTimeout(() => {
            musicaFundo.volume = 0.5; // Restaura o volume
        }, 2000);
    }
};

// --- 4. LÓGICA DA CARTEIRA E FIM DE LEILÃO ---
function atualizarCarteira() {
    if(displaySaldo) displaySaldo.innerText = `€${saldoJogador}`;
}

function processarFimDeLeilao(vencedor, valorFinal) {
    if (vencedor === "Jogador") {
        saldoJogador -= valorFinal;
        atualizarCarteira();
        alert(`O martelo bateu! Arremataste "${leilaoAtivo.fantasma.nome}" por €${valorFinal}.`);
    } else {
        alert(`Perdeste o lote. O bot "${vencedor}" levou a melhor por €${valorFinal}.`);
    }
    
    btnLicitar.disabled = true;

    // Devolve o jogador ao cemitério após 2 segundos
    setTimeout(() => {
        ecraLeilao.style.display = 'none';
        ecraCemiterio.style.display = 'block'; 
    }, 2000);
}

// --- 5. PREPARAÇÃO DO LEILÃO ---
function carregarLote(index) {
    if (leilaoAtivo) {
        leilaoAtivo.parar(); 
    }

    leilaoAtivo = new LeilaoGravebidders(bdFantasmas[index], processarFimDeLeilao);

    document.getElementById('nome-lote').innerText = leilaoAtivo.fantasma.nome;
    document.getElementById('preco-atual').innerText = `€${leilaoAtivo.fantasma.lanceInicial}`;
    document.getElementById('ultimo-licitante').innerText = "---";
    document.getElementById('tempo-restante').innerText = "30s";

    btnIniciar.style.display = 'inline-block';
    btnLicitar.disabled = true;
}

// --- 6. LÓGICA DO CEMITÉRIO E CHAT ---
const cova0 = document.getElementById('cova-0');
const cova1 = document.getElementById('cova-1');

if (cova0) cova0.addEventListener('click', () => invocarFantasma(0));
if (cova1) cova1.addEventListener('click', () => invocarFantasma(1));

function invocarFantasma(index) {
    indiceFantasmaSelecionado = index;
    const fantasma = bdFantasmas[index];

    ecraDialogo.style.display = 'block';
    document.getElementById('nome-fantasma-chat').innerText = fantasma.nome;
    
    textoChat.textContent = "";
    let i = 0;
    const mensagem = `"${fantasma.dialogo}"`;
    
    if (intervaloTypewriter) clearInterval(intervaloTypewriter);
    
    intervaloTypewriter = setInterval(() => {
        if (i < mensagem.length) {
            textoChat.textContent += mensagem.charAt(i);
            i++;
        } else {
            clearInterval(intervaloTypewriter);
        }
    }, 40); 
}

if (btnIrLeilao) {
    btnIrLeilao.addEventListener('click', () => {
        if (intervaloTypewriter) clearInterval(intervaloTypewriter); 
        
        ecraDialogo.style.display = 'none';
        ecraCemiterio.style.display = 'none'; 
        ecraLeilao.style.display = 'block'; 
        
        carregarLote(indiceFantasmaSelecionado); 
    });
}

// --- 7. LÓGICA DOS BOTÕES DO LEILÃO ---
if (btnIniciar) {
    btnIniciar.addEventListener('click', () => {
        btnIniciar.style.display = 'none'; 
        btnLicitar.disabled = false;
        leilaoAtivo.iniciar(); 
    });
}

if (btnLicitar) {
    btnLicitar.addEventListener('click', () => {
        const valorMinimo = leilaoAtivo.valorAtual + leilaoAtivo.fantasma.incremento;
        
        if (saldoJogador >= valorMinimo) {
            leilaoAtivo.processarLance(valorMinimo, "Jogador");
        } else {
            alert("Fundos insuficientes! Estás demasiado pobre para os negócios do além.");
        }
    });
}

// --- 8. ARRANQUE DO SISTEMA ---
atualizarCarteira();