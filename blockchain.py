from time import time
import json
import hashlib
from uuid import uuid4
from flask import Flask, jsonify, request
import requests
from urllib.parse import urlparse


class Blockchain:
    def __init__(self):
        self.nuove_transazioni = []
        self.catena = []
        self.nodi = set()

        # Creazione del primo blocco
        self.nuovo_blocco(hash_precedente='1', proof=100)

    def registrazione_nuovo_nodo(self, address):
        """
        aggiunge un nuovo nodo alla lista di nodi

        :param address: indirizzo del nodo, ad es. 'http://10.0.0.2:8000'
        """

        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodi.add(parsed_url.netloc)
        elif parsed_url.path:
            # per accettare url con schemi diversi da 'x.x.x.x:x'.
            self.nodi.add(parsed_url.path)
        else:
            raise ValueError('Invalid URL')

    def validazione_catena(self, blockchain_da_validare):
        """
        Determina se una blockchain è valida

        :param blockchain_da_validare: la blockchain da validare
        :return: True se valida, False altrimenti
        """

        ultimo_blocco = blockchain_da_validare[0]
        indice_corrente = 1

        while indice_corrente < len(blockchain_da_validare):
            blocco = blockchain_da_validare[indice_corrente]
            print(f'{ultimo_blocco}')
            print(f'{blocco}')
            print("\n-----------\n")
            # verifica correttezza hash del blocco
            hash_ultimo_blocco = self.hash(ultimo_blocco)
            if blocco['hash_precedente'] != hash_ultimo_blocco:
                return False

            # verifica correttezza della Proof of Work
            if not self.validazione_prova(ultimo_blocco['proof'], blocco['proof'], hash_ultimo_blocco):
                return False

            ultimo_blocco = blocco
            indice_corrente += 1

        return True

    def algoritmo_per_consenso(self):
        """
        Risoluzione conflitti tramite verifica tra catene diverse
        Viene sostituita la catena corrente con quella più lunga
        :return: True per blockchain sostituita, False se resta valida la blockchain attuale
        """

        vicini = self.nodi
        nuova_blockchain = None
        max_len = len(self.catena)

        # verifica le blockchain dei "vicini"
        for node in vicini:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                lunghezza = response.json()['lunghezza']
                catena = response.json()['catena']

                if lunghezza > max_len and self.validazione_catena(catena):
                    max_len = lunghezza
                    nuova_blockchain = catena

        if nuova_blockchain:
            self.catena = nuova_blockchain
            return True

        return False

    def nuovo_blocco(self, proof, hash_precedente):
        """
        Crea un nuovo blocco nella blockchain

        :param proof: la "prova" fornita dall'algoritmo Proof of Work
        :param hash_precedente
        :return: un nuovo blocco
        """

        block = {
            'index': len(self.catena) + 1,
            'timestamp': time(),
            'transazioni': self.nuove_transazioni,
            'proof': proof,
            'hash_precedente': hash_precedente or self.hash(self.catena[-1]),
        }

        # pulizia lista transazioni da memorizzare
        self.nuove_transazioni = []

        self.catena.append(block)
        return block

    def nuova_transazione(self, id, canale, dati, timestamp):
        """
        Crea una nuova transazione che sarà inserita nel prossimo blocco minato

        :param id: identificatore di chi ha generato il messaggio
        :param canale: bluetooth/zigbee/wifi/ethernet
        :param dati: messaggio
        :param timestamp: data e ora dell'operazione
        :return: indice del blocco che conterrà la transazione
        """
        self.nuove_transazioni.append({
            'id': id,
            'canale': canale,
            'dati': dati,
            'timestamp': timestamp
        })

        return self.ultimo_blocco['index'] + 1

    @property
    def ultimo_blocco(self):
        return self.catena[-1]

    @staticmethod
    def hash(blocco):
        """
        Crea un hash a 256bit di un blocco

        :param blocco: blocco da cui generare l'hash
        """

        # ordinamento del dizionario
        block_string = json.dumps(blocco, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, ultimo_blocco):
        """
        Trova un numero n tale che hash(p+n) finisca con 4 zeri
        dove n è la nuova prova e p la prova precedente

        :param ultimo_blocco: <dict> last Block
        :return: <int>
        """

        ultima_prova = ultimo_blocco['proof']
        ultimo_hash = self.hash(ultimo_blocco)

        prova = 0
        while self.validazione_prova(ultima_prova, prova, ultimo_hash) is False:
            prova += 1

        return prova

    @staticmethod
    def validazione_prova(ultima_prova, prova, ultimo_hash):
        """
        Valida la prova verificando che l'hash dell'ultima prova insieme a quello della
        prova attuale e dell'hash del blocco precedente termini con 4 zeri

        :param ultima_prova: <int>
        :param prova: <int> prova corrente
        :param ultimo_hash: <str> hash del blocco precedente
        :return: <bool> risultato della validazione

        """

        supposizione = f'{ultima_prova}{prova}{ultimo_hash}'.encode()
        hash_della_supposizione = hashlib.sha256(supposizione).hexdigest()
        return hash_della_supposizione[:4] == "0000"


# creazione server
app = Flask(__name__)

# genera un numero univoco per il nodo attuale
node_identifier = str(uuid4()).replace('-', '')

# istanziazione blockchain
blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
def mine():
    # recupero prossima "prova" tramite "Proof of Work"
    ultimo_blocco = blockchain.ultimo_blocco
    proof = blockchain.proof_of_work(ultimo_blocco)

    # creazione prima transazione (ha canale e dati nulli e identifica
    # il nodo creatore tramite il suo identificatore nella prima
    # transazione del blocco)
    blockchain.nuova_transazione(
        id=node_identifier,
        canale="",
        dati="",
        timestamp=time()
    )

    # aggiunge il nuovo blocco alla catena
    hash_precedente = blockchain.hash(ultimo_blocco)
    blocco = blockchain.nuovo_blocco(proof, hash_precedente)

    response = {
        'risposta': "Nuovo blocco creato",
        'index': blocco['index'],
        'transazioni': blocco['transazioni'],
        'proof': blocco['proof'],
        'hash_precedente': blocco['hash_precedente'],
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # verifica presenza parametri necessari
    required = ['id', 'canale', 'dati', 'timestamp']
    if not all(k in values for k in required):
        msg = 'Parametri mancanti: '
        missing = list(set(required) - set(values))
        for m in missing:
            msg += m
            if m != missing[-1]:
                msg += ', '
        return msg, 400

    # creazione di una nuova transazione
    index = blockchain.nuova_transazione(values['id'], values['canale'], values['dati'], values['timestamp'])

    response = {'risposta': f'La transazione sarà aggiunta al blocco {index}'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'catena': blockchain.catena,
        'lunghezza': len(blockchain.catena),
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodo = values.get('node')
    if nodo is None:
        return "(err) fornire un indirizzo di nodo valido", 400

    blockchain.registrazione_nuovo_nodo(nodo)

    nodi = list(blockchain.nodi)
    nodi_txt = ''
    for nodo in blockchain.nodi:
        nodi_txt += nodo
        if nodo != nodi[-1]:
            nodi_txt += ', '

    response = {
        'risposta': 'Nodo aggiunto',
        'nodi': nodi_txt
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.algoritmo_per_consenso()

    if replaced:
        response = {
            'risposta': 'Sostituita catena attuale con quella dei vicini',
            'nuova catena': blockchain.catena
        }
    else:
        response = {
            'risposta': 'Catena attuale valida',
            'chain': blockchain.catena
        }

    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=8000, type=int, help='porta in ascolto')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)
