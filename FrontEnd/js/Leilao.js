// js/Leilao.js
class LeilaoGravebidders {
    constructor(dadosFantasma) {
        this.fantasma = dadosFantasma;
        this.valorAtual = dadosFantasma.lanceInicial;
        this.ultimoLicitante = "A Casa (Gravebidders)";
        this.tempoRestante = 30; // 30 segundos
        this.ativo = false;
        this.timer = null;
        this.botAdversario = new LicitanteBot("Sr. Sombra");
    }

    iniciar() {
        this.ativo = true;
        this.atualizarInterface();
        this.timer = setInterval(() => this.tickRelogio(), 1000);
        console.log(`Leilão Iniciado: ${this.fantasma.nome}`);
    }

    tickRelogio() {
        if (!this.ativo) return;
        
        this.tempoRestante--;
        this.atualizarInterface();
        
        if (this.tempoRestante <= 0) {
            this.encerrar();
        }
    }

    processarLance(valor, licitante) {
        if (!this.ativo) return;

        // Garante que o lance é válido (maior ou igual ao lance atual + incremento mínimo)
        if (valor >= this.valorAtual + this.fantasma.incremento) {
            this.valorAtual = valor;
            this.ultimoLicitante = licitante;
            
            // Regra do Martelo: se faltarem menos de 5 segundos, repõe para 10s
            if (this.tempoRestante < 5) {
                this.tempoRestante = 10; 
            }

            this.atualizarInterface();

            // Se foi o jogador real a licitar, diz ao bot para avaliar a situação
            if (licitante === "Jogador") {
                this.botAdversario.reagir(this);
            }
        }
    }

    encerrar() {
        this.ativo = false;
        clearInterval(this.timer);
        this.atualizarInterface(); // Atualiza o ecrã uma última vez
        alert(`FIM DO LEILÃO! Vendido a: ${this.ultimoLicitante} por €${this.valorAtual}`);
    }
    
    parar() {
        // Desativa a lógica
        this.ativo = false;
        
        // Limpa o cronómetro do leilão
        if (this.timer) clearInterval(this.timer);
        
        // Limpa qualquer decisão pendente do bot adversário
        if (this.botAdversario && this.botAdversario.timeoutId) {
            clearTimeout(this.botAdversario.timeoutId);
        }
    }

    // Método ponte entre a Lógica e o HTML
    atualizarInterface() {
        // Garantimos que estes IDs existem no HTML
        const elPreco = document.getElementById('preco-atual');
        const elTempo = document.getElementById('tempo-restante');
        const elLicitante = document.getElementById('ultimo-licitante');

        if (elPreco) elPreco.innerText = `€${this.valorAtual}`;
        if (elTempo) elTempo.innerText = this.tempoRestante > 0 ? `${this.tempoRestante}s` : "Encerrado";
        if (elLicitante) elLicitante.innerText = this.ultimoLicitante;
    }
}