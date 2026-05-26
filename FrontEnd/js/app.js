// js/app.js

let leilaoAtivo = null; // Variável global que vai guardar a instância atual

// Selecionar os elementos do DOM
const selectLotes = document.getElementById('lista-lotes');
const btnIniciar = document.getElementById('btn-iniciar');
const btnLicitar = document.getElementById('btn-licitar');

// 1. Preencher o Dropdown automaticamente com os dados do dados.js
bdFantasmas.forEach((fantasma, index) => {
    const opcao = document.createElement('option');
    opcao.value = index;
    opcao.text = fantasma.nome;
    selectLotes.appendChild(opcao);
});

// 2. Função para instanciar um novo leilão
function carregarLote(index) {
    // Se já existe um leilão a decorrer, destrói os seus cronómetros primeiro
    if (leilaoAtivo) {
        leilaoAtivo.parar();
    }

    // Instanciar o novo lote escolhido
    leilaoAtivo = new LeilaoGravebidders(bdFantasmas[index]);

    // Fazer "Reset" à interface visual
    document.getElementById('nome-lote').innerText = leilaoAtivo.fantasma.nome;
    document.getElementById('preco-atual').innerText = `€${leilaoAtivo.fantasma.lanceInicial}`;
    document.getElementById('ultimo-licitante').innerText = "---";
    document.getElementById('tempo-restante').innerText = "30s";

    // Repor os botões ao estado original
    btnIniciar.style.display = 'inline-block';
    btnLicitar.disabled = true;
}

// 3. O que acontece quando o utilizador escolhe outro fantasma na lista?
selectLotes.addEventListener('change', (evento) => {
    const indiceEscolhido = evento.target.value;
    carregarLote(indiceEscolhido);
});

// 4. Ligar os botões do HTML à instância ativa
btnIniciar.addEventListener('click', () => {
    btnIniciar.style.display = 'none'; 
    btnLicitar.disabled = false;
    leilaoAtivo.iniciar();
});

btnLicitar.addEventListener('click', () => {
    const valorMinimo = leilaoAtivo.valorAtual + leilaoAtivo.fantasma.incremento;
    leilaoAtivo.processarLance(valorMinimo, "Jogador");
});

// 5. Arranque inicial da página (Carrega o primeiro lote da lista por defeito)
carregarLote(0);