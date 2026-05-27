// js/app.js

// --- LÓGICA DO MENU INICIAL E ÁUDIO ---
const menuInicial = document.getElementById('menu-inicial');
const conteudoJogo = document.getElementById('conteudo-jogo');
const btnEntrar = document.getElementById('btn-entrar');
const musicaFundo = document.getElementById('musica-fundo');

// NOVO: Função que cria o efeito dramático de áudio
window.efeitoSustoBot = function() {
    if (musicaFundo) {
        // Baixa o volume quase para o mínimo
        musicaFundo.volume = 0.15; 
        
        // Efeito visual brutalista: o preço fica vermelho sangue por meio segundo
        const precoElement = document.getElementById('preco-atual');
        if (precoElement) {
            precoElement.style.color = "#D32F2F";
            setTimeout(() => {
                precoElement.style.color = "var(--ink-black)"; // Volta ao preto
            }, 500);
        }

        // Espera 2 segundos e restaura o volume suavemente
        setTimeout(() => {
            musicaFundo.volume = 0.5; 
        }, 2000);
    }
};

btnEntrar.addEventListener('click', () => {
    // 1. Iniciar a música (o volume vai de 0.0 a 1.0)
    musicaFundo.volume = 0.5; 
    musicaFundo.play().catch(erro => {
        console.log("O navegador bloqueou o áudio:", erro);
    });

    // 2. Esconder o Menu Inicial
    menuInicial.style.display = 'none';

    // 3. Mostrar o Jogo Principal
    conteudoJogo.style.display = 'block';
});
// --------------------------------------

let leilaoAtivo = null; 
let saldoJogador = 2500; // Orçamento inicial para as compras assombradas

const selectLotes = document.getElementById('lista-lotes');
const btnIniciar = document.getElementById('btn-iniciar');
const btnLicitar = document.getElementById('btn-licitar');
const displaySaldo = document.getElementById('saldo-jogador');

// Atualiza o texto da carteira no HTML
function atualizarCarteira() {
    displaySaldo.innerText = `€${saldoJogador}`;
}

// O que acontece quando o cronómetro chega a zero
function processarFimDeLeilao(vencedor, valorFinal) {
    if (vencedor === "Jogador") {
        // Desconta o dinheiro
        saldoJogador -= valorFinal;
        atualizarCarteira();
        alert(`O martelo bateu! Arremataste "${leilaoAtivo.fantasma.nome}" por €${valorFinal}.`);
    } else {
        alert(`Perdeste o lote. O bot "${vencedor}" levou a melhor por €${valorFinal}.`);
    }
    
    // Desativa o botão de licitar até escolherem um novo fantasma
    btnLicitar.disabled = true;
}

bdFantasmas.forEach((fantasma, index) => {
    const opcao = document.createElement('option');
    opcao.value = index;
    opcao.text = fantasma.nome;
    selectLotes.appendChild(opcao);
});

function carregarLote(index) {
    if (leilaoAtivo) {
        leilaoAtivo.parar();
    }

    // Passamos a função processarFimDeLeilao como o tal "Callback"
    leilaoAtivo = new LeilaoGravebidders(bdFantasmas[index], processarFimDeLeilao);

    document.getElementById('nome-lote').innerText = leilaoAtivo.fantasma.nome;
    document.getElementById('preco-atual').innerText = `€${leilaoAtivo.fantasma.lanceInicial}`;
    document.getElementById('ultimo-licitante').innerText = "---";
    document.getElementById('tempo-restante').innerText = "30s";

    btnIniciar.style.display = 'inline-block';
    btnLicitar.disabled = true;
}

selectLotes.addEventListener('change', (evento) => {
    carregarLote(evento.target.value);
});

btnIniciar.addEventListener('click', () => {
    btnIniciar.style.display = 'none'; 
    btnLicitar.disabled = false;
    leilaoAtivo.iniciar();
});

btnLicitar.addEventListener('click', () => {
    const valorMinimo = leilaoAtivo.valorAtual + leilaoAtivo.fantasma.incremento;
    
    // A barreira de proteção: O jogador tem dinheiro suficiente?
    if (saldoJogador >= valorMinimo) {
        leilaoAtivo.processarLance(valorMinimo, "Jogador");
    } else {
        alert("Fundos insuficientes! Estás demasiado pobre para os negócios do além.");
    }
});

// Inicialização
atualizarCarteira();
carregarLote(0);