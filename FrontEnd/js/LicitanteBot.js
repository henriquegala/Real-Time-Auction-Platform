// js/LicitanteBot.js
class LicitanteBot {
    constructor(nome) {
        this.nome = nome;
        this.timeoutId = null;
    }

    reagir(leilaoAtual) {
        // Se já estava a preparar um lance, cancela para recalcular
        if (this.timeoutId) clearTimeout(this.timeoutId);

        const fantasma = leilaoAtual.fantasma;
        const lanceAtual = leilaoAtual.valorAtual;

        // Verifica se o valor já ultrapassou o orçamento do bot
        if (lanceAtual >= fantasma.limiteMaximoBot) {
            console.log(`[Bot ${this.nome}] O valor está demasiado alto. Desisto.`);
            return;
        }

        // Rola os dados para ver se vai cobrir a aposta
        const deveLicitar = Math.random() < fantasma.agressividade;

        if (deveLicitar) {
            // Tempo de reação humano simulado: entre 1 e 3 segundos
            const tempoReacao = Math.floor(Math.random() * 2000) + 1000;
            
            this.timeoutId = setTimeout(() => {
                if (leilaoAtual.ativo) {
                    const novoLance = leilaoAtual.valorAtual + fantasma.incremento;
                    console.log(`[Bot ${this.nome}] cobriu a aposta com €${novoLance}!`);
                    
                    // NOVO: Dispara o efeito dramático de áudio
                    if (window.efeitoSustoBot) {
                        window.efeitoSustoBot();
                    }
                    
                    leilaoAtual.processarLance(novoLance, this.nome);
                }
            }, tempoReacao);
        }
    }
}